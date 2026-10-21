"""Isolated-database resolution and the safety guard for destructive evaluation runs.

Why this exists
---------------
The research runners in ``evaluation/experiments/`` write to the database the
*application* uses (``settings.database_url``) and several of them delete rows
before they start.  ``run_phase3d_upload_integration.py`` even issued an
unscoped ``DELETE FROM document_chunks``.  Pointed at the application database
that is a destructive operation against live user data, and it was previously
one missing argument away.

This module makes the evaluation target **explicit and provably different** from
the application's:

    resolve target      --database-url, else DOCUMIND_INTEGRATION_DATABASE_URL,
                        else the application DSN (the behaviour that existed
                        before, so nothing changes silently)
        |
    refuse unverifiable URLs
                        an unsupported scheme, a libpq connection-override
                        parameter, a malformed port, or a missing host or
                        database name cannot be shown to name a database
        |
    prove it different  the database NAME must differ from the application's
                        (case-insensitively).  Hostnames are never used to prove
                        separation: two different hostnames, or "localhost" and
                        "127.0.0.1", cannot be shown to name different servers
                        without DNS or a connection, and this guard makes neither
        |
    name the operation  a clear, credential-free error when it is not

The guard runs *before* the first connection, so a rejected run touches neither
database.

Relationship to ``tests/fixtures/integration_db.py``
---------------------------------------------------
The test layer already has an equivalent guard for the destructive integration
validation.  Its rules are narrower than this module's and must be brought into
step separately: it still compares ``(host, port, database)`` textually, so it
does not yet refuse the host-alias cases this module now refuses.

It is a mirror rather than an import because the dependency direction is
one-way: ``evaluation/`` never imports from ``tests/`` (see
``evaluation/README.md`` and ``AGENTS.md`` — production and research code never
import test code).

Deliberately **not** implemented here
-------------------------------------
This module does not create, migrate, verify or drop a database.  A runner that
needs an isolated database must be given one that already exists and is
migrated (the sanctioned workflow is the integration fixture / the operator's
own provisioning); the guard's job is only to refuse an unsafe target.  That
keeps the safety-critical surface small and keeps destructive DDL out of the
research runners entirely.

Known limitation
----------------
A target with a *different* database name on the application's own server is
accepted.  That is correct for a separate database, but it relies on the
application URL naming the database it really uses.  Postgres does not give one
database two names, so no string can make two different names refer to the
same database.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

#: ``evaluation/isolation.py`` -> ``evaluation`` -> ``backend``.
BACKEND_DIR = Path(__file__).resolve().parents[1]

#: The file the application itself loads its configuration from.
ENV_FILE = BACKEND_DIR / ".env"

#: Environment variable naming the database an evaluation run may use.  The
#: suffix is deliberately the same one ``tests/fixtures/integration_db.py``
#: honours, so one exported variable points every isolated runner at the same
#: place.
EVALUATION_DATABASE_URL_ENV = "DOCUMIND_INTEGRATION_DATABASE_URL"

#: Query parameters that make libpq (and therefore its drivers) connect somewhere
#: other than the URL's own host, port or database.  A URL that sets one has no
#: identity the URL itself can establish, so it is refused outright.
CONNECTION_OVERRIDE_PARAMS = frozenset({"host", "hostaddr", "port", "dbname", "service"})

Identity = tuple[str, int | None, str]


class UnsafeEvaluationTarget(RuntimeError):
    """An evaluation run was asked to target a database it must not touch.

    Raised for both unsafe outcomes: the target *is* (or cannot be shown to differ
    from) the application database, or the target's or the application's identity
    could not be established at all — in which case the guard fails closed rather
    than assuming it is safe.
    """


# ---------------------------------------------------------------------------
# Resolving the two databases
# ---------------------------------------------------------------------------


def _read_env_file_value(name: str, env_file: Path) -> str | None:
    """Read one ``KEY=VALUE`` from an env file.  Comments and blanks ignored."""
    if not env_file.is_file():
        return None
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value or None
    return None


def application_database_url(*, env_file: Path | None = None) -> str:
    """The DSN the application itself uses.

    ``backend/.env`` wins over the ambient environment, matching
    ``tests/fixtures/e2e_config.py`` so "the application database" means one
    thing across the repository.  Reading the file the application actually
    loads is what makes this immune to a runner that sets ``DATABASE_URL`` in
    ``os.environ`` for its own child processes.
    """
    value = _read_env_file_value("DATABASE_URL", ENV_FILE if env_file is None else env_file)

    if value:
        return value

    # No env file (or no DATABASE_URL in it): fall back to the same resolver the
    # application uses, including its built-in default.
    from config import get_settings

    return get_settings().database_url


def database_identity(dsn: str) -> Identity:
    """``(host, port, database)`` — the part of a DSN that names a database.

    The credentials are never part of the identity, so it is safe to log and to
    record in a manifest.  The host is reported as written (lower-cased by the
    URL parser); it is descriptive only and is not used to decide separation.

    A malformed URL (for example a non-numeric port) raises
    :class:`UnsafeEvaluationTarget` with a fixed message that does not echo the
    URL, so no credential can reach an error message through here.
    """
    try:
        parts = urlsplit(dsn)
        port = parts.port
    except ValueError:
        raise UnsafeEvaluationTarget(
            "malformed database URL: the port is not a valid number. Refusing to continue."
        ) from None
    return (parts.hostname or "", port, unquote(parts.path or "").lstrip("/"))


def describe_identity(identity: Identity) -> str:
    """``host:port/database`` (port omitted when it is the DSN's default)."""
    host, port, database = identity
    return f"{host}:{port}/{database}" if port else f"{host}/{database}"


def display_dsn(dsn: str) -> str:
    """A credential-free rendering of ``dsn``: scheme, host, port, database.

    The user name and password are dropped entirely, so this is safe to print
    and to put in an error message or a report.
    """
    try:
        parts = urlsplit(dsn)
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "<malformed database URL>"
    return f"{parts.scheme}://{parts.hostname or ''}{port}/{unquote(parts.path or '').lstrip('/')}"


def evaluation_database_url(
    *,
    override: str | None = None,
    application_url: str | None = None,
) -> str:
    """The database an evaluation run targets — explicit, never invented.

    Precedence:

    1. ``override`` (the runner's ``--database-url``);
    2. ``DOCUMIND_INTEGRATION_DATABASE_URL``;
    3. the application DSN — the pre-existing behaviour, preserved so that no
       run is silently redirected to a different database than it asked for.
       The guard, not this function, is what then refuses an unsafe target.

    An override that is set but empty raises rather than falling back: falling
    back would be exactly the silent redirect this module exists to prevent.
    """
    explicit = override if override is not None else os.environ.get(EVALUATION_DATABASE_URL_ENV)

    if explicit is not None:
        stripped = explicit.strip()
        if not stripped:
            raise UnsafeEvaluationTarget(
                f"the evaluation database URL is set but empty "
                f"(source: {'--database-url' if override is not None else EVALUATION_DATABASE_URL_ENV}). "
                "Refusing to fall back to the application database; either unset it "
                "or point it at an isolated database."
            )
        return stripped

    return application_url if application_url is not None else application_database_url()


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


def _refuse_unverifiable_url(dsn: str, *, role: str, operation: str) -> None:
    """Refuse a URL whose connection cannot be tied to the database it names.

    Checked for both the target and the application.  Messages name the scheme
    and the parameter *keys* only, never a value, so no credential is echoed.
    """
    parts = urlsplit(dsn)
    scheme = parts.scheme.lower()
    if not scheme.startswith("postgresql"):
        raise UnsafeEvaluationTarget(
            f"REFUSING {operation}: the {role} URL uses the scheme {scheme!r}. Only "
            "PostgreSQL URLs can be shown to name a database, so anything else is refused."
        )
    keys = {key.lower() for key, _ in parse_qsl(parts.query, keep_blank_values=True)}
    overrides = sorted(keys & CONNECTION_OVERRIDE_PARAMS)
    if overrides:
        raise UnsafeEvaluationTarget(
            f"REFUSING {operation}: the {role} URL sets the connection parameter(s) "
            f"{', '.join(overrides)}. Those can redirect the connection away from the host "
            "named in the URL, so its database cannot be established. Remove them."
        )


def assert_safe_evaluation_target(
    dsn: str,
    *,
    operation: str,
    application_url: str | None = None,
) -> Identity:
    """Prove ``dsn`` names a different database from the application's, or refuse.

    Call this *before* the first connection of any run that creates, drops,
    truncates, migrates or otherwise destructively modifies a database.  It is
    pure string inspection: it establishes no connection and reads no rows, so
    it cannot itself be destructive.

    Separation is decided by database name alone (case-insensitively).  Two
    databases with different names are separate; two with the same name are
    refused, however their hosts and ports are written, because no string can
    prove that two hostnames, or ``localhost`` and ``127.0.0.1``, do or do not
    name the same server.

    Fails closed in every direction: a missing host or database name, an
    unsupported scheme, a connection-override parameter, a malformed port or an
    empty application URL all refuse the run.  ``application_url`` is used exactly
    as given; an empty string is not replaced by the application's settings.

    Returns the target's identity so the caller has the verified value.
    """
    identity = database_identity(dsn)

    if not identity[0] or not identity[2]:
        raise UnsafeEvaluationTarget(
            "cannot establish the database identity of the evaluation target "
            f"({display_dsn(dsn)}): a host and a database name are both required. "
            f"Refusing {operation}, because an unidentified target cannot be shown "
            "to differ from the application database."
        )

    application_dsn = application_database_url() if application_url is None else application_url
    application = database_identity(application_dsn)

    if not application[0] or not application[2]:
        raise UnsafeEvaluationTarget(
            "cannot establish the application database's identity, so the evaluation "
            f"target ({describe_identity(identity)}) cannot be shown to differ from it. "
            f"Refusing {operation}. Configure DATABASE_URL for the application."
        )

    _refuse_unverifiable_url(dsn, role="evaluation target", operation=operation)
    _refuse_unverifiable_url(application_dsn, role="application database", operation=operation)

    if identity[2].casefold() == application[2].casefold():
        if identity == application:
            detail = "it is the application database itself."
        else:
            detail = (
                "two databases with the same name cannot be shown to be separate, "
                "because their hosts and ports cannot be proven to name different servers."
            )
        raise UnsafeEvaluationTarget(
            f"REFUSING {operation}: the target {describe_identity(identity)} shares the "
            f"database name {identity[2]!r} with the application database "
            f"({describe_identity(application)}), and {detail} This operation writes or "
            f"deletes rows. Point {EVALUATION_DATABASE_URL_ENV} (or --database-url) at an "
            "isolated database with a different name."
        )

    return identity


def describe_targets(*, dsn: str, application_url: str | None = None) -> str:
    """Two credential-free lines naming the application and evaluation targets."""
    application_dsn = application_database_url() if application_url is None else application_url
    application = database_identity(application_dsn)
    evaluation = database_identity(dsn)
    return (
        f"[evaluation-db] application database : {describe_identity(application)}\n"
        f"[evaluation-db] evaluation database  : {describe_identity(evaluation)}"
    )


# ---------------------------------------------------------------------------
# Disposal authorization
#
# Five distinct questions, each answered by a different check and none of them
# implying another:
#
#   1. URL validity            -> assert_safe_evaluation_target (scheme, identity)
#   2. application isolation   -> assert_safe_evaluation_target (database name)
#   3. target identity         -> database_identity / assert_engine_matches_target
#   4. destructive permission  -> assert_disposal_authorized (this section)
#   5. proof of disposability  -> NOT ESTABLISHED by any check in this repository
#
# Step 1.6K: no enforceable external authorization or connection-bound lifecycle
# exists. All creation, evidence issuance, row cleanup and deletion are blocked.
# In-process proofs, issuer markers and registries cannot establish that boundary.
# ---------------------------------------------------------------------------

# No issuer exists. Python objects and module-private registries are not an
# authorization boundary. Until an external lifecycle authority is implemented,
# creation, evidence issuance, row cleanup and deletion all refuse.


@dataclass(frozen=True)
class DisposalProof:
    """Legacy evidence-shaped data, never authority to create, clean up or drop.

    Constructing, copying or altering this object cannot enable a lifecycle.
    Kept for compatibility with callers that must now fail closed.
    """

    identity: Identity
    _issuer: object = field(default=None, repr=False, compare=False)
    lifecycle: str = field(default="")


def _proof_is_live(proof: object) -> bool:
    """No proof can be live until an enforceable lifecycle authority exists."""
    # Even a matching registry entry cannot establish external authorization.
    return False


def record_created_database(dsn: str) -> DisposalProof:
    """Refuse caller-asserted creation evidence; no authorized issuer exists."""
    raise UnsafeEvaluationTarget(
        "REFUSING proof issuance: no authorized creation lifecycle or verified "
        "successful-creation evidence exists. Caller declarations are not evidence."
    )


def assert_disposal_authorized(
    dsn: str,
    *,
    operation: str,
    application_url: str | None = None,
    proof: DisposalProof | None = None,
) -> Identity:
    """Always refuse destruction: no enforceable lifecycle authority exists.

    Validate the target and application isolation independently, without I/O when
    application_url is explicit. Ordinary proof objects never authorize work.
    """
    identity = database_identity(dsn)
    name = identity[2]
    if not name:
        raise UnsafeEvaluationTarget(
            f"REFUSING {operation}: the target has no database name."
        )

    application_dsn = application_database_url() if application_url is None else application_url
    application_name = database_identity(application_dsn)[2]
    if name.casefold() == application_name.casefold():
        raise UnsafeEvaluationTarget(
            f"REFUSING {operation}: the target's database name is the application database's "
            "name, which is never destroyed."
        )

    assert_safe_evaluation_target(
        dsn, operation=operation, application_url=application_dsn
    )
    raise UnsafeEvaluationTarget(
        f"REFUSING {operation}: no enforceable disposal boundary for "
        f"{describe_identity(identity)}. No authorized, connection-bound lifecycle "
        "exists. A URL, database name, environment variable, or Python proof object "
        "is not authorization. Destructive use is blocked by default."
    )


def assert_creation_authorized(
    dsn: str,
    *,
    operation: str,
    application_url: str | None = None,
    database_exists: bool | None = None,
) -> Identity:
    """Refuse creation without an enforceable create authority.

    Creation is distinct from disposal and cannot require post-creation evidence.
    Nevertheless URL isolation and a caller-supplied absence claim are not create
    authorization. No accepted create authorization is implemented. No I/O occurs.
    """
    identity = assert_safe_evaluation_target(
        dsn, operation=operation, application_url=application_url
    )
    if database_exists:
        raise UnsafeEvaluationTarget(
            f"REFUSING {operation}: a database named {identity[2]!r} already exists on "
            f"{describe_identity(identity)}. Creation refuses an existing name. An existing "
            "database is never adopted or dropped."
        )
    raise UnsafeEvaluationTarget(
        f"REFUSING {operation}: missing enforceable create authorization. "
        "A valid isolated URL and an absent database name do not authorize creation."
    )


def assert_row_cleanup_authorized(
    dsn: str,
    *,
    operation: str,
    application_url: str | None = None,
    proof: DisposalProof | None = None,
) -> Identity:
    """Refuse row cleanup under the same missing-authority rule as database drop."""
    return assert_disposal_authorized(
        dsn, operation=operation, application_url=application_url, proof=proof
    )


def assert_cleanup_execution_authorized(
    resource: object,
    *,
    operation: str,
    proof: DisposalProof | None = None,
) -> None:
    """Block destructive callables before inspecting a session/engine or doing I/O.

    There is no trusted lifecycle authority or actual-connection identity binding.
    Thus no resource or proof is accepted, including a configured matching engine.
    Do not inspect attributes: caller-supplied properties can themselves perform I/O.
    A future positive path requires an approved connection-bound authority, not a
    URL comparison or registry. This refusal is independent of environment/settings.
    """
    raise UnsafeEvaluationTarget(
        f"REFUSING {operation}: cleanup execution is blocked; no enforceable, "
        "connection-bound lifecycle authorization exists. A caller-supplied "
        "session, engine, URL, or proof object is not authorization."
    )


def release_database_proof(proof: DisposalProof, *, operation: str) -> None:
    """Refuse lifecycle release: no authorized open lifecycle can exist."""
    raise UnsafeEvaluationTarget(
        f"REFUSING {operation}: the disposal proof is not live; no authorized "
        "lifecycle exists to close."
    )


def assert_engine_bound_to_proof(
    engine,
    dsn: str,
    *,
    operation: str,
    application_url: str | None = None,
    proof: DisposalProof | None = None,
) -> None:
    """Refuse unless ``engine`` targets the database the open proof covers.

    Checks the proof against ``dsn`` first, then the engine against ``dsn``.  Run
    it before any session is opened.  No connection is made.
    """
    assert_engine_matches_target(engine, dsn)
    assert_disposal_authorized(
        dsn, operation=operation, application_url=application_url, proof=proof
    )


def assert_engine_matches_target(engine, dsn: str) -> None:
    """Refuse unless ``engine`` is configured for the database named by ``dsn``.

    Reads the engine's URL object only.  It opens no connection, so it can run
    right after the engine is constructed and before any session is made.  The
    comparison is literal and conservative: a host spelled differently from the
    approved target is a mismatch, not an alias to be accepted.
    """
    expected_host, expected_port, expected_name = database_identity(dsn)
    actual = (
        str(engine.url.host or "").lower(),
        engine.url.port,
        engine.url.database or "",
    )
    if actual != (expected_host.lower(), expected_port, expected_name):
        raise UnsafeEvaluationTarget(
            "the database engine is configured for a different target than the one "
            "the isolation guard approved; refusing before any connection is attempted"
        )

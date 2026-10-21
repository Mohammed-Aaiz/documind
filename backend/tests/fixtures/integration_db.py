"""Integration database lifecycle — BLOCKED pending external authorization.

Step 1.6K supersedes the historical workflow below: create authorization refuses
before probes, existence checks or SQL. Drop and row-cleanup authorization always
refuse, including for constructed Python proofs. No lifecycle is currently enabled.
The retained workflow documents the intended shape, not authorization to run it.

Historically: provision an explicitly isolated PostgreSQL database for integration tests.

Why this exists
---------------
``tests/integration/rag/test_real_e2e_validation.py`` validates the *real* RAG
pipeline (real PostgreSQL, real pgvector, real embeddings, real Brain, real QA
model) and its first act is to delete every row from ``users``, ``documents``
and ``document_chunks``.  That is only safe when the database it talks to is
provably not the application's own.

This module supplies that isolation.  Its whole lifecycle is:

    resolve target        DOCUMIND_INTEGRATION_DATABASE_URL, else the
                          application's server with a dedicated database name
        ↓
    refuse if identity == application identity
        ↓
    drop + create the database
        ↓
    alembic upgrade head, in a subprocess pinned to that DSN
        ↓
    verify: revision == alembic head, pgvector present, required tables present
        ↓
    yield
        ↓
    drop the database

Safety rules, in order
----------------------
1. :func:`assert_isolated_target` runs *before* the first destructive statement
   — the drop cannot happen until the target has been proven to be somewhere
   else.
2. Isolation is asserted on the complete identity ``(host, port, database)``,
   never on a database name alone.
3. Nothing is written into this process's environment.  Alembic is pointed at
   the isolated database through the environment of its **own subprocess**,
   which is the mechanism ``scripts/setup_db.py`` and
   ``tests/integration/documents/test_table_row_migration.py`` already use.

Provisioning reuses the existing ``psql`` discovery and connection handling in
``tests/fixtures/e2e_config.py``; the application database is used only as the
maintenance connection for ``CREATE DATABASE`` / ``DROP DATABASE``.

Owned by the test layer; never imported by production code.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

from typing import NamedTuple

from evaluation.isolation import DisposalProof
from evaluation.isolation import assert_creation_authorized as _central_assert_creation_authorized
from evaluation.isolation import assert_disposal_authorized as _central_assert_disposal_authorized
from evaluation.isolation import assert_row_cleanup_authorized as _central_assert_row_cleanup_authorized
from evaluation.isolation import assert_safe_evaluation_target
from evaluation.isolation import record_created_database
from evaluation.isolation import release_database_proof
from evaluation.isolation import database_identity as _central_database_identity
from tests.fixtures import e2e_config
from tests.fixtures.paths import BACKEND_DIR

#: Environment variable naming the database an integration test may use.
INTEGRATION_DATABASE_URL_ENV = "DOCUMIND_INTEGRATION_DATABASE_URL"

#: The dedicated integration database, created on the application's own server.
#: A separate *database* — not a separate cluster — is the smallest isolation
#: that guarantees the destructive validation cannot reach application data.
INTEGRATION_DATABASE_NAME = "documind_integration"

#: Tables the migration chain must produce.  Asserted after ``upgrade head`` so
#: a database that is reachable but unmigrated fails loudly instead of letting
#: the validation run against an empty schema.
REQUIRED_TABLES = frozenset(
    {
        "alembic_version",
        "chat_messages",
        "chat_sessions",
        "document_chunks",
        "document_graph_edges",
        "document_structure_edges",
        "document_structure_elements",
        "document_table_rows",
        "documents",
        "reliability_logs",
        "source_refs",
        "user_settings",
        "users",
        "verification_results",
    }
)

_HEAD_LINE = re.compile(r"^(\S+)\s+\((?:head|mergepoint|branchpoint|effective head)")


# ---------------------------------------------------------------------------
# Target resolution and the safety guard
# ---------------------------------------------------------------------------


def application_database_url() -> str:
    """The DSN the application itself uses (``backend/.env`` wins over ambient).

    Deliberately the *same* resolver the E2E harness uses, so "the application
    database" means one thing across the whole test layer.
    """
    return e2e_config.database_url()


def database_identity(dsn: str) -> tuple[str, int | None, str]:
    """``(host, port, database)`` — delegates to the central guard's parser.

    One parser for the whole evaluation and test layer, so a malformed port or
    an encoded database name is read the same way everywhere.  The password is
    never part of the identity, so it is safe to log.
    """
    return _central_database_identity(dsn)


def _with_database(dsn: str, database: str) -> str:
    """``dsn`` with its database name replaced, everything else preserved."""
    parts = urlsplit(dsn)
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment)
    )


def integration_database_url() -> str:
    """The database an integration test targets — explicit, never ambient.

    ``DOCUMIND_INTEGRATION_DATABASE_URL`` overrides everything.  Otherwise the
    target is derived from the application's DSN by swapping in
    :data:`INTEGRATION_DATABASE_NAME`, which keeps it on a server that is known
    to be reachable and carries the same credentials, while guaranteeing the
    database it names is a different one.
    """
    override = os.environ.get(INTEGRATION_DATABASE_URL_ENV)
    if override is not None:
        # An empty override is returned as-is so the guard refuses it.  Falling
        # back to the derived name here would be a silent redirect.
        return override
    return _with_database(application_database_url(), INTEGRATION_DATABASE_NAME)


def assert_isolated_target() -> str:
    """Return the integration DSN, refusing to run against the application's.

    This is the single gate that makes the destructive validation safe.  It
    compares the *complete* identity — host, port and database — of the resolved
    target against the application's, so neither an override that points at the
    live database nor a derived name that happens to collide can slip through.

    Returns the resolved DSN so callers cannot accidentally use an unguarded
    value, and is called before any destructive statement is issued.
    """
    application_dsn = application_database_url()
    target = integration_database_url()

    # Central policy: fails closed on malformed, unsupported, override-carrying,
    # or unidentifiable URLs, and refuses any target whose database name matches
    # the application's (case-insensitively), whatever its host spelling.
    assert_safe_evaluation_target(
        target,
        operation="the integration validation (it drops and recreates its database)",
        application_url=application_dsn,
    )

    # This fixture creates, migrates and drops the target through the
    # application server's maintenance connection (``_drop_database`` and
    # ``psql_value`` connect to the application's host and port).  A target on
    # another server would therefore be acted on in the wrong place, so refuse it.
    target_host, target_port, _ = database_identity(target)
    app_host, app_port, _ = database_identity(application_dsn)
    if (target_host.lower(), target_port) != (app_host.lower(), app_port):
        raise RuntimeError(
            "Refusing to run: the integration target is on a different server "
            f"({target_host}:{target_port}) from the application server "
            f"({app_host}:{app_port}). This fixture provisions the integration "
            "database through the application server only. Use the same host and port."
        )

    return target


# ---------------------------------------------------------------------------
# Disposal authorization (Step 1.6K: all lifecycle operations blocked)
#
# Validating a URL is not permission to destroy a database.  Neither is a database
# name, an environment variable, nor a target that differs from the application.
# No proof issuer or external create authority exists. Python objects, configured
# names, claimed successful creation and free-name checks cannot authorize work.
# The retained create/drop workflow is unreachable behind fail-closed gates.
# ---------------------------------------------------------------------------


def assert_disposal_authorized(dsn: str, *, proof=None) -> None:
    """Refuse destruction of ``dsn`` unless ``proof`` covers it.

    Delegates to the central contract.  It performs no I/O.
    """
    _central_assert_disposal_authorized(
        dsn,
        operation="the integration fixture (it drops the database it created)",
        application_url=application_database_url(),
        proof=proof,
    )


def assert_row_cleanup_authorized(dsn: str, *, proof: DisposalProof | None) -> None:
    """Refuse row deletion in ``dsn`` unless ``proof`` is open for that exact target.

    Delegates to the central contract.  Performs no I/O.  Creating a database
    needs no proof; deleting its rows does.
    """
    _central_assert_row_cleanup_authorized(
        dsn,
        operation="the integration validation (it deletes rows in the database it created)",
        application_url=application_database_url(),
        proof=proof,
    )


class ProvisionedDatabase(NamedTuple):
    """A database this run created, with the proof that covers it.

    ``dsn`` is the target every destructive statement runs against.  ``proof`` is
    the only evidence accepted for deleting its rows or dropping it.
    """

    dsn: str
    proof: DisposalProof


def assert_authorized_destructive_target() -> str:
    """Always refuses.  Kept so the ``__main__`` path cannot silently skip the gate.

    Validates the URL, then requires a disposal proof that this path cannot have,
    because no enforceable lifecycle authority exists. Provisioning is also
    blocked; changing entry points is not an authorization workaround.
    """
    dsn = assert_isolated_target()
    assert_disposal_authorized(dsn)
    return dsn


def target_name(dsn: str) -> str:
    """The database name inside ``dsn`` (the thing that gets created/dropped)."""
    name = database_identity(dsn)[2]
    if not name:
        raise RuntimeError(f"integration DSN has no database name: {dsn!r}")
    return name


# ---------------------------------------------------------------------------
# Server availability
# ---------------------------------------------------------------------------


def postgres_available(timeout: float = 2.0) -> bool:
    """True when the application's PostgreSQL server accepts connections."""
    cfg = e2e_config.postgres()
    try:
        with socket.create_connection((cfg.host, cfg.port), timeout=timeout):
            return True
    except OSError:
        return False


def require_postgres() -> None:
    """``pytest.skip`` unless the PostgreSQL server is reachable.

    Only a genuinely absent server skips.  Every other failure — a missing
    ``psql`` binary, a provisioning error, a failed migration, a guard
    violation — raises, so it can never be mistaken for "not applicable".
    """
    import pytest

    if not postgres_available():
        cfg = e2e_config.postgres()
        pytest.skip(f"PostgreSQL not reachable at {cfg.host}:{cfg.port}")


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------


def psql_value(dsn: str, sql: str, *, timeout: float = 60.0) -> str:
    """Run ``sql`` against the database named by ``dsn``; return the bare value.

    ``-t -A`` (tuples only, unaligned) makes a single-value query come back as
    exactly one unadorned line, so callers never parse psql's table formatting.
    Binary discovery and credentials come from the same source the E2E harness
    uses; the password travels through the environment, never argv.
    """
    cfg = e2e_config.postgres()
    env = dict(os.environ)
    if cfg.password:
        env["PGPASSWORD"] = cfg.password
    else:
        env.pop("PGPASSWORD", None)

    result = subprocess.run(
        [
            e2e_config.psql_binary(),
            "-h", cfg.host,
            "-p", str(cfg.port),
            "-U", cfg.user,
            "-d", database_identity(dsn)[2],
            "-t", "-A",
            "-c", sql,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"psql exited {result.returncode} against "
            f"{database_identity(dsn)}: {(result.stderr or '').strip()[:400]}"
        )
    return result.stdout.strip()


def database_exists(name: str) -> bool:
    return (
        psql_value(
            application_database_url(),
            f"SELECT count(*) FROM pg_database WHERE datname = '{name}'",
        )
        == "1"
    )


def _drop_database(dsn: str, proof) -> None:
    """Drop the database named by ``dsn``, but only with a proof that this run created it.

    The gate reads the DSN passed in, not the environment, so configuration that
    changed after provisioning cannot redirect the drop.  ``WITH (FORCE)`` ends
    any leftover connection first, so cleanup is not defeated by a stray handle.
    Requires PostgreSQL 13+; this project targets 16.
    """
    assert_disposal_authorized(dsn, proof=proof)
    name = target_name(dsn)
    psql_value(
        application_database_url(),
        f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)',
    )
    # The database is gone, so its lifecycle closes and the proof becomes dead.
    release_database_proof(
        proof,
        operation="the integration fixture (it drops the database it created)",
    )


def _create_database(name: str) -> None:
    """Refuse creation before I/O: enforceable create authorization is absent.

    The application database's name remains prohibited independently.
    """
    _central_assert_creation_authorized(
        _with_database(application_database_url(), name),
        operation="creating an integration database",
        application_url=application_database_url(),
    )
    application_name = database_identity(application_database_url())[2]
    if not name or name.casefold() == application_name.casefold():
        raise RuntimeError(
            f"Refusing to create {name!r}: it is empty or the application database's name."
        )
    psql_value(application_database_url(), f'CREATE DATABASE "{name}"')


# ---------------------------------------------------------------------------
# Schema provisioning
# ---------------------------------------------------------------------------


def _alembic_env(dsn: str) -> dict:
    """A child-process environment pinned to ``dsn``.

    ``migrations/env.py`` resolves its URL from settings, and a real environment
    variable outranks ``backend/.env``; passing it through the subprocess's own
    environment is therefore what aims Alembic at the isolated database.  This
    process's environment is left untouched.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = dsn
    return env


def alembic_head() -> str:
    """The head revision of the migration chain, read from the real CLI."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    heads = [
        match.group(1)
        for line in result.stdout.splitlines()
        if (match := _HEAD_LINE.match(line.strip()))
    ]
    if result.returncode != 0 or len(heads) != 1:
        raise RuntimeError(
            "could not determine a single alembic head "
            f"(exit {result.returncode}, heads={heads}):\n{result.stderr.strip()[:400]}"
        )
    return heads[0]


def migrate_to_head(dsn: str) -> None:
    """Bring the isolated database to ``head`` using the normal migration path."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env=_alembic_env(dsn),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed (exit {result.returncode}) on the "
            f"isolated database:\n{result.stdout.strip()[-600:]}\n"
            f"{result.stderr.strip()[-600:]}"
        )


def inspect_schema(dsn: str) -> dict:
    """Real database facts about the isolated target: revision, vector, tables.

    Deliberately synchronous.  Provisioning runs from a fixture, and creating or
    closing an event loop there disturbs the loop pytest-asyncio manages for the
    tests that follow it — so this reads the catalogs through ``psql`` instead of
    standing up an async engine of its own.
    """
    return {
        "revision": psql_value(dsn, "SELECT version_num FROM alembic_version"),
        "vector": psql_value(
            dsn, "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ),
        "tables": set(
            filter(
                None,
                psql_value(
                    dsn,
                    "SELECT string_agg(tablename, ',') FROM pg_tables "
                    "WHERE schemaname = 'public'",
                ).split(","),
            )
        ),
    }


def verify_schema(dsn: str, *, expected_revision: str) -> dict:
    """Assert the isolated database really is migrated PostgreSQL + pgvector.

    Raises rather than skipping: a reachable-but-unmigrated database would let
    the validation run against an empty schema and report meaningless results.
    """
    report = inspect_schema(dsn)
    report["expected_revision"] = expected_revision

    if report["revision"] != expected_revision:
        raise RuntimeError(
            f"isolated database is at revision {report['revision']!r}, "
            f"expected {expected_revision!r}"
        )
    if not report["vector"]:
        raise RuntimeError(
            "pgvector is not installed in the isolated database "
            "(the validation needs real vector columns)"
        )

    missing = sorted(REQUIRED_TABLES - report["tables"])
    if missing:
        raise RuntimeError(f"isolated database is missing tables: {missing}")

    return report


# ---------------------------------------------------------------------------
# Lifecycle entry points
# ---------------------------------------------------------------------------


#: Flag telling the validation module to use an already-provisioned database
#: instead of provisioning one itself (standalone runs against a database that
#: was set up by the caller).
USE_PROVISIONED_DATABASE_FLAG = "--use-provisioned-database"

# NOTE: the validation no longer runs in a child process.  It used to, because
# ``tests/conftest.py`` monkey-patched the production ORM column types in place
# for SQLite; the validation needs the genuine PostgreSQL metadata and the rest
# of the suite needed the patched one, so the two could not share a process.
# SQLite compatibility now lives in dialect-scoped rules installed on the SQLite
# test engine, so the validation runs in-process and this helper is gone.


@contextmanager
def provisioned_integration_database():
    """Refuse provisioning until enforceable create/lifecycle authority exists.

    The retained lifecycle implementation below the create gate is unreachable.
    A bare DSN or Python proof never enables it. No reachability or existence
    check runs before that gate.
    """
    # URL validation is pure string inspection.  Nothing below drops a database
    # this run did not create.
    dsn = assert_isolated_target()
    # Absence checks, reachability probes and provisioning are not permission.
    # Refuse before any database/socket/subprocess access until create authority
    # exists, separately from post-creation evidence and disposal permission.
    _central_assert_creation_authorized(
        dsn,
        operation="provisioning an integration database",
        application_url=application_database_url(),
    )
    name = target_name(dsn)
    identity = database_identity(dsn)
    application = database_identity(application_database_url())

    print(f"[integration-db] application database : {application}")
    print(f"[integration-db] integration database : {identity}")

    if not postgres_available():
        raise RuntimeError(
            f"PostgreSQL is not reachable at {identity[0]}:{identity[1]}; "
            "the integration database cannot be provisioned"
        )

    # Creation authorization.  It needs no disposal proof: creating cannot destroy
    # data, and a name that already exists is refused rather than adopted.  The
    # proof comes only after the create succeeds, below.
    _central_assert_creation_authorized(
        dsn,
        operation="the integration fixture (it creates the database)",
        application_url=application_database_url(),
        database_exists=database_exists(name),
    )
    _create_database(name)
    # Only now does this run hold evidence that it created ``name``.
    proof = record_created_database(dsn)
    try:
        head = alembic_head()
        migrate_to_head(dsn)
        report = verify_schema(dsn, expected_revision=head)
        print(
            f"[integration-db] provisioned {name}: "
            f"revision={report['revision']} pgvector={report['vector']} "
            f"tables={len(report['tables'])}"
        )
        yield ProvisionedDatabase(dsn, proof)
    finally:
        _drop_database(dsn, proof)
        print(f"[integration-db] dropped {name}")


try:  # pragma: no cover - pytest is present in every supported environment
    import pytest
except Exception:  # pragma: no cover
    pytest = None

if pytest is not None:  # pragma: no cover - exercised by the test module

    @pytest.fixture(scope="module")
    def isolated_database():
        """Module-scoped isolated database: provision, migrate, drop.  Yields a ProvisionedDatabase."""
        # Authorization must refuse before require_postgres can open a socket.
        dsn = assert_isolated_target()
        _central_assert_creation_authorized(
            dsn,
            operation="the isolated database fixture",
            application_url=application_database_url(),
        )
        require_postgres()
        with provisioned_integration_database() as provisioned:
            yield provisioned

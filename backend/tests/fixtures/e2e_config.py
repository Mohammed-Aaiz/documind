"""Single source of truth for the live-server E2E harnesses.

Owned by the test layer; never imported by production code.

The harnesses in ``tests/e2e/browser/`` drive a **real** running server
(Vite dev proxy on :3000 -> FastAPI :8000) against the **real** PostgreSQL
database.  Before this module existed, each harness re-derived that runtime
environment in its own way, which produced three distinct classes of
environment dependence:

1. **The PostgreSQL port was implicit.**  The harnesses shelled out to a
   hard-coded ``psql.exe`` with ``-h localhost`` and *no* ``-p``, so they
   silently targeted port 5432 while the sanctioned runtime listens on 55433.
   They only worked when a developer remembered to export ``PGPORT=55433`` —
   an undocumented, unenforced assumption.
2. **The psql binary path was machine-specific.**  A literal
   ``C:/pg/pg16/pgsql/bin/psql.exe`` is only correct on one machine.
3. **The connection parameters drifted from the application's own.**  Nothing
   tied the tests to the database the backend actually uses.

Design
------
``postgres()`` resolves the connection from the **application's own**
``backend/.env`` (the sanctioned runtime configuration), in this order:

    DOCUMIND_E2E_DATABASE_URL   explicit test-only override
    backend/.env DATABASE_URL   the file the application itself loads
    os.environ DATABASE_URL     last resort

``backend/.env`` deliberately outranks the ambient process environment.  Other
integration tests mutate ``os.environ["DATABASE_URL"]`` at import time (for
example ``tests/integration/rag/test_real_e2e_validation.py`` does
``os.environ.setdefault("DATABASE_URL", "...localhost:5432...")``), and pytest
imports modules before the e2e tests run — so honouring the ambient variable
would let an unrelated test silently re-point database verification at the
wrong server.  Reading the file the application actually uses is both
deterministic and immune to that cross-test contamination.

Nothing here reads or writes the password of the *application*: the DSN is
parsed only to recover host/port/database/user, and the credentials are passed
to ``psql`` through the child process environment (``PGPASSWORD``), never on
the command line and never printed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tests.fixtures.paths import BACKEND_DIR

# ---------------------------------------------------------------------------
# Environment variables (test-only; production is never affected)
# ---------------------------------------------------------------------------

BASE_URL_ENV = "DOCUMIND_E2E_BASE_URL"
DATABASE_URL_ENV = "DOCUMIND_E2E_DATABASE_URL"
PSQL_ENV = "DOCUMIND_E2E_PSQL"

DEFAULT_BASE_URL = "http://localhost:3000"

#: The canonical demo account the product documentation refers to.  It must
#: already exist; E2E harnesses that only *read* it must not silently replace
#: it with a freshly created account.
DEMO_USER_EMAIL = "test@documind.io"
DEMO_USER_PASSWORD = "TestPass123!"
DEMO_USER_NAME = "Test User"

#: A dedicated account for corpus-sensitive harnesses.  Sharing one account
#: across harnesses is what let an unrelated document contaminate a retrieval
#: assertion (see ``test_rag_flow``): retrieval is user-scoped, so a shared
#: user means a shared — and therefore unpredictable — corpus.
RAG_TEST_USER_EMAIL = "e2e.rag@test.local"
RAG_TEST_USER_PASSWORD = "E2ERagPass123!"
RAG_TEST_USER_NAME = "E2E RAG Harness"

# ---------------------------------------------------------------------------
# Test-owned paths (never the application's upload directory)
# ---------------------------------------------------------------------------

TESTS_DIR = BACKEND_DIR / "tests"
FIXTURES_DIR = TESTS_DIR / "fixtures"

#: Scratch directory for PDFs a harness generates at run time.  Deliberately
#: *not* ``backend/uploads/`` — that is the application's storage root.
GENERATED_UPLOADS_DIR = TESTS_DIR / "e2e" / "browser" / "uploads"

#: Static fixtures the assertions depend on verbatim.
DARWIN_PDF = FIXTURES_DIR / "darwin_proper.pdf"

# Candidate psql locations for the project's own PostgreSQL distribution.
PSQL_CANDIDATES = (
    Path("C:/pg/pg16/pgsql/bin/psql.exe"),
    Path("C:/pgdata/pgsql/bin/psql.exe"),
    Path("C:/Program Files/PostgreSQL/16/bin/psql.exe"),
)


# ---------------------------------------------------------------------------
# HTTP base URL
# ---------------------------------------------------------------------------

def base_url() -> str:
    """The live server the harnesses drive (Vite proxy by default)."""
    return (os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")


# ---------------------------------------------------------------------------
# PostgreSQL
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


def database_url() -> str:
    """The DSN of the sanctioned runtime the tests must verify against."""
    for source, value in (
        (DATABASE_URL_ENV, os.environ.get(DATABASE_URL_ENV)),
        ("backend/.env", _read_env_file_value("DATABASE_URL", BACKEND_DIR / ".env")),
        ("os.environ", os.environ.get("DATABASE_URL")),
    ):
        if value:
            return value
    raise RuntimeError(
        "No DATABASE_URL could be resolved for the E2E harness. Set "
        f"{DATABASE_URL_ENV}=postgresql+asyncpg://user:pass@host:port/db, or "
        f"configure DATABASE_URL in {BACKEND_DIR / '.env'}."
    )


@dataclass(frozen=True)
class PostgresConfig:
    """Connection parameters for direct database verification via psql."""

    host: str
    port: int
    database: str
    user: str
    password: str | None

    def describe(self) -> str:
        """A log-safe summary.  Never includes the password."""
        return f"{self.user}@{self.host}:{self.port}/{self.database}"


def postgres() -> PostgresConfig:
    """Parse the sanctioned DSN into explicit ``psql`` connection parameters."""
    parts = urlsplit(database_url())
    if not parts.hostname:
        raise RuntimeError("DATABASE_URL has no host; cannot configure psql")
    return PostgresConfig(
        host=parts.hostname,
        port=parts.port or 5432,
        database=(parts.path or "").lstrip("/") or "postgres",
        user=unquote(parts.username or ""),
        password=unquote(parts.password) if parts.password else None,
    )


def psql_binary() -> str:
    """Locate a ``psql`` binary without depending on the developer's PATH.

    Direct row verification is the whole point of the harnesses that use this,
    so a missing binary is an error rather than a skip — silently skipping
    would turn "not verified" into "passed".
    """
    override = os.environ.get(PSQL_ENV)
    if override:
        if Path(override).is_file():
            return override
        raise RuntimeError(f"{PSQL_ENV}={override!r} does not point to a file")

    for candidate in PSQL_CANDIDATES:
        if candidate.is_file():
            return str(candidate)

    found = shutil.which("psql")
    if found:
        return found

    raise RuntimeError(
        "No psql binary found. Direct database verification cannot run. "
        f"Set {PSQL_ENV} to a psql executable path."
    )


def psql(sql: str, *, timeout: float = 60.0) -> str:
    """Run ``sql`` against the sanctioned database and return stdout.

    Runs in plain (aligned, header-bearing) mode, which is what the existing
    harness assertions inspect.  ``-h``/``-p``/``-U``/``-d`` are always passed
    explicitly so no ambient ``PGPORT``/``PGHOST`` can re-point the query.
    """
    cfg = postgres()
    env = dict(os.environ)
    # Delivered through the environment, never argv: a password must not appear
    # in a process listing or an error message.
    if cfg.password:
        env["PGPASSWORD"] = cfg.password
    else:
        env.pop("PGPASSWORD", None)

    result = subprocess.run(
        [
            psql_binary(),
            "-h", cfg.host,
            "-p", str(cfg.port),
            "-U", cfg.user,
            "-d", cfg.database,
            "-c", sql,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"psql exited {result.returncode} against {cfg.describe()}: "
            f"{(result.stderr or '').strip()[:400]}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Generated fixtures
# ---------------------------------------------------------------------------

def generated_uploads_dir() -> Path:
    """Return the harness scratch directory, creating it if needed.

    Creating it here (rather than relying on the developer's local filesystem
    state) is what makes ``ml_test.pdf`` and friends reproducible on a clean
    checkout.
    """
    GENERATED_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return GENERATED_UPLOADS_DIR


def require_fixture(path: Path) -> Path:
    """Return ``path`` or fail loudly when a required static fixture is absent."""
    if not path.is_file():
        raise RuntimeError(
            f"Required E2E fixture is missing: {path}. "
            "It is a committed test fixture; restore it rather than letting the "
            "harness silently substitute a different document."
        )
    return path


# ---------------------------------------------------------------------------
# Test accounts and corpora
# ---------------------------------------------------------------------------

def ensure_test_user(
    email: str,
    password: str,
    name: str,
    *,
    timeout: float = 180.0,
) -> None:
    """Create ``email`` if absent, via the project's canonical script.

    Delegates to ``backend/scripts/create_test_user.py`` so the test layer
    never re-implements password hashing (and therefore can never drift from
    how the application verifies a password).  The script is idempotent.
    """
    script = BACKEND_DIR / "scripts" / "create_test_user.py"
    if not script.is_file():
        raise RuntimeError(f"canonical user-creation script not found: {script}")

    # Pin the child to the DSN this harness resolved and verified against.
    #
    # The script re-reads DATABASE_URL itself, and pydantic-settings lets a real
    # environment variable outrank ``backend/.env``.  A sibling test that sets
    # ``os.environ["DATABASE_URL"]`` process-wide at import time (e.g.
    # ``tests/integration/rag/test_real_e2e_validation.py``, which defaults it to
    # the 5432 developer port) would otherwise leak into this subprocess and
    # make the child create the user in a *different* database — passing in
    # isolation and failing only in a full-suite run.  Same rule as
    # ``database_url()``: the sanctioned runtime wins over ambient state.
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url()

    result = subprocess.run(
        [sys.executable, str(script), "--email", email, "--password", password, "--name", name],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    # The script prints a passlib/bcrypt version-probe traceback on some
    # versions and still succeeds, so the exit status is the contract.
    if result.returncode != 0:
        raise RuntimeError(
            f"create_test_user.py exited {result.returncode} for {email}: "
            f"{(result.stderr or '').strip()[:400]}"
        )


def purge_documents(base: str | None = None, *, token: str, name: str | None = None) -> int:
    """Delete the user's own documents through the real API.

    Used to give a corpus-sensitive harness a known starting state.  Only the
    acting user's documents are reachable (the API scopes by the JWT), and
    ``name`` narrows it further.  Returns the number deleted.
    """
    from tests.fixtures.integration_http import api_call

    base = base or base_url()
    status, body = api_call("GET", "/api/documents", token=token, base=base)
    if status != 200:
        raise RuntimeError(f"could not list documents (HTTP {status}): {body}")

    deleted = 0
    for document in body.get("documents", []):
        if name is not None and document.get("name") != name:
            continue
        code, _ = api_call("DELETE", f"/api/documents/{document['id']}", token=token, base=base)
        if code == 200:
            deleted += 1
    return deleted


def login(email: str, password: str, base: str | None = None) -> str:
    """Log in and return the bearer token."""
    from tests.fixtures.integration_http import api_call

    base = base or base_url()
    status, body = api_call(
        "POST", "/api/auth/login", body={"email": email, "password": password}, base=base
    )
    if status != 200:
        raise RuntimeError(f"login failed for {email} (HTTP {status})")
    token = body.get("access_token", "")
    if not token:
        raise RuntimeError(f"login for {email} returned no access_token")
    return token


def document_names(base: str | None = None, *, token: str) -> list[str]:
    """The acting user's document names, for reporting corpus isolation."""
    from tests.fixtures.integration_http import api_call

    base = base or base_url()
    status, body = api_call("GET", "/api/documents", token=token, base=base)
    if status != 200:
        raise RuntimeError(f"could not list documents (HTTP {status})")
    return [d.get("name", "") for d in body.get("documents", [])]

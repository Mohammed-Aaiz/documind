"""Database-free tests for the Step 1.6G target-safety contract.

Covers two runners and the integration fixture:

* ``run_phase3d_evaluation.py`` and ``run_phase3e_integration.py``: the guard
  runs before the application database is configured, the effective settings
  are re-checked after the cache is cleared, the application engine
  (``storage.database``) and the runner's own engine are checked against the
  approved target, and all of that happens before any database-dependent
  import.  These are source-order tests: the runner modules are read as text,
  never imported, so ``main()`` is not executed.
* ``tests/fixtures/integration_db.py``: the target policy refuses unsafe or
  mismatched targets before any destructive setup.  Only string parsing is
  exercised.  The application DSN is monkeypatched, and no fixture provisioning
  or ``psql`` call is made.

Nothing here connects to a database, runs a migration, or runs cleanup.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation import isolation
from tests.fixtures import integration_db

BACKEND_DIR = Path(__file__).resolve().parents[3]
RUNNER_DIR = BACKEND_DIR / "evaluation" / "experiments"

APPLICATION = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind"
INTEGRATION = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_integration"


def _main_source(filename: str) -> str:
    """The text of ``main()`` in a runner file, read without importing it."""
    text = (RUNNER_DIR / filename).read_text(encoding="utf-8")
    start = text.index("\nasync def main(")
    end = text.find("\ndef ", start + 1)
    return text[start:] if end == -1 else text[start:end]


RUNNERS = ["run_phase3d_evaluation.py", "run_phase3e_integration.py"]


# ---------------------------------------------------------------------------
# Runner source order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", RUNNERS)
def test_guard_precedes_application_database_configuration(filename):
    source = _main_source(filename)
    guard = source.index("assert_safe_evaluation_target(")
    configure = source.index('os.environ["DATABASE_URL"] = evaluation_dsn')
    assert guard < configure


@pytest.mark.parametrize("filename", RUNNERS)
def test_settings_cache_is_cleared_and_effective_url_checked_before_imports(filename):
    source = _main_source(filename)
    configure = source.index('os.environ["DATABASE_URL"] = evaluation_dsn')
    cleared = source.index("get_settings.cache_clear()")
    check = source.index("if get_settings().database_url != evaluation_dsn")
    first_model = source.index("from auth.models import User")
    assert configure < cleared < check < first_model


@pytest.mark.parametrize("filename", RUNNERS)
def test_application_engine_is_checked_before_any_route_or_session(filename):
    source = _main_source(filename)
    storage = source.index("from storage.database import engine as application_engine")
    check = source.index("assert_engine_matches_target(application_engine, evaluation_dsn)")
    # Routes and sessions are only reachable after the engine check.
    later_use = [
        source.index(marker)
        for marker in ("import documents.routes", "from main import app", "async with session_factory()")
        if marker in source
    ]
    assert storage < check
    assert all(check < use for use in later_use)


@pytest.mark.parametrize("filename", RUNNERS)
def test_runner_engine_is_checked_against_target_after_creation(filename):
    source = _main_source(filename)
    create = source.index("engine = create_async_engine(evaluation_dsn)")
    check = source.index("assert_engine_matches_target(engine, evaluation_dsn)")
    session = source.index("async_sessionmaker(engine")
    assert create < check < session


@pytest.mark.parametrize("filename", RUNNERS)
def test_runner_imports_the_central_engine_check(filename):
    text = (RUNNER_DIR / filename).read_text(encoding="utf-8")
    assert "    assert_engine_matches_target,\n" in text
    assert "from evaluation.isolation import" in text


@pytest.mark.parametrize("filename", RUNNERS)
def test_runner_module_has_no_top_level_database_import(filename):
    """Database-dependent modules must not be imported at module import time."""
    text = (RUNNER_DIR / filename).read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(("from storage", "from auth", "from documents", "from chat", "from main")):
            pytest.fail(f"top-level database import in {filename}: {line!r}")


# ---------------------------------------------------------------------------
# Central guard behaviour used by the fixture
# ---------------------------------------------------------------------------


def _use_application(monkeypatch, dsn: str = APPLICATION) -> None:
    monkeypatch.setattr(integration_db, "application_database_url", lambda: dsn)


def test_default_target_is_isolated_database_on_application_server(monkeypatch):
    monkeypatch.delenv(integration_db.INTEGRATION_DATABASE_URL_ENV, raising=False)
    _use_application(monkeypatch)
    # Derived target keeps the application's credentials and host, and swaps only the database name.
    derived = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind_integration"
    assert integration_db.assert_isolated_target() == derived


def test_explicit_isolated_override_is_accepted(monkeypatch):
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, INTEGRATION)
    _use_application(monkeypatch)
    assert integration_db.assert_isolated_target() == INTEGRATION


def test_override_naming_application_database_is_refused(monkeypatch):
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, APPLICATION)
    _use_application(monkeypatch)
    with pytest.raises(isolation.UnsafeEvaluationTarget, match="shares the database name"):
        integration_db.assert_isolated_target()


def test_same_name_under_host_alias_is_refused(monkeypatch):
    """The old fixture compared host text, so ``127.0.0.1`` slipped past."""
    alias = "postgresql+asyncpg://documind:eval-secret@127.0.0.1:55433/documind"
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, alias)
    _use_application(monkeypatch)
    with pytest.raises(isolation.UnsafeEvaluationTarget, match="shares the database name"):
        integration_db.assert_isolated_target()


def test_same_name_with_case_difference_is_refused(monkeypatch):
    upper = "postgresql+asyncpg://documind:eval-secret@localhost:55433/DOCUMIND"
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, upper)
    _use_application(monkeypatch)
    with pytest.raises(isolation.UnsafeEvaluationTarget, match="shares the database name"):
        integration_db.assert_isolated_target()


def test_empty_override_is_refused_not_silently_derived(monkeypatch):
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, "")
    _use_application(monkeypatch)
    with pytest.raises(isolation.UnsafeEvaluationTarget, match="cannot establish"):
        integration_db.assert_isolated_target()


@pytest.mark.parametrize(
    "override",
    [
        "postgresql+asyncpg://documind:x@localhost:55433/documind_integration?host=/tmp/other",
        "postgresql+asyncpg://documind:x@localhost:55433/documind_integration?dbname=documind",
        "mysql://documind:x@localhost:3306/documind_integration",
        "postgresql+asyncpg://documind:x@localhost:notaport/documind_integration",
        "postgresql+asyncpg://documind:x@localhost:55433/",
        "postgresql+asyncpg://documind:x@:55433/documind_integration",
    ],
)
def test_unidentifiable_or_unsafe_override_is_refused(monkeypatch, override):
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, override)
    _use_application(monkeypatch)
    with pytest.raises(RuntimeError):
        integration_db.assert_isolated_target()


def test_target_on_a_different_server_is_refused(monkeypatch):
    other_host = "postgresql+asyncpg://documind:x@db.example.com:55433/documind_integration"
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, other_host)
    _use_application(monkeypatch)
    with pytest.raises(RuntimeError, match="different server"):
        integration_db.assert_isolated_target()


def test_target_on_a_different_port_is_refused(monkeypatch):
    other_port = "postgresql+asyncpg://documind:x@localhost:55434/documind_integration"
    monkeypatch.setenv(integration_db.INTEGRATION_DATABASE_URL_ENV, other_port)
    _use_application(monkeypatch)
    with pytest.raises(RuntimeError, match="different server"):
        integration_db.assert_isolated_target()


def test_unsafe_application_dsn_refuses_before_any_target_is_returned(monkeypatch):
    monkeypatch.delenv(integration_db.INTEGRATION_DATABASE_URL_ENV, raising=False)
    _use_application(monkeypatch, "")
    with pytest.raises(isolation.UnsafeEvaluationTarget):
        integration_db.assert_isolated_target()


def test_fixture_identity_matches_central_identity():
    for dsn in (APPLICATION, INTEGRATION, "postgresql://u:p@h:5432/d%20x"):
        assert integration_db.database_identity(dsn) == isolation.database_identity(dsn)


def test_fixture_validates_then_refuses_existing_name_before_creating():
    """Step 1.6J: the fixture never drops a pre-existing database.

    Order: URL validation, then the existence refusal, then creation.
    """
    text = Path(integration_db.__file__).read_text(encoding="utf-8")
    body = text[text.index("def provisioned_integration_database"):]
    guard = body.index("assert_isolated_target()")
    exists = body.index("database_exists(name)")
    create = body.index("_create_database(name)")
    assert guard < exists < create

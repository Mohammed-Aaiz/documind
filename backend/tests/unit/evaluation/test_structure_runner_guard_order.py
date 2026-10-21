"""Database-free tests for the guard-first binding of the three structure runners.

What these tests can and cannot show
------------------------------------
They prove *ordering and failure behaviour* in the runners' Python import and
binding code:

* importing a runner imports no database module and creates no engine;
* the central isolation guard runs before the first database-dependent import;
* the effective settings value is checked against the approved target before
  storage is imported, so a mismatch builds no engine;
* a stale cached settings value cannot substitute another target;
* a refused or mismatched target never replaces the database modules.

They do NOT show PostgreSQL safety.  No database is contacted: ``storage.database``
and ``chat`` are replaced by poison entries (importing them raises), and
``config`` is replaced by a stub.  The stub models the effective setting as the
environment value behind a cache that ``cache_clear`` empties; it never reads
``backend/.env``.  The runners are never executed; only their binding functions
are called, and those stop before any database work.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from evaluation import isolation

APP = "postgresql+asyncpg://documind:app-secret@localhost:5432/documind"
ISOLATED = "postgresql+asyncpg://documind:app-secret@localhost:5432/documind_integration"

ELEMENT = "evaluation.experiments.run_structure_element_measurement"
RRF = "evaluation.experiments.run_structure_rrf_calibration"
CONFIRMATION = "evaluation.experiments.run_structure_confirmation"
RUNNERS = (ELEMENT, RRF, CONFIRMATION)

#: The real disposal check, captured before any harness replaces it.
_REAL_DISPOSAL_CHECK = isolation.assert_disposal_authorized

EXPERIMENTS_DIR = Path(__file__).resolve().parents[3] / "evaluation" / "experiments"
SOURCE_FILES = {
    ELEMENT: EXPERIMENTS_DIR / "run_structure_element_measurement.py",
    RRF: EXPERIMENTS_DIR / "run_structure_rrf_calibration.py",
    CONFIRMATION: EXPERIMENTS_DIR / "run_structure_confirmation.py",
}

#: Top-level packages that initialise the database when imported.
DATABASE_PACKAGES = {
    "storage", "chat", "documents", "graph", "auth", "user", "reliability",
    "verification", "brain", "embeddings", "config",
}

#: Names bound only after the guard; none may be read at module scope.
BOUND_NAMES = {"async_session", "engine", "rag", "RRF_K"}


class FakeEngine:
    """Stands in for a SQLAlchemy engine: only ``url`` is inspected; nothing connects."""

    def __init__(self, dsn: str):
        self.url = make_url(dsn)


@pytest.fixture
def harness(monkeypatch):
    """Poison the database modules, stub config, and clear the runners' imports.

    The config stub models the effective setting as the value that
    ``DATABASE_URL`` holds in the environment, behind a cache.  A stale value in
    the cache is what ``cache_clear`` must remove.  ``backend/.env`` is never read.
    """
    config_calls: list[str] = []
    cache: dict[str, str] = {}

    def _get_settings():
        config_calls.append("get")
        if "database_url" not in cache:
            cache["database_url"] = os.environ.get("DATABASE_URL", "")
        return types.SimpleNamespace(database_url=cache["database_url"])

    def _cache_clear():
        config_calls.append("cache_clear")
        cache.clear()

    _get_settings.cache_clear = _cache_clear

    fake_config = types.ModuleType("config")
    fake_config.get_settings = _get_settings
    monkeypatch.setitem(sys.modules, "config", fake_config)
    # ``None`` in sys.modules makes any import of these names raise ImportError.
    monkeypatch.setitem(sys.modules, "storage.database", None)
    monkeypatch.setitem(sys.modules, "chat", None)

    for name in RUNNERS:
        monkeypatch.delitem(sys.modules, name, raising=False)

    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
    # These tests check guard ORDER and engine BINDING, not disposal.  The disposal
    # check is replaced with a recording stub that accepts the identity, so these
    # tests stay focused.  The real refusal is proven by
    # test_unauthorized_target_refuses_before_settings_or_storage below.
    def _accepting_disposal_check(dsn, *, operation, application_url=None, proof=None):
        return isolation.database_identity(dsn)

    monkeypatch.setattr(isolation, "assert_disposal_authorized", _accepting_disposal_check)
    return types.SimpleNamespace(
        monkeypatch=monkeypatch,
        config_calls=config_calls,
        cache=cache,
        fake_config=fake_config,
    )


def _fake_database_modules(monkeypatch, dsn: str) -> None:
    """Install stand-in storage and chat modules (no engine is created)."""
    storage = types.ModuleType("storage.database")
    storage.async_session = "SESSION-FACTORY"
    storage.engine = FakeEngine(dsn)
    chat = types.ModuleType("chat")
    chat.rag = types.SimpleNamespace(RRF_K=60)
    monkeypatch.setitem(sys.modules, "storage.database", storage)
    monkeypatch.setitem(sys.modules, "chat", chat)


def _install_storage_built_from_settings(monkeypatch) -> None:
    """Model storage.database: its engine is built from the effective settings.

    The engine is constructed on first attribute access, which is when a runner
    imports ``engine`` from the module, so the model reads the settings at the
    same point in the sequence the real module does.  Nothing connects.
    """
    storage = types.ModuleType("storage.database")

    def _module_getattr(attr):
        if attr == "engine":
            return FakeEngine(sys.modules["config"].get_settings().database_url)
        if attr == "async_session":
            return "SESSION-FACTORY"
        raise AttributeError(attr)

    storage.__getattr__ = _module_getattr
    chat = types.ModuleType("chat")
    chat.rag = types.SimpleNamespace(RRF_K=60)
    monkeypatch.setitem(sys.modules, "storage.database", storage)
    monkeypatch.setitem(sys.modules, "chat", chat)


def _load(name: str):
    """Import a runner fresh.  Returns the runner and the element runner it binds through."""
    runner = importlib.import_module(name)
    return runner, sys.modules[ELEMENT]


# ---------------------------------------------------------------------------
# 1. Importing a runner touches no database module and creates no engine.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", RUNNERS)
def test_importing_a_runner_creates_no_engine(harness, name):
    runner, _element = _load(name)
    assert runner.engine is None
    assert runner.async_session is None
    assert runner.rag is None


# ---------------------------------------------------------------------------
# 2. The guard runs before the first database-dependent import.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", RUNNERS)
def test_guard_runs_before_any_database_module_is_imported(harness, name):
    runner, element = _load(name)
    calls: list[str] = []

    def approving_guard(dsn, *, operation, application_url=None):
        calls.append("guard")
        # Replace the poison only now.  Had any storage or chat import run
        # before the guard, it would already have raised ImportError against
        # the None entries.
        _fake_database_modules(harness.monkeypatch, ISOLATED)
        return isolation.database_identity(dsn)

    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)
    harness.monkeypatch.setattr(element, "assert_safe_evaluation_target", approving_guard)
    harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)

    runner.bind_database_runtime()

    assert calls == ["guard"], "the guard must run exactly once, before binding"
    assert runner.engine is not None
    assert os.environ["DATABASE_URL"] == ISOLATED
    assert harness.config_calls[:1] == ["cache_clear"]


# ---------------------------------------------------------------------------
# 3. A rejected target prevents engine initialisation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", RUNNERS)
def test_rejected_target_never_replaces_the_database_modules(harness, name):
    runner, element = _load(name)
    calls: list[str] = []

    def refusing_guard(dsn, *, operation, application_url=None):
        calls.append("guard")
        raise isolation.UnsafeEvaluationTarget("refused by the test")

    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)
    harness.monkeypatch.setattr(element, "assert_safe_evaluation_target", refusing_guard)
    harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)

    with pytest.raises(isolation.UnsafeEvaluationTarget):
        runner.bind_database_runtime()

    assert calls == ["guard"]
    assert sys.modules["storage.database"] is None, "storage must not have been imported"
    assert sys.modules["chat"] is None, "chat must not have been imported"
    assert runner.engine is None
    assert os.environ["DATABASE_URL"] == "", "no target may be exported on refusal"


# ---------------------------------------------------------------------------
# 4 & 5. Missing, malformed and unsafe configuration fail closed (real guard).
# ---------------------------------------------------------------------------

_FAIL_CLOSED_CASES = [
    pytest.param(None, "shares the database name", id="unset-falls-back-to-application"),
    pytest.param("", "set but empty", id="empty-override"),
    pytest.param(
        "postgresql+asyncpg://documind:app-secret@localhost:abc/documind_integration",
        "malformed database URL",
        id="malformed-port",
    ),
    pytest.param(
        "postgresql+asyncpg://documind:app-secret@127.0.0.1:5432/documind",
        "shares the database name",
        id="host-alias-of-application",
    ),
    pytest.param(
        "mysql://documind:app-secret@localhost:3306/documind_integration",
        "scheme",
        id="unsupported-scheme",
    ),
]


@pytest.mark.parametrize("name", RUNNERS)
@pytest.mark.parametrize("override, expected", _FAIL_CLOSED_CASES)
def test_unsafe_or_malformed_configuration_fails_closed(harness, name, override, expected):
    runner, element = _load(name)
    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)
    if override is not None:
        harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, override)

    with pytest.raises(isolation.UnsafeEvaluationTarget, match=expected) as exc:
        runner.bind_database_runtime()

    assert sys.modules["storage.database"] is None
    assert runner.engine is None
    assert os.environ["DATABASE_URL"] == ""
    assert "app-secret" not in str(exc.value), "credentials must never reach an error"


# ---------------------------------------------------------------------------
# 6. An approved target binds, and the bound engine is verified against it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", RUNNERS)
def test_approved_target_binds_the_verified_engine(harness, name):
    runner, element = _load(name)
    _fake_database_modules(harness.monkeypatch, ISOLATED)
    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)
    harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)

    runner.bind_database_runtime()
    runner.bind_database_runtime()  # idempotent: a second call changes nothing

    assert runner.engine is sys.modules["storage.database"].engine
    assert runner.async_session == "SESSION-FACTORY"
    assert os.environ["DATABASE_URL"] == ISOLATED
    assert harness.config_calls == ["cache_clear", "get"]


@pytest.mark.parametrize("name", RUNNERS)
def test_approved_target_reaches_the_engine_configuration(harness, name):
    """The engine is built from the effective settings, which equal the approved target."""
    runner, element = _load(name)
    _install_storage_built_from_settings(harness.monkeypatch)
    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)
    harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)

    runner.bind_database_runtime()

    # The storage model builds its engine on first attribute access, i.e. at the
    # moment the runner imports it, after the guard and the settings check.
    assert runner.engine.url.database == "documind_integration"
    assert runner.engine.url.host == "localhost"
    assert element.APPROVED_EVALUATION_DSN == ISOLATED


def test_an_engine_built_for_another_target_is_refused(harness):
    element = importlib.import_module(ELEMENT)
    element.APPROVED_EVALUATION_DSN = ISOLATED
    with pytest.raises(RuntimeError, match="different target"):
        element.verify_bound_engine(FakeEngine(APP))


# ---------------------------------------------------------------------------
# 7. Cached settings cannot substitute an unintended target.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", RUNNERS)
def test_stale_cached_settings_are_cleared_and_do_not_substitute_the_target(harness, name):
    """A stale cache naming the application is dropped; the approved target is used."""
    runner, element = _load(name)
    harness.cache["database_url"] = APP  # simulate a value cached before the guard ran
    _fake_database_modules(harness.monkeypatch, ISOLATED)
    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)
    harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)

    runner.bind_database_runtime()

    assert harness.config_calls[0] == "cache_clear"
    assert element.APPROVED_EVALUATION_DSN == ISOLATED


@pytest.mark.parametrize("name", RUNNERS)
def test_settings_that_still_name_another_target_refuse_before_storage_import(harness, name):
    """If the effective setting cannot be made to match, no engine is ever built."""
    runner, element = _load(name)

    # A settings source that cache_clear cannot remove: it always names the application.
    def stuck_settings():
        return types.SimpleNamespace(database_url=APP)

    stuck_settings.cache_clear = lambda: harness.config_calls.append("cache_clear")
    harness.fake_config.get_settings = stuck_settings
    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)
    harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)

    with pytest.raises(RuntimeError, match="refusing before any engine is built") as exc:
        runner.bind_database_runtime()

    assert sys.modules["storage.database"] is None, "storage must not be imported on mismatch"
    assert sys.modules["chat"] is None
    assert runner.engine is None
    assert element.APPROVED_EVALUATION_DSN is None
    assert "app-secret" not in str(exc.value)


@pytest.mark.parametrize("name", RUNNERS)
def test_unauthorized_target_refuses_before_settings_or_storage(harness, name):
    """Validity is not permission: without disposal authorization, nothing else runs."""
    runner, element = _load(name)
    # Restore the real check: this test is about the refusal itself.
    harness.monkeypatch.setattr(element, "assert_disposal_authorized", _REAL_DISPOSAL_CHECK)
    harness.monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)
    harness.monkeypatch.setenv("DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE", "documind_integration")
    harness.monkeypatch.setattr(element, "application_database_url", lambda: APP)

    with pytest.raises(isolation.UnsafeEvaluationTarget, match="no enforceable disposal boundary"):
        element.guard_evaluation_target()

    assert harness.config_calls == [], "settings must not be read before authorization"
    assert sys.modules["storage.database"] is None
    assert element.APPROVED_EVALUATION_DSN is None


# ---------------------------------------------------------------------------
# 8. Static checks on the source (no import): no module-scope database import,
#    no module-scope read of a bound name, and main() binds before any work.
# ---------------------------------------------------------------------------


def _tree(name: str) -> ast.Module:
    return ast.parse(SOURCE_FILES[name].read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", RUNNERS)
def test_no_module_scope_import_reaches_the_database(name):
    for node in _tree(name).body:
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            assert module.split(".")[0] not in DATABASE_PACKAGES, (
                f"{name}: module-scope import of {module!r} can initialise the database"
            )


@pytest.mark.parametrize("name", RUNNERS)
def test_no_module_scope_code_reads_a_bound_name(name):
    for node in _tree(name).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Decorators and default values run at definition time, at import.
            evaluated = [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]
        elif isinstance(node, ast.ClassDef):
            evaluated = [*node.decorator_list, *node.bases, *[k.value for k in node.keywords]]
        else:
            evaluated = [node]
        for root in evaluated:
            if root is None:
                continue
            for sub in ast.walk(root):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    assert sub.id not in BOUND_NAMES, (
                        f"{name}: module-scope read of {sub.id!r} before the guard"
                    )


@pytest.mark.parametrize("name", RUNNERS)
def test_main_binds_the_database_before_any_work(name):
    main = next(
        node
        for node in _tree(name).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "main"
    )
    for statement in main.body:
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and getattr(statement.value.func, "id", None) == "bind_database_runtime"
        ):
            return
        assert isinstance(statement, ast.Assign), (
            f"{name}: main() does work before bind_database_runtime(): "
            f"line {statement.lineno}"
        )
    pytest.fail(f"{name}: main() never calls bind_database_runtime()")


# ---------------------------------------------------------------------------
# 9. Evaluation semantics are unchanged by the binding refactor.
# ---------------------------------------------------------------------------


def test_evaluation_constants_are_unchanged(harness):
    element, rrf, confirmation = (
        importlib.import_module(name) for name in (ELEMENT, RRF, CONFIRMATION)
    )
    assert element.TOP_K == 5 and element.RUNS == 2
    assert rrf.SWEEP[0] == ("sw070_st030", 0.70, 0.30)
    assert len(rrf.SWEEP) == 4
    assert confirmation.SEMANTIC_WEIGHT == 0.50 and confirmation.STRUCTURAL_WEIGHT == 0.50

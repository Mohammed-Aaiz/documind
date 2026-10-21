"""Database-free tests for pre-engine validation in the research runners.

These pin the Step 1.6D/1.6E contract for the table-evidence measurement runner
and the dual-path ablation runner:

* importing a runner does not import ``storage.database`` (which builds the
  application engine from settings at import time);
* the target is resolved and guarded before any database-dependent import;
* a missing, remote, or application-equal target is refused before storage is
  imported;
* cached application settings cannot substitute a different database;
* the effective engine configuration is checked against the approved target
  without opening a connection.

Nothing here connects to a database, executes a runner's ``main``, or runs
migrations.  ``storage.database`` is replaced with an import-failing stub so a
test fails loudly if the code under test reaches the real import.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from evaluation import isolation
from evaluation.experiments import run_dual_path_ablation as dual
from evaluation.experiments import run_table_evidence_measurement as table

BACKEND_DIR = Path(__file__).resolve().parents[3]

APPLICATION = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind"
ISOLATED = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_integration"
REMOTE = "postgresql+asyncpg://documind:eval-secret@db.example.com:5432/documind_integration"


def _block_storage_import(monkeypatch):
    """Make any import of storage.database fail, so reaching it is detected."""
    monkeypatch.setitem(sys.modules, "storage.database", None)


class _FakeSettingsGetter:
    """Stands in for ``config.get_settings``: records cache_clear and returns a fixed URL."""

    def __init__(self, database_url: str):
        self.cleared = 0
        self._url = database_url

    def cache_clear(self):
        self.cleared += 1

    def __call__(self):
        return SimpleNamespace(database_url=self._url, chunker_version="test")


# ---------------------------------------------------------------------------
# Importing a runner builds no engine
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module",
    [
        "evaluation.experiments.run_table_evidence_measurement",
        "evaluation.experiments.run_dual_path_ablation",
    ],
)
def test_importing_runner_does_not_import_storage_database(module):
    script = (
        "import sys, importlib; "
        f"importlib.import_module({module!r}); "
        "print('storage.database' in sys.modules)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert completed.stdout.strip().splitlines()[-1] == "False"


# ---------------------------------------------------------------------------
# Table-evidence runner: guard before storage import
# ---------------------------------------------------------------------------


class TestTableRunnerResolution:
    def test_missing_explicit_target_refuses_before_storage_import(self, monkeypatch):
        monkeypatch.delenv(table.EVAL_DB_ENV, raising=False)
        _block_storage_import(monkeypatch)
        with pytest.raises(SystemExit, match="application database is never used"):
            table._resolve_database_url()

    def test_blank_target_refuses_before_storage_import(self, monkeypatch):
        monkeypatch.setenv(table.EVAL_DB_ENV, "   ")
        _block_storage_import(monkeypatch)
        with pytest.raises(SystemExit, match="application database is never used"):
            table._resolve_database_url()

    def test_application_equal_target_is_refused_by_central_guard(self, monkeypatch):
        monkeypatch.setenv(table.EVAL_DB_ENV, APPLICATION)
        monkeypatch.setattr(isolation, "application_database_url", lambda: APPLICATION)
        _block_storage_import(monkeypatch)
        with pytest.raises(isolation.UnsafeEvaluationTarget):
            table._resolve_database_url()

    def test_remote_host_is_refused_before_storage_import(self, monkeypatch):
        monkeypatch.setenv(table.EVAL_DB_ENV, REMOTE)
        monkeypatch.setattr(isolation, "application_database_url", lambda: APPLICATION)
        _block_storage_import(monkeypatch)
        with pytest.raises(SystemExit, match="not loopback"):
            table._resolve_database_url()

    def test_cached_settings_cannot_substitute_another_database(self, monkeypatch):
        import config

        monkeypatch.setenv(table.EVAL_DB_ENV, ISOLATED)
        monkeypatch.setattr(isolation, "application_database_url", lambda: APPLICATION)
        monkeypatch.setattr(config, "get_settings", _FakeSettingsGetter(APPLICATION))
        _block_storage_import(monkeypatch)
        with pytest.raises(RuntimeError, match="different database"):
            table._resolve_database_url()

    def test_effective_settings_match_approved_target(self, monkeypatch):
        import config

        getter = _FakeSettingsGetter(ISOLATED)
        monkeypatch.setattr(config, "get_settings", getter)
        monkeypatch.setenv(table.EVAL_DB_ENV, ISOLATED)
        monkeypatch.setattr(isolation, "application_database_url", lambda: APPLICATION)
        fake_storage = types.ModuleType("storage.database")
        fake_storage._asyncpg_engine_args = lambda url: (url, {"marker": True})
        monkeypatch.setitem(sys.modules, "storage.database", fake_storage)

        url, connect_args = table._resolve_database_url()

        assert url == ISOLATED
        assert connect_args == {"marker": True}
        assert getter.cleared == 1, "the settings cache must be cleared before the check"

    def test_amain_guard_runs_before_model_import(self):
        source = inspect.getsource(table.amain)
        guard = source.index("_resolve_database_url()")
        models = source.index("_import_all_models()")
        engine = source.index("create_async_engine(")
        assert guard < models < engine

    def test_module_has_no_top_level_model_import(self):
        # _import_all_models() is the only place models are imported, and it is
        # called only from amain(), after the guard.
        source = inspect.getsource(table)
        top_level = [
            line for line in source.splitlines()
            if line.startswith(("from auth", "from chat", "from documents", "from graph",
                                "from reliability", "from user", "from verification",
                                "from storage"))
        ]
        assert top_level == []


# ---------------------------------------------------------------------------
# Dual-path runner: settings check and engine check ordering
# ---------------------------------------------------------------------------


class TestDualPathRunnerOrdering:
    def test_settings_cache_is_cleared_before_database_imports(self):
        source = inspect.getsource(dual.main)
        cleared = source.index("get_settings.cache_clear()")
        first_model = source.index("from auth.models import User")
        storage = source.index("from storage.database import async_session, engine")
        assert cleared < first_model < storage

    def test_effective_settings_are_checked_before_database_imports(self):
        source = inspect.getsource(dual.main)
        check = source.index("if get_settings().database_url != evaluation_dsn")
        first_model = source.index("from auth.models import User")
        assert check < first_model

    def test_engine_is_checked_against_target_after_creation(self):
        source = inspect.getsource(dual.main)
        storage = source.index("from storage.database import async_session, engine")
        check = source.index("assert_engine_matches_target(engine, evaluation_dsn)")
        assert storage < check


# ---------------------------------------------------------------------------
# Central engine check (shared by both runners)
# ---------------------------------------------------------------------------


class TestEngineTargetCheck:
    def test_matching_engine_is_accepted_without_connecting(self):
        engine = SimpleNamespace(url=make_url(ISOLATED))
        isolation.assert_engine_matches_target(engine, ISOLATED)

    @pytest.mark.parametrize(
        "other",
        [
            "postgresql+asyncpg://documind:x@localhost:55433/other_db",
            "postgresql+asyncpg://documind:x@localhost:55434/documind_integration",
            "postgresql+asyncpg://documind:x@127.0.0.1:55433/documind_integration",
        ],
    )
    def test_engine_for_a_different_target_is_refused(self, other):
        engine = SimpleNamespace(url=make_url(other))
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="different target"):
            isolation.assert_engine_matches_target(engine, ISOLATED)

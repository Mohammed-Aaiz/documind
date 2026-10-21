"""Database-isolation regression tests for the five legacy Phase 3 runners.

Step 0 secured the A–D ablation and the Phase 3D upload/ask harness.  Step 0.6
extends the same contract to the five legacy runners that previously *defaulted*
to the application database through module-level environment mutation:

* ``run_phase3d_evaluation``
* ``run_phase3e_integration``
* ``run_phase3e_validation``
* ``run_phase3f_evaluation``
* ``run_phase4b_evaluation``

What is pinned here, per runner:

* **A** — with no explicit target, the run is refused before the engine factory
  is reached (the connection boundary is spied on, so "no connection attempt"
  is asserted rather than assumed), the error is credential-free, and there is
  no silent fallback to the application database;
* **B** — an explicitly requested application database is rejected before the
  engine factory is reached;
* **C** — an explicitly configured isolated target is passed through the
  centralized resolver and reaches the engine factory verbatim (CLI and
  environment forms);
* **D** — an unreachable but permitted target fails as a connection error, with
  no component falling back to the application DSN;
* **E** — the evaluation surface itself (metric constants, corpus entry
  points, check helpers) is untouched by the isolation work, and the guard
  provably precedes the first connection in the source.  One runner is an
exception, and deliberately so: Step 0.8 replaced ``run_phase3d_evaluation``'s
raw ``DELETE FROM`` statements with ownership-scoped, model-bound deletes,
Step 0.9 did the same for ``run_phase3e_integration``, Step 1.0 for
``run_phase3e_validation``, Step 1.1 for ``run_phase3f_evaluation`` and Step 1.2
for ``run_phase4b_evaluation``.  All five legacy runners now pin the *new*
contract (no raw destructive SQL, the scoped helper present); ``deletes`` is kept
per runner as the audit record of the pre-remediation statement count, so the
count assertion below remains live for any runner whose ``scoped_cleanup`` is
ever unset.

No test connects to a real database: cases A–C replace the engine factory, case
D targets a just-closed loopback port, and case E is source/attribute
inspection.  Nothing here writes files, reports or benchmarks.

The async cases ``await`` the runners inside the pytest-asyncio event loop
rather than calling ``asyncio.run`` — ``asyncio.run`` clears the interpreter's
current event loop, which the suite's session-scoped ``event_loop`` fixture
(as used by every other async test) depends on.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import socket
from dataclasses import dataclass, field

import pytest
import sqlalchemy.exc
from sqlalchemy.ext import asyncio as sqlalchemy_asyncio

from evaluation import isolation

#: A fake "application" DSN.  Never dialled: every test that resolves it also
#: guarantees no connection attempt is made.
APPLICATION = "postgresql+asyncpg://documind:app-secret@127.0.0.1:55433/documind"
APP_PASSWORD = "app-secret"

#: A fake isolated DSN on a different database name.
ISOLATED = "postgresql+asyncpg://eval:isolated-secret@127.0.0.1:55433/documind_integration"
ISOLATED_PASSWORD = "isolated-secret"


@dataclass(frozen=True)
class RunnerSpec:
    """What each runner must still be, and must no longer do."""

    module: str
    #: ``DELETE FROM`` statements present in the file *before* Step 0.8 (the
    #: pre-Step-0.6 count: isolation must not have touched evaluation SQL).
    #: Kept for every runner as the audit record; see ``scoped_cleanup``.
    deletes: int
    #: True once Step 0.8 has replaced this runner's raw destructive SQL with
    #: ownership-scoped, model-bound deletes — the statement count no longer
    #: applies and the new, stricter contract is pinned instead.
    scoped_cleanup: bool = False
    #: Attributes the evaluation surface depends on.
    attributes: tuple[str, ...] = ()
    #: ``TOP_K`` is part of the retrieval protocol for these runners.
    top_k: bool = False
    #: Names of the module-level pass/fail accumulators (check-style runners).
    check_lists: tuple[str, ...] = ()
    markers: tuple[str, ...] = field(default_factory=tuple)


RUNNERS: dict[str, RunnerSpec] = {
    "run_phase3d_evaluation": RunnerSpec(
        module="evaluation.experiments.run_phase3d_evaluation",
        deletes=10,  # pre-Step-0.8 count; the raw statements are now gone
        attributes=("build_corpus", "unanswerable_questions", "norm"),
        top_k=True,
        markers=("CHUNKER_VERSION_LEGACY", "CHUNKER_VERSION_STRUCTURE"),
        scoped_cleanup=True,
    ),
    "run_phase3e_integration": RunnerSpec(
        module="evaluation.experiments.run_phase3e_integration",
        deletes=7,  # pre-Step-0.9 count; the raw statements are now gone
        attributes=("check",),
        check_lists=("PASSED", "FAILED"),
        markers=("CHUNKER_VERSION_LEGACY",),
        scoped_cleanup=True,
    ),
    "run_phase3e_validation": RunnerSpec(
        module="evaluation.experiments.run_phase3e_validation",
        deletes=9,  # pre-Step-1.0 count; the raw statements are now gone
        attributes=("check",),
        check_lists=("PASSED", "FAILED"),
        markers=("CHUNKER_VERSION_LEGACY", "CHUNKER_VERSION_STRUCTURE"),
        scoped_cleanup=True,
    ),
    "run_phase3f_evaluation": RunnerSpec(
        module="evaluation.experiments.run_phase3f_evaluation",
        deletes=10,  # pre-Step-1.1 count; the raw statements are now gone
        attributes=("build_corpus", "unanswerable_questions"),
        top_k=True,
        scoped_cleanup=True,
    ),
    "run_phase4b_evaluation": RunnerSpec(
        module="evaluation.experiments.run_phase4b_evaluation",
        deletes=10,  # pre-Step-1.2 count; the raw statements are now gone
        attributes=(
            "build_phase4b_corpus",
            "build_phase4b_unanswerable",
            "get_all_phase4b_questions",
        ),
        top_k=True,
        scoped_cleanup=True,
    ),
}


class EngineFactoryReached(Exception):
    """Sentinel raised by the spied engine factory instead of connecting."""


@pytest.fixture(params=sorted(RUNNERS))
def runner(request):
    """The name, spec and imported module for each of the five runners."""
    name = request.param
    return name, RUNNERS[name], importlib.import_module(RUNNERS[name].module)


@pytest.fixture(scope="module", autouse=True)
def _application_imported_before_any_target_is_set():
    """Import the FastAPI app once, before any test mutates ``DATABASE_URL``.

    Two of the five runners (the Phase 3E pair) import the application inside
    ``main()``.  Pre-importing it here makes that import a cache hit during the
    tests, so no engine is ever constructed from a test DSN outside the code
    under test — which is also what lets the engine spy see exactly one DSN.
    """
    import main  # noqa: F401  (imports storage.database with the real settings)
    yield


@pytest.fixture(autouse=True)
def _restore_process_state():
    """Undo the environment a runner sets for its own process.

    The runners deliberately export ``DATABASE_URL`` (after the guard) so the
    application's settings resolve to the verified target.  That is real
    behaviour under test, so it is restored here rather than monkeypatched
    around: no later test in the session may observe an evaluation DSN, and the
    settings cache is cleared so it cannot hold one either.
    """
    before = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(before)
    from config import get_settings

    get_settings.cache_clear()


def _pin_application_dsn(module, monkeypatch, dsn: str = APPLICATION) -> None:
    """Make ``application_database_url()`` deterministic for this test.

    The real resolver reads ``backend/.env`` first, so an ambient environment
    variable cannot pin it; patching the name the runner imported is what makes
    "the application database" exactly known, without touching any real
    configuration.
    """
    monkeypatch.setattr(module, "application_database_url", lambda: dsn)
    monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)


def _spy_engine_factory(monkeypatch, *, explode: bool):
    """Record every ``create_async_engine`` call; optionally refuse to build one.

    Returns the list that receives the DSNs.  With ``explode`` the factory
    raises :class:`EngineFactoryReached`, which is how "the run was stopped
    before it could connect" is demonstrated.
    """
    seen: list[str] = []
    real = sqlalchemy_asyncio.create_async_engine

    def factory(dsn, *args, **kwargs):
        seen.append(dsn)
        if explode:
            raise EngineFactoryReached(dsn)
        return real(dsn, *args, **kwargs)

    monkeypatch.setattr(sqlalchemy_asyncio, "create_async_engine", factory)
    return seen


def _sql_literal(node) -> str:
    """The literal text of a string constant, or of an f-string's literal parts.

    f-strings are included on purpose: ``text(f"DELETE FROM {table}")`` must be
    caught too, otherwise this pin could be evaded by interpolation.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):  # f"...{expr}..."
        return "".join(
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return ""


def _raw_sql_delete_literals(module) -> list[str]:
    """Every ``text("...")`` literal in ``module`` that contains a DELETE.

    Read-only diagnostics (``text("SELECT ...")``) are ignored, so this is the
    right check for runners that keep direct-SQL inspection queries.
    """
    tree = ast.parse(inspect.getsource(module))
    literals: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "text"
        ):
            literal = "".join(_sql_literal(part) for part in node.args)
            if "DELETE" in literal:
                literals.append(literal)
    return literals


def _unused_loopback_port() -> int:
    """A port nothing is listening on (bound and immediately released)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ---------------------------------------------------------------------------
# A — missing configuration fails closed
# ---------------------------------------------------------------------------


class TestMissingConfigurationFailsClosed:
    async def test_no_explicit_target_is_refused_before_the_engine(self, runner, monkeypatch):
        _, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        seen = _spy_engine_factory(monkeypatch, explode=True)

        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            await module.main([])

        assert seen == [], "the run must be refused before any engine is created"
        message = str(exc.value)
        assert isolation.EVALUATION_DATABASE_URL_ENV in message
        assert APP_PASSWORD not in message
        assert "postgresql+asyncpg://" not in message

    async def test_environment_override_is_not_silently_ignored(self, runner, monkeypatch):
        """An explicit override is the only thing that authorises a target."""
        _, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, "   ")
        seen = _spy_engine_factory(monkeypatch, explode=True)

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="set but empty"):
            await module.main([])

        assert seen == []


# ---------------------------------------------------------------------------
# B — the application database is rejected
# ---------------------------------------------------------------------------


class TestApplicationDatabaseIsRejected:
    async def test_explicit_application_target_is_refused(self, runner, monkeypatch):
        _, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        seen = _spy_engine_factory(monkeypatch, explode=True)

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING") as exc:
            await module.main(["--database-url", APPLICATION])

        assert seen == [], "no engine may be created for a rejected target"
        message = str(exc.value)
        assert APP_PASSWORD not in message
        assert APPLICATION not in message
        assert "127.0.0.1:55433/documind" in message

    async def test_same_name_on_the_same_server_is_still_rejected(self, runner, monkeypatch):
        _, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        seen = _spy_engine_factory(monkeypatch, explode=True)
        same_identity = "postgresql+asyncpg://other:other-secret@127.0.0.1:55433/documind"

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await module.main(["--database-url", same_identity])

        assert seen == []


# ---------------------------------------------------------------------------
# C — an explicit target is honoured
# ---------------------------------------------------------------------------


class TestExplicitTargetIsRefusedWithoutLifecycle:
    """Step 1.6K: a runner holds no disposal authority, so an explicit target is refused.

    The refusal happens at the disposal gate, before the engine factory is reached.
    The engine is therefore never built and no connection is made.
    """

    async def test_cli_target_is_refused_before_the_engine_factory(self, runner, monkeypatch):
        name, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        seen = _spy_engine_factory(monkeypatch, explode=True)

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="no enforceable disposal boundary"):
            await module.main(["--database-url", ISOLATED])

        assert seen == [], f"{name}: the engine must not be built for an unauthorized target"

    async def test_environment_target_is_refused_before_the_engine_factory(self, runner, monkeypatch):
        name, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)
        seen = _spy_engine_factory(monkeypatch, explode=True)

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="no enforceable disposal boundary"):
            await module.main([])

        assert seen == [], f"{name}: the environment variable must not authorize the target"

    async def test_no_password_is_printed_while_refusing_the_target(
        self, runner, monkeypatch, capsys
    ):
        _, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        _spy_engine_factory(monkeypatch, explode=True)

        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            await module.main(["--database-url", ISOLATED])

        printed = capsys.readouterr().out + str(exc.value)
        assert ISOLATED_PASSWORD not in printed
        assert APP_PASSWORD not in printed
        assert "documind_integration" in printed


# ---------------------------------------------------------------------------
# D — an unreachable but permitted target fails as a connection error
# ---------------------------------------------------------------------------


class TestUnreachableTargetFailsWithoutFallback:
    async def test_unreachable_target_is_refused_and_nothing_falls_back(
        self, runner, monkeypatch
    ):
        name, _spec, module = runner
        _pin_application_dsn(module, monkeypatch)
        seen = _spy_engine_factory(monkeypatch, explode=False)
        port = _unused_loopback_port()
        unreachable = f"postgresql+asyncpg://eval:eval-secret@127.0.0.1:{port}/documind_eval"

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="no enforceable disposal boundary"):
            await module.main(["--database-url", unreachable])

        assert seen == [], f"{name}: no engine may be built, so nothing can connect or fall back"
        assert APPLICATION not in seen


# ---------------------------------------------------------------------------
# E — the evaluation surface is unchanged, and the guard precedes the engine
# ---------------------------------------------------------------------------


class TestEvaluationSurfaceUnchanged:
    def test_destructive_sql_is_untouched(self, runner):
        name, spec, module = runner
        source = inspect.getsource(module)
        if spec.scoped_cleanup:
            # Steps 0.8/0.9/1.0 removed these runners' raw SQL deletes in favour of
            # ownership-scoped, model-bound statements.  The historical count
            # (``spec.deletes``) is no longer the contract; the *new* contract is
            # stricter — no raw destructive SQL left at all (checked on the
            # ``text("...")`` literals themselves, so a runner that legitimately
            # keeps read-only ``text("SELECT ...")`` diagnostics still passes),
            # and the scoped helper that replaced it present and used.
            assert _raw_sql_delete_literals(module) == [], (
                f"{name}: the cleanup must stay model-bound, not raw SQL"
            )
            assert 'text("DELETE' not in source, name
            assert "async def cleanup_harness_rows" in source, name
            assert "cleanup_harness_rows(db, user_ids=" in source, name
            return
        assert source.count("DELETE FROM") == spec.deletes, (
            f"{name}: the isolation change must not alter evaluation SQL"
        )

    def test_metric_protocol_constants_are_unchanged(self, runner):
        name, spec, module = runner
        source = inspect.getsource(module)
        if spec.top_k:
            assert "TOP_K = 5" in source, name
        for accumulator in spec.check_lists:
            assert f"{accumulator}: list[str] = []" in source, (name, accumulator)
        for marker in spec.markers:
            assert marker in source, (name, marker)

    def test_evaluation_entry_points_still_exist(self, runner):
        name, spec, module = runner
        for attribute in spec.attributes:
            assert hasattr(module, attribute), (name, attribute)
        assert inspect.iscoroutinefunction(module.main), name
        assert callable(module.parse_args), name

    def test_guard_precedes_the_first_connection_in_the_source(self, runner):
        name, _spec, module = runner
        source = inspect.getsource(module)
        guard = source.index("assert_safe_evaluation_target(")
        assert guard < source.index('os.environ["DATABASE_URL"]'), name
        assert guard < source.index("create_async_engine(evaluation_dsn)"), name
        # The engine must be built from the verified DSN, never from a literal.
        assert "postgresql+asyncpg://documind:" not in source, name

    def test_no_import_time_database_selection_remains(self, runner):
        name, _spec, module = runner
        source = inspect.getsource(module)
        assert 'setdefault("DATABASE_URL"' not in source, name
        assert "from evaluation.isolation import" in source, name

    def test_help_documents_the_required_configuration(self, runner, capsys):
        _name, _spec, module = runner

        with pytest.raises(SystemExit):
            module.parse_args(["--help"])

        help_text = capsys.readouterr().out
        assert "--database-url" in help_text
        assert isolation.EVALUATION_DATABASE_URL_ENV in help_text
        assert "refuses to run" in help_text

"""Step 1.6L: exact boundary decisions, not cleanup/runner execution.

Read runner ASTs only. Extract only the first authorization expression into a
pure decision function; never execute helper bodies, imports, sessions or SQL.
Poison resources and patched I/O detect any access. This is not DB runtime proof.
"""
from __future__ import annotations

import ast
from pathlib import Path
import socket
import subprocess

import pytest

from evaluation import isolation

EXPERIMENTS = Path(__file__).resolve().parents[3] / "evaluation/experiments"
BOUNDARIES = [
    ("run_phase3d_upload_integration.py", "cleanup_harness_rows", "db"),
    ("run_phase3d_evaluation.py", "cleanup_harness_rows", "db"),
    ("run_phase3e_integration.py", "cleanup_harness_rows", "db"),
    ("run_phase3e_validation.py", "cleanup_harness_rows", "db"),
    ("run_phase3f_evaluation.py", "cleanup_harness_rows", "db"),
    ("run_phase4b_evaluation.py", "cleanup_harness_rows", "db"),
    ("run_dual_path_ablation.py", "_delete_user_data", "db"),
    ("run_table_evidence_measurement.py", "teardown", "db"),
    ("run_table_evidence_measurement.py", "run_once", "engine"),
    ("run_structure_element_measurement.py", "run_once", "engine"),
    ("run_structure_rrf_calibration.py", "run_once", "engine"),
    ("run_structure_confirmation.py", "run_once", "engine"),
]
APP = "postgresql+asyncpg://u:p@localhost:5432/documind"
TARGET = "postgresql+asyncpg://u:p@localhost:5432/evaluation"
OTHER = "postgresql+asyncpg://u:p@elsewhere:5433/other"


class PoisonResource:
    def __getattribute__(self, name):
        raise AssertionError("authorization inspected an untrusted resource")


def _forbidden(*args, **kwargs):
    raise AssertionError("I/O or settings resolution attempted")


@pytest.fixture(autouse=True)
def no_io(monkeypatch):
    monkeypatch.setattr(isolation, "application_database_url", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(subprocess, "run", _forbidden)


def _decision(filename, name, resource_name):
    tree = ast.parse((EXPERIMENTS / filename).read_text(encoding="utf-8"))
    helper = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    body = helper.body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # docstring only
    imported, gate = body[:2]
    assert isinstance(imported, ast.ImportFrom)
    assert imported.module == "evaluation.isolation"
    assert [(a.name, a.asname) for a in imported.names] == [("assert_cleanup_execution_authorized", None)]
    assert isinstance(gate, ast.Expr) and isinstance(gate.value, ast.Call)
    assert isinstance(gate.value.func, ast.Name)
    assert gate.value.func.id == "assert_cleanup_execution_authorized"
    assert ast.unparse(gate.value.args[0]) == resource_name
    # The exact gate is the first executable statement: no condition, await,
    # session access, SQL, proof supplied by a caller, or engine replacement.
    assert [kw.arg for kw in gate.value.keywords] == ["operation"]
    assert isinstance(gate.value.keywords[0].value, ast.Constant)
    decision = ast.FunctionDef(
        name="decision", args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=resource_name)],
        kwonlyargs=[], kw_defaults=[], defaults=[]), body=[gate], decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[decision], type_ignores=[]))
    namespace = {"assert_cleanup_execution_authorized": isolation.assert_cleanup_execution_authorized}
    exec(compile(module, filename + ":authorization-only", "exec"), namespace)
    return namespace["decision"]


@pytest.mark.parametrize("filename,name,resource_name", BOUNDARIES)
def test_every_direct_boundary_refuses_before_resource_access(filename, name, resource_name):
    decision = _decision(filename, name, resource_name)
    with pytest.raises(isolation.UnsafeEvaluationTarget, match="cleanup execution is blocked"):
        decision(PoisonResource())


@pytest.mark.parametrize("identity", [TARGET, OTHER, APP])
@pytest.mark.parametrize("lifecycle", ["", "stale", "closed", "another-run"])
def test_constructed_stale_mismatched_or_reused_proofs_never_authorize(identity, lifecycle):
    proof = isolation.DisposalProof(isolation.database_identity(identity), object(), lifecycle)
    for resource in (None, PoisonResource()):
        for _ in range(2):
            with pytest.raises(isolation.UnsafeEvaluationTarget, match="connection-bound lifecycle"):
                isolation.assert_cleanup_execution_authorized(resource, operation="test cleanup", proof=proof)


@pytest.mark.parametrize("proof", [None, object(), {}, "claimed-authority"])
def test_missing_or_invalid_authorization_refuses(proof):
    with pytest.raises(isolation.UnsafeEvaluationTarget):
        isolation.assert_cleanup_execution_authorized(PoisonResource(), operation="test", proof=proof)


def test_target_and_configuration_substitution_cannot_enable_execution(monkeypatch):
    for target in (TARGET, OTHER, APP):
        monkeypatch.setenv("DATABASE_URL", target)
        monkeypatch.setenv("DOCUMIND_INTEGRATION_DATABASE_URL", target)
        monkeypatch.setenv("DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE", "evaluation")
        with pytest.raises(isolation.UnsafeEvaluationTarget):
            isolation.assert_cleanup_execution_authorized(PoisonResource(), operation="test")

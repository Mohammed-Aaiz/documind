"""Database-free tests for the central disposal contract (Step 1.6J).

Five questions, each answered by a different check, none implying another:

1. URL validity            ``assert_safe_evaluation_target``
2. application isolation   ``assert_safe_evaluation_target`` (database name)
3. target identity         ``database_identity`` / ``assert_engine_matches_target``
4. explicit intent         recorded in the report; not accepted as authority
5. destructive permission  ``assert_disposal_authorized`` with a ``DisposalProof``
                           that this run issued by creating the database

Only (5) authorizes destruction, and only with a proof.  Nothing in the repository
establishes that an *existing* database is disposable, so every destructive runner
refuses by default.

Safety of these tests
---------------------
Every function exercised is pure string inspection.  The application DSN is always
passed explicitly, so no ``.env`` file is read.  The fixture's destructive
primitives and provisioning are never called.  The runners are checked by reading
their source text only.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from evaluation import isolation
from tests.fixtures import integration_db as idb

BACKEND_DIR = Path(__file__).resolve().parents[3]
EXPERIMENTS = BACKEND_DIR / "evaluation" / "experiments"

APPLICATION = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind"
ISOLATED = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_integration"
OTHER = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_other"

RETIRED_AUTH_ENV = "DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE"
URL = isolation.EVALUATION_DATABASE_URL_ENV


def _forbidden(*args, **kwargs):
    raise AssertionError("database, subprocess or destructive call attempted by a database-free test")


@pytest.fixture(autouse=True)
def _no_io(monkeypatch):
    monkeypatch.delenv(RETIRED_AUTH_ENV, raising=False)
    monkeypatch.delenv(URL, raising=False)
    monkeypatch.setattr(idb, "psql_value", _forbidden)
    monkeypatch.setattr(idb, "postgres_available", _forbidden)
    monkeypatch.setattr(idb, "_create_database", _forbidden)
    monkeypatch.setattr(idb, "_drop_database", _forbidden)
    monkeypatch.setattr(subprocess, "run", _forbidden)


def _refusal(dsn: str, *, proof=None, application=APPLICATION):
    try:
        isolation.assert_disposal_authorized(
            dsn, operation="contract test", application_url=application, proof=proof
        )
    except isolation.UnsafeEvaluationTarget as exc:
        return str(exc)
    return None


# ---------------------------------------------------------------------------
# Configuration alone never authorizes destruction
# ---------------------------------------------------------------------------


def test_a_safe_target_with_no_proof_is_refused():
    assert "no enforceable disposal boundary" in _refusal(ISOLATED)


def test_the_retired_variable_naming_the_target_has_no_effect(monkeypatch):
    monkeypatch.setenv(RETIRED_AUTH_ENV, "documind_integration")
    assert "no enforceable disposal boundary" in _refusal(ISOLATED)


@pytest.mark.parametrize("name", ["documind_integration", "integration", "test", "documind_other"])
def test_a_database_name_alone_never_authorizes(name):
    dsn = ISOLATED.replace("documind_integration", name)
    assert "no enforceable disposal boundary" in _refusal(dsn)


def test_a_different_target_is_not_authorization():
    assert "no enforceable disposal boundary" in _refusal(OTHER)


def test_the_application_target_is_never_destroyed_even_with_a_proof():
    proof = isolation.DisposalProof(isolation.database_identity(APPLICATION))
    assert "application database's name" in _refusal(APPLICATION, proof=proof)


def test_a_target_with_no_database_name_is_refused():
    assert "no database name" in _refusal("postgresql+asyncpg://documind:x@localhost:55433/")


def test_a_failed_url_check_is_not_rescued_by_anything(monkeypatch):
    monkeypatch.setenv(RETIRED_AUTH_ENV, "documind_integration")
    with pytest.raises(isolation.UnsafeEvaluationTarget):
        isolation.assert_safe_evaluation_target(
            "mysql://documind:x@localhost:3306/documind_integration",
            operation="contract test",
            application_url=APPLICATION,
        )


# ---------------------------------------------------------------------------
# Python proof objects cannot establish external authorization, even on a match
# ---------------------------------------------------------------------------


def test_a_proof_for_the_same_identity_still_cannot_authorize():
    proof = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    assert "no enforceable disposal boundary" in _refusal(ISOLATED, proof=proof)


def test_a_proof_does_not_follow_a_changed_target():
    proof = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    assert "no enforceable disposal boundary" in _refusal(OTHER, proof=proof)


def test_a_forged_proof_is_refused():
    forged = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    assert "no enforceable disposal boundary" in _refusal(ISOLATED, proof=forged)


def test_changing_the_environment_after_issue_does_not_alter_the_decision(monkeypatch):
    proof = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    monkeypatch.setenv(URL, OTHER)
    monkeypatch.setenv(RETIRED_AUTH_ENV, "documind_other")
    # The check reads the DSN it is given, not the environment.
    assert "no enforceable disposal boundary" in _refusal(ISOLATED, proof=proof)
    assert "no enforceable disposal boundary" in _refusal(OTHER, proof=proof)


# ---------------------------------------------------------------------------
# Fixture and central contract agree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("env_value", [None, "", "documind_integration", "DOCUMIND_INTEGRATION"])
def test_fixture_and_central_both_refuse_a_safe_target_without_a_proof(monkeypatch, env_value):
    if env_value is not None:
        monkeypatch.setenv(RETIRED_AUTH_ENV, env_value)
    monkeypatch.setattr(idb, "application_database_url", lambda: APPLICATION)
    with pytest.raises(isolation.UnsafeEvaluationTarget):
        isolation.assert_disposal_authorized(
            ISOLATED, operation="contract test", application_url=APPLICATION
        )
    with pytest.raises(isolation.UnsafeEvaluationTarget):
        idb.assert_disposal_authorized(ISOLATED)


# ---------------------------------------------------------------------------
# Gate coverage and guard order, source-level
# ---------------------------------------------------------------------------

#: Runners that call ``assert_disposal_authorized`` (or ``_authorize_disposal``)
#: directly, after their validity guard.
GATED_DIRECTLY = {
    "run_phase3d_evaluation.py",
    "run_phase3d_upload_integration.py",
    "run_phase3e_integration.py",
    "run_phase3e_validation.py",
    "run_phase3f_evaluation.py",
    "run_phase4b_evaluation.py",
    "run_dual_path_ablation.py",
    "run_table_evidence_measurement.py",
    "run_structure_element_measurement.py",
}

#: Runners that reach the database only through ``guard_evaluation_target`` in
#: ``run_structure_element_measurement.py``, which runs the disposal check.
GATED_VIA_SHARED_GUARD = {"run_structure_rrf_calibration.py", "run_structure_confirmation.py"}

_DESTRUCTIVE_SOURCE = re.compile(r"\bdelete\(|DELETE FROM|DROP DATABASE|CREATE DATABASE|\brmtree\(|\bunlink\(")


def _text(name: str) -> str:
    return (EXPERIMENTS / name).read_text(encoding="utf-8")


def test_every_destructive_experiment_runner_is_accounted_for():
    destructive = sorted(
        path.name
        for path in EXPERIMENTS.glob("run_*.py")
        if _DESTRUCTIVE_SOURCE.search(path.read_text(encoding="utf-8"))
    )
    unaccounted = [n for n in destructive if n not in GATED_DIRECTLY | GATED_VIA_SHARED_GUARD]
    assert unaccounted == [], f"destructive runner without a gate: {unaccounted}"


@pytest.mark.parametrize("name", sorted(GATED_DIRECTLY))
def test_directly_gated_runner_authorizes_after_its_validity_guard(name):
    text = _text(name)
    guard = re.search(r"assert_safe_evaluation_target\(|_resolve_database_url\(\)", text)
    authorize = re.search(r"assert_disposal_authorized\(|_authorize_disposal\(", text)
    assert guard is not None, f"{name} has no validity guard"
    assert authorize is not None, f"{name} has no disposal authorization call"
    assert guard.start() < authorize.start(), f"{name}: authorization must follow the guard"


@pytest.mark.parametrize("name", sorted(GATED_DIRECTLY | GATED_VIA_SHARED_GUARD))
def test_no_runner_can_pass_a_proof_it_did_not_create(name):
    """A runner never constructs or passes a proof, so its gate always refuses."""
    text = _text(name)
    assert "proof=" not in text, f"{name} passes a disposal proof"
    assert "record_created_database" not in text, f"{name} issues a disposal proof"
    assert "DisposalProof(" not in text, f"{name} constructs a disposal proof"


@pytest.mark.parametrize("name", sorted(GATED_DIRECTLY))
def test_directly_gated_runner_does_not_read_the_retired_variable(name):
    assert RETIRED_AUTH_ENV not in _text(name)
    assert "authorized_disposal_name" not in _text(name)


def test_shared_guard_authorizes_after_validity_and_before_the_database_is_bound():
    element = _text("run_structure_element_measurement.py")
    body = element[element.index("def guard_evaluation_target("):]
    end = body.find("\ndef ", 1)
    body = body if end == -1 else body[:end]
    assert "assert_disposal_authorized(" in body
    assert body.index("assert_safe_evaluation_target(") < body.index("assert_disposal_authorized(")
    assert body.index("assert_disposal_authorized(") < body.index('os.environ["DATABASE_URL"]')
    for name in GATED_VIA_SHARED_GUARD:
        assert "run_structure_element_measurement" in _text(name)

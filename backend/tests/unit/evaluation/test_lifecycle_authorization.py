"""Step 1.6K: pure authorization guards and source-only operation ordering.

No provisioning, create/drop, cleanup, runner main or E2E function is invoked.
All proof objects are constructed data, not valid authorization. Creation,
evidence issuance, row cleanup and deletion remain blocked until an enforceable
external lifecycle authority exists. Source checks are not runtime DB evidence.
Application resolvers, subprocesses and sockets are patched; no .env is read.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import socket
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from evaluation import isolation
from tests.fixtures import integration_db as idb

APPLICATION = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind"
ISOLATED = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_integration"
OTHER = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_other"

_DESTRUCTIVE_PRIMITIVES = (
    "postgres_available",
    "database_exists",
    "_create_database",
    "_drop_database",
    "provisioned_integration_database",
    "alembic_head",
    "migrate_to_head",
)


def _forbidden(*args, **kwargs):
    raise AssertionError("database, subprocess or destructive call attempted by a database-free test")


@pytest.fixture(autouse=True)
def _no_io(monkeypatch):
    monkeypatch.delenv(idb.INTEGRATION_DATABASE_URL_ENV, raising=False)
    monkeypatch.setattr(idb, "application_database_url", lambda: APPLICATION)
    for name in _DESTRUCTIVE_PRIMITIVES:
        monkeypatch.setattr(idb, name, _forbidden)
    monkeypatch.setattr(idb, "psql_value", _forbidden)
    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(isolation, "application_database_url", lambda **kw: APPLICATION)


def _raises(match, callable_, *args, **kwargs):
    with pytest.raises(isolation.UnsafeEvaluationTarget, match=match):
        callable_(*args, **kwargs)


# ---------------------------------------------------------------------------
# Creation authorization: no proof, but an existing name and the app are refused
# ---------------------------------------------------------------------------


def test_creation_refuses_without_external_authority_even_for_a_free_name():
    _raises(
        "missing enforceable create authorization", isolation.assert_creation_authorized,
        ISOLATED, operation="test create", application_url=APPLICATION, database_exists=False,
    )


def test_creation_refuses_an_existing_name():
    _raises(
        "already exists",
        isolation.assert_creation_authorized,
        ISOLATED,
        operation="test create",
        application_url=APPLICATION,
        database_exists=True,
    )


def test_creation_refuses_the_application_database_even_when_the_name_is_free():
    _raises(
        "shares the database name",
        isolation.assert_creation_authorized,
        APPLICATION,
        operation="test create",
        application_url=APPLICATION,
        database_exists=False,
    )


def test_creation_authorization_does_not_authorize_destruction():
    _raises(
        "no enforceable disposal boundary",
        isolation.assert_disposal_authorized,
        ISOLATED,
        operation="test drop",
        application_url=APPLICATION,
        proof=None,
    )


def _source_body(path, name):
    text = path.read_text(encoding="utf-8")
    node = next(n for n in ast.walk(ast.parse(text))
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    return ast.get_source_segment(text, node)


def test_provisioning_creation_gate_precedes_database_and_socket_io():
    body = _source_body(Path(idb.__file__), "provisioned_integration_database")
    assert body.index("assert_isolated_target()") < body.index("_central_assert_creation_authorized(")
    assert body.index("_central_assert_creation_authorized(") < body.index("postgres_available()")
    assert body.index("_central_assert_creation_authorized(") < body.index("database_exists(name)")


def test_create_primitive_requires_authority_before_sql():
    body = _source_body(Path(idb.__file__), "_create_database")
    assert body.index("_central_assert_creation_authorized(") < body.index("psql_value(")


def test_isolated_fixture_requires_authority_before_reachability_probe():
    body = _source_body(Path(idb.__file__), "isolated_database")
    assert body.index("_central_assert_creation_authorized(") < body.index("require_postgres()")


# ---------------------------------------------------------------------------
# Proof lifecycle: open, reuse, duplicate, release
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dsn", [ISOLATED, OTHER, APPLICATION, "", "mysql://u:p@h/db"])
def test_caller_cannot_issue_successful_creation_evidence(dsn):
    _raises("no authorized creation lifecycle", isolation.record_created_database, dsn)


def _constructed_proof(dsn=ISOLATED, lifecycle="caller-lifecycle"):
    return isolation.DisposalProof(isolation.database_identity(dsn), object(), lifecycle)


@pytest.mark.parametrize("lifecycle", ["", "old-run", "new-run", "copied-run"])
def test_proofs_cannot_be_reused_across_targets_or_lifecycles(lifecycle):
    proof = _constructed_proof(lifecycle=lifecycle)
    assert isolation._proof_is_live(proof) is False
    for dsn in (ISOLATED, OTHER):
        _raises(
            "no enforceable disposal boundary", isolation.assert_disposal_authorized,
            dsn, operation="drop", application_url=APPLICATION, proof=proof,
        )
    _raises("not live", isolation.release_database_proof, proof, operation="release")


def test_a_forged_proof_is_not_live_and_cannot_authorize():
    forged = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    assert not isolation._proof_is_live(forged)
    _raises(
        "no enforceable disposal boundary",
        isolation.assert_disposal_authorized,
        ISOLATED,
        operation="test drop",
        application_url=APPLICATION,
        proof=forged,
    )


def test_copying_a_constructed_issuer_does_not_supply_authority():
    real = _constructed_proof()
    tampered = isolation.DisposalProof(real.identity, real._issuer, "")
    assert not isolation._proof_is_live(tampered)


def test_a_proof_object_that_is_not_a_disposal_proof_is_refused():
    assert not isolation._proof_is_live({"identity": isolation.database_identity(ISOLATED)})


# ---------------------------------------------------------------------------
# Row cleanup: needs the open lifecycle's proof for the exact target; keeps it open
# ---------------------------------------------------------------------------


def test_row_cleanup_is_refused_without_a_proof():
    _raises(
        "no enforceable disposal boundary",
        isolation.assert_row_cleanup_authorized,
        ISOLATED,
        operation="test cleanup",
        application_url=APPLICATION,
        proof=None,
    )


def test_row_cleanup_is_refused_for_a_proof_covering_another_database():
    proof = _constructed_proof(OTHER)
    _raises(
        "no enforceable disposal boundary",
        isolation.assert_row_cleanup_authorized,
        ISOLATED,
        operation="test cleanup",
        application_url=APPLICATION,
        proof=proof,
    )


def test_repeated_row_cleanup_requests_with_constructed_proof_remain_blocked():
    proof = _constructed_proof()
    for _ in range(2):
        _raises(
            "no enforceable disposal boundary", isolation.assert_row_cleanup_authorized,
            ISOLATED, operation="test cleanup", application_url=APPLICATION, proof=proof,
        )
    assert isolation._proof_is_live(proof) is False


def test_row_cleanup_remains_refused_after_invalid_release():
    proof = _constructed_proof()
    _raises("not live", isolation.release_database_proof, proof, operation="test drop")
    _raises(
        "no enforceable disposal boundary",
        isolation.assert_row_cleanup_authorized,
        ISOLATED,
        operation="test cleanup",
        application_url=APPLICATION,
        proof=proof,
    )


def test_row_cleanup_is_refused_for_the_application_database_even_with_a_proof():
    proof = _constructed_proof(APPLICATION)
    _raises(
        "never destroyed",
        isolation.assert_row_cleanup_authorized,
        APPLICATION,
        operation="test cleanup",
        application_url=APPLICATION,
        proof=proof,
    )


# ---------------------------------------------------------------------------
# Engine binding: the engine must target the database the proof covers
# ---------------------------------------------------------------------------


def test_matching_engine_and_proof_still_cannot_authorize_cleanup():
    proof = _constructed_proof()
    engine = SimpleNamespace(url=make_url(ISOLATED))
    _raises(
        "no enforceable disposal boundary", isolation.assert_engine_bound_to_proof,
        engine, ISOLATED, operation="test cleanup", application_url=APPLICATION, proof=proof,
    )


def test_engine_for_a_different_database_is_refused_with_constructed_proof():
    proof = _constructed_proof()
    engine = SimpleNamespace(url=make_url(OTHER))
    with pytest.raises(isolation.UnsafeEvaluationTarget, match="different target"):
        isolation.assert_engine_bound_to_proof(
            engine, ISOLATED, operation="test cleanup", application_url=APPLICATION, proof=proof
        )


def test_an_engine_is_refused_without_a_proof():
    engine = SimpleNamespace(url=make_url(ISOLATED))
    _raises(
        "no enforceable disposal boundary",
        isolation.assert_engine_bound_to_proof,
        engine,
        ISOLATED,
        operation="test cleanup",
        application_url=APPLICATION,
        proof=None,
    )


# ---------------------------------------------------------------------------
# Fixture-level drop and row cleanup
# ---------------------------------------------------------------------------


def test_drop_gate_precedes_sql_from_source_only():
    body = _source_body(Path(idb.__file__), "_drop_database")
    assert body.index("assert_disposal_authorized(dsn, proof=proof)") < body.index("psql_value(")


@pytest.mark.parametrize("proof", [None, _constructed_proof(), _constructed_proof(OTHER)])
def test_drop_authorization_refuses_every_constructed_claim(proof):
    _raises(
        "no enforceable disposal boundary", idb.assert_disposal_authorized,
        ISOLATED, proof=proof,
    )


def test_fixture_row_cleanup_follows_the_same_proof_rules():
    proof = _constructed_proof()
    with pytest.raises(isolation.UnsafeEvaluationTarget):
        idb.assert_row_cleanup_authorized(ISOLATED, proof=proof)
    with pytest.raises(isolation.UnsafeEvaluationTarget):
        idb.assert_row_cleanup_authorized(ISOLATED, proof=None)


# ---------------------------------------------------------------------------
# run_full_validation refuses before any engine is created
# ---------------------------------------------------------------------------


def test_run_full_validation_guard_precedes_imports_engine_and_sessions():
    path = Path(idb.__file__).parents[1] / "integration/rag/test_real_e2e_validation.py"
    body = _source_body(path, "run_full_validation")
    assert body.index("assert_row_cleanup_authorized(") < body.index("from sqlalchemy")
    assert body.index("assert_engine_bound_to_proof(") < body.index("async with session_factory()")
    assert body.index("async with session_factory()") < body.index("DELETE FROM")


def test_configuration_changes_never_enable_a_lifecycle(monkeypatch):
    monkeypatch.setenv(idb.INTEGRATION_DATABASE_URL_ENV, OTHER)
    monkeypatch.setenv("DATABASE_URL", OTHER)
    monkeypatch.setenv("DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE", "documind_other")
    for dsn in (ISOLATED, OTHER):
        _raises(
            "no enforceable disposal boundary", isolation.assert_row_cleanup_authorized,
            dsn, operation="cleanup", application_url=APPLICATION, proof=_constructed_proof(),
        )

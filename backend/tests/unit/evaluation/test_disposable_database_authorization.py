"""Database-free tests for the integration fixture's fail-closed destructive path.

Step 1.6J replaced the operator-named environment variable with a proof model.
Destruction requires a ``DisposalProof`` issued because this run created the
database.  These tests prove that:

* configuration alone is never authorization (URL, name, environment variable,
  or a target that differs from the application);
* invalid, missing, empty, malformed or unsupported URLs refuse safely;
* the application database is always refused;
* provisioning never drops a database it did not create;
* the ``__main__`` destructive path refuses.

Safety of these tests
---------------------
Every function here is pure string inspection.  Every I/O entry point and every
destructive primitive the fixture owns is replaced with a function that fails the
test on use.  The provisioning context manager is never called; its order is
checked from its source.  No database is contacted, nothing is migrated, and no
cleanup runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from evaluation import isolation
from tests.fixtures import integration_db as idb

TESTS_DIR = Path(__file__).resolve().parents[2]

APPLICATION = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind"
ISOLATED = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_integration"
OTHER = "postgresql+asyncpg://documind:eval-secret@localhost:55433/documind_other"

URL_ENV = idb.INTEGRATION_DATABASE_URL_ENV
#: The variable Step 1.6H used.  It must have no effect now.
RETIRED_AUTH_ENV = "DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE"

_DESTRUCTIVE_PRIMITIVES = (
    "psql_value",
    "postgres_available",
    "database_exists",
    "_create_database",
    "_drop_database",
    "alembic_head",
    "migrate_to_head",
)


def _forbidden(*args, **kwargs):
    raise AssertionError("database, subprocess or destructive call attempted by a database-free test")


@pytest.fixture(autouse=True)
def _no_io(monkeypatch):
    monkeypatch.delenv(URL_ENV, raising=False)
    monkeypatch.delenv(RETIRED_AUTH_ENV, raising=False)
    monkeypatch.setattr(idb, "application_database_url", lambda: APPLICATION)
    for name in _DESTRUCTIVE_PRIMITIVES:
        monkeypatch.setattr(idb, name, _forbidden)
    monkeypatch.setattr(subprocess, "run", _forbidden)


def _refusal(callable_, *args, **kwargs):
    with pytest.raises((isolation.UnsafeEvaluationTarget, RuntimeError)) as info:
        callable_(*args, **kwargs)
    return str(info.value)


# ---------------------------------------------------------------------------
# The retired name-based authorization has no effect
# ---------------------------------------------------------------------------


def test_retired_variable_naming_the_target_does_not_authorize(monkeypatch):
    monkeypatch.setenv(URL_ENV, ISOLATED)
    monkeypatch.setenv(RETIRED_AUTH_ENV, "documind_integration")
    message = _refusal(idb.assert_authorized_destructive_target)
    assert "no enforceable disposal boundary" in message


def test_name_based_authorization_is_gone_from_both_layers():
    assert not hasattr(idb, "DISPOSAL_AUTHORIZATION_ENV")
    assert not hasattr(isolation, "DISPOSAL_AUTHORIZATION_ENV")
    assert not hasattr(isolation, "authorized_disposal_name")


# ---------------------------------------------------------------------------
# URL validity is necessary and insufficient
# ---------------------------------------------------------------------------


def test_valid_url_alone_is_not_authorization(monkeypatch):
    monkeypatch.setenv(URL_ENV, ISOLATED)
    assert "no enforceable disposal boundary" in _refusal(idb.assert_authorized_destructive_target)


def test_different_target_is_not_authorization_without_a_proof(monkeypatch):
    monkeypatch.setenv(URL_ENV, OTHER)
    assert "no enforceable disposal boundary" in _refusal(idb.assert_authorized_destructive_target)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "\t\n",
        "postgresql+asyncpg://documind:x@localhost:notaport/documind_integration",
        "mysql://documind:x@localhost:3306/documind_integration",
        "sqlite:///documind_integration.db",
        "not a url at all",
        "postgresql+asyncpg://documind:x@localhost:55433/",
        "postgresql+asyncpg://documind:x@localhost:55433/documind_integration?host=/tmp/other",
    ],
)
def test_missing_empty_malformed_or_unsupported_url_fails_safely(monkeypatch, value):
    monkeypatch.setenv(URL_ENV, value)
    _refusal(idb.assert_authorized_destructive_target)


def test_missing_url_derives_a_target_that_still_is_not_authorized():
    message = _refusal(idb.assert_authorized_destructive_target)
    assert "no enforceable disposal boundary" in message


# ---------------------------------------------------------------------------
# The application database is never destroyed, even with a proof
# ---------------------------------------------------------------------------


def test_application_target_is_refused_even_with_a_proof_for_it():
    proof = isolation.DisposalProof(isolation.database_identity(APPLICATION))
    message = _refusal(idb.assert_disposal_authorized, APPLICATION, proof=proof)
    assert "application database's name" in message


def test_application_name_under_host_alias_is_refused_even_with_a_proof():
    alias = "postgresql+asyncpg://documind:x@127.0.0.1:55433/documind"
    proof = isolation.DisposalProof(isolation.database_identity(alias))
    message = _refusal(idb.assert_disposal_authorized, alias, proof=proof)
    assert "application database's name" in message


# ---------------------------------------------------------------------------
# Ordinary proof objects cannot supply the missing external lifecycle authority
# ---------------------------------------------------------------------------


def test_a_constructed_proof_cannot_authorize_its_own_target():
    proof = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    assert "no enforceable disposal boundary" in _refusal(
        idb.assert_disposal_authorized, ISOLATED, proof=proof
    )


def test_a_proof_does_not_cover_a_changed_target():
    proof = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    message = _refusal(idb.assert_disposal_authorized, OTHER, proof=proof)
    assert "no enforceable disposal boundary" in message


def test_a_forged_proof_without_the_issuer_is_refused():
    forged = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    message = _refusal(idb.assert_disposal_authorized, ISOLATED, proof=forged)
    assert "no enforceable disposal boundary" in message


def test_proof_none_is_refused(monkeypatch):
    monkeypatch.setenv(RETIRED_AUTH_ENV, "documind_integration")
    message = _refusal(idb.assert_disposal_authorized, ISOLATED, proof=None)
    assert "no enforceable disposal boundary" in message


# ---------------------------------------------------------------------------
# Configuration changes between validation and execution
# ---------------------------------------------------------------------------


def test_changing_the_environment_after_a_proof_cannot_redirect_the_destruction(monkeypatch):
    proof = isolation.DisposalProof(isolation.database_identity(ISOLATED))
    monkeypatch.setenv(URL_ENV, OTHER)
    # The destructive gate takes the DSN it is given, never the environment, so the
    # changed variable is ignored and the proof is checked against the DSN passed in.
    assert "no enforceable disposal boundary" in _refusal(
        idb.assert_disposal_authorized, ISOLATED, proof=proof
    )
    assert "no enforceable disposal boundary" in _refusal(idb.assert_disposal_authorized, OTHER, proof=proof)


# ---------------------------------------------------------------------------
# Destructive primitives and provisioning: source-level order
# ---------------------------------------------------------------------------


def _function_text(source: str, name: str) -> str:
    start = source.index(f"def {name}(")
    end = source.find("\ndef ", start + 1)
    return source[start:] if end == -1 else source[start:end]


def test_drop_gate_precedes_every_destructive_statement():
    source = (TESTS_DIR / "fixtures" / "integration_db.py").read_text(encoding="utf-8")
    body = _function_text(source, "_drop_database")
    gate = body.index("assert_disposal_authorized(dsn, proof=proof)")
    drop = body.index("DROP DATABASE")
    assert gate < drop


def test_create_primitive_never_drops_and_refuses_the_application_name():
    source = (TESTS_DIR / "fixtures" / "integration_db.py").read_text(encoding="utf-8")
    body = _function_text(source, "_create_database")
    assert "DROP" not in body
    assert "application database's name" in body


def test_provisioning_refuses_an_existing_name_before_creating_and_drops_only_with_proof():
    source = (TESTS_DIR / "fixtures" / "integration_db.py").read_text(encoding="utf-8")
    body = _function_text(source, "provisioned_integration_database")
    validate = body.index("assert_isolated_target()")
    exists = body.index("database_exists(name)")
    create = body.index("_create_database(name)")
    issue = body.index("record_created_database(dsn)")
    try_block = body.index("try:")
    finally_block = body.index("finally:")
    create_gate = body.index("_central_assert_creation_authorized(")
    first_io = body.index("postgres_available()")
    assert validate < create_gate < first_io < exists < create < issue < try_block
    # The only drop in provisioning is in ``finally``, with the proof it issued.
    assert "_drop_database(name)" not in body
    assert body.index("_drop_database(dsn, proof)") > finally_block


def test_provisioning_never_calls_the_destructive_gate_without_a_proof_in_scope():
    source = (TESTS_DIR / "fixtures" / "integration_db.py").read_text(encoding="utf-8")
    body = _function_text(source, "provisioned_integration_database")
    assert "assert_authorized_destructive_target()" not in body


# ---------------------------------------------------------------------------
# The __main__ destructive path refuses
# ---------------------------------------------------------------------------


def test_main_path_refuses_without_a_proof(monkeypatch):
    monkeypatch.setenv(URL_ENV, ISOLATED)
    message = _refusal(idb.assert_authorized_destructive_target)
    assert "no enforceable disposal boundary" in message


def test_main_path_uses_the_gate_not_the_bare_url_check():
    text = (TESTS_DIR / "integration" / "rag" / "test_real_e2e_validation.py").read_text(
        encoding="utf-8"
    )
    assert "target = assert_authorized_destructive_target()" in text
    assert "run_full_validation(target, None)" in text
    assert "run_full_validation(assert_isolated_target()" not in text

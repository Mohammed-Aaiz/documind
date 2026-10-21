"""Regression tests for the evaluation-database safety guard.

Every destructive research runner (the A–D ablation, the Phase 3D upload/ask
harness) resolves its target and proves it is not the application database
*before* its first connection.  These tests pin that contract:

* an explicit isolated target is honoured, from ``--database-url`` or from the
  environment, with ``--database-url`` winning;
* an explicitly requested target is never silently replaced by the application
  database — including the empty-string case;
* the application database is rejected before any destructive operation;
* an unresolvable identity (target *or* application) fails closed;
* the guard establishes no connection at all, and no error, description or
  manifest line ever contains a credential;
* the rules stay in step with ``tests/fixtures/integration_db.py``.

Nothing here touches a database: the guard is pure string inspection, which is
what makes it safe to test.
"""

from __future__ import annotations

import inspect
import os

import pytest

from evaluation import isolation
from tests.fixtures import integration_db

APPLICATION = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind"
ISOLATED = "postgresql+asyncpg://documind:app-secret@localhost:55433/documind_integration"


# ---------------------------------------------------------------------------
# Resolving the target
# ---------------------------------------------------------------------------


class TestTargetResolution:
    def test_cli_override_is_honoured(self):
        resolved = isolation.evaluation_database_url(
            override=ISOLATED, application_url=APPLICATION
        )
        assert resolved == ISOLATED

    def test_environment_override_is_honoured(self, monkeypatch):
        monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, ISOLATED)
        assert (
            isolation.evaluation_database_url(application_url=APPLICATION) == ISOLATED
        )

    def test_cli_override_beats_the_environment(self, monkeypatch):
        monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, "postgresql+asyncpg://h:1/envdb")
        resolved = isolation.evaluation_database_url(
            override=ISOLATED, application_url=APPLICATION
        )
        assert resolved == ISOLATED

    def test_no_override_keeps_the_application_dsn(self, monkeypatch):
        # The pre-existing behaviour: nothing is redirected behind the caller's
        # back.  The guard, not this function, is what refuses an unsafe target.
        monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
        assert isolation.evaluation_database_url(application_url=APPLICATION) == APPLICATION

    def test_empty_cli_override_refuses_rather_than_falling_back(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="set but empty"):
            isolation.evaluation_database_url(override="   ", application_url=APPLICATION)

    def test_empty_environment_override_refuses_rather_than_falling_back(self, monkeypatch):
        monkeypatch.setenv(isolation.EVALUATION_DATABASE_URL_ENV, "")
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="set but empty"):
            isolation.evaluation_database_url(application_url=APPLICATION)


class TestApplicationResolution:
    def test_env_file_outranks_the_ambient_environment(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            f"DATABASE_URL={APPLICATION}\n# comment\nOTHER=1\n", encoding="utf-8"
        )
        # A runner that exports DATABASE_URL for its own children must not be
        # able to redefine which database counts as the application's.
        monkeypatch.setenv("DATABASE_URL", ISOLATED)
        assert isolation.application_database_url(env_file=env_file) == APPLICATION

    def test_quoted_values_are_unwrapped(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(f'DATABASE_URL="{APPLICATION}"\n', encoding="utf-8")
        assert isolation.application_database_url(env_file=env_file) == APPLICATION

    def test_missing_env_file_still_resolves_a_dsn(self, tmp_path):
        # Falls back to the application's own settings resolver rather than
        # raising; the guard is what then decides whether it is safe.
        resolved = isolation.application_database_url(env_file=tmp_path / "absent.env")
        assert isolation.database_identity(resolved)[2]


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


class TestGuardRefusesTheApplicationDatabase:
    def test_same_identity_is_rejected(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            isolation.assert_safe_evaluation_target(
                APPLICATION,
                operation="the test operation",
                application_url=APPLICATION,
            )
        message = str(exc.value)
        assert "REFUSING the test operation" in message
        assert isolation.EVALUATION_DATABASE_URL_ENV in message

    def test_same_name_on_another_host_is_refused(self):
        # Same *name* on a host that cannot be shown to be a different server is
        # refused: the guard no longer treats a different hostname as proof.
        other_server = "postgresql+asyncpg://documind:app-secret@db.internal:5432/documind"
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="shares the database name"):
            isolation.assert_safe_evaluation_target(
                other_server, operation="op", application_url=APPLICATION
            )

    def test_isolated_database_on_the_same_server_is_accepted(self):
        identity = isolation.assert_safe_evaluation_target(
            ISOLATED, operation="op", application_url=APPLICATION
        )
        assert identity == ("localhost", 55433, "documind_integration")

    def test_port_difference_alone_is_refused(self):
        # A different port does not prove a different server (a tunnel can map
        # one server to two ports), so a shared name is refused.
        other_port = "postgresql+asyncpg://documind:app-secret@localhost:55434/documind"
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="shares the database name"):
            isolation.assert_safe_evaluation_target(
                other_port, operation="op", application_url=APPLICATION
            )

    def test_returns_the_verified_identity(self):
        identity = isolation.assert_safe_evaluation_target(
            ISOLATED, operation="op", application_url=APPLICATION
        )
        assert identity == isolation.database_identity(ISOLATED)


class TestGuardFailsClosed:
    def test_target_without_a_host_is_rejected(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="cannot establish"):
            isolation.assert_safe_evaluation_target(
                "sqlite+aiosqlite:///:memory:", operation="op", application_url=APPLICATION
            )

    def test_target_without_a_database_name_is_rejected(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="cannot establish"):
            isolation.assert_safe_evaluation_target(
                "postgresql+asyncpg://localhost:5432/",
                operation="op",
                application_url=APPLICATION,
            )

    def test_unresolvable_application_identity_fails_closed(self):
        with pytest.raises(
            isolation.UnsafeEvaluationTarget, match="application database's identity"
        ):
            isolation.assert_safe_evaluation_target(
                ISOLATED, operation="op", application_url="sqlite+aiosqlite:///:memory:"
            )

    def test_empty_target_is_rejected(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="cannot establish"):
            isolation.assert_safe_evaluation_target(
                "", operation="op", application_url=APPLICATION
            )


class TestNoCredentialsLeak:
    def test_display_dsn_drops_userinfo(self):
        display = isolation.display_dsn(ISOLATED)
        assert display == "postgresql+asyncpg://localhost:55433/documind_integration"
        assert "app-secret" not in display
        assert "documind:" not in display

    def test_identity_and_description_are_credential_free(self):
        identity = isolation.database_identity(ISOLATED)
        assert "app-secret" not in isolation.describe_identity(identity)
        assert identity == ("localhost", 55433, "documind_integration")

    def test_refusal_message_never_includes_the_password(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            isolation.assert_safe_evaluation_target(
                APPLICATION, operation="op", application_url=APPLICATION
            )
        assert "app-secret" not in str(exc.value)

    def test_describe_targets_never_includes_the_password(self):
        text = isolation.describe_targets(dsn=ISOLATED, application_url=APPLICATION)
        assert "app-secret" not in text
        assert "localhost:55433/documind_integration" in text
        assert "localhost:55433/documind\n" in text


class TestGuardIsPureInspection:
    def test_the_module_opens_no_connection(self):
        # The guard must be safe to run against a database that is down, a
        # database that does not exist, and the application database itself.
        source = inspect.getsource(isolation)
        for forbidden in (
            "create_async_engine",
            "create_engine",
            "asyncpg",
            "psycopg",
            "import subprocess",
            "connect(",
        ):
            assert forbidden not in source, forbidden


# ---------------------------------------------------------------------------
# Consistency with the test layer's equivalent guard
# ---------------------------------------------------------------------------


class TestMirrorsTheTestLayerGuard:
    def test_same_environment_variable(self):
        assert (
            isolation.EVALUATION_DATABASE_URL_ENV
            == integration_db.INTEGRATION_DATABASE_URL_ENV
        )

    def test_same_identity_definition(self):
        assert isolation.database_identity(ISOLATED) == integration_db.database_identity(
            ISOLATED
        )

    def test_application_dsn_resolution_matches(self, monkeypatch):
        # No ambient DATABASE_URL override, no test-only override: both modules
        # must name the same database, or "the application database" means two
        # different things depending on which guard runs.
        if not isolation.ENV_FILE.is_file():
            pytest.skip("this checkout has no backend/.env to compare against")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
        assert isolation.database_identity(
            isolation.application_database_url()
        ) == integration_db.database_identity(integration_db.application_database_url())

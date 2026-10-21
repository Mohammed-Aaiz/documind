"""Database-free tests for how the evaluation guard decides two databases differ.

The guard in ``evaluation/isolation.py`` is pure string inspection.  These tests
never create an engine, never connect, never read ``backend/.env``, and never
import the test-layer fixtures (which carry their own side effects).  Every
application URL is passed explicitly, so the guard is never asked to resolve the
application's settings.
"""

from __future__ import annotations

import pytest

from evaluation import isolation

APP = "postgresql+asyncpg://documind:app-secret@localhost:5432/documind"
ISOLATED = "postgresql+asyncpg://documind:app-secret@localhost:5432/documind_integration"


def _guard(dsn: str, app: str = APP):
    return isolation.assert_safe_evaluation_target(dsn, operation="op", application_url=app)


# 1 & 2 — the demonstrated aliases and IPv4/IPv6 loopback representations ----


class TestHostAliasesOfTheApplicationDatabaseAreRefused:
    @pytest.mark.parametrize(
        "target",
        [
            "postgresql+asyncpg://documind:app-secret@127.0.0.1:5432/documind",  # demonstrated
            "postgresql+asyncpg://documind:app-secret@localhost/documind",  # demonstrated
            "postgresql+asyncpg://documind:app-secret@LOCALHOST:5432/documind",
            "postgresql+asyncpg://documind:app-secret@[::1]:5432/documind",
            "postgresql+asyncpg://documind:app-secret@[::1]/documind",
            "postgresql+asyncpg://documind:app-secret@127.0.0.2:5432/documind",
        ],
    )
    def test_alias_of_application_database_is_refused(self, target):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="shares the database name"):
            _guard(target)

    def test_ipv6_loopback_is_refused_against_an_ipv6_application(self):
        app = "postgresql+asyncpg://documind:app-secret@[::1]:5432/documind"
        with pytest.raises(isolation.UnsafeEvaluationTarget):
            _guard("postgresql+asyncpg://documind:app-secret@127.0.0.1:5432/documind", app)


# 3 — explicit versus default PostgreSQL port -------------------------------


class TestDefaultAndExplicitPortAreTheSameDatabase:
    def test_default_port_against_explicit_5432_is_refused(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget):
            _guard("postgresql+asyncpg://documind:app-secret@localhost/documind")

    def test_explicit_5432_against_default_port_application_is_refused(self):
        app = "postgresql+asyncpg://documind:app-secret@localhost/documind"
        with pytest.raises(isolation.UnsafeEvaluationTarget):
            _guard(APP, app)


# 4 — equivalent database names after normalised parsing -------------------


class TestDatabaseNamesAreComparedNormalised:
    @pytest.mark.parametrize(
        "name",
        ["DocuMind", "DOCUMIND", "docu%6Dind"],  # case and percent-encoding
    )
    def test_equivalent_name_is_refused(self, name):
        target = f"postgresql+asyncpg://documind:app-secret@localhost:5432/{name}"
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="shares the database name"):
            _guard(target)

    def test_driver_scheme_difference_does_not_change_the_answer(self):
        target = "postgresql://documind:app-secret@localhost:5432/documind"
        with pytest.raises(isolation.UnsafeEvaluationTarget):
            _guard(target)


# 5 & 6 — missing application and evaluation URLs --------------------------


class TestMissingUrlsFailClosed:
    def test_empty_application_url_is_not_replaced_by_settings(self, monkeypatch):
        def must_not_be_called():
            raise AssertionError("the application settings must not be consulted")

        monkeypatch.setattr(isolation, "application_database_url", must_not_be_called)
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="application database's identity"):
            _guard(ISOLATED, app="")

    def test_missing_evaluation_url_with_no_override_is_the_application_and_is_refused(
        self, monkeypatch
    ):
        monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
        resolved = isolation.evaluation_database_url(application_url=APP)
        assert resolved == APP
        with pytest.raises(isolation.UnsafeEvaluationTarget):
            _guard(resolved)

    def test_empty_evaluation_target_is_refused(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="cannot establish"):
            _guard("")


# 7 — malformed and unsupported URLs ---------------------------------------


class TestMalformedAndUnsupportedUrlsFailClosed:
    @pytest.mark.parametrize(
        "target",
        [
            "mysql://documind:app-secret@db.internal:3306/documind_integration",
            "mongodb://documind:app-secret@db.internal/documind_integration",
        ],
    )
    def test_unsupported_scheme_is_refused(self, target):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="unsupported|scheme"):
            _guard(target)

    def test_sqlite_has_no_host_and_is_refused(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="cannot establish"):
            _guard("sqlite+aiosqlite:///tmp.db")

    @pytest.mark.parametrize(
        "target",
        [
            "postgresql+asyncpg://documind:app-secret@localhost:abc/documind_integration",
            "postgresql+asyncpg://documind:app-secret@localhost:99999/documind_integration",
        ],
    )
    def test_malformed_port_is_refused_without_echoing_the_url(self, target):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="malformed database URL") as exc:
            _guard(target)
        assert "app-secret" not in str(exc.value)


# 8 — different database names on a shared host ---------------------------


class TestDifferentNamesOnASharedHostAreAccepted:
    def test_isolated_database_on_the_application_server_is_accepted(self):
        assert _guard(ISOLATED) == ("localhost", 5432, "documind_integration")

    def test_different_name_on_a_loopback_alias_is_accepted(self):
        target = "postgresql+asyncpg://documind:app-secret@127.0.0.1:5432/documind_integration"
        assert _guard(target) == ("127.0.0.1", 5432, "documind_integration")


# 9 — different hostnames whose equivalence is unknown ---------------------


class TestUnknownHostEquivalenceIsNotProofOfSeparation:
    def test_same_name_on_an_unknown_host_is_refused(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="cannot be shown to be separate"):
            _guard("postgresql+asyncpg://documind:app-secret@db.internal:5432/documind")

    def test_different_name_on_an_unknown_host_is_accepted(self):
        target = "postgresql+asyncpg://documind:app-secret@db.internal:5432/documind_integration"
        assert _guard(target) == ("db.internal", 5432, "documind_integration")


# 10 — credentials and query values never reach a message -------------------


class TestNoCredentialOrQueryValueInMessages:
    def test_override_parameter_value_is_not_echoed(self):
        target = (
            "postgresql+asyncpg://documind:app-secret@localhost:5432/documind_integration"
            "?host=/tmp/zzz-hidden-socket&password=zzz-secret"
        )
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="host") as exc:
            _guard(target)
        message = str(exc.value)
        assert "zzz-hidden-socket" not in message
        assert "zzz-secret" not in message
        assert "app-secret" not in message

    def test_same_name_refusal_does_not_echo_the_password(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            _guard(APP)
        assert "app-secret" not in str(exc.value)

    def test_unknown_host_refusal_does_not_echo_the_password(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            _guard("postgresql+asyncpg://documind:app-secret@db.internal:5432/documind")
        assert "app-secret" not in str(exc.value)


# 11 — regression cases for legitimate isolated targets --------------------


class TestLegitimateIsolatedTargetsStillPass:
    def test_sslmode_query_is_not_an_override(self):
        target = ISOLATED + "?sslmode=require"
        assert _guard(target) == ("localhost", 5432, "documind_integration")

    def test_isolated_name_with_explicit_default_port_is_accepted(self):
        target = "postgresql+asyncpg://documind:app-secret@localhost:5432/documind_integration"
        assert _guard(target)[2] == "documind_integration"

    def test_returned_identity_is_the_verified_one(self):
        assert _guard(ISOLATED) == isolation.database_identity(ISOLATED)


# 12 — fail closed when separation cannot be established --------------------


class TestFailClosedWhenSeparationIsUnknown:
    @pytest.mark.parametrize(
        "target",
        [
            "postgresql+asyncpg://documind:app-secret@localhost:5432/documind?service=prod",
            "postgresql+asyncpg://documind:app-secret@localhost:5432/documind_integration?hostaddr=10.0.0.5",
            "postgresql+asyncpg://documind:app-secret@localhost:5432/documind_integration?dbname=documind",
            "postgresql+asyncpg://documind:app-secret@localhost:5432/documind_integration?PORT=5433",
        ],
    )
    def test_connection_override_parameters_are_refused(self, target):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="connection parameter"):
            _guard(target)

    def test_override_on_the_application_url_is_refused(self):
        app = APP + "?host=db.internal"
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="application database"):
            _guard(ISOLATED, app)

    def test_empty_override_is_refused_rather_than_falling_back(self):
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="set but empty"):
            isolation.evaluation_database_url(override="", application_url=APP)

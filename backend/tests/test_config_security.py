"""Tests for JWT configuration security behaviour.

Verifies that:
  • The insecure default secret is detected
  • Production mode rejects the insecure default
  • Development mode allows the insecure default (with a warning)
  • A custom secure secret passes validation
"""

import os
import pytest
from unittest.mock import patch


class TestInsecureSecretDetection:
    """Verify that the Settings class can detect insecure defaults."""

    def test_default_secret_is_insecure(self):
        from config import Settings, _INSECURE_SECRETS
        s = Settings(jwt_secret_key="change-me-in-production")
        assert s.is_jwt_secret_insecure() is True
        assert "change-me-in-production" in _INSECURE_SECRETS

    def test_empty_secret_is_insecure(self):
        from config import Settings
        s = Settings(jwt_secret_key="")
        assert s.is_jwt_secret_insecure() is True

    def test_custom_secret_is_secure(self):
        from config import Settings
        s = Settings(jwt_secret_key="a-real-secret-that-is-not-default-abc123xyz")
        assert s.is_jwt_secret_insecure() is False

    def test_hex_secret_is_secure(self):
        from config import Settings
        s = Settings(
            jwt_secret_key="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        )
        assert s.is_jwt_secret_insecure() is False


class TestProductionJWTSecretValidation:
    """Verify that production mode rejects insecure defaults."""

    def test_production_rejects_default_secret(self):
        from config import Settings
        s = Settings(jwt_secret_key="change-me-in-production")
        # Simulate non-production (no DOCUMIND_DEV env var)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCUMIND_DEV", None)
            with pytest.raises(RuntimeError, match="insecure default"):
                s.require_production_jwt_secret()

    def test_production_rejects_empty_secret(self):
        from config import Settings
        s = Settings(jwt_secret_key="")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCUMIND_DEV", None)
            with pytest.raises(RuntimeError, match="insecure default"):
                s.require_production_jwt_secret()

    def test_production_accepts_custom_secret(self):
        from config import Settings
        s = Settings(jwt_secret_key="my-production-secret-abc123xyz")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCUMIND_DEV", None)
            # Should NOT raise
            s.require_production_jwt_secret()

    def test_dev_mode_allows_default_secret(self):
        from config import Settings
        s = Settings(jwt_secret_key="change-me-in-production")
        with patch.dict(os.environ, {"DOCUMIND_DEV": "1"}):
            # Should NOT raise — dev mode allows insecure defaults
            s.require_production_jwt_secret()

    def test_dev_mode_allows_empty_secret(self):
        from config import Settings
        s = Settings(jwt_secret_key="")
        with patch.dict(os.environ, {"DOCUMIND_DEV": "true"}):
            s.require_production_jwt_secret()


class TestJWTAlgorithm:
    """Verify JWT algorithm defaults are sensible."""

    def test_default_algorithm_is_hs256(self):
        from config import Settings
        s = Settings()
        assert s.jwt_algorithm == "HS256"

    def test_default_expire_is_24_hours(self):
        from config import Settings
        s = Settings()
        assert s.jwt_expire_minutes == 1440

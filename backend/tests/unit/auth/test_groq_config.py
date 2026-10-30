"""Credential compatibility and provider-selection regressions; no real secrets."""
import os

import pytest
from pydantic import ValidationError

from config import Settings


@pytest.fixture(autouse=True)
def isolated_provider_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.lower() in {"groq_api_key", "groq_api_url", "answer_provider", "answer_auto_fallback"}:
            monkeypatch.delenv(name)


def test_existing_mislabeled_key_loads_without_exposure(monkeypatch):
    secret = "gsk_fake_legacy_test_key"
    monkeypatch.setenv("GROQ_API_URL", secret)
    settings = Settings(_env_file=None)
    assert settings.groq_api_key.get_secret_value() == secret
    assert secret not in repr(settings)
    assert "groq_api_key" not in settings.model_dump()
    assert secret not in settings.model_dump_json()
    assert settings.answer_provider == "groq"
    assert settings.answer_auto_fallback is False


def test_canonical_key_wins_over_legacy_alias(monkeypatch):
    monkeypatch.setenv("GROQ_API_URL", "gsk_fake_legacy_test_key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake_canonical_test_key")
    settings = Settings(_env_file=None)
    assert settings.groq_api_key.get_secret_value() == "gsk_fake_canonical_test_key"


def test_canonical_empty_key_does_not_silently_select_legacy_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_URL", "gsk_fake_legacy_test_key")
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert Settings(_env_file=None).groq_api_key.get_secret_value() == ""


def test_legacy_alias_in_env_file_uses_same_loading_contract(tmp_path):
    path = tmp_path / "test-settings.env"
    path.write_text("GROQ_API_URL=gsk_fake_file_test_key\n", encoding="utf-8")
    assert Settings(_env_file=path).groq_api_key.get_secret_value() == "gsk_fake_file_test_key"


@pytest.mark.parametrize("name", ["GROQ_API_KEY", "GROQ_API_URL"])
def test_url_is_rejected_as_credential_without_echoing_it(monkeypatch, name):
    value = "https://api.groq.com/private-example?token=sensitive-test-value"
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)
    assert value not in str(caught.value)
    assert "sensitive-test-value" not in str(caught.value)


def test_local_provider_cannot_be_reenabled_from_environment(monkeypatch):
    monkeypatch.setenv("ANSWER_PROVIDER", "ollama")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_automatic_fallback_cannot_be_reenabled_from_environment(monkeypatch):
    monkeypatch.setenv("ANSWER_AUTO_FALLBACK", "true")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

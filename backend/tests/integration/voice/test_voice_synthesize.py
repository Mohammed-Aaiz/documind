"""Integration tests for the Voice TTS endpoint (POST /api/voice/synthesize).

Covers:
- Authentication (CurrentUser requirement)
- Input text validation (empty, whitespace-only, exact 2000 chars, >2000 chars)
- Language validation and normalization (valid ISO, case/whitespace handling, invalid codes)
- Response contract (200, audio/mpeg, inline content-disposition, MP3 bytes)
- Upstream error handling and sanitization (gTTSError, RequestException -> 503, no leaks)
- Unexpected failure handling and sanitization (RuntimeError -> 500, no leaks)
- Empty audio return safeguard (503)

In accordance with the project test rules:
- Does NOT make live network requests to Google Translate.
- Mocks only the internal synthesis boundary (`voice._synthesize_speech_bytes`).
- Reuses existing conftest fixtures (`client`, `create_test_user`).
"""

from __future__ import annotations

import logging
import uuid
import pytest
from httpx import AsyncClient

import voice
from gtts.tts import gTTSError
import requests


SYNTHESIZE_URL = "/api/voice/synthesize"
LOGIN_URL = "/api/auth/login"

# Deterministic mock MP3 bytes (ID3v2 header signature)
MOCK_MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x23TIT2\x00\x00\x00\x0b\x00\x00\x00DocuMind\xff\xf3\x84\xc4mockaudio"

SENTINEL_UPSTREAM_URL = "SUPER_SECRET_GOOGLE_INTERNAL_URL_https://translate.google.com/private/api"
SENTINEL_INTERNAL_ERROR = "SUPER_SECRET_INTERNAL_TTS_FAILURE_AT_MEMORY_OFFSET_0xDEADBEEF"


@pytest.fixture(autouse=True)
def _pin_gtts_engine(monkeypatch):
    """These cases pin ``TTS_ENGINE=gtts``.

    Their subject is the gTTS mapping — its language table, its MP3 contract and
    its upstream 503s.  The default local engine has its own module
    (``test_voice_tts_local.py``); pinning here keeps these assertions about the
    engine they actually name.
    """
    monkeypatch.setattr(voice.settings, "tts_engine", "gtts")


async def _auth_headers(client: AsyncClient, create_test_user, email: str) -> dict:
    """Create a real user, log in, and return a Bearer authorization header."""
    await create_test_user(email=email, password="Pass123!", name="TTS User")
    resp = await client.post(
        LOGIN_URL, json={"email": email, "password": "Pass123!"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===========================================================================
# 1. Authentication
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_unauthenticated_rejected(client: AsyncClient, monkeypatch):
    """Unauthenticated request must return 401 without invoking synthesis."""
    called = []

    def _fake_synth(text, lang, slow):
        called.append(True)
        return MOCK_MP3_BYTES

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _fake_synth)

    resp = await client.post(SYNTHESIZE_URL, json={"text": "Hello world"})
    assert resp.status_code == 401
    assert not called, "Synthesis must not be invoked for unauthenticated requests"


# ===========================================================================
# 2. Successful synthesis
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_success_returns_mp3_contract(
    client: AsyncClient, create_test_user, monkeypatch
):
    """Authenticated request returns 200 with raw MP3 audio and inline header."""
    recorded_args = {}

    def _fake_synth(text, lang, slow):
        recorded_args["text"] = text
        recorded_args["lang"] = lang
        recorded_args["slow"] = slow
        return MOCK_MP3_BYTES

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _fake_synth)
    headers = await _auth_headers(client, create_test_user, f"tts_ok_{uuid.uuid4().hex[:8]}@test.com")

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hello from DocuMind", "language": "en", "slow": False},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type") == "audio/mpeg"
    assert resp.headers.get("content-disposition") == 'inline; filename="speech.mp3"'
    assert resp.content == MOCK_MP3_BYTES

    assert recorded_args["text"] == "Hello from DocuMind"
    assert recorded_args["lang"] == "en"
    assert recorded_args["slow"] is False


@pytest.mark.asyncio
async def test_synthesize_slow_parameter_passed_to_helper(
    client: AsyncClient, create_test_user, monkeypatch
):
    """The 'slow' boolean option is properly passed through to the synthesis helper."""
    recorded_args = {}

    def _fake_synth(text, lang, slow):
        recorded_args["slow"] = slow
        return MOCK_MP3_BYTES

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _fake_synth)
    headers = await _auth_headers(client, create_test_user, f"tts_slow_{uuid.uuid4().hex[:8]}@test.com")

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Speak slowly please", "language": "en", "slow": True},
        headers=headers,
    )

    assert resp.status_code == 200
    assert recorded_args["slow"] is True


# ===========================================================================
# 3. Empty text validation
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_empty_text_rejected(
    client: AsyncClient, create_test_user, monkeypatch
):
    """Empty text string must be rejected before calling synthesis."""
    called = []
    monkeypatch.setattr(voice, "_synthesize_speech_bytes", lambda t, l, s: called.append(True))
    headers = await _auth_headers(client, create_test_user, f"tts_empty_{uuid.uuid4().hex[:8]}@test.com")

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": ""},
        headers=headers,
    )

    assert resp.status_code in (400, 422)
    assert not called


# ===========================================================================
# 4. Whitespace-only text validation
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("whitespace_val", ["   ", "\t\t", "\n\n  \t  \n"])
async def test_synthesize_whitespace_only_text_rejected(
    client: AsyncClient, create_test_user, monkeypatch, whitespace_val
):
    """Whitespace-only strings must return HTTP 400 Bad Request."""
    called = []
    monkeypatch.setattr(voice, "_synthesize_speech_bytes", lambda t, l, s: called.append(True))
    headers = await _auth_headers(client, create_test_user, f"tts_ws_{uuid.uuid4().hex[:8]}@test.com")

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": whitespace_val},
        headers=headers,
    )

    assert resp.status_code == 400
    body = resp.json()
    assert "empty or whitespace" in body["detail"].lower()
    assert not called


# ===========================================================================
# 5. Text length limit validation
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_exact_2000_chars_accepted(
    client: AsyncClient, create_test_user, monkeypatch
):
    """Text of exactly 2000 characters must be accepted."""
    recorded = []

    def _fake_synth(text, lang, slow):
        recorded.append(len(text))
        return MOCK_MP3_BYTES

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _fake_synth)
    headers = await _auth_headers(client, create_test_user, f"tts_max_{uuid.uuid4().hex[:8]}@test.com")

    text_2000 = "a" * 2000
    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": text_2000},
        headers=headers,
    )

    assert resp.status_code == 200
    assert recorded == [2000]


@pytest.mark.asyncio
async def test_synthesize_over_2000_chars_rejected(
    client: AsyncClient, create_test_user, monkeypatch
):
    """Text exceeding 2000 characters must be rejected without calling synthesis."""
    called = []
    monkeypatch.setattr(voice, "_synthesize_speech_bytes", lambda t, l, s: called.append(True))
    headers = await _auth_headers(client, create_test_user, f"tts_toolong_{uuid.uuid4().hex[:8]}@test.com")

    text_2001 = "a" * 2001
    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": text_2001},
        headers=headers,
    )

    # Handled by Pydantic max_length=2000 (422) or endpoint check (400)
    assert resp.status_code in (400, 422)
    assert not called


# ===========================================================================
# 6. Invalid language validation
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_invalid_language_rejected(
    client: AsyncClient, create_test_user, monkeypatch
):
    """Unsupported language codes must return HTTP 400 without internal tracebacks."""
    called = []
    monkeypatch.setattr(voice, "_synthesize_speech_bytes", lambda t, l, s: called.append(True))
    headers = await _auth_headers(client, create_test_user, f"tts_badlang_{uuid.uuid4().hex[:8]}@test.com")

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hello", "language": "nonexistent_lang_xyz"},
        headers=headers,
    )

    assert resp.status_code == 400
    body = resp.json()
    assert "unsupported language code" in body["detail"].lower()
    assert not called
    # No tracebacks leaked
    assert "traceback" not in resp.text.lower()


# ===========================================================================
# 7. Language normalization
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("input_lang, expected_lang", [
    ("  EN  ", "en"),
    ("ES", "es"),
    ("  fr  ", "fr"),
])
async def test_synthesize_language_normalization(
    client: AsyncClient, create_test_user, monkeypatch, input_lang, expected_lang
):
    """Language codes with harmless whitespace or uppercase are normalized."""
    recorded_lang = []

    def _fake_synth(text, lang, slow):
        recorded_lang.append(lang)
        return MOCK_MP3_BYTES

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _fake_synth)
    headers = await _auth_headers(client, create_test_user, f"tts_norm_{uuid.uuid4().hex[:8]}@test.com")

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hello", "language": input_lang},
        headers=headers,
    )

    assert resp.status_code == 200
    assert recorded_lang == [expected_lang]


# ===========================================================================
# 8. Upstream gTTS / network failure handling (503 and leak proof)
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_upstream_request_exception_returns_503_without_leak(
    client: AsyncClient, create_test_user, monkeypatch, caplog
):
    """Network failure communicating with Google returns 503 and hides internal URLs."""
    def _failing_synth(text, lang, slow):
        raise requests.RequestException(f"Connection failed to {SENTINEL_UPSTREAM_URL}")

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _failing_synth)
    headers = await _auth_headers(client, create_test_user, f"tts_neterr_{uuid.uuid4().hex[:8]}@test.com")

    with caplog.at_level(logging.ERROR, logger="voice"):
        resp = await client.post(
            SYNTHESIZE_URL,
            json={"text": "Hello network test"},
            headers=headers,
        )

    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"] == "Voice synthesis service is unavailable"

    # Regression proof: sentinel URL must never reach client
    assert SENTINEL_UPSTREAM_URL not in resp.text
    assert "requests" not in resp.text.lower()
    assert "traceback" not in resp.text.lower()

    # But diagnostic is logged server-side
    assert SENTINEL_UPSTREAM_URL in caplog.text


@pytest.mark.asyncio
async def test_synthesize_gtts_error_returns_503_without_leak(
    client: AsyncClient, create_test_user, monkeypatch, caplog
):
    """gTTSError returns 503 and hides upstream error details from client response."""
    def _failing_synth(text, lang, slow):
        raise gTTSError(f"Google 429 Too Many Requests: {SENTINEL_UPSTREAM_URL}")

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _failing_synth)
    headers = await _auth_headers(client, create_test_user, f"tts_gttserr_{uuid.uuid4().hex[:8]}@test.com")

    with caplog.at_level(logging.ERROR, logger="voice"):
        resp = await client.post(
            SYNTHESIZE_URL,
            json={"text": "Hello rate limit test"},
            headers=headers,
        )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Voice synthesis service is unavailable"
    assert SENTINEL_UPSTREAM_URL not in resp.text
    assert "gttserror" not in resp.text.lower()
    assert SENTINEL_UPSTREAM_URL in caplog.text


# ===========================================================================
# 9. Unexpected internal exception handling (500 and leak proof)
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_unexpected_internal_error_returns_500_without_leak(
    client: AsyncClient, create_test_user, monkeypatch, caplog
):
    """Unexpected runtime exceptions return clean 500 without leaking tracebacks or sentinels."""
    def _crashing_synth(text, lang, slow):
        raise RuntimeError(SENTINEL_INTERNAL_ERROR)

    monkeypatch.setattr(voice, "_synthesize_speech_bytes", _crashing_synth)
    headers = await _auth_headers(client, create_test_user, f"tts_crash_{uuid.uuid4().hex[:8]}@test.com")

    with caplog.at_level(logging.ERROR, logger="voice"):
        resp = await client.post(
            SYNTHESIZE_URL,
            json={"text": "Hello crash test"},
            headers=headers,
        )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Text-to-speech synthesis failed"

    # Regression proof: sentinel must not appear in client response
    assert SENTINEL_INTERNAL_ERROR not in resp.text
    assert "runtimeerror" not in resp.text.lower()
    assert "traceback" not in resp.text.lower()

    # Diagnostic logged server-side
    assert SENTINEL_INTERNAL_ERROR in caplog.text


# ===========================================================================
# 10. Empty audio safeguard
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_empty_audio_safeguard_returns_503(
    client: AsyncClient, create_test_user, monkeypatch, caplog
):
    """If synthesis returns empty bytes, endpoint must fail with 503 rather than returning empty 200."""
    monkeypatch.setattr(voice, "_synthesize_speech_bytes", lambda t, l, s: b"")
    headers = await _auth_headers(client, create_test_user, f"tts_emptybytes_{uuid.uuid4().hex[:8]}@test.com")

    with caplog.at_level(logging.ERROR, logger="voice"):
        resp = await client.post(
            SYNTHESIZE_URL,
            json={"text": "Hello empty audio test"},
            headers=headers,
        )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Voice synthesis service returned empty audio"
    assert "empty audio" in caplog.text.lower()

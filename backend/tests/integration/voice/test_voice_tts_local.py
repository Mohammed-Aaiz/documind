"""Tests for the local Piper text-to-speech engine (``TTS_ENGINE=local``).

Scope, stated honestly
----------------------

* Wiring, the language policy, the media-type contract, the fail-closed 503 and
  the ``slow`` mapping run through the real FastAPI app and the real
  authentication boundary, with the synthesis boundary patched.  They prove the
  endpoint behaviour, not model quality.
* ``test_real_local_synthesis_is_offline`` runs the actual provisioned Piper
  voice, with socket creation blocked, so it proves the local path needs no
  network.  It is skipped when the voice artifact is absent — the same
  provisioning contract as the Whisper tests.

No test here calls gTTS or Google.
"""

from __future__ import annotations

import socket
import uuid
import wave
from io import BytesIO

import pytest
from httpx import AsyncClient

import voice

SYNTHESIZE_URL = "/api/voice/synthesize"
LOGIN_URL = "/api/auth/login"

#: Minimal but structurally valid WAV prefix (the tests below only ever need
#: the container signature, never decodable audio).
WAV_BYTES = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"fmt " + b"\x00" * 32

SENTINEL_VOICE_PATH = "SUPER_SECRET_LOCAL_VOICE_PATH_D:\\private\\voices"


async def _auth_headers(client: AsyncClient, create_test_user, email: str) -> dict:
    """Create a real user, log in, and return a Bearer authorization header."""
    await create_test_user(email=email, password="Pass123!", name="TTS Local")
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "Pass123!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(autouse=True)
def _local_engine(monkeypatch):
    """Pin the engine under test; each case may still override the boundary."""
    monkeypatch.setattr(voice.settings, "tts_engine", "local")
    monkeypatch.setattr(voice.settings, "tts_voice", "en_US-ljspeech-medium")


# ===========================================================================
# 1. Engine identity
# ===========================================================================


def test_reports_the_local_engine_and_its_container():
    assert voice.tts_engine_name() == "piper-local"
    assert voice.tts_media_type() == "audio/wav"
    assert voice.tts_file_suffix() == "wav"


def test_unknown_engine_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setattr(voice.settings, "tts_engine", "nonsense")
    assert voice.tts_engine_name() == "unavailable"


# ===========================================================================
# 2. Success contract
# ===========================================================================


@pytest.mark.asyncio
async def test_synthesize_returns_wav_contract(
    client: AsyncClient, create_test_user, monkeypatch
):
    recorded = {}

    def _fake_local(text, slow):
        recorded["text"] = text
        recorded["slow"] = slow
        return WAV_BYTES

    monkeypatch.setattr(voice, "_synthesize_local_speech_bytes", _fake_local)
    headers = await _auth_headers(
        client, create_test_user, f"tts_local_ok_{uuid.uuid4().hex[:8]}@test.com"
    )

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hello from DocuMind", "language": "en", "slow": False},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type") == "audio/wav"
    assert resp.headers.get("content-disposition") == 'inline; filename="speech.wav"'
    assert resp.content == WAV_BYTES
    assert recorded == {"text": "Hello from DocuMind", "slow": False}


@pytest.mark.asyncio
async def test_regional_english_is_accepted(
    client: AsyncClient, create_test_user, monkeypatch
):
    """The en_US voice can speak en-GB / en_US spellings of the same language."""
    monkeypatch.setattr(voice, "_synthesize_local_speech_bytes", lambda t, s: WAV_BYTES)
    headers = await _auth_headers(
        client, create_test_user, f"tts_local_gb_{uuid.uuid4().hex[:8]}@test.com"
    )

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hello", "language": "en-GB"},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text


# ===========================================================================
# 3. Language policy — refuse, never speak the wrong language
# ===========================================================================


@pytest.mark.asyncio
async def test_language_the_voice_cannot_speak_is_refused(
    client: AsyncClient, create_test_user, monkeypatch
):
    called = []
    monkeypatch.setattr(
        voice, "_synthesize_local_speech_bytes", lambda t, s: called.append(True)
    )
    headers = await _auth_headers(
        client, create_test_user, f"tts_local_de_{uuid.uuid4().hex[:8]}@test.com"
    )

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hallo", "language": "de"},
        headers=headers,
    )

    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "unsupported language code" in detail
    assert "en" in detail
    assert called == [], "synthesis must not run for an unsupported language"


# ===========================================================================
# 4. Fail-closed: a missing voice is a 503, never a network fallback
# ===========================================================================


@pytest.mark.asyncio
async def test_unavailable_voice_returns_503_without_leak(
    client: AsyncClient, create_test_user, monkeypatch, caplog
):
    def _broken_voice():
        raise voice.TTSEngineUnavailable(
            f"Local TTS voice not found at '{SENTINEL_VOICE_PATH}'"
        )

    monkeypatch.setattr(voice, "_load_local_voice", _broken_voice)
    headers = await _auth_headers(
        client, create_test_user, f"tts_local_missing_{uuid.uuid4().hex[:8]}@test.com"
    )

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hello", "language": "en"},
        headers=headers,
    )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Text-to-speech engine is unavailable"
    # The server-side path is logged, the client sees no internals.
    assert SENTINEL_VOICE_PATH not in resp.text
    assert "traceback" not in resp.text.lower()


@pytest.mark.asyncio
async def test_unknown_engine_returns_503(client: AsyncClient, create_test_user, monkeypatch):
    monkeypatch.setattr(voice.settings, "tts_engine", "nonsense")
    headers = await _auth_headers(
        client, create_test_user, f"tts_local_unknown_{uuid.uuid4().hex[:8]}@test.com"
    )

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "Hello", "language": "en"},
        headers=headers,
    )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Text-to-speech engine is unavailable"


# ===========================================================================
# 5. `slow` maps onto Piper's phoneme duration
# ===========================================================================


def test_slow_request_stretches_the_phoneme_timeline():
    normal = voice._tts_synthesis_config(False)
    slow = voice._tts_synthesis_config(True)

    assert normal.length_scale == 1.0
    assert slow.length_scale > normal.length_scale


# ===========================================================================
# 6. Real local inference, with the network blocked
# ===========================================================================


@pytest.mark.skipif(
    not voice.local_tts_model_path().is_file(),
    reason="provisioned Piper voice is not present (backend/models/tts/)",
)
@pytest.mark.asyncio
async def test_real_local_synthesis_is_offline(
    client: AsyncClient, create_test_user, monkeypatch
):
    """The provisioned voice synthesizes with outbound connections blocked.

    ``socket.create_connection`` is the choke point every stdlib HTTP client
    (and therefore requests/gTTS) goes through.  Only that is blocked: patching
    ``socket.socket`` itself breaks the event loop's own wakeup plumbing on
    Windows, which would test the harness instead of the engine.
    """

    def _no_connections(*args, **kwargs):
        raise AssertionError("the local TTS engine must not open a connection")

    monkeypatch.setattr(socket, "create_connection", _no_connections)

    headers = await _auth_headers(
        client, create_test_user, f"tts_local_real_{uuid.uuid4().hex[:8]}@test.com"
    )

    resp = await client.post(
        SYNTHESIZE_URL,
        json={"text": "DocuMind local speech check.", "language": "en"},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type") == "audio/wav"
    assert resp.content[:4] == b"RIFF"

    with wave.open(BytesIO(resp.content)) as audio:
        assert audio.getnframes() > 0
        assert audio.getframerate() > 0

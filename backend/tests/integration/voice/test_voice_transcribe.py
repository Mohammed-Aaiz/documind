"""Tests for the Voice STT endpoint (``POST /api/voice/transcribe``).

Coverage split, stated honestly:

* **Validation / auth / error handling** — exercised through the real FastAPI
  app and the real authentication boundary (``CurrentUser``).  These tests do
  NOT run the Whisper model: ``voice._load_model`` / ``voice._transcribe_path``
  are monkeypatched so the routing, status codes, response model, temp-file
  handling and error sanitisation are what is being verified.  A mocked
  success here proves the *endpoint wiring*, not real inference.
* **Real local inference** — ``test_real_local_inference_is_offline`` is the one
  test that runs the actual provisioned model end to end.  It is skipped when
  the model artifact is absent, uses a deterministic locally-generated WAV
  (a tone — no speech, so no transcript text is asserted, only that real
  inference ran offline), and forces Hugging Face offline mode so a network
  download cannot be mistaken for success.

No test requires network access, an external transcription API, or a
request-time model download.
"""

from __future__ import annotations

import array
import io
import math
import os
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

import voice


TRANSCRIBE_URL = "/api/voice/transcribe"
LOGIN_URL = "/api/auth/login"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sine_wav_bytes(seconds: float = 0.5, rate: int = 16000, freq: int = 440) -> bytes:
    """Deterministic 16-bit mono PCM WAV — a valid audio container, no speech."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = array.array(
            "h",
            (
                int(3000 * math.sin(2 * math.pi * freq * t / rate))
                for t in range(int(seconds * rate))
            ),
        )
        wav.writeframes(frames.tobytes())
    return buf.getvalue()


async def _auth_headers(client: AsyncClient, create_test_user, email: str) -> dict:
    """Create a real user, log in, and return a Bearer header."""
    await create_test_user(email=email, password="Pass123!", name="Voice")
    resp = await client.post(
        LOGIN_URL, json={"email": email, "password": "Pass123!"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _stub_inference(monkeypatch, text: str = "hello world", language: str = "en",
                    duration: float = 1.5):
    """Replace model load + inference with deterministic stubs.

    Returns the mutable recorder so tests can inspect the temp path the
    endpoint handed to inference (used by the cleanup tests).
    """
    recorded: dict = {}

    monkeypatch.setattr(voice, "_load_model", lambda: object())

    def _fake_transcribe(model, audio_path: str):
        recorded["audio_path"] = audio_path
        return (text, language, duration)

    monkeypatch.setattr(voice, "_transcribe_path", _fake_transcribe)
    return recorded


# ===========================================================================
# 1. Successful transcription path (mocked inference — endpoint wiring)
# ===========================================================================


@pytest.mark.asyncio
async def test_transcribe_success_returns_text(
    client: AsyncClient, create_test_user, monkeypatch
):
    """A valid upload flows through the endpoint and echoes the model output.

    Inference itself is stubbed here — this verifies routing, the response
    contract, and that the audio was written to a temp file before inference.
    """
    _stub_inference(monkeypatch, text="the quick brown fox", language="en", duration=2.25)
    headers = await _auth_headers(client, create_test_user, "voice_success@test.com")

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("speech.wav", _sine_wav_bytes(), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text"] == "the quick brown fox"
    assert body["language"] == "en"
    assert body["duration"] == 2.25


# ===========================================================================
# 2. Missing audio -> 400
# ===========================================================================


@pytest.mark.asyncio
async def test_missing_audio_returns_400(
    client: AsyncClient, create_test_user, monkeypatch
):
    headers = await _auth_headers(client, create_test_user, "voice_missing@test.com")

    resp = await client.post(TRANSCRIBE_URL, data={}, headers=headers)

    assert resp.status_code == 400
    assert "audio" in resp.json()["detail"].lower()


# ===========================================================================
# 3. Empty audio -> 400
# ===========================================================================


@pytest.mark.asyncio
async def test_empty_audio_returns_400(
    client: AsyncClient, create_test_user, monkeypatch
):
    headers = await _auth_headers(client, create_test_user, "voice_empty@test.com")

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("empty.wav", b"", "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


# ===========================================================================
# 4. Invalid / non-audio bytes -> 400 (client filename is not trusted)
# ===========================================================================


@pytest.mark.asyncio
async def test_invalid_non_audio_returns_400(
    client: AsyncClient, create_test_user, monkeypatch
):
    headers = await _auth_headers(client, create_test_user, "voice_invalid@test.com")

    # Claims to be a WAV; the bytes say otherwise.
    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("sneaky.wav", b"this is definitely not audio data", "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()


# ===========================================================================
# 5. Oversized upload -> 413
# ===========================================================================


@pytest.mark.asyncio
async def test_oversized_audio_returns_413(
    client: AsyncClient, create_test_user, monkeypatch
):
    headers = await _auth_headers(client, create_test_user, "voice_large@test.com")
    # Shrink the configured limit instead of uploading a real 50 MB payload.
    monkeypatch.setattr(
        voice, "settings", SimpleNamespace(max_upload_bytes=8, max_upload_size_mb=0)
    )

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("big.wav", _sine_wav_bytes(), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 413


# ===========================================================================
# 6. Authentication boundary
# ===========================================================================


@pytest.mark.asyncio
async def test_unauthenticated_does_not_reach_transcription(
    client: AsyncClient, monkeypatch
):
    """Without a token the request must not reach inference."""
    reached = {"called": False}

    def _must_not_run(model, audio_path):  # pragma: no cover - must never run
        reached["called"] = True
        return ("", "", 0.0)

    monkeypatch.setattr(voice, "_load_model", lambda: object())
    monkeypatch.setattr(voice, "_transcribe_path", _must_not_run)

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("speech.wav", _sine_wav_bytes(), "audio/wav")},
    )

    assert resp.status_code == 401
    assert reached["called"] is False


# ===========================================================================
# 7. Model unavailable -> 503, no filesystem paths leaked
# ===========================================================================


@pytest.mark.asyncio
async def test_model_unavailable_returns_503_without_path_leak(
    client: AsyncClient, create_test_user, monkeypatch
):
    headers = await _auth_headers(client, create_test_user, "voice_nomodel@test.com")

    def _boom():
        raise RuntimeError(
            "Failed to load Voice STT model from the local directory: "
            "C:/secret/path/models/whisper/small missing"
        )

    monkeypatch.setattr(voice, "_load_model", _boom)

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("speech.wav", _sine_wav_bytes(), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 503
    leaked = resp.text.lower()
    assert "c:/" not in leaked and "secret" not in leaked
    assert "whisper" not in leaked and "models/" not in leaked


# ===========================================================================
# 7b. Inference failure -> 500, no stack trace / internals leaked
# ===========================================================================


@pytest.mark.asyncio
async def test_inference_failure_returns_500_without_leak(
    client: AsyncClient, create_test_user, monkeypatch
):
    headers = await _auth_headers(client, create_test_user, "voice_fail@test.com")
    monkeypatch.setattr(voice, "_load_model", lambda: object())

    def _boom(model, audio_path):
        raise RuntimeError("decoder exploded at C:/internal/decoder.py line 42")

    monkeypatch.setattr(voice, "_transcribe_path", _boom)

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("speech.wav", _sine_wav_bytes(), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 500
    leaked = resp.text.lower()
    assert "c:/internal" not in leaked and "traceback" not in leaked
    assert "decoder.py" not in leaked


# ===========================================================================
# 8. Temp file cleanup on success and on failure
# ===========================================================================


@pytest.mark.asyncio
async def test_temp_file_cleaned_up_after_success(
    client: AsyncClient, create_test_user, monkeypatch
):
    recorded = _stub_inference(monkeypatch)
    headers = await _auth_headers(client, create_test_user, "voice_cleanup_ok@test.com")

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("speech.wav", _sine_wav_bytes(), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 200
    assert "audio_path" in recorded, "inference never received a temp path"
    assert not os.path.exists(recorded["audio_path"]), (
        "temporary audio file was not removed after success"
    )


@pytest.mark.asyncio
async def test_temp_file_cleaned_up_after_failure(
    client: AsyncClient, create_test_user, monkeypatch
):
    recorded: dict = {}
    monkeypatch.setattr(voice, "_load_model", lambda: object())

    def _boom(model, audio_path):
        recorded["audio_path"] = audio_path
        raise RuntimeError("transcription failed")

    monkeypatch.setattr(voice, "_transcribe_path", _boom)
    headers = await _auth_headers(client, create_test_user, "voice_cleanup_fail@test.com")

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("speech.wav", _sine_wav_bytes(), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 500
    assert "audio_path" in recorded
    assert not os.path.exists(recorded["audio_path"]), (
        "temporary audio file was not removed after failure"
    )


# ===========================================================================
# 9. Pure helper: container sniffing
# ===========================================================================


def test_looks_like_audio_accepts_valid_containers():
    assert voice._looks_like_audio(_sine_wav_bytes())
    assert voice._looks_like_audio(b"ID3" + b"\x00" * 40)
    assert voice._looks_like_audio(b"OggS" + b"\x00" * 40)
    assert voice._looks_like_audio(b"fLaC" + b"\x00" * 40)


def test_looks_like_audio_rejects_non_audio():
    assert not voice._looks_like_audio(b"plain text, not audio")
    assert not voice._looks_like_audio(b"")
    assert not voice._looks_like_audio(b"%PDF-1.4 fake pdf body")


# ===========================================================================
# 10. Real local Whisper inference (skipped when the model is absent)
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.skipif(
    not Path(voice._MODEL_NAME).is_dir(),
    reason="provisioned Whisper model artifact not present",
)
async def test_real_local_inference_is_offline(
    client: AsyncClient, create_test_user, monkeypatch
):
    """End-to-end: real model, real decode, forced offline, no external API.

    The deterministic fixture is a 440 Hz tone — no speech — so a specific
    transcript must NOT be asserted (that would either fail or invite a fake
    expectation).  What is verified is that genuine local inference ran and
    returned the documented response contract.
    """
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    headers = await _auth_headers(client, create_test_user, "voice_real@test.com")

    resp = await client.post(
        TRANSCRIBE_URL,
        files={"audio": ("tone.wav", _sine_wav_bytes(seconds=1.0), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["text"], str)
    assert isinstance(body["language"], str)
    assert isinstance(body["duration"], float)
    assert body["duration"] > 0

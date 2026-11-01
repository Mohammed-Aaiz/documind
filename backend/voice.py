"""Voice speech-to-text (local Whisper) and text-to-speech (local Piper or gTTS).

Speech-to-text
--------------

``POST /api/voice/transcribe`` accepts an uploaded audio file and returns a
transcription produced **only** by the locally provisioned Whisper model
(``backend/models/whisper/small``, upstream ``Systran/faster-whisper-small``).

Design constraints (all satisfied here):

* **Local model only.** The model directory is resolved from this file's own
  location (never from user input or the request filename) and loaded with
  ``local_files_only=True``.  There is no request-time download, no external
  transcription API, and no fallback to another speech model.  If the model
  cannot be loaded, the request fails honestly — a transcript is never
  fabricated.
* **Loaded once per process.** ``WhisperModel`` is expensive to construct, so
  the instance is created lazily on first use and cached in a module global,
  exactly like ``chat/qa_model.py``.  It is never constructed inside the
  request handler.
* **CPU-safe inference.** ``device="cpu"`` / ``compute_type="int8"``, matching
  the environment the model was provisioned and offline-verified in.
* **Off the event loop.** The blocking decode + inference runs in a worker
  thread via ``run_in_threadpool`` so the async server stays responsive.
* **Untrusted upload.** The audio is written to an OS-generated temporary file
  (never a path derived from the client filename) and is removed on every
  exit path — success, validation failure, transcription failure, and
  unexpected exception.
"""

import io
import logging
import os
import tempfile
import threading
import wave
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from auth.dependencies import CurrentUser
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Backend package root, so the model resolves correctly regardless of the
# process working directory (mirrors ``main.py``'s Alembic path handling).
_BACKEND_DIR = Path(__file__).resolve().parent

# The provisioned CTranslate2 Whisper artifact.  Overridable for deployment
# layouts via an env var, but always a filesystem path pointing at a local
# directory — never a bare model size such as ``"small"``, which would let
# faster-whisper resolve (and download) a Hub model at request time.
_DEFAULT_MODEL_DIR = _BACKEND_DIR / "models" / "whisper" / "small"
_MODEL_NAME = os.getenv("WHISPER_MODEL_NAME", str(_DEFAULT_MODEL_DIR))

# Container signatures for the audio formats PyAV/FFmpeg can decode here.  The
# client-provided filename/extension is never trusted; the bytes decide.
_AUDIO_SIGNATURES: tuple[tuple[str, bytes], ...] = (
    ("wav", b"RIFF"),        # checked further below for the "WAVE" tag
    ("mp3", b"ID3"),
    ("ogg", b"OggS"),
    ("flac", b"fLaC"),
    ("matroska", b"\x1a\x45\xdf\xa3"),
)

# faster-whisper / CTranslate2 is not safe to invoke concurrently on a single
# model instance.  Serialising inference is the conservative choice; requests
# still run on worker threads so the event loop is never blocked.
_inference_lock = threading.Lock()

# --- Process-level singleton (mirrors chat/qa_model.py) ---
_model = None
_model_loaded = False
_model_load_error: str | None = None
_model_lock = threading.Lock()

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TranscribeResponse(BaseModel):
    """Honest transcription output.

    ``text`` is the actual model output (empty string when the audio contains
    no speech).  ``language`` and ``duration`` are the real values reported by
    the model's transcription info — never estimated or synthesised.
    """

    text: str
    language: str
    duration: float


def _load_model():
    """Construct (once) and return the shared ``WhisperModel``.

    Raises ``RuntimeError`` with a server-side-only message when the local
    model directory is missing or the model cannot be loaded.  The error is
    cached so repeated requests fail fast instead of re-attempting the load.
    """
    global _model, _model_loaded, _model_load_error

    if _model_loaded:
        if _model_load_error:
            raise RuntimeError(_model_load_error)
        return _model

    with _model_lock:
        # Re-check inside the lock — another thread may have loaded it.
        if _model_loaded:
            if _model_load_error:
                raise RuntimeError(_model_load_error)
            return _model

        model_dir = Path(_MODEL_NAME)
        if not model_dir.is_dir():
            _model_load_error = (
                f"Voice STT model directory not found at '{_MODEL_NAME}'. "
                f"The provisioned Whisper model must be present locally."
            )
            _model_loaded = True
            raise RuntimeError(_model_load_error)

        try:
            # Imported lazily: faster-whisper pulls in ctranslate2/PyAV, which
            # are slow to import and only needed once transcription is actually
            # requested.
            from faster_whisper import WhisperModel

            _model = WhisperModel(
                str(model_dir),
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
            _model_loaded = True
        except Exception as exc:
            _model_loaded = True
            _model_load_error = (
                f"Failed to load Voice STT model from the local directory: {exc}"
            )
            raise RuntimeError(_model_load_error) from exc

    return _model


def is_model_available() -> bool:
    """True when the local Whisper model can be loaded and used."""
    try:
        _load_model()
        return _model is not None
    except RuntimeError:
        return False


def _looks_like_audio(head: bytes) -> bool:
    """Best-effort container check on the leading bytes.

    Not a substitute for decoding — it only rejects obviously non-audio
    payloads before we spend time on the model.  Anything that passes is
    still verified by the decoder, and a decode failure is reported honestly.
    """
    if len(head) < 12:
        return False
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return True
    # MP4/M4A family: ``ftyp`` box at offset 4.
    if head[4:8] == b"ftyp":
        return True
    # MPEG audio frame sync (0xFFEx / 0xFFFx).
    if head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return True
    # Remaining magic signatures (mp3/ID3, ogg, flac, matroska).  Index 0
    # (RIFF/WAV) is already handled by the stricter check above.
    return any(head.startswith(sig) for _, sig in _AUDIO_SIGNATURES[1:])


def _transcribe_path(model, audio_path: str) -> tuple[str, str, float]:
    """Run blocking inference on a local audio file.

    Consumes the segment generator (faster-whisper decodes lazily) and joins
    the real segment text.  Returns ``(text, language, duration)``.
    """
    return _transcribe_path_with_partials(model, audio_path)


def _transcribe_path_with_partials(
    model,
    audio_path: str,
    on_partial: Callable[[str, int, str], None] | None = None,
) -> tuple[str, str, float]:
    """Consume the one local Whisper decode, optionally publishing snapshots.

    faster-whisper accepts a complete audio source; it does not expose an
    incremental microphone input API. Its segment iterator can yield decoded
    segments while a longer utterance is being processed. This callback emits
    cumulative snapshots from that *same* iterator; it does not run duplicate
    inference. The final return value is assembled from exactly those same
    segments and remains authoritative for the answer pipeline.

    Short utterances may be represented by one Whisper segment, so they may
    produce only one snapshot near the end of decoding. This is progress during
    post-utterance decoding, not live transcription while the user is speaking.
    """
    with _inference_lock:
        segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)
        language = str(getattr(info, "language", "") or "")
        pieces: list[str] = []
        segment_count = 0
        for segment in segments:
            pieces.append(segment.text)
            segment_count += 1
            if on_partial is not None:
                snapshot = "".join(pieces).strip()
                if snapshot:
                    try:
                        on_partial(snapshot, segment_count, language)
                    except Exception:
                        # A dropped UI progress event must never invalidate
                        # the final locally decoded transcript.
                        logger.debug("Voice partial transcript delivery failed", exc_info=True)

    return (
        "".join(pieces).strip(),
        language,
        float(getattr(info, "duration", 0.0) or 0.0),
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    current_user: CurrentUser,
    audio: UploadFile | None = File(default=None),
):
    """Transcribe an uploaded audio file with the local Whisper model."""
    # --- 1. Validate that audio was actually provided ---
    if audio is None or not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided. Send multipart/form-data with an 'audio' field.",
        )

    audio_bytes = await audio.read()

    # --- 2. Size validation (existing project convention) ---
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty",
        )
    if len(audio_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds maximum size of {settings.max_upload_size_mb} MB",
        )

    # --- 3. Content validation — never trust the client filename/extension ---
    if not _looks_like_audio(audio_bytes[:64]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported or invalid audio file",
        )

    # --- 4. Model availability (honest 503, no fabricated transcript) ---
    try:
        # The first local model load is CPU/file work too. Keep health checks,
        # text chat and cancellation responsive during a cold voice request.
        model = await run_in_threadpool(_load_model)
    except RuntimeError:
        logger.exception("Voice STT model unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech-to-text model is unavailable",
        )

    # --- 5. Write to an OS-generated temp file (never a client-derived path) ---
    fd, temp_path = tempfile.mkstemp(prefix="voice_", suffix=".audio")
    try:
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(audio_bytes)

            # --- 6. Real inference, off the event loop ---
            text, language, duration = await run_in_threadpool(
                _transcribe_path, model, temp_path
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("Voice STT transcription failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Transcription failed",
            )
    finally:
        # --- 7. Clean up on every path: success, validation, failure, error ---
        try:
            os.unlink(temp_path)
        except OSError:
            logger.warning("Failed to remove temporary audio file")

    return TranscribeResponse(
        text=text,
        language=language,
        duration=round(duration, 3),
    )


# ---------------------------------------------------------------------------
# Voice Text-to-Speech (TTS) — local Piper voice (default) or gTTS
# ---------------------------------------------------------------------------
#
# ``TTS_ENGINE`` selects the synthesizer **explicitly**:
#
# * ``local`` (default) — the provisioned Piper voice at
#   ``models/tts/<TTS_VOICE>.onnx``, run through ONNX Runtime on the CPU.  No
#   network, no VRAM, no system-level espeak-ng (the ``piper-tts`` wheels carry
#   their own espeak-ng data).
# * ``gtts`` — the previous behaviour: an HTTPS request to Google Translate,
#   which sends the answer text off the machine.
#
# There is deliberately **no fallback between them**.  A missing local voice is
# an honest ``503``, never a silent trip to the network: keeping the answer text
# local is the entire point of the local engine.

TTS_ENGINE_LOCAL = "local"
TTS_ENGINE_GTTS = "gtts"

_LOCAL_TTS_ENGINE_NAME = "piper-local"
_GTTS_ENGINE_NAME = "gtts"

#: ``slow=True`` has no direct Piper switch.  A longer phoneme duration is the
#: honest equivalent (1.0 is the voice's natural rate).
_TTS_SLOW_LENGTH_SCALE = 1.3

#: Provisioned voices live beside the other local models, never in the repo.
_DEFAULT_TTS_DIR = _BACKEND_DIR / "models" / "tts"


class TTSEngineUnavailable(RuntimeError):
    """The configured speech engine cannot produce audio.  Never faked."""


class SynthesizeRequest(BaseModel):
    """Voice Text-to-Speech synthesis request."""

    text: str = Field(..., min_length=1, max_length=2000)
    language: str = Field(default="en")
    slow: bool = Field(default=False)


def _is_valid_language(lang: str) -> bool:
    """Validate language against gTTS supported language codes."""
    if not lang or not isinstance(lang, str):
        return False
    try:
        from gtts.lang import tts_langs

        return lang.strip().lower() in tts_langs()
    except Exception:
        # Fallback to standard ISO codes if dynamic lookup fails
        return lang.strip().lower() in {
            "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh", "zh-cn", "zh-tw"
        }


def _configured_engine() -> str:
    """The raw, normalised ``TTS_ENGINE`` value."""
    return (settings.tts_engine or "").strip().lower()


def tts_engine_name() -> str:
    """The engine **actually configured**, for honest capability reporting.

    Returns ``"piper-local"``, ``"gtts"`` or ``"unavailable"`` for an unknown
    ``TTS_ENGINE`` value.  Nothing here probes or loads a model.
    """
    engine = _configured_engine()
    if engine == TTS_ENGINE_LOCAL:
        return _LOCAL_TTS_ENGINE_NAME
    if engine == TTS_ENGINE_GTTS:
        return _GTTS_ENGINE_NAME
    return "unavailable"


def tts_media_type() -> str:
    """The container the configured engine returns (``audio/wav`` or MP3)."""
    return "audio/wav" if tts_engine_name() == _LOCAL_TTS_ENGINE_NAME else "audio/mpeg"


def tts_file_suffix(media_type: str | None = None) -> str:
    return "wav" if (media_type or tts_media_type()) == "audio/wav" else "mp3"


def tts_language() -> str:
    """Language the provisioned voice speaks, from its name (``en_US-...``)."""
    prefix = (settings.tts_voice or "").split("_")[0].split("-")[0]
    return prefix.strip().lower() or "en"


def tts_supports_language(language: str) -> bool:
    """Whether the configured engine can speak ``language``.

    gTTS keeps its own language table.  A local voice speaks exactly one
    language, so ``en``, ``en-US`` and ``en_GB`` are accepted for an ``en_*``
    voice and everything else is refused rather than spoken in the wrong
    language.
    """
    if tts_engine_name() == _GTTS_ENGINE_NAME:
        return _is_valid_language(language)
    base = tts_language()
    code = (language or "").strip().lower().replace("_", "-")
    return bool(base) and (code == base or code.startswith(f"{base}-"))


def local_tts_model_path() -> Path:
    """Resolve the provisioned voice file (never from request input)."""
    configured = (settings.tts_model_path or "").strip()
    if configured:
        return Path(configured)
    return _DEFAULT_TTS_DIR / f"{settings.tts_voice}.onnx"


# --- Process-level singleton (mirrors the Whisper loader above) -------------
_local_voice = None
_local_voice_loaded = False
_local_voice_error: str | None = None
_local_voice_lock = threading.Lock()

#: Piper is not safe to invoke concurrently on one voice instance; synthesis is
#: serialised the same way Whisper transcription is.
_tts_lock = threading.Lock()


def _load_local_voice():
    """Construct (once) and return the shared ``PiperVoice``.

    Raises :class:`TTSEngineUnavailable` with a server-side-only message when
    the voice file is missing or cannot be loaded.  The error is cached so
    repeated requests fail fast instead of retrying a broken load.
    """
    global _local_voice, _local_voice_loaded, _local_voice_error

    if _local_voice_loaded:
        if _local_voice_error:
            raise TTSEngineUnavailable(_local_voice_error)
        return _local_voice

    with _local_voice_lock:
        # Re-check inside the lock — another thread may have loaded it.
        if _local_voice_loaded:
            if _local_voice_error:
                raise TTSEngineUnavailable(_local_voice_error)
            return _local_voice

        model_path = local_tts_model_path()
        if not model_path.is_file():
            _local_voice_loaded = True
            _local_voice_error = (
                f"Local TTS voice not found at '{model_path}'. The provisioned "
                f"Piper voice must be present locally."
            )
            raise TTSEngineUnavailable(_local_voice_error)

        try:
            # Imported lazily: piper pulls in onnxruntime, which is slow to
            # import and only needed once speech is actually requested.
            from piper import PiperVoice

            _local_voice = PiperVoice.load(str(model_path), use_cuda=False)
            _local_voice_loaded = True
        except Exception as exc:
            _local_voice_loaded = True
            _local_voice_error = f"Failed to load the local TTS voice: {exc}"
            raise TTSEngineUnavailable(_local_voice_error) from exc

    return _local_voice


def _tts_synthesis_config(slow: bool):
    """Piper synthesis settings; ``slow`` becomes a longer phoneme duration."""
    from piper import SynthesisConfig

    return SynthesisConfig(length_scale=_TTS_SLOW_LENGTH_SCALE if slow else 1.0)


def _synthesize_local_speech_bytes(text: str, slow: bool) -> bytes:
    """Synthesize with the provisioned local voice and return WAV bytes."""
    voice = _load_local_voice()
    config = _tts_synthesis_config(slow)

    buffer = io.BytesIO()
    with _tts_lock:
        with wave.open(buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=config)

    audio = buffer.getvalue()
    if not audio:
        raise TTSEngineUnavailable("The local TTS voice produced no audio.")
    return audio


def _synthesize_gtts_bytes(text: str, language: str, slow: bool) -> bytes:
    """Generate speech audio using gTTS and return raw MP3 bytes.

    Executed in a worker thread via ``run_in_threadpool`` because gTTS makes a
    blocking synchronous HTTPS request to Google Translate.
    """
    from gtts import gTTS

    buffer = io.BytesIO()
    tts = gTTS(text=text, lang=language, slow=slow)
    tts.write_to_fp(buffer)
    return buffer.getvalue()


def _synthesize_speech_bytes(text: str, language: str, slow: bool) -> bytes:
    """Synthesize with the configured engine, or raise ``TTSEngineUnavailable``.

    The only dispatch point: no engine silently stands in for another one.
    """
    engine = tts_engine_name()
    if engine == _LOCAL_TTS_ENGINE_NAME:
        return _synthesize_local_speech_bytes(text, slow)
    if engine == _GTTS_ENGINE_NAME:
        return _synthesize_gtts_bytes(text, language, slow)
    raise TTSEngineUnavailable(f"Unknown TTS_ENGINE {_configured_engine()!r}")


@router.post("/synthesize")
async def synthesize(
    body: SynthesizeRequest,
    current_user: CurrentUser,
) -> Response:
    """Synthesize text into speech with the configured engine.

    ``TTS_ENGINE=local`` (default) returns WAV audio from the provisioned Piper
    voice with ``Content-Type: audio/wav``; ``TTS_ENGINE=gtts`` keeps the
    previous MP3 contract (``audio/mpeg``).  The media type and filename always
    describe the engine that actually ran.

    Security and reliability constraints:
    - Requires authenticated user via ``CurrentUser``.
    - Input text is bounded to 1..2000 characters and cannot be whitespace-only.
    - Audio is generated entirely in memory (zero persistent or temporary files).
    - An unavailable engine (missing local voice, unknown ``TTS_ENGINE``) is an
      honest HTTP 503 — never a silent fallback to the network, and never a
      fabricated audio response.
    - Upstream gTTS network/API failures return 503 without leaking internal
      URLs, tracebacks, or credentials.
    """
    # --- 1. Reject empty or whitespace-only text ---
    clean_text = body.text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty or whitespace only",
        )

    # --- 2. Enforce length bound ---
    if len(body.text) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text exceeds maximum length of 2000 characters",
        )

    # --- 3. Validate language code against the *configured* engine ---
    clean_lang = body.language.strip().lower()
    if not tts_supports_language(clean_lang):
        if tts_engine_name() == _LOCAL_TTS_ENGINE_NAME:
            # A local voice speaks one language; saying anything else is a
            # refusal, not an attempt in the wrong language.
            detail = (
                f"Unsupported language code: {body.language}. The local speech "
                f"voice speaks '{tts_language()}'; set TTS_ENGINE=gtts for other "
                "languages."
            )
        else:
            detail = f"Unsupported language code: {body.language}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    # --- 4. Synthesize speech in threadpool ---
    try:
        audio_bytes = await run_in_threadpool(
            _synthesize_speech_bytes, clean_text, clean_lang, body.slow
        )
    except HTTPException:
        raise
    except TTSEngineUnavailable:
        # Missing voice file, failed load, unknown engine: report it, never
        # substitute another engine (and never send an empty 200).
        logger.exception("Voice TTS engine unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text-to-speech engine is unavailable",
        )
    except ValueError as exc:
        logger.warning("gTTS validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported or invalid language code",
        )
    except Exception as exc:
        # Check for upstream network / gTTSError / RequestException
        from gtts.tts import gTTSError
        import requests

        if isinstance(
            exc,
            (gTTSError, requests.RequestException, TimeoutError, ConnectionError, OSError),
        ):
            logger.exception("Voice TTS upstream synthesis failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Voice synthesis service is unavailable",
            )

        logger.exception("Voice TTS synthesis unexpected failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text-to-speech synthesis failed",
        )

    if not audio_bytes:
        logger.error("The speech engine returned empty audio bytes")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice synthesis service returned empty audio",
        )

    media_type = tts_media_type()
    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="speech.{tts_file_suffix(media_type)}"'
        },
    )


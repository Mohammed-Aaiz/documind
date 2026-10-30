"""Silero voice-activity detection, offline, on the pinned ONNX Runtime.

Why this exists
---------------

The voice transport needs two decisions the browser cannot make honestly:

* when a spoken turn has finished (a natural pause, not a fixed recording
  length), and
* when the user starts speaking *while the assistant is talking*, which is the
  barge-in signal that must cancel the in-flight answer.

Both are made on the server from the actual audio frames, using the Silero VAD
model.  The model is **not** a network service: ``models/vad/silero_vad.onnx`` is
provisioned locally like the QA/TTS/Whisper weights, and inference runs on the
already-pinned ``onnxruntime`` CPU provider.  There is no torch, no torchaudio,
no CUDA and no external egress, so the 3 GB VRAM ceiling is unaffected.

The model is stateful at 16 kHz (the v5 ONNX export takes an explicit
``state`` tensor), which is why :class:`SileroVad` owns the state instead of
exposing a stateless helper: a per-frame call with fresh state detects nothing
useful.

Failure is explicit: a missing/invalid model raises :class:`VadUnavailable`
with the server-side reason, and the transport reports
``vad:"unavailable"`` instead of pretending to detect speech.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

#: Silero v5 operates on 16 kHz audio in 512-sample windows, each *prefixed*
#: with the previous 64 samples as context.  The reference wrapper builds a
#: 576-sample input (64 context + 512 new) and keeps the last 64 samples for the
#: next call; feeding 512 alone returns ~0.001 even for loud speech (measured
#: 2026-10-24 on the silero test corpus: 0.008 max vs 1.0 with the context).
SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 512
WINDOW_BYTES = WINDOW_SAMPLES * 2
CONTEXT_SAMPLES = 64

#: Default model location; provisioned beside the other local models.
DEFAULT_VAD_PATH = Path(__file__).resolve().parent / "models" / "vad" / "silero_vad.onnx"


class VadUnavailable(RuntimeError):
    """The VAD model cannot be used.  Never replaced by a fabricated decision."""


_session = None
_session_error: str | None = None
_session_loaded = False
_lock = threading.Lock()


def model_path() -> Path:
    """Resolve the provisioned VAD model path (configurable, never request input)."""
    from config import get_settings

    configured = (get_settings().vad_model_path or "").strip()
    return Path(configured) if configured else DEFAULT_VAD_PATH


def _load_session():
    """Load the ONNX VAD session once, or raise :class:`VadUnavailable`."""
    global _session, _session_error, _session_loaded

    if _session_loaded:
        if _session_error:
            raise VadUnavailable(_session_error)
        return _session

    with _lock:
        if _session_loaded:
            if _session_error:
                raise VadUnavailable(_session_error)
            return _session

        path = model_path()
        if not path.is_file():
            _session_loaded = True
            _session_error = (
                f"Silero VAD model not found at '{path}'. Provision "
                "models/vad/silero_vad.onnx (see models/README.md)."
            )
            raise VadUnavailable(_session_error)

        try:
            import onnxruntime as ort

            _session = ort.InferenceSession(
                str(path), providers=["CPUExecutionProvider"]
            )
            _session_loaded = True
        except Exception as exc:  # pragma: no cover - depends on the local model
            _session_loaded = True
            _session_error = f"Failed to load the Silero VAD model: {exc}"
            raise VadUnavailable(_session_error) from exc

    return _session


def is_available() -> bool:
    """Whether the VAD model can be loaded, without leaking its error."""
    try:
        _load_session()
        return True
    except VadUnavailable:
        return False


def vad_status() -> dict:
    """Honest capability report for the API / health surfaces."""
    try:
        _load_session()
    except VadUnavailable as exc:
        return {"engine": "silero-onnx", "available": False, "error": str(exc)}
    return {"engine": "silero-onnx", "available": True, "error": None}


class SileroVad:
    """Streaming Silero VAD over 16 kHz mono int16 frames.

    One instance belongs to one audio stream: the model's recurrent state is
    per-stream and must be reset (:meth:`reset`) when a new stream starts.
    """

    def __init__(self, *, threshold: float = 0.5) -> None:
        import numpy as np  # local import: tests of other paths need no numpy

        self.threshold = float(threshold)
        self._np = np
        self._session = _load_session()
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, CONTEXT_SAMPLES), dtype=np.float32)
        self._sr = np.array(SAMPLE_RATE, dtype=np.int64)
        self._pending = bytearray()

    def reset(self) -> None:
        """Forget the recurrent state (new stream / new utterance)."""
        self._state = self._np.zeros((2, 1, 128), dtype=self._np.float32)
        self._context = self._np.zeros((1, CONTEXT_SAMPLES), dtype=self._np.float32)

    def probability(self, window: bytes) -> float:
        """Speech probability for exactly one 512-sample int16 window."""
        if len(window) != WINDOW_BYTES:
            raise ValueError(
                f"Silero VAD expects {WINDOW_SAMPLES} samples ({WINDOW_BYTES} bytes), "
                f"got {len(window)} bytes"
            )
        samples = self._np.frombuffer(window, dtype=self._np.int16).astype(
            self._np.float32
        ) / 32768.0
        chunk = samples.reshape(1, -1)
        model_input = self._np.concatenate([self._context, chunk], axis=1)
        out, state = self._session.run(
            None,
            {
                "input": model_input,
                "state": self._state,
                "sr": self._sr,
            },
        )
        self._state = state
        self._context = model_input[..., -CONTEXT_SAMPLES:]
        return float(out[0][0])

    def feed(self, pcm16: bytes) -> list[tuple[bytes, float]]:
        """Consume arbitrary-length PCM, returning whole windows with probabilities.

        A trailing partial window is buffered until the next call; nothing is
        zero-padded silently, because padding invents silence that was not in the
        stream and would bias the decision.
        """
        self._pending.extend(pcm16)
        results: list[tuple[bytes, float]] = []
        while len(self._pending) >= WINDOW_BYTES:
            window = bytes(self._pending[:WINDOW_BYTES])
            del self._pending[:WINDOW_BYTES]
            results.append((window, self.probability(window)))
        return results

    def is_speech(self, window: bytes) -> bool:
        """Whether one window is speech at the configured threshold."""
        return self.probability(window) >= self.threshold


__all__ = [
    "CONTEXT_SAMPLES",
    "DEFAULT_VAD_PATH",
    "SAMPLE_RATE",
    "SileroVad",
    "VadUnavailable",
    "WINDOW_BYTES",
    "WINDOW_SAMPLES",
    "is_available",
    "model_path",
    "vad_status",
]

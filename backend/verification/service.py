"""Image-only Media Verification service.

Loads the provisioned local deepfake-detection model once per process and runs
real CPU inference.  Everything returned is model-derived; nothing is
fabricated.  When the model cannot be loaded an explicit unavailable error is
raised so the API can answer honestly.

Model:  prithivMLmods/Deep-Fake-Detector-v2-Model  (ViT, labels Realism/Deepfake)
Path:   <backend>/models/media-verification  (resolved relative to this file)
Load:   offline only (local_files_only=True); never downloads at request time.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from io import BytesIO
from pathlib import Path

# ---------------------------------------------------------------------------
# Model location / metadata
# ---------------------------------------------------------------------------

# backend/verification/service.py -> backend/verification -> backend
_BACKEND_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = _BACKEND_DIR / "models" / "media-verification"
_MANIFEST_PATH = MODEL_DIR / "MANIFEST.json"

# ---------------------------------------------------------------------------
# Upload validation limits
# ---------------------------------------------------------------------------

# Hard cap on decoded pixels and per-axis dimensions to defuse decompression
# bombs.  50 MP is comfortably above any normal photograph while bounding the
# memory a decode can allocate.
MAX_PIXELS = 50_000_000
MAX_DIMENSION = 20_000

# Detected format families (magic-byte based, NOT client-claimed).
_EXTENSION_FORMAT = {
    "png": "png",
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "gif": "gif",
    "bmp": "bmp",
    "webp": "webp",
}
_MIME_FORMAT = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/webp": "webp",
}

# CPU inference timeout.  Generous enough to cover the one-time model load on
# the first request, bounded so a pathological input cannot hang a worker.
INFERENCE_TIMEOUT_SECONDS = 30.0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MediaValidationError(Exception):
    """Uploaded media failed validation.  Carries an HTTP status + safe detail."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ModelUnavailableError(Exception):
    """The verification model could not be loaded (honest unavailability)."""


class InferenceError(Exception):
    """Inference failed unexpectedly (detail is server-log only)."""


# ---------------------------------------------------------------------------
# Lazy singleton model loading (thread-safe, once per process)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_processor = None
_model = None
_model_loaded = False
_model_load_error: str | None = None
_metadata: dict | None = None

# Serialize CPU inference so concurrent requests cannot multiply memory use.
_inference_semaphore = asyncio.Semaphore(1)


def _load_metadata() -> dict:
    """Return the provisioned model's recorded name/revision (cached)."""
    global _metadata
    if _metadata is not None:
        return _metadata
    try:
        with open(_MANIFEST_PATH, encoding="utf-8") as handle:
            manifest = json.load(handle)
        _metadata = {
            "name": str(manifest.get("model_name") or "unknown"),
            "version": str(manifest.get("revision") or "unknown"),
        }
    except Exception:
        _metadata = {"name": "unknown", "version": "unknown"}
    return _metadata


def get_model_metadata() -> dict:
    """Public accessor for the model name/revision reported in responses."""
    return dict(_load_metadata())


def _load_model() -> None:
    """Load processor + model once (thread-safe).  Raises ModelUnavailableError."""
    global _processor, _model, _model_loaded, _model_load_error

    if _model_loaded:
        if _model_load_error:
            raise ModelUnavailableError(_model_load_error)
        return

    with _lock:
        # Another thread may have completed loading while we waited.
        if _model_loaded:
            if _model_load_error:
                raise ModelUnavailableError(_model_load_error)
            return

        if not MODEL_DIR.exists():
            _model_load_error = (
                f"Media verification model not found at '{MODEL_DIR}'."
            )
            _model_loaded = True
            raise ModelUnavailableError(_model_load_error)

        try:
            # Imported lazily: torch/transformers are among the slowest imports
            # in the application (see chat/qa_model.py for the same rationale).
            from transformers import AutoImageProcessor, ViTForImageClassification

            _processor = AutoImageProcessor.from_pretrained(
                str(MODEL_DIR), local_files_only=True
            )
            _model = ViTForImageClassification.from_pretrained(
                str(MODEL_DIR), local_files_only=True
            )
            _model.eval()
        except Exception as exc:  # noqa: BLE001 - reported honestly, not leaked
            _model_loaded = True
            _model_load_error = (
                f"Media verification model failed to load: {type(exc).__name__}"
            )
            raise ModelUnavailableError(_model_load_error) from exc

        _model_loaded = True


def is_model_available() -> bool:
    """True when the model and processor are loaded and ready."""
    try:
        _load_model()
        return _model is not None and _processor is not None
    except ModelUnavailableError:
        return False


def get_model_status() -> dict:
    """Availability info for potential health reporting (no exception raised)."""
    try:
        _load_model()
        return {"available": True, "model_path": str(MODEL_DIR), "error": None}
    except ModelUnavailableError as exc:
        return {"available": False, "model_path": str(MODEL_DIR), "error": str(exc)}


# ---------------------------------------------------------------------------
# Content validation (no decoding yet; cheap byte-level checks)
# ---------------------------------------------------------------------------

def _detect_image_format(data: bytes) -> str | None:
    """Return the image format family from magic bytes, or None."""
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(data) >= 2 and data[:2] == b"BM":
        return "bmp"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def validate_image_upload(
    data: bytes,
    filename: str | None,
    content_type: str | None,
) -> str:
    """Validate an uploaded image at the byte/name level.

    Returns the detected format family.  Raises MediaValidationError with an
    HTTP status (400 for bad content, 415 for unsupported type) otherwise.
    The client-supplied MIME type is validated but never trusted over the
    actual magic bytes.
    """
    if not data:
        raise MediaValidationError(400, "Uploaded file is empty")

    # Extension allowlist.
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    if suffix not in _EXTENSION_FORMAT:
        allowed = ", ".join(sorted(f".{e}" for e in _EXTENSION_FORMAT))
        raise MediaValidationError(
            415,
            f"Unsupported file type '.{suffix}'. Allowed: {allowed}",
        )

    # Declared MIME (parameter-stripped) must be a known image type.
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in _MIME_FORMAT:
        raise MediaValidationError(415, "Unsupported media type")

    # Actual content must be a supported image.
    detected = _detect_image_format(data)
    if detected is None:
        raise MediaValidationError(400, "File is not a valid supported image")

    # Content must agree with the declared extension and MIME type.
    if _EXTENSION_FORMAT[suffix] != detected:
        raise MediaValidationError(400, "File content does not match its extension")
    if declared and _MIME_FORMAT[declared] != detected:
        raise MediaValidationError(400, "File content does not match its declared type")

    return detected


# ---------------------------------------------------------------------------
# Inference (runs in a worker thread)
# ---------------------------------------------------------------------------

def _predict_sync(data: bytes) -> dict:
    """Decode + preprocess + CPU inference.  Blocking; call from a thread."""
    from PIL import Image, UnidentifiedImageError

    _load_model()  # raises ModelUnavailableError if not loadable

    # Bound PIL's own decompression-bomb protection to our pixel cap.
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS

    started = time.perf_counter()
    try:
        with Image.open(BytesIO(data)) as img:
            width, height = img.size
            if width <= 0 or height <= 0:
                raise MediaValidationError(400, "Image has invalid dimensions")
            if (
                width > MAX_DIMENSION
                or height > MAX_DIMENSION
                or width * height > MAX_PIXELS
            ):
                raise MediaValidationError(
                    400, "Image dimensions exceed the supported limits"
                )

            rgb = img.convert("RGB")
            try:
                inputs = _processor(images=rgb, return_tensors="pt")

                import torch

                with torch.inference_mode():
                    logits = _model(**inputs).logits

                probs = torch.softmax(logits, dim=1)[0]
                index = int(torch.argmax(probs).item())
                score = float(probs[index].item())

                id2label = _model.config.id2label
                label = id2label.get(index, id2label.get(str(index)))
                if label is None:
                    raise InferenceError(
                        "Model produced a class with no corresponding label"
                    )
            finally:
                rgb.close()
    except MediaValidationError:
        raise
    except Image.DecompressionBombError as exc:
        raise MediaValidationError(
            400, "Image dimensions exceed the supported limits"
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        # Corrupt / truncated / undecodable image.
        raise MediaValidationError(400, "Uploaded file is not a valid image") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "verdict": label,
        "score": round(min(1.0, max(0.0, score)), 4),
        "width": int(width),
        "height": int(height),
        "elapsed_ms": elapsed_ms,
    }


async def analyze_image_bytes(data: bytes) -> dict:
    """Validate + classify an image on CPU without blocking the event loop.

    Raises MediaValidationError (bad media), ModelUnavailableError (no model),
    asyncio.TimeoutError (bounded inference), or InferenceError (unexpected).
    """
    loop = asyncio.get_running_loop()

    # Serialize inference; CPU-bound work runs in the default thread pool.
    async with _inference_semaphore:
        run = loop.run_in_executor(None, _predict_sync, data)
        result = await asyncio.wait_for(run, timeout=INFERENCE_TIMEOUT_SECONDS)
        return result

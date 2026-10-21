"""Image-only Media Verification API.

POST /api/verification/analyze accepts one authenticated image upload and
returns the real prediction of the provisioned local deepfake-detection model.
No persistence, no fabricated metrics: the verdict is the model's own label and
the score is its softmax probability for that label.
"""

import asyncio
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from auth.dependencies import CurrentUser
from config import get_settings
from verification.service import (
    InferenceError,
    MediaValidationError,
    ModelUnavailableError,
    analyze_image_bytes,
    get_model_metadata,
    validate_image_upload,
)

router = APIRouter(prefix="/api/verification", tags=["verification"])
logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class VerificationModelInfo(BaseModel):
    """Provenance for the model that produced the verdict."""

    name: str
    version: str


class VerificationProcessing(BaseModel):
    """Bounded processing metadata for the analysed upload."""

    bytes: int
    width: int
    height: int
    elapsedMs: int


class VerificationResultOut(BaseModel):
    """A real classification result — every field is model-derived."""

    available: bool = True
    verdict: str
    score: float
    model: VerificationModelInfo
    processing: VerificationProcessing


# ---------------------------------------------------------------------------
# POST /api/verification/analyze
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=VerificationResultOut)
async def analyze_media(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """Classify one uploaded image with the local media-verification model.

    Auth: JWT-derived (``CurrentUser``); unauthenticated requests get 401.
    Validation: size, extension, declared MIME and magic bytes — the client's
    MIME is checked but never trusted over the actual content.
    """
    # 1. Read a bounded number of bytes (never load an unbounded upload).
    max_bytes = settings.max_upload_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
        )

    # 2. Byte-level validation (raises MediaValidationError with a safe status).
    try:
        validate_image_upload(data, file.filename, file.content_type)
    except MediaValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    # 3. Inference (CPU, in a worker thread, bounded by a timeout).
    try:
        result = await analyze_image_bytes(data)
    except MediaValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ModelUnavailableError:
        # Honest unavailability — never a fabricated result.
        logger.error("Media verification model unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media verification model is unavailable",
        )
    except asyncio.TimeoutError:
        logger.error("Media verification inference timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Media verification timed out",
        )
    except InferenceError:
        logger.exception("Media verification inference failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Media verification failed",
        )
    except Exception:
        # Full detail is server-log only; the client never sees internals.
        logger.exception("Media verification unexpected failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Media verification failed",
        )

    metadata = get_model_metadata()
    return VerificationResultOut(
        verdict=result["verdict"],
        score=result["score"],
        model=VerificationModelInfo(
            name=metadata["name"],
            version=metadata["version"],
        ),
        processing=VerificationProcessing(
            bytes=len(data),
            width=result["width"],
            height=result["height"],
            elapsedMs=result["elapsed_ms"],
        ),
    )

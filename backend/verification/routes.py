from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/verification", tags=["verification"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class VerificationUnavailable(BaseModel):
    """Response when media verification is not yet implemented.

    The frontend must handle this honestly — no fabricated results.
    """
    status: str = "unavailable"
    message: str = "Media verification pipeline is not yet implemented."
    available: bool = False


# ---------------------------------------------------------------------------
# POST /api/verification/analyze
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=VerificationUnavailable,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def analyze_media():
    """Media file analysis for deepfake/synthetic content detection.

    Returns 501 Not Implemented — the analysis pipeline does not yet
    exist.  The frontend must not fabricate results in lieu of this.
    """
    return VerificationUnavailable()

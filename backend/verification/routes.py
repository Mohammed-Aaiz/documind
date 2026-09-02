from fastapi import APIRouter

router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.post("/analyze")
async def analyze_media():
    """Anze media file for deepfake/synthetic content detection."""
    # Phase 2: implement media analysis pipeline
    raise NotImplementedError("Media analysis not yet implemented")

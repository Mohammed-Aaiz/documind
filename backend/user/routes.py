from fastapi import APIRouter

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/profile")
async def get_profile():
    """Return the current user's profile."""
    # Phase 2: implement profile retrieval
    raise NotImplementedError("Profile retrieval not yet implemented")


@router.put("/profile")
async def update_profile():
    """Update the current user's profile."""
    # Phase 2: implement profile update
    raise NotImplementedError("Profile update not yet implemented")


@router.get("/preferences")
async def get_preferences():
    """Return the current user's settings/preferences."""
    # Phase 2: implement preferences retrieval
    raise NotImplementedError("Preferences retrieval not yet implemented")


@router.put("/preferences")
async def update_preferences():
    """Update the current user's settings/preferences."""
    # Phase 2: implement preferences update
    raise NotImplementedError("Preferences update not yet implemented")

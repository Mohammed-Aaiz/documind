"""
Settings API for DocuMind.

Provides user-scoped, persisted settings backed by PostgreSQL.

Endpoints:
  GET  /api/settings  — return the authenticated user's settings
  PATCH /api/settings — update permitted settings fields

All settings are user-scoped.  The user_id comes exclusively from the
authenticated JWT — the client cannot supply or override it.
"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from storage.database import get_db
from user.models import UserSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Allowed setting fields — explicit allowlist for PATCH updates
# ---------------------------------------------------------------------------

_ALLOWED_FIELDS: frozenset[str] = frozenset({
    "processing_depth",
    "context_window",
    "theme",
    "density",
    "glass_intensity",
})

_VALID_CONTEXT_WINDOWS: frozenset[str] = frozenset({
    "session",
    "24h",
    "persistent",
})

_VALID_THEMES: frozenset[str] = frozenset({
    "dark-cyber",
    "light",
})

_VALID_DENSITIES: frozenset[str] = frozenset({
    "standard",
    "high",
})


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SettingsResponse(BaseModel):
    """Response schema for GET /api/settings."""

    processingDepth: int = Field(description="AI analysis depth (1–5)")
    contextWindow: str = Field(description="Context memory window")
    theme: str = Field(description="Visual theme")
    density: str = Field(description="Data density")
    glassIntensity: int = Field(description="Glassmorphism blur intensity (0–100)")


class SettingsPatchRequest(BaseModel):
    """Request schema for PATCH /api/settings.

    All fields are optional.  Only explicitly supplied permitted fields
    are updated.  The user_id is always derived from authentication.
    """

    processingDepth: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="AI analysis depth (1–5)",
    )
    contextWindow: str | None = Field(
        default=None,
        description="Context memory window (session | 24h | persistent)",
    )
    theme: str | None = Field(
        default=None,
        description="Visual theme (dark-cyber | light)",
    )
    density: str | None = Field(
        default=None,
        description="Data density (standard | high)",
    )
    glassIntensity: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Glassmorphism blur intensity (0–100)",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_settings(
    db: AsyncSession, user_id: str
) -> UserSettings:
    """Return existing settings or create defaults for this user."""
    from uuid import UUID

    user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_uuid)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = UserSettings(user_id=user_uuid)
        db.add(settings)
        await db.flush()
        await db.refresh(settings)

    return settings


def _model_to_response(settings: UserSettings) -> SettingsResponse:
    """Map SQLAlchemy model → Pydantic response schema."""
    return SettingsResponse(
        processingDepth=settings.processing_depth,
        contextWindow=settings.context_window,
        theme=settings.theme,
        density=settings.density,
        glassIntensity=settings.glass_intensity,
    )


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------

@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's persisted settings.

    Creates default settings on first access.
    """
    settings = await _get_or_create_settings(db, str(current_user.id))
    return _model_to_response(settings)


# ---------------------------------------------------------------------------
# PATCH /api/settings
# ---------------------------------------------------------------------------

@router.patch("", response_model=SettingsResponse)
async def patch_settings(
    body: SettingsPatchRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's settings.

    Only explicitly supplied permitted fields are updated.
    Returns the full updated settings after applying changes.
    """
    settings = await _get_or_create_settings(db, str(current_user.id))

    # Apply each field if provided
    if body.processingDepth is not None:
        settings.processing_depth = body.processingDepth

    if body.contextWindow is not None:
        if body.contextWindow not in _VALID_CONTEXT_WINDOWS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid contextWindow: '{body.contextWindow}'. "
                       f"Must be one of: {sorted(_VALID_CONTEXT_WINDOWS)}",
            )
        settings.context_window = body.contextWindow

    if body.theme is not None:
        if body.theme not in _VALID_THEMES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid theme: '{body.theme}'. "
                       f"Must be one of: {sorted(_VALID_THEMES)}",
            )
        settings.theme = body.theme

    if body.density is not None:
        if body.density not in _VALID_DENSITIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid density: '{body.density}'. "
                       f"Must be one of: {sorted(_VALID_DENSITIES)}",
            )
        settings.density = body.density

    if body.glassIntensity is not None:
        settings.glass_intensity = body.glassIntensity

    await db.flush()
    await db.refresh(settings)

    return _model_to_response(settings)

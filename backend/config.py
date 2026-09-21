import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Known insecure default values that must never be used in production.
_INSECURE_SECRETS: frozenset[str] = frozenset({
    "change-me-in-production",
    "change-me-in-production-use-openssl-rand-hex-32",
    "",
})

# Sentinel: when no JWT_SECRET_KEY env var is set, pydantic-settings falls
# back to the class default.  We detect this and treat it as insecure.
_DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://documind:documind@localhost:5432/documind"

    # Auth
    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # File storage
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    # --- Chunking strategy (Phase 3D) --------------------------------------
    # "legacy" keeps the original 1000-char / 200-char chunker.  The
    # structure-aware candidate is "structure-v2".  The default is legacy so
    # production ingestion behaviour is unchanged until the candidate has
    # passed validation; see documents/chunking.py.
    chunker_version: str = "legacy"

    # --- Security helpers --------------------------------------------------

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def is_jwt_secret_insecure(self) -> bool:
        """Return True if the current JWT secret is a known insecure default."""
        return self.jwt_secret_key in _INSECURE_SECRETS

    def require_production_jwt_secret(self) -> None:
        """
        Raise if running in a non-development environment with an insecure
        JWT secret.  Development is detected by the presence of a
        ``DOCUMIND_DEV`` environment variable set to ``1`` or ``true``.

        In development the insecure default is allowed (with a warning) so
        that ``uvicorn main:app`` still works out of the box.
        """
        import os

        dev_mode = os.getenv("DOCUMIND_DEV", "").lower() in ("1", "true")

        if self.is_jwt_secret_insecure():
            if dev_mode:
                logger.warning(
                    "JWT_SECRET_KEY is using an insecure default value. "
                    "This is allowed in development mode (DOCUMIND_DEV=1). "
                    "Set a strong JWT_SECRET_KEY for production."
                )
            else:
                raise RuntimeError(
                    "JWT_SECRET_KEY is set to an insecure default value. "
                    "You MUST set a strong, unique JWT_SECRET_KEY in your "
                    ".env file or environment for non-development environments. "
                    "Example: openssl rand -hex 32"
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()

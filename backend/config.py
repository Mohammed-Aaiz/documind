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

# Known local development / preview frontend origins.  These are loopback-only
# (nothing is exposed beyond the local machine) and are used both as the
# default CORS allowlist and as a completeness safeguard for a partial loopback
# allowlist; see ``Settings.cors_origin_list``.
_LOCAL_DEV_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


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

    # CORS — comma-separated allowlist of frontend origins (never "*").
    # Development defaults cover the Vite dev server (port 3000), the Vite
    # default port (5173) and the Vite preview server (4173), through both the
    # ``localhost`` and ``127.0.0.1`` loopback hostnames — a browser may be
    # opened through either, and preflight succeeds only for an exact match.
    # Production MUST override this with the deployed frontend origin, e.g.
    #   CORS_ORIGINS=https://documind.vercel.app
    cors_origins: str = ",".join(_LOCAL_DEV_ORIGINS)

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
        """Return the allowlisted CORS origins, normalised and de-duplicated.

        Trailing slashes are stripped because the CORS spec compares the
        browser ``Origin`` header (which never carries a trailing slash)
        against these entries exactly.

        For any loopback origin (``localhost`` / ``127.0.0.1``) the other
        loopback spelling is added automatically.  A browser can reach the
        Vite dev server through either hostname, and CORS preflight succeeds
        only for an *exact* origin match, so ``http://localhost:3000`` in the
        allowlist must not reject ``http://127.0.0.1:3000``.  This never
        widens access beyond the local machine.
        """
        origins: list[str] = []

        def add(origin: str) -> None:
            origin = origin.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)

        for raw in self.cors_origins.split(","):
            add(raw)

        # Completeness safeguard for local development: if the configured
        # allowlist is local (contains a loopback origin) but partial, fill in
        # the project's known local Vite dev/preview origins.  A stale or
        # truncated CORS_ORIGINS value in `.env` must not silently break the
        # local frontend.  A production allowlist (non-loopback only) is left
        # exactly as configured — nothing non-loopback is ever added.
        if any(self._is_loopback(origin) for origin in origins):
            for origin in _LOCAL_DEV_ORIGINS:
                add(origin)

        # A browser may reach Vite through either loopback hostname, and CORS
        # preflight succeeds only for an *exact* Origin match.
        for origin in list(origins):
            counterpart = self._loopback_counterpart(origin)
            if counterpart:
                add(counterpart)

        return origins

    @staticmethod
    def _is_loopback(origin: str) -> bool:
        """Return True if ``origin``'s hostname is a loopback host."""
        from urllib.parse import urlsplit

        return urlsplit(origin).hostname in ("localhost", "127.0.0.1")

    @staticmethod
    def _loopback_counterpart(origin: str) -> str | None:
        """Return the opposite loopback hostname for ``origin``, if any."""
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(origin)
        if parts.hostname == "localhost":
            host = "127.0.0.1"
        elif parts.hostname == "127.0.0.1":
            host = "localhost"
        else:
            return None

        netloc = host if parts.port is None else f"{host}:{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))

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

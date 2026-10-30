import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator
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
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Shared deployment files may contain container-only settings. They
        # are not application fields; validation must not echo their values.
        extra="ignore",
        hide_input_in_errors=True,
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

    # --- Stateful conversation memory (Phase C) ----------------------------
    # Redis is the conversation-memory backend.  The URL is a normal Redis
    # DSN; nothing is guessed from it.  When Redis cannot be reached the
    # store reports that honestly (``backend="memory"``) and keeps the
    # conversation in process memory instead of pretending to be Redis.
    redis_url: str = "redis://localhost:6379/0"
    conversation_ttl_seconds: int = 86_400
    conversation_history_limit: int = 12
    #: Chat model for the stateful conversation graph.  Empty (the default)
    #: keeps the project's existing, provisioned generator; a value such as a
    #: provisioned ``Qwen/Qwen2.5-...-Instruct`` directory enables the
    #: instruct-model path in ``generation.causal``.  It is never assumed to
    #: be downloaded.
    conversation_model: str = ""

    # The product uses Groq for all LLM tasks. Historical local-adapter settings
    # remain available to evaluation code, but cannot select a production LLM.
    answer_provider: Literal["groq"] = "groq"
    answer_auto_fallback: bool = False
    ollama_timeout_seconds: float = Field(default=20.0, ge=1, le=120)
    groq_timeout_seconds: float = Field(default=30.0, ge=1, le=120)
    query_router_timeout_seconds: float = Field(default=3.0, ge=.5, le=10)
    query_router_enabled: bool = True
    # Optional image/text-aligned CLIP index. Only pre-provisioned local assets
    # are loaded; missing assets leave the text/graph pipeline operational.
    visual_embeddings_enabled: bool = True
    visual_model_path: str = str(Path(__file__).resolve().parent / "embeddings" / "assets" / "clip")
    visual_max_regions_per_page: int = Field(default=8, ge=1, le=8)
    visual_max_pages_per_document: int = Field(default=12, ge=1, le=32)
    visual_render_dpi: int = Field(default=96, ge=48, le=144)
    visual_embedding_batch_size: int = Field(default=2, ge=1, le=2)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = Field(default="llama3.2:3b", min_length=1, max_length=120)
    ollama_num_ctx: int = Field(default=2048, ge=1024, le=32768)
    ollama_num_thread: int = Field(default=4, ge=1, le=64)
    ollama_keep_alive: str = Field(default="5m", pattern=r"^(?:0|[1-9][0-9]{0,3}[smh])$")
    # Accept the existing installation's mislabeled secret without changing its
    # protected .env file. GROQ_API_KEY takes precedence over the legacy name;
    # GROQ_API_URL never changes the destination to which credentials are sent.
    groq_api_key: SecretStr = Field(
        default=SecretStr(""), repr=False, exclude=True,
        validation_alias=AliasChoices("groq_api_key", "GROQ_API_URL"),
    )
    groq_model: str = Field(default="openai/gpt-oss-20b", min_length=1, max_length=120)
    # Application input budget; this is deliberately below the hosted model's
    # capacity to bound retrieval/extraction cost and request latency. Student
    # prompt assembly further caps 5/10/15-mark requests at 8k/12k/16k tokens.
    groq_context_tokens: int = Field(default=16384, ge=2048, le=32768)
    answer_timeout_seconds: float = Field(default=120.0, ge=5, le=300)

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def validate_groq_api_key(cls, value: str | SecretStr) -> str:
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(secret, str):
            raise ValueError("Groq API key must be a string")
        secret = secret.strip()
        if secret.lower().startswith(("http://", "https://")):
            raise ValueError("Groq requires an API key, not a URL; set GROQ_API_KEY")
        return secret

    @field_validator("answer_auto_fallback")
    @classmethod
    def require_groq_only(cls, value: bool) -> bool:
        if value:
            raise ValueError("Automatic provider fallback is disabled; DocuMind uses Groq only")
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in {"", "/"}
        ):
            raise ValueError("Ollama must use a loopback HTTP URL without credentials or a path")
        return value.rstrip("/")

    # --- Voice text-to-speech ----------------------------------------------
    # "local" (default) synthesizes with the provisioned Piper voice: no
    # network, no VRAM, and the answer text stays on this machine.  "gtts" is
    # the previous Google Translate call and is opt-in only — there is no
    # automatic fallback between the two; a missing local voice is a 503.
    tts_engine: str = "local"
    #: Voice identifier from the Piper voice set; the artifact is provisioned
    #: as ``models/tts/<tts_voice>.onnx`` (git-ignored, like the other models).
    tts_voice: str = "en_US-ljspeech-medium"
    #: Explicit path to the ``.onnx`` voice file; empty resolves the default.
    tts_model_path: str = ""

    # --- Voice activity detection (Silero, ONNX, CPU) ----------------------
    # Server-side VAD decides when a spoken turn ends and when the user talks
    # over the answer (barge-in).  The model is provisioned locally beside the
    # other models and runs on onnxruntime: no network, no VRAM.
    vad_model_path: str = ""
    #: Probability above which a 512-sample window counts as speech.
    vad_threshold: float = 0.5
    #: Silence that ends a spoken turn.
    vad_silence_ms: int = 700
    #: Speech required before a turn is considered started (rejects clicks).
    vad_min_speech_ms: int = 200
    #: Longest single utterance kept for transcription (memory bound).
    webrtc_max_utterance_seconds: int = 60

    # --- OCR for pages with no text layer ---------------------------------
    # A scanned page (or the scanned pages of a mixed PDF) has no text layer;
    # the native extractor returns nothing for it.  The OCR fallback reads such
    # pages with a local engine so their content is searchable and citable.
    # "rapidocr" (default) uses the bundled PP-OCR models on the ONNX Runtime —
    # offline, CPU-only, no system binary.  "off" disables the fallback: pages
    # without a text layer are then reported unaccounted, exactly as before.
    # Engine choice and measurements: architecture/
    # DOCUMIND_OCR_ENGINE_DECISION_2026-10-24.md
    ocr_engine: str = "rapidocr"
    #: Render resolution for OCR.  300 dpi measured CER 0.000 on digital-quality
    #: scans; 150 dpi agreed on that corpus but lost a line on one page.
    ocr_dpi: int = 300
    #: Per-page and per-document ceilings, so a pathological scan cannot make
    #: ingestion run unbounded.  Measured cost is ~2.5-3 s/page.
    ocr_page_timeout_seconds: float = 25.0
    ocr_document_budget_seconds: float = 180.0

    # --- Chunking strategy (Phase 3D) --------------------------------------
    # New uploads preserve section/page boundaries and respect the embedding
    # encoder's token limit. Existing indexed documents keep their recorded
    # version until explicitly reprocessed; "legacy" remains a baseline option.
    chunker_version: str = "structure-v2"

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

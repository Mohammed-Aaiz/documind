import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from storage.database import Base, engine
from generation.providers import provider_status
from orchestration.service import conversation_status

# Import all models so Alembic can detect them
from auth.models import User  # noqa: F401
from documents.models import Document, DocumentChunk  # noqa: F401
from chat.models import ChatSession, ChatMessage  # noqa: F401
from verification.models import VerificationResult  # noqa: F401
from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
from user.models import UserSettings  # noqa: F401

# Import routers
from generation.routes import router as generation_router
from auth.routes import router as auth_router
from documents.routes import router as documents_router
from chat.routes import router as chat_router
from verification.routes import router as verification_router
from reliability.routes import router as reliability_router
from embeddings.routes import router as embeddings_router
from settings.routes import router as settings_router
from voice import router as voice_router
from conversation.routes import router as conversation_router
import voice_webrtc
from voice_webrtc import router as voice_webrtc_router

settings = get_settings()

logger = logging.getLogger(__name__)

# Backend package root, so Alembic is pointed at the right alembic.ini and
# script directory regardless of the process working directory.
_BACKEND_DIR = Path(__file__).resolve().parent


def _run_migrations() -> None:
    """Apply all pending Alembic migrations (sync; run in a worker thread).

    The Alembic environment (``migrations/env.py``) opens its own async engine
    and calls ``asyncio.run`` internally, so this must NOT be invoked from a
    thread that already owns a running event loop.
    """
    alembic_cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    command.upgrade(alembic_cfg, "head")


async def _ensure_database_schema() -> None:
    """Bring the configured database up to the latest migration revision.

    Runs before any model or service is used so the application can start
    against a fresh database.  Failure is fatal and reported explicitly:
    starting with an unmigrated schema would silently break every data path.
    """
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _run_migrations)
    except Exception as exc:
        logger.error("Database migration failed: %s", exc, exc_info=True)
        raise RuntimeError(
            "Database migration failed. The application cannot start with an "
            "out-of-date or unreachable database schema. See the server log "
            "for the underlying error."
        ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure the database schema exists and is current
    await _ensure_database_schema()
    # Startup: validate security configuration
    settings.require_production_jwt_secret()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    # Pay the local cross-encoder cold start once, before serving questions.
    from generation.reranking import warm_reranker
    reranker = await warm_reranker()
    logger.info("Reranker startup status: %s", reranker["status"])
    yield
    # Shutdown: end live WebRTC calls, then dispose the engine
    await voice_webrtc.close_all_sessions()
    await engine.dispose()


app = FastAPI(
    title="DocuMind API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    # Pydantic normally reflects rejected inputs (including passwords) in
    # validation responses. Clients need the field and reason, never the value.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]})

# CORS — allow the Vite dev server and preview server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(verification_router)
app.include_router(reliability_router)
app.include_router(embeddings_router)
app.include_router(settings_router)
app.include_router(voice_router)
app.include_router(generation_router)
app.include_router(conversation_router)
# Full-duplex voice conversation (WebRTC) — same conversation service as the
# text API, so voice and text share one history.  The old WebSocket transport
# was removed when this replaced it; there is one voice transport.
app.include_router(voice_webrtc_router)


@app.get("/api/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "documind-api",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "qa_model": {
            "available": False,
            "role": "retired",
            "error": "The product uses the Groq answer provider.",
        },
        # Liveness reports configuration without loading or probing a model.
        # Authenticated conversation/status can perform a bounded local probe.
        "generator": provider_status(),
        "conversation": await conversation_status(),
    }

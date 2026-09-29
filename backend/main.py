import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from storage.database import Base, engine
from chat.qa_model import get_model_status

# Import all models so Alembic can detect them
from auth.models import User  # noqa: F401
from documents.models import Document, DocumentChunk  # noqa: F401
from chat.models import ChatSession, ChatMessage  # noqa: F401
from verification.models import VerificationResult  # noqa: F401
from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
from user.models import UserSettings  # noqa: F401

# Import routers
from auth.routes import router as auth_router
from documents.routes import router as documents_router
from chat.routes import router as chat_router
from verification.routes import router as verification_router
from reliability.routes import router as reliability_router
from user.routes import router as user_router
from embeddings.routes import router as embeddings_router
from settings.routes import router as settings_router

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
    yield
    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(
    title="DocuMind API",
    version="1.0.0",
    lifespan=lifespan,
)

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
app.include_router(user_router)
app.include_router(embeddings_router)
app.include_router(settings_router)


@app.get("/api/health", tags=["health"])
async def health_check():
    qa_status = get_model_status()
    return {
        "status": "healthy",
        "service": "documind-api",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "qa_model": {
            "available": qa_status["available"],
            "path": qa_status["model_path"],
            "error": qa_status["error"],
        },
    }

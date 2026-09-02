from contextlib import asynccontextmanager
from datetime import datetime, timezone

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

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create upload directory
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

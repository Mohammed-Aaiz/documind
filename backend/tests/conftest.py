"""Pytest fixtures for backend tests.

Uses an in-memory SQLite database to avoid requiring a running PostgreSQL
instance during the test suite.  PostgreSQL-specific column types (UUID)
are transparently replaced with String for compatibility.
"""

import asyncio
import uuid
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, types
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Patch storage.database so every module that imports get_db / engine / Base
# receives the SQLite-backed versions during tests.
# ---------------------------------------------------------------------------

import storage.database as _db_module

# We will build everything here and patch at module level before the app is
# first imported.

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Type helpers – map PostgreSQL UUID to plain String so SQLite is happy.
# ---------------------------------------------------------------------------

class _StringUUID(types.TypeDecorator):
    """Transparent String-based UUID for SQLite compatibility."""
    impl = types.String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


def _patch_uuid_columns():
    """Monkey-patch the UUID columns on every model so SQLite can store them."""
    from auth.models import User
    from documents.models import Document, DocumentChunk
    from chat.models import ChatSession, ChatMessage
    from verification.models import VerificationResult
    from reliability.models import SourceRef
    from user.models import UserSettings

    for model in (User, Document, DocumentChunk, ChatSession, ChatMessage,
                  VerificationResult, SourceRef, UserSettings):
        for col in model.__table__.columns:
            if isinstance(col.type, postgresql.UUID):
                col.type = _StringUUID()
                col._user_defined_foreign_key = col.foreign_keys  # preserve FKs


# ---------------------------------------------------------------------------
# Async event-loop fixture (session-scoped so the engine lives across tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def _test_engine():
    """Create an async SQLite engine (session-scoped)."""
    engine = create_async_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def _create_tables(_test_engine):
    """Create all tables once for the whole test session."""
    _patch_uuid_columns()
    from storage.database import Base

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(_test_engine, _create_tables) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional session that is rolled back after each test."""
    async with _test_engine.connect() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI app fixture (overrides get_db dependency)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app(_test_engine, _create_tables):
    """Return a FastAPI test app with DB dependency overridden."""
    from main import app as real_app
    from storage.database import get_db

    async def _override_get_db():
        async with async_sessionmaker(
            _test_engine, class_=AsyncSession, expire_on_commit=False
        )() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    real_app.dependency_overrides[get_db] = _override_get_db
    yield real_app
    real_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: create a user in the test database
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def create_test_user(db_session: AsyncSession):
    """Factory fixture – call with email/password/name to insert a user."""

    async def _factory(
        email: str = "test@example.com",
        password: str = "SecureP@ss123",
        name: str = "Test User",
        is_active: bool = True,
    ):
        from auth.models import User
        from passlib.context import CryptContext

        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name,
            hashed_password=pwd_ctx.hash(password),
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _factory

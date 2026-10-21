"""Pytest fixtures for backend tests.

Uses an in-memory SQLite database to avoid requiring a running PostgreSQL
instance during the test suite.

SQLite compatibility is provided by *dialect-scoped type rules* instead of by
rewriting production column types.  The production ORM models keep defining
PostgreSQL ``UUID`` and ``JSONB`` columns, and those definitions remain the
single authoritative source in ``Base.metadata``:

* ``postgresql.UUID`` compiles natively to ``UUID`` on PostgreSQL.  SQLite has
  no UUID type, so SQLAlchemy already converts values to and from
  :class:`uuid.UUID` using 32-character hex; the SQLite rules below declare the
  column as ``CHAR(32)`` so the declared type matches that representation
  (instead of ``UUID``, which would give the column SQLite's NUMERIC affinity),
  and accept a canonical UUID *string* because PostgreSQL does — production
  routes pass ``str(current_user.id)`` straight into UUID comparisons.
* ``postgresql.JSONB`` compiles natively to ``JSONB`` on PostgreSQL and has no
  SQLite renderer at all (its bind/result handling already falls back to the
  generic ``JSON`` behaviour off PostgreSQL), so the SQLite rule below renders
  the column as SQLite's ``JSON``.

Every rule is scoped to SQLite — ``@compiles`` dispatch is by visit name plus
dialect, and the ``colspecs`` mapping is installed on the one SQLite test
engine's dialect instance — so PostgreSQL compilation is untouched.  Nothing in
this module mutates ``Base.metadata``, ``Table`` or ``Column`` objects: a real
PostgreSQL test running later in the same pytest process — in any collection
order — sees the genuine production metadata and types.

``PRAGMA foreign_keys=ON`` is mandatory, not cosmetic: SQLite disables
foreign-key enforcement by default, while PostgreSQL (the real database)
enforces it.  Without this pragma every ``ON DELETE CASCADE`` — including
``document_graph_edges`` — silently does nothing, so a cascade test would pass
or fail for the wrong reason.
"""

import asyncio
import uuid
from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


SQLITE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# SQLite dialect compatibility rules.
#
# Registered for the ``sqlite`` dialect only, so PostgreSQL compilation (and
# every production ``Table``/``Column`` object) is untouched.  This replaces
# the previous approach of rewriting ``col.type`` on the shared production
# tables, which leaked into every later test in the pytest process.
# ---------------------------------------------------------------------------

@compiles(postgresql.UUID, "sqlite")
def _render_uuid_as_char32_on_sqlite(type_, compiler, **kw):
    """Declare ``UUID`` as ``CHAR(32)`` on SQLite, matching SQLAlchemy's hex emulation."""
    return "CHAR(32)"


@compiles(postgresql.JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(type_, compiler, **kw):
    """Render ``JSONB`` as SQLite's ``JSON`` storage class (SQLite has no JSONB)."""
    return "JSON"


class _SQLiteUUID(postgresql.UUID):
    """SQLite stand-in for ``UUID``; accepts the same values PostgreSQL does.

    PostgreSQL stores ``uuid.UUID`` and also accepts its canonical string form,
    and production code relies on that (``ReliabilityLog.user_id ==
    str(current_user.id)``).  SQLAlchemy's SQLite emulation only accepts
    :class:`uuid.UUID`, so coerce a canonical string first and leave everything
    else — including the rejection of a malformed id — to the inherited
    implementation, which is what PostgreSQL does too.  The DDL declaration
    comes from the ``@compiles`` rule above, which also dispatches for this
    subclass.
    """

    def bind_processor(self, dialect):
        parent = super().bind_processor(dialect)

        def process(value):
            if isinstance(value, str):
                value = uuid.UUID(value)
            return parent(value) if parent is not None else value

        return process


def _apply_sqlite_type_mapping(engine) -> None:
    """Map PostgreSQL-only types onto this SQLite engine's dialect only.

    ``dialect.colspecs`` is the SQLAlchemy hook that resolves a type to its
    dialect-specific implementation, and it is read per dialect *instance*.
    Replacing it here scopes the mapping to this one test engine: no other
    engine, and no production ``Table``/``Column`` object, is affected.  (A
    class-level edit on ``SQLiteDialect`` would not even apply — the pysqlite
    dialect builds its own copy of the mapping.)
    """
    dialect = engine.sync_engine.dialect
    dialect.colspecs = {**dialect.colspecs, postgresql.UUID: _SQLiteUUID}


def _register_all_models():
    """Import every model module so ``Base.metadata`` holds the whole schema.

    Mirrors ``migrations/env.py``.  ``create_all`` must create the complete
    schema no matter which test module happened to be collected first, so the
    imports cannot be left implicit to unrelated test files.
    """
    import auth.models  # noqa: F401
    import chat.models  # noqa: F401
    import documents.models  # noqa: F401
    import graph.models  # noqa: F401
    import reliability.models  # noqa: F401
    import user.models  # noqa: F401
    import verification.models  # noqa: F401


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
    """Create an async SQLite engine (session-scoped) with the type mapping."""
    engine = create_async_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _apply_sqlite_type_mapping(engine)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def _create_tables(_test_engine):
    """Create all tables once for the whole test session."""
    _register_all_models()
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

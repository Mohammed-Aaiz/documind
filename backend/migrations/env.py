import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure the backend package root is importable no matter where Alembic is
# invoked from.  Without this, ``from storage.database import Base`` fails when
# the console script is used (``alembic upgrade head``) because the backend
# directory is not automatically placed on sys.path.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models so Alembic can detect them
from storage.database import Base
from auth.models import User  # noqa: F401
from documents.models import Document, DocumentChunk  # noqa: F401
from chat.models import ChatSession, ChatMessage  # noqa: F401
from verification.models import VerificationResult  # noqa: F401
from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
from user.models import UserSettings  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at the application's configured database (settings / .env)
# instead of the placeholder URL hard-coded in alembic.ini, so `alembic` and
# the running app always target the same database.  The asyncpg `sslmode`
# translation is reused so managed-Postgres URLs behave identically here.
_DATABASE_URL = config.get_main_option("sqlalchemy.url")
_CONNECT_ARGS: dict = {}
try:
    from config import get_settings
    from storage.database import _asyncpg_engine_args

    _DATABASE_URL, _CONNECT_ARGS = _asyncpg_engine_args(get_settings().database_url)
except Exception:
    # Settings unavailable or malformed: keep the alembic.ini value unchanged.
    pass

if _DATABASE_URL:
    config.set_main_option("sqlalchemy.url", _DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_CONNECT_ARGS,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

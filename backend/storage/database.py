from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()


def _asyncpg_engine_args(database_url: str) -> tuple[str, dict]:
    """Translate a libpq-style ``sslmode`` query param for asyncpg.

    Managed Postgres providers (Supabase, Render, Heroku, ...) commonly hand
    out URLs such as ``postgresql+asyncpg://...?sslmode=require``.  asyncpg's
    ``connect()`` has no ``sslmode`` keyword, so passing the URL through
    unchanged fails at connect time with::

        TypeError: connect() got an unexpected keyword argument 'sslmode'

    asyncpg *does* accept the equivalent libpq TLS modes through its ``ssl``
    argument, so move the value across rather than dropping it.

    Returns the ``(url, connect_args)`` pair to build the engine with.
    """
    if not database_url.startswith("postgresql+asyncpg"):
        return database_url, {}

    parts = urlsplit(database_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    if sslmode is None:
        return database_url, {}

    cleaned_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    return cleaned_url, {"ssl": sslmode}


_database_url, _connect_args = _asyncpg_engine_args(settings.database_url)

engine = create_async_engine(
    _database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

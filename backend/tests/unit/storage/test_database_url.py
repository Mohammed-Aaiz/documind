"""Regression tests for asyncpg ``DATABASE_URL`` normalisation.

Managed Postgres providers hand out URLs with a libpq-style
``?sslmode=require`` query param.  asyncpg's ``connect()`` rejects that
keyword with::

    TypeError: connect() got an unexpected keyword argument 'sslmode'

so ``storage.database`` must move it across to the ``ssl`` argument.
"""

from storage.database import _asyncpg_engine_args


def test_sslmode_is_moved_to_connect_args():
    url, args = _asyncpg_engine_args(
        "postgresql+asyncpg://u:p@host:5432/db?sslmode=require"
    )
    assert url == "postgresql+asyncpg://u:p@host:5432/db"
    assert args == {"ssl": "require"}


def test_other_query_params_are_preserved():
    url, args = _asyncpg_engine_args(
        "postgresql+asyncpg://u:p@host:5432/db?sslmode=require&application_name=documind"
    )
    assert "sslmode" not in url
    assert "application_name=documind" in url
    assert args == {"ssl": "require"}


def test_url_without_sslmode_is_unchanged():
    original = "postgresql+asyncpg://u:p@host:5432/db"
    url, args = _asyncpg_engine_args(original)
    assert url == original
    assert args == {}


def test_non_asyncpg_url_is_unchanged():
    original = "sqlite+aiosqlite:///:memory:"
    url, args = _asyncpg_engine_args(original)
    assert url == original
    assert args == {}

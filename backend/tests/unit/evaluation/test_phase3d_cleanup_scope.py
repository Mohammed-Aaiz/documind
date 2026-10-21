"""Regression tests for the Phase 3D upload/ask harness cleanup boundary.

The harness used to end a run with an **unscoped** ``DELETE FROM
document_chunks``.  Pointed at an isolated database that is shared with another
experiment (or re-used between runs), that statement removes every chunk in the
database, not just the ones the harness created.  Database isolation proves the
target is not the application database; it does not make a database-wide delete
safe, so the deletion now runs through :func:`cleanup_harness_rows`, scoped by
the ownership key the schema actually has:

* ``documents.user_id`` -> ``users.id`` (``ondelete="CASCADE"``);
* ``document_chunks.document_id`` -> ``documents.id`` (``ondelete="CASCADE"``).

These tests are behavioural: they seed real rows through the project's SQLite
fixtures (``tests/conftest.py``) using the shared builders in
``tests/fixtures/graph_data.py`` and then run the real cleanup function.  Nothing
here connects to PostgreSQL or to the application database.

Destructive expectations in this module are either refusal-assertions or marked
``requires_disposable_database``: the lifecycle gate refuses cleanup by design,
so a destructive-success expectation cannot hold and must not be faked.  See
``tests/fixtures/disposable_db.py``.
"""

from __future__ import annotations

import ast
import inspect
import re

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext import asyncio as sqlalchemy_asyncio

from auth.models import User
from documents.models import Document, DocumentChunk
from evaluation import isolation
from evaluation.experiments import run_phase3d_upload_integration as harness
from reliability.models import ReliabilityLog
from tests.fixtures import graph_data
from tests.fixtures.disposable_db import requires_disposable_database

#: A fake application DSN: the guard tests never dial it.
APPLICATION = "postgresql+asyncpg://documind:app-secret@127.0.0.1:55433/documind"


async def _seed(db, email: str, *, document_name: str, chunk_contents: tuple[str, ...]):
    """Insert one user, one document, its chunks and one reliability log."""
    user = await graph_data.create_test_user(db, email)
    document, chunks = await graph_data.create_document_with_chunks(
        db,
        user.id,
        name=document_name,
        chunks=[{"content": content} for content in chunk_contents],
    )
    db.add(ReliabilityLog(user_id=user.id))
    await db.flush()
    return user, document, chunks


async def _count(db, model, **criteria) -> int:
    statement = select(func.count()).select_from(model)
    for column, value in criteria.items():
        statement = statement.where(getattr(model, column) == value)
    return int((await db.execute(statement)).scalar_one())


async def _chunk_contents(db, document_id) -> list[str]:
    rows = (
        await db.execute(
            select(DocumentChunk.content).where(DocumentChunk.document_id == document_id)
        )
    ).scalars()
    return sorted(rows)


# ---------------------------------------------------------------------------
# A / B — owned records are removed, unrelated records survive
# ---------------------------------------------------------------------------


class TestCleanupScope:
    @requires_disposable_database
    async def test_owned_records_are_removed(self, db_session):
        owner, document, _chunks = await _seed(
            db_session,
            "phase3d_upload_owner@test.local",
            document_name="owner.txt",
            chunk_contents=("owner chunk one", "owner chunk two"),
        )

        await harness.cleanup_harness_rows(db_session, user_id=owner.id)

        assert await _count(db_session, ReliabilityLog, user_id=owner.id) == 0
        assert await _count(db_session, DocumentChunk, document_id=document.id) == 0
        assert await _count(db_session, Document, user_id=owner.id) == 0
        assert await _count(db_session, User, id=owner.id) == 0

    async def test_unrelated_records_survive_untouched(self, db_session):
        owner, owner_document, _owner_chunks = await _seed(
            db_session,
            "phase3d_upload_owner@test.local",
            document_name="owner.txt",
            chunk_contents=("owner chunk one",),
        )
        other, other_document, other_chunks = await _seed(
            db_session,
            "unrelated_experiment@test.local",
            document_name="unrelated.txt",
            chunk_contents=("unrelated one", "unrelated two", "unrelated three"),
        )

        # STEP 1.6X: destructive cleanup is refused by design; the property
        # asserted here is that the refusal mutates nothing.
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await harness.cleanup_harness_rows(db_session, user_id=owner.id)

        # The other experiment's rows are all still there, unchanged.
        assert await _count(db_session, User, id=other.id) == 1
        assert await _count(db_session, ReliabilityLog, user_id=other.id) == 1
        assert await _count(db_session, Document, user_id=other.id) == 1
        assert await _count(db_session, DocumentChunk, document_id=other_document.id) == 3
        assert await _chunk_contents(db_session, other_document.id) == [
            "unrelated one",
            "unrelated three",
            "unrelated two",
        ]
        surviving_ids = set(
            (
                await db_session.execute(
                    select(DocumentChunk.id).where(
                        DocumentChunk.document_id == other_document.id
                    )
                )
            ).scalars()
        )
        assert surviving_ids == {chunk.id for chunk in other_chunks}

        # …and the owner's own rows are untouched too: the refusal mutated nothing.
        assert await _count(db_session, User, id=owner.id) == 1
        assert await _count(db_session, ReliabilityLog, user_id=owner.id) == 1
        assert await _count(db_session, Document, user_id=owner.id) == 1
        assert await _count(db_session, DocumentChunk, document_id=owner_document.id) == 1

    @requires_disposable_database
    async def test_ownership_is_the_key_not_the_document_name_or_chunk_text(self, db_session):
        """Identical names and identical chunk text must not decide deletion."""
        owner, _owner_document, _owner_chunks = await _seed(
            db_session,
            "phase3d_upload_owner@test.local",
            document_name="shared-name.txt",
            chunk_contents=("identical chunk text",),
        )
        other, other_document, _other_chunks = await _seed(
            db_session,
            "unrelated_experiment@test.local",
            document_name="shared-name.txt",
            chunk_contents=("identical chunk text",),
        )

        await harness.cleanup_harness_rows(db_session, user_id=owner.id)

        assert await _count(db_session, Document, user_id=other.id) == 1
        assert await _chunk_contents(db_session, other_document.id) == [
            "identical chunk text"
        ]
        assert await _count(db_session, Document, user_id=owner.id) == 0

    async def test_repeated_cleanup_is_safe_and_does_not_spread(self, db_session):
        owner, owner_document, _owner_chunks = await _seed(
            db_session,
            "phase3d_upload_owner@test.local",
            document_name="owner.txt",
            chunk_contents=("owner chunk one",),
        )
        other, other_document, _other_chunks = await _seed(
            db_session,
            "unrelated_experiment@test.local",
            document_name="unrelated.txt",
            chunk_contents=("unrelated one", "unrelated two"),
        )

        # STEP 1.6X: destructive cleanup is refused by design; the property
        # asserted here is that the refusal mutates nothing.  Repeating the
        # attempt must behave identically — it never spreads to other rows.
        for _attempt in range(2):
            with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
                await harness.cleanup_harness_rows(db_session, user_id=owner.id)

        assert await _count(db_session, User, id=owner.id) == 1
        assert await _count(db_session, Document, user_id=owner.id) == 1
        assert await _count(db_session, DocumentChunk, document_id=owner_document.id) == 1
        assert await _count(db_session, Document, user_id=other.id) == 1
        assert await _count(db_session, DocumentChunk, document_id=other_document.id) == 2

    @requires_disposable_database
    async def test_cleaning_up_one_user_never_touches_a_second_one(self, db_session):
        first, first_document, _ = await _seed(
            db_session,
            "phase3d_upload_first@test.local",
            document_name="first.txt",
            chunk_contents=("first chunk",),
        )
        second, second_document, _ = await _seed(
            db_session,
            "phase3d_upload_second@test.local",
            document_name="second.txt",
            chunk_contents=("second chunk",),
        )

        await harness.cleanup_harness_rows(db_session, user_id=first.id)

        assert await _count(db_session, Document, user_id=first.id) == 0
        assert await _count(db_session, DocumentChunk, document_id=first_document.id) == 0
        assert await _count(db_session, Document, user_id=second.id) == 1
        assert await _count(db_session, DocumentChunk, document_id=second_document.id) == 1


# ---------------------------------------------------------------------------
# D (secondary) — the unscoped statement is gone, and every remaining raw
# delete carries its own WHERE clause
# ---------------------------------------------------------------------------


def _raw_sql_statements() -> list[str]:
    """Every ``text("...")`` literal in the harness, joined across line breaks."""
    tree = ast.parse(inspect.getsource(harness))
    statements: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "text":
            statements.append(
                "".join(
                    part.value
                    for part in node.args
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                )
            )
    return statements


class TestNoUnscopedDeleteRemains:
    def test_the_unscoped_chunk_delete_is_gone(self):
        source = inspect.getsource(harness)
        assert 'DELETE FROM document_chunks")' not in source
        assert 'text("DELETE FROM document_chunks")' not in source

    def test_every_raw_sql_delete_is_scoped_by_a_predicate(self):
        deletes = [sql for sql in _raw_sql_statements() if "DELETE FROM" in sql]
        assert deletes, "the email-scoped cleanups must still be raw SQL"
        for statement in deletes:
            assert "WHERE" in statement.upper(), statement

    def test_the_only_chunk_delete_is_keyed_on_document_ownership(self):
        chunk_deletes = [
            sql for sql in _raw_sql_statements() if "DELETE FROM document_chunks" in sql
        ]
        for statement in chunk_deletes:
            assert "document_id IN" in statement, statement

    def test_cleanup_uses_the_ownership_key_and_not_a_bare_table_delete(self):
        source = inspect.getsource(harness.cleanup_harness_rows)
        assert "Document.user_id" in source
        assert "DocumentChunk.document_id.in_(owned_documents)" in source
        assert "ReliabilityLog.user_id" in source
        assert "User.id" in source


# ---------------------------------------------------------------------------
# E — database isolation still guards the destructive work
# ---------------------------------------------------------------------------


class TestIsolationGuardStillPrecedesCleanup:
    async def test_no_explicit_target_is_refused_before_any_engine(self, monkeypatch):
        monkeypatch.setattr(harness, "application_database_url", lambda: APPLICATION)
        monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
        seen: list[str] = []
        real = sqlalchemy_asyncio.create_async_engine

        def factory(dsn, *args, **kwargs):
            seen.append(dsn)
            return real(dsn, *args, **kwargs)

        monkeypatch.setattr(sqlalchemy_asyncio, "create_async_engine", factory)

        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            await harness.main([])

        assert seen == [], "the harness must be refused before any engine exists"
        assert "app-secret" not in str(exc.value)

    async def test_application_database_is_refused_as_an_explicit_target(self, monkeypatch):
        monkeypatch.setattr(harness, "application_database_url", lambda: APPLICATION)
        monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
        seen: list[str] = []
        monkeypatch.setattr(
            sqlalchemy_asyncio,
            "create_async_engine",
            lambda dsn, *args, **kwargs: seen.append(dsn),
        )

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await harness.main(["--database-url", APPLICATION])

        assert seen == []

    def test_the_guard_call_precedes_the_cleanup_call_in_the_source(self):
        source = inspect.getsource(harness)
        assert source.index("assert_safe_evaluation_target(") < source.index(
            "cleanup_harness_rows(db, user_id=user_id)"
        )
        assert source.index('os.environ["DATABASE_URL"] = evaluation_dsn') < source.index(
            "cleanup_harness_rows(db, user_id=user_id)"
        )


# ---------------------------------------------------------------------------
# F — the evaluation surface is unchanged
# ---------------------------------------------------------------------------


class TestEvaluationSurfaceUnchanged:
    def test_check_count_is_unchanged(self):
        source = inspect.getsource(harness)
        assert len(re.findall(r"^\s*check\(", source, flags=re.MULTILINE)) == 40

    def test_checks_json_payload_shape_is_unchanged(self):
        source = inspect.getsource(harness)
        for key in ('"runId"', '"checks"', '"passed"', '"failed"'):
            assert key in source, key
        assert '"checks.json"' in source
        assert "write_manifest(" in source
        assert "MANIFEST_NAME" in source

    def test_run_restores_the_production_chunker_default(self):
        assert (
            "documents_routes.settings.chunker_version = default_version"
            in inspect.getsource(harness)
        )

    async def test_entry_points_and_flags_still_behave(self):
        args = harness.parse_args([])
        assert args.database_url is None
        assert args.out is None
        assert harness.parse_args(["--out", "run-1"]).out == "run-1"
        assert harness.parse_args(["--database-url", "postgresql+asyncpg://h:1/d"]).database_url
        assert inspect.iscoroutinefunction(harness.main)
        assert inspect.iscoroutinefunction(harness.cleanup_harness_rows)

    def test_result_schema_documents_the_guard_and_the_scope(self):
        source = inspect.getsource(harness)
        assert "scoped to its own evaluation user" in source
        assert "including an unscoped" not in source

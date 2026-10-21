"""Regression tests for the Phase 3E integration harness's cleanup boundary.

``run_phase3e_integration.py`` used to run four **raw SQL** deletes, three of them
in its final cleanup block::

    await db.execute(text("DELETE FROM reliability_logs WHERE user_id = :u"), {"u": str(user_id)})
    await db.execute(text("DELETE FROM document_chunks"))            # ← unscoped
    await db.execute(text("DELETE FROM documents WHERE user_id = :u"), {"u": str(user_id)})
    await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})

plus ``DELETE FROM users WHERE email = :e`` (step 8) and
``DELETE FROM document_chunks WHERE document_id = :id`` /
``DELETE FROM documents WHERE id = :id`` (step 9).

The second statement carries **no predicate**: it removes every row of
``document_chunks`` in whatever database the harness targets — every owner, every
document, every chunk — including rows belonging to other experiments that share
the same isolated database.  Database isolation proves the target is not the
application database; it does not make a database-wide delete safe.

Ownership, proven from the schema and the runner's execution flow, is the two
users the harness creates:

* ``user_id`` — ``phase3e_<8 hex>@test.local``, the one user the harness uploads
  through the real API as; every document and chunk it creates hangs off it
  (``documents.user_id`` -> ``users.id``, ``document_chunks.document_id`` ->
  ``documents.id``), and ``/api/chat/ask`` writes a ``reliability_logs`` row for
  it through ``store_query_reliability``;
* the temporary isolation-check user ``phase3e_other_<8 hex>@test.local``, which
  only exists to prove that a second user retrieves nothing (step 8).

Neither child table (``document_chunks``, ``chat_messages``) has an owner column,
so its owner is reached through ``documents`` / ``chat_sessions``.  That is what
makes a user-id set the narrowest correct scope.

These tests are behavioural: they seed real rows through the project's SQLite
fixtures and the shared builders in ``tests/fixtures/graph_data.py``, then run the
real ``owned_user_ids`` / ``cleanup_harness_rows`` functions.  Nothing here
connects to PostgreSQL or to the application database.

Destructive expectations are now either refusal-assertions -- the cleanup refuses
``before`` it mutates anything, which is the property asserted -- or marked
``requires_disposable_database`` when they can only hold once a genuine
connection-bound lifecycle authorization exists (STEP 1.6X, Workstream A).
"""

from __future__ import annotations

import ast
import inspect
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext import asyncio as sqlalchemy_asyncio

from auth.models import User
from chat.models import ChatMessage, ChatSession
from documents.models import Document, DocumentChunk
from evaluation import isolation
from evaluation.experiments import run_phase3e_integration as runner
from reliability.models import ReliabilityLog
from tests.fixtures import graph_data
from tests.fixtures.disposable_db import requires_disposable_database

#: Another experiment's users: they share the isolated database and must survive.
SIBLING_EMAIL = "phase3e_other_deadbeef@test.local"
UNRELATED_EMAIL = "phase3d_legacy@test.local"

#: A fake application DSN: the guard tests never dial it.
APPLICATION = "postgresql+asyncpg://documind:app-secret@127.0.0.1:55433/documind"


async def _seed_user(db, email: str, *, label: str):
    """One user with a document, chunks, a reliability log and a chat session."""
    user = await graph_data.create_test_user(db, email)
    document, chunks = await graph_data.create_document_with_chunks(
        db,
        user.id,
        name=f"{label}.txt",
        chunks=[{"content": f"{label} chunk one"}, {"content": f"{label} chunk two"}],
    )
    db.add(ReliabilityLog(user_id=user.id))
    session = ChatSession(id=uuid.uuid4(), user_id=user.id)
    db.add(session)
    await db.flush()
    db.add(
        ChatMessage(
            id=uuid.uuid4(), session_id=session.id, sender="user", content=f"{label}?"
        )
    )
    await db.flush()
    return user, document, chunks, session


async def _count(db, model, **criteria) -> int:
    statement = select(func.count()).select_from(model)
    for column, value in criteria.items():
        statement = statement.where(getattr(model, column) == value)
    return int((await db.execute(statement)).scalar_one())


async def _rows_for_user(db, user_id) -> dict[str, int]:
    """How many rows of each table this user still owns (chats via their session)."""
    sessions = select(ChatSession.id).where(ChatSession.user_id == user_id)
    documents = select(Document.id).where(Document.user_id == user_id)
    return {
        "users": await _count(db, User, id=user_id),
        "documents": await _count(db, Document, user_id=user_id),
        "document_chunks": int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(DocumentChunk.document_id.in_(documents))
                )
            ).scalar_one()
        ),
        "reliability_logs": await _count(db, ReliabilityLog, user_id=user_id),
        "chat_sessions": await _count(db, ChatSession, user_id=user_id),
        "chat_messages": int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(ChatMessage)
                    .where(ChatMessage.session_id.in_(sessions))
                )
            ).scalar_one()
        ),
    }


EMPTY_ROWS = {
    "users": 0,
    "documents": 0,
    "document_chunks": 0,
    "reliability_logs": 0,
    "chat_sessions": 0,
    "chat_messages": 0,
}

FULL_ROWS = {
    "users": 1,
    "documents": 1,
    "document_chunks": 2,
    "reliability_logs": 1,
    "chat_sessions": 1,
    "chat_messages": 1,
}


# ---------------------------------------------------------------------------
# A / B / C — the harness's own rows go, everything else stays
# ---------------------------------------------------------------------------


class TestCleanupScope:
    async def test_ownership_is_selected_by_the_exact_email(self, db_session):
        owner, _document, _chunks, _session = await _seed_user(
            db_session, SIBLING_EMAIL, label="other"
        )
        # A decoy whose email shares the whole prefix but is not the same address.
        await _seed_user(db_session, f"{SIBLING_EMAIL}.bak", label="decoy")
        await _seed_user(db_session, UNRELATED_EMAIL, label="unrelated")

        ids = await runner.owned_user_ids(db_session, emails=[SIBLING_EMAIL])

        assert ids == [owner.id], "the lookup must be by exact email, not by prefix"

    @requires_disposable_database
    async def test_owned_rows_are_removed(self, db_session):
        user, document, _chunks, _session = await _seed_user(
            db_session, "phase3e_1a2b3c4d@test.local", label="phase3e"
        )
        assert await _rows_for_user(db_session, user.id) == FULL_ROWS

        await runner.cleanup_harness_rows(db_session, user_ids=[user.id])

        assert await _rows_for_user(db_session, user.id) == EMPTY_ROWS
        assert await _count(db_session, DocumentChunk, document_id=document.id) == 0

    async def test_other_experiments_survive_untouched(self, db_session):
        owner, owner_document, owner_chunks, owner_session = await _seed_user(
            db_session, "phase3e_1a2b3c4d@test.local", label="phase3e"
        )
        sibling, sibling_document, sibling_chunks, sibling_session = await _seed_user(
            db_session, SIBLING_EMAIL, label="other"
        )
        unrelated, unrelated_document, unrelated_chunks, unrelated_session = (
            await _seed_user(db_session, UNRELATED_EMAIL, label="unrelated")
        )

        # STEP 1.6X: destructive cleanup is refused by design; the property asserted
        # here is that the refusal mutates nothing.
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=[owner.id])

        for survivor in (sibling, unrelated):
            assert await _rows_for_user(db_session, survivor.id) == FULL_ROWS

        # Identity *and* content of the other experiments' evidence is unchanged —
        # the old unscoped delete would have removed every one of these rows.
        async def surviving_chunk_ids(document):
            return set(
                (
                    await db_session.execute(
                        select(DocumentChunk.id).where(
                            DocumentChunk.document_id == document.id
                        )
                    )
                ).scalars()
            )

        assert await surviving_chunk_ids(sibling_document) == {
            chunk.id for chunk in sibling_chunks
        }
        assert await surviving_chunk_ids(unrelated_document) == {
            chunk.id for chunk in unrelated_chunks
        }
        assert await _count(db_session, ChatMessage, session_id=sibling_session.id) == 1
        assert await _count(db_session, ChatMessage, session_id=unrelated_session.id) == 1
        assert await _count(db_session, ReliabilityLog, user_id=sibling.id) == 1
        assert await _count(db_session, ReliabilityLog, user_id=unrelated.id) == 1

        # …and the refusal left the harness's own rows in place too, so the ownership
        # scope cannot have been exceeded.
        assert await _rows_for_user(db_session, owner.id) == FULL_ROWS
        assert await _count(db_session, DocumentChunk, document_id=owner_document.id) == 2
        assert await _count(db_session, ChatMessage, session_id=owner_session.id) == 1
        assert {chunk.id for chunk in owner_chunks}  # the seed really created chunks

    async def test_repeated_cleanup_is_safe_and_does_not_spread(self, db_session):
        owner, _document, _chunks, _session = await _seed_user(
            db_session, "phase3e_1a2b3c4d@test.local", label="phase3e"
        )
        sibling, _document, _chunks, _session = await _seed_user(
            db_session, SIBLING_EMAIL, label="other"
        )

        # STEP 1.6X: destructive cleanup is refused by design; the property asserted
        # here is that the refusal mutates nothing, so repeated attempts cannot
        # spread beyond the requested ownership set.
        for _attempt in range(2):
            with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
                await runner.cleanup_harness_rows(db_session, user_ids=[owner.id])

        assert await _rows_for_user(db_session, owner.id) == FULL_ROWS
        assert await _rows_for_user(db_session, sibling.id) == FULL_ROWS
        # An empty sweep (the step-8 shape when the email lookup finds nothing)
        # refuses too, and mutates nothing either.
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=[])
        assert await _rows_for_user(db_session, owner.id) == FULL_ROWS
        # The ownership lookup is unchanged and still resolves the requested user:
        # the row survives precisely because nothing was deleted.
        assert await runner.owned_user_ids(db_session, emails=[owner.email]) == [owner.id]


# ---------------------------------------------------------------------------
# D — no unscoped or raw destructive SQL remains
# ---------------------------------------------------------------------------


def _literal(node) -> str:
    """The literal text of a string constant, or of an f-string's literal parts.

    f-strings are included on purpose: ``text(f"DELETE FROM {table}")`` must be
    caught too, otherwise this pin could be evaded by interpolation.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):  # f"...{expr}..."
        return "".join(
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return ""


def _raw_sql_statements() -> list[str]:
    """Every ``text("...")`` literal in the runner, joined across line breaks."""
    tree = ast.parse(inspect.getsource(runner))
    statements: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "text"
        ):
            statements.append("".join(_literal(part) for part in node.args))
    return statements


class TestNoUnscopedDeleteRemains:
    def test_no_raw_sql_delete_exists(self):
        deletes = [sql for sql in _raw_sql_statements() if "DELETE FROM" in sql]
        assert deletes == [], deletes
        assert "db.execute(text(" not in inspect.getsource(runner)

    def test_own_cleanup_is_keyed_on_the_user_id_set(self):
        source = inspect.getsource(runner.cleanup_harness_rows)
        for predicate in (
            "ReliabilityLog.user_id.in_(ids)",
            "ChatMessage.session_id.in_(owned_sessions)",
            "ChatSession.user_id.in_(ids)",
            "DocumentChunk.document_id.in_(owned_documents)",
            "Document.user_id.in_(ids)",
            "User.id.in_(ids)",
        ):
            assert predicate in source, predicate

    def test_all_three_cleanup_sites_use_the_scoped_helpers(self):
        source = inspect.getsource(runner)
        assert source.count("await cleanup_harness_rows(db, user_ids=") == 2, (
            "step 8 and the final cleanup must both go through the helper"
        )
        assert source.count("await owned_user_ids(db, emails=") == 1
        assert 'text("DELETE FROM users WHERE email' not in source
        assert 'text("DELETE FROM document_chunks")' not in source
        assert 'text("DELETE FROM document_chunks WHERE' not in source

    def test_step_nine_delete_is_scoped_to_the_one_document(self):
        source = inspect.getsource(runner)
        assert "delete(DocumentChunk).where(DocumentChunk.document_id == stale_id)" in source
        assert "delete(Document).where(Document.id == stale_id)" in source


# ---------------------------------------------------------------------------
# E — the database guard still precedes the engine and every cleanup
# ---------------------------------------------------------------------------


class TestIsolationGuardStillPrecedesCleanup:
    async def test_no_explicit_target_is_refused_before_any_engine(self, monkeypatch):
        monkeypatch.setattr(runner, "application_database_url", lambda: APPLICATION)
        monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
        seen: list[str] = []
        real = sqlalchemy_asyncio.create_async_engine

        def factory(dsn, *args, **kwargs):
            seen.append(dsn)
            return real(dsn, *args, **kwargs)

        monkeypatch.setattr(sqlalchemy_asyncio, "create_async_engine", factory)

        with pytest.raises(isolation.UnsafeEvaluationTarget) as exc:
            await runner.main([])

        assert seen == [], "the runner must be refused before any engine exists"
        assert "app-secret" not in str(exc.value)

    async def test_application_database_is_refused_as_an_explicit_target(
        self, monkeypatch
    ):
        monkeypatch.setattr(runner, "application_database_url", lambda: APPLICATION)
        monkeypatch.delenv(isolation.EVALUATION_DATABASE_URL_ENV, raising=False)
        seen: list[str] = []
        monkeypatch.setattr(
            sqlalchemy_asyncio,
            "create_async_engine",
            lambda dsn, *args, **kwargs: seen.append(dsn),
        )

        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.main(["--database-url", APPLICATION])

        assert seen == []

    def test_the_guard_precedes_the_engine_and_both_cleanups_in_the_source(self):
        source = inspect.getsource(runner)
        guard = source.index("assert_safe_evaluation_target(")
        assert guard < source.index('os.environ["DATABASE_URL"] = evaluation_dsn')
        assert guard < source.index("create_async_engine(evaluation_dsn)")
        assert guard < source.index("other_ids = await owned_user_ids(")
        assert guard < source.index("await cleanup_harness_rows(db, user_ids=[user_id])")


# ---------------------------------------------------------------------------
# F — the evaluation protocol is unchanged
# ---------------------------------------------------------------------------


class TestEvaluationSurfaceUnchanged:
    def test_the_ten_step_protocol_is_unchanged(self):
        source = inspect.getsource(runner)
        for marker in (
            'print("\\n--- 1. Successful upload -> READY ---")',
            'print("\\n--- 2. Duplicate READY upload ---")',
            'print("\\n--- 3. Embedding failure -> ERROR ---")',
            'print("\\n--- 4. ERROR document not searchable ---")',
            'print("\\n--- 5. Reprocessing ERROR document ---")',
            'print("\\n--- 6. Duplicate upload of ERROR document ---")',
            'print("\\n--- 7. Delete consistency ---")',
            'print("\\n--- 8. User isolation ---")',
            'print("\\n--- 9. Stale PROCESSING detection ---")',
            'print("\\n--- 10. Structure-v2 still works ---")',
        ):
            assert marker in source, marker

    def test_check_accumulators_still_behave(self, capsys):
        passed_before = list(runner.PASSED)
        failed_before = list(runner.FAILED)
        try:
            runner.check("ok-case", True)
            runner.check("bad-case", False, "because")
            recorded_pass = list(runner.PASSED)
            recorded_fail = list(runner.FAILED)
        finally:
            output = capsys.readouterr().out
            runner.PASSED[:] = passed_before
            runner.FAILED[:] = failed_before

        assert recorded_pass[len(passed_before):] == ["ok-case"]
        assert recorded_fail[len(failed_before):] == ["bad-case :: because"]
        assert output.count("PASS") == 1 and output.count("FAIL") == 1

    def test_exit_code_is_failure_when_any_check_fails(self):
        assert "return 1 if FAILED else 0" in inspect.getsource(runner)

    def test_the_chunker_default_is_restored_after_the_run(self):
        source = inspect.getsource(runner)
        last_restore = source.rindex('documents_routes.settings.chunker_version = "legacy"')
        assert last_restore > source.index(
            "await cleanup_harness_rows(db, user_ids=[user_id])"
        )

    def test_cli_flags_and_entry_points_still_behave(self):
        assert runner.parse_args([]).database_url is None
        assert (
            runner.parse_args(["--database-url", "postgresql+asyncpg://h:1/d"]).database_url
            == "postgresql+asyncpg://h:1/d"
        )
        assert inspect.iscoroutinefunction(runner.main)
        assert inspect.iscoroutinefunction(runner.cleanup_harness_rows)
        assert inspect.iscoroutinefunction(runner.owned_user_ids)
        assert "it deletes rows it owns" in inspect.getsource(runner)

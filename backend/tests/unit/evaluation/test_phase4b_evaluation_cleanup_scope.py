"""Regression tests for the Phase 4B evaluation harness's cleanup boundary.

``run_phase4b_evaluation.py`` used to bracket a run with **ten** raw ``DELETE
FROM`` statements in two blocks::

    # before ingest ("Clean")
    await db.execute(text("DELETE FROM reliability_logs"))
    await db.execute(text("DELETE FROM chat_messages"))
    await db.execute(text("DELETE FROM chat_sessions"))
    await db.execute(text("DELETE FROM document_chunks"))
    await db.execute(text("DELETE FROM documents"))
    await db.execute(text("DELETE FROM users WHERE email LIKE 'phase4b_%'"))

    # after the report ("Cleanup")
    await db.execute(text("DELETE FROM reliability_logs"))
    await db.execute(text("DELETE FROM document_chunks"))
    await db.execute(text("DELETE FROM documents"))
    await db.execute(text("DELETE FROM users WHERE email LIKE 'phase4b_%'"))

Eight of those statements carry **no predicate at all** (``reliability_logs``,
``chat_messages``, ``chat_sessions``, ``document_chunks`` and ``documents`` before
the run; ``reliability_logs``, ``document_chunks`` and ``documents`` after it):
each removes every row of that table in whatever database the harness targets —
every owner, every document, every chunk — including rows created by unrelated
experiments that share the same isolated database (the project points every
isolated runner at one shared ``DOCUMIND_INTEGRATION_DATABASE_URL``).  The
remaining two match users by the ``phase4b_%`` **email prefix**, which is broader
than ownership requires.  Database isolation proves the target is not the
application database; it does not make a database-wide delete safe.

Ownership, proven from the schema and the runner's execution flow, is the two
evaluation users this harness creates:

* ``phase4b_legacy@test.local`` — owns the legacy-chunker corpus (arms A and B);
* ``phase4b_candidate@test.local`` — owns the structure-v2 corpus (arm C).

Their emails are **deterministic** (``phase4b_<label>@test.local``,
``HARNESS_LABELS``), so a later run can recognise — and clean up — the rows an
earlier, interrupted run left behind, and the sweep can use the exact addresses
instead of a prefix.  Every row the run writes is reached from those users:
``documents.user_id`` / ``chat_sessions.user_id`` / ``reliability_logs.user_id``
reference ``users.id``, and ``document_chunks`` / ``chat_messages`` reach their
owner through ``documents`` / ``chat_sessions`` (neither child table has an owner
column of its own).

These tests are behavioural: they seed real rows through the project's SQLite
fixtures and the shared builders in ``tests/fixtures/graph_data.py``, then run the
real ``owned_user_ids`` / ``cleanup_harness_rows`` functions.  Nothing here
connects to PostgreSQL or to the application database.

STEP 1.6X: ``cleanup_harness_rows`` refuses every destructive sweep until a
genuine connection-bound lifecycle authorization exists.  Tests whose property
still holds under refusal assert the refusal and the absence of mutation; tests
that assert destructive *success* are marked ``requires_disposable_database``
rather than deleted or made to pass by relaxing the gate.
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
from evaluation.experiments import run_phase4b_evaluation as runner
from reliability.models import ReliabilityLog
from tests.fixtures import graph_data
from tests.fixtures.disposable_db import requires_disposable_database

#: Another experiment's user: it matches the old ``phase4b_%`` prefix and must survive.
SIBLING_EMAIL = "phase4b_extra_cafe1234@test.local"
#: And one that shares no prefix with this harness at all.
UNRELATED_EMAIL = "phase3f_legacy@test.local"

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
# A / B / C — the harness's own rows are never swept without authorization,
# and every other experiment's rows stay
# ---------------------------------------------------------------------------


class TestCleanupScope:
    async def test_ownership_is_selected_by_the_exact_emails(self, db_session):
        legacy, _document, _chunks, _session = await _seed_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        candidate, _document, _chunks, _session = await _seed_user(
            db_session, runner.HARNESS_USER_EMAILS[1], label="candidate"
        )
        # A decoy whose email shares the whole prefix but is not the same address.
        await _seed_user(db_session, f"{runner.HARNESS_USER_EMAILS[0]}.bak", label="decoy")
        await _seed_user(db_session, UNRELATED_EMAIL, label="unrelated")

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)

        assert set(ids) == {legacy.id, candidate.id}, (
            "only this harness's two evaluation users may be selected"
        )

    @requires_disposable_database
    async def test_owned_records_are_removed(self, db_session):
        user, document, _chunks, _session = await _seed_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        assert await _rows_for_user(db_session, user.id) == FULL_ROWS

        await runner.cleanup_harness_rows(db_session, user_ids=[user.id])

        assert await _rows_for_user(db_session, user.id) == EMPTY_ROWS
        assert await _count(db_session, DocumentChunk, document_id=document.id) == 0

    @requires_disposable_database
    async def test_both_owned_users_are_cleaned_in_one_sweep(self, db_session):
        legacy, _document, _chunks, _session = await _seed_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        candidate, _document, _chunks, _session = await _seed_user(
            db_session, runner.HARNESS_USER_EMAILS[1], label="candidate"
        )

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        await runner.cleanup_harness_rows(db_session, user_ids=ids)

        assert await _rows_for_user(db_session, legacy.id) == EMPTY_ROWS
        assert await _rows_for_user(db_session, candidate.id) == EMPTY_ROWS

    async def test_unrelated_users_and_their_records_survive(self, db_session):
        legacy, legacy_document, legacy_chunks, legacy_session = await _seed_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        sibling, sibling_document, sibling_chunks, sibling_session = await _seed_user(
            db_session, SIBLING_EMAIL, label="sibling"
        )
        unrelated, unrelated_document, unrelated_chunks, unrelated_session = (
            await _seed_user(db_session, UNRELATED_EMAIL, label="unrelated")
        )

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        # STEP 1.6X: destructive cleanup is refused by design; the property asserted
        # here is that the refusal mutates nothing.
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=ids)

        for survivor in (sibling, unrelated):
            assert await _rows_for_user(db_session, survivor.id) == FULL_ROWS

        # Identity *and* content of the other experiments' evidence is unchanged —
        # the old unscoped deletes would have removed every one of these rows.
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

        # …and the harness's own rows are untouched too: the refusal happens before
        # any mutation, so nothing anywhere was removed.
        assert await _rows_for_user(db_session, legacy.id) == FULL_ROWS
        assert await surviving_chunk_ids(legacy_document) == {
            chunk.id for chunk in legacy_chunks
        }
        assert await _count(db_session, ChatMessage, session_id=legacy_session.id) == 1
        assert {chunk.id for chunk in legacy_chunks}  # the seed really created chunks

    async def test_repeated_cleanup_is_safe_and_does_not_spread(self, db_session):
        legacy, _document, _chunks, _session = await _seed_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        sibling, _document, _chunks, _session = await _seed_user(
            db_session, SIBLING_EMAIL, label="sibling"
        )

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        # STEP 1.6X: destructive cleanup is refused by design; the property asserted
        # here is that a repeated sweep mutates nothing and never spreads.
        for _attempt in range(2):
            with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
                await runner.cleanup_harness_rows(db_session, user_ids=ids)

        assert await _rows_for_user(db_session, legacy.id) == FULL_ROWS
        assert await _rows_for_user(db_session, sibling.id) == FULL_ROWS
        # The sweep still recognises exactly this harness's user, and only it: a
        # refusal must neither widen nor lose the ownership selection.
        assert set(
            await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        ) == {legacy.id}

    async def test_an_empty_ownership_set_is_a_no_op(self, db_session):
        """No ids must mean *no* deletion — never a fallback to a broad delete."""
        sibling, sibling_document, sibling_chunks, sibling_session = await _seed_user(
            db_session, SIBLING_EMAIL, label="sibling"
        )
        before = await _rows_for_user(db_session, sibling.id)

        # STEP 1.6X: destructive cleanup is refused by design; the property asserted
        # here is that an empty ownership set mutates nothing and never falls back
        # to a broader delete.
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=[])

        assert await _rows_for_user(db_session, sibling.id) == before == FULL_ROWS
        assert await _count(db_session, DocumentChunk, document_id=sibling_document.id) == 2
        assert await _count(db_session, ChatMessage, session_id=sibling_session.id) == 1
        assert {chunk.id for chunk in sibling_chunks}


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
    def test_no_raw_destructive_sql_exists(self):
        destructive = ("DELETE", "TRUNCATE", "UPDATE ", "INSERT INTO", "DROP ")
        found = [
            sql for sql in _raw_sql_statements() if any(word in sql for word in destructive)
        ]
        assert found == [], found
        assert 'text("DELETE' not in inspect.getsource(runner)
        assert "db.execute(text(" not in inspect.getsource(runner)

    def test_the_runner_no_longer_imports_text_at_all(self):
        """This runner had no read-only raw SQL: every ``text()`` use was a delete."""
        assert "from sqlalchemy import text" not in inspect.getsource(runner)
        assert _raw_sql_statements() == []

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

    def test_dependent_rows_are_deleted_before_their_parents(self):
        source = inspect.getsource(runner.cleanup_harness_rows)
        order = [
            "delete(ReliabilityLog)",
            "delete(ChatMessage)",
            "delete(ChatSession)",
            "delete(DocumentChunk)",
            "delete(Document)",
            "delete(User)",
        ]
        positions = [source.index(token) for token in order]
        assert positions == sorted(positions), order

    def test_both_cleanup_call_sites_use_the_scoped_helpers(self):
        source = inspect.getsource(runner)
        assert source.count("await cleanup_harness_rows(db, user_ids=") == 2, (
            "the pre-run sweep and the final cleanup must both use the helper"
        )
        assert source.count("await owned_user_ids(db, emails=") == 1
        assert "email LIKE 'phase4b_%'" not in source
        assert 'text("DELETE FROM document_chunks")' not in source

    def test_ownership_identity_is_single_sourced(self):
        assert runner.HARNESS_LABELS == ("legacy", "candidate")
        assert runner.HARNESS_USER_EMAILS == (
            "phase4b_legacy@test.local",
            "phase4b_candidate@test.local",
        )
        source = inspect.getsource(runner)
        # The ingest loop must create its users through the single source of truth.
        assert "email=harness_user_email(label)" in source
        assert 'email=f"phase4b_{label}@test.local"' not in source


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
        assert guard < source.index("previous_users = await owned_user_ids(")
        assert guard < source.index(
            "await cleanup_harness_rows(db, user_ids=list(users.values()))"
        )


# ---------------------------------------------------------------------------
# F — the evaluation protocol, metrics and interfaces are unchanged
# ---------------------------------------------------------------------------


class TestEvaluationSurfaceUnchanged:
    def test_protocol_markers_and_report_path_are_unchanged(self):
        source = inspect.getsource(runner)
        for marker in (
            'print("PHASE 4B — QA EVALUATION EXPANSION")',
            'print("  warm-up complete")',
            'print(f"\\n  --- arm {arm_id}: {description}")',
            'print(f"\\n  wrote {out.resolve()}")',
            'print("METRIC COMPARISON (Phase 4B expanded)")',
            'print("FAILURE DISTRIBUTION (Arm C)")',
            'print("CHUNK STATISTICS")',
            '"separate_evaluation_users": True',
            '"phase4b_evaluation_report.json"',
        ):
            assert marker in source, marker
        assert "_print_summary(summary)" in source
        assert callable(runner._print_summary)

    def test_metric_protocol_and_arms_are_unchanged(self):
        assert runner.TOP_K == 5
        source = inspect.getsource(runner)
        for arm in (
            '("A", "legacy", "legacy + legacy char context (pre-Phase-3D baseline)")',
            '("B", "legacy", "legacy chunks + token-aware context")',
            '("C", "candidate", "structure-v2 + token-aware context (candidate)")',
        ):
            assert arm in source, arm
        for metric in (
            "recall@1", "recall@3", "recall@5", "precision@1", "mrr",
            "answer_exact_match", "acceptable_answer_match", "token_f1",
            "answer_exactness_substring", "evidence_coverage", "context_utilisation",
            "false_abstention_rate", "abstention_on_unsupported",
            "spurious_answers_on_unsupported", "duplicate_retrieval_rate",
        ):
            assert f'"{metric}"' in source, metric

    def test_corpus_and_failure_analysis_entry_points_still_exist(self):
        assert callable(runner.build_phase4b_corpus)
        assert callable(runner.build_phase4b_unanswerable)
        assert callable(runner.get_all_phase4b_questions)
        assert callable(runner.classify_failure)
        assert callable(runner.per_format_breakdown)
        assert inspect.iscoroutinefunction(runner.ingest_corpus)
        assert inspect.iscoroutinefunction(runner.run_question)

    def test_exit_code_and_entry_points_still_behave(self):
        source = inspect.getsource(runner)
        assert "    return 0\n" in source  # the harness exits 0 when it completed
        assert "it deletes rows it owns" in source
        assert runner.parse_args([]).database_url is None
        assert (
            runner.parse_args(["--database-url", "postgresql+asyncpg://h:1/d"]).database_url
            == "postgresql+asyncpg://h:1/d"
        )
        assert inspect.iscoroutinefunction(runner.main)
        assert inspect.iscoroutinefunction(runner.cleanup_harness_rows)
        assert inspect.iscoroutinefunction(runner.owned_user_ids)
        assert callable(runner.harness_user_email)
        assert runner.harness_user_email("legacy") == "phase4b_legacy@test.local"

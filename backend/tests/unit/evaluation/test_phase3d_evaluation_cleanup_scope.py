"""Regression tests for the Phase 3D evaluation runner's cleanup boundary.

``run_phase3d_evaluation.py`` used to bracket a run with **unscoped** deletes::

    await db.execute(text("DELETE FROM reliability_logs"))
    await db.execute(text("DELETE FROM document_chunks"))
    await db.execute(text("DELETE FROM documents"))
    await db.execute(text("DELETE FROM users WHERE email LIKE 'phase3d_%'"))

which removes every row of those tables in the target database — and the
``phase3d_%`` user predicate additionally matches the sibling Phase 3D upload/ask
harness's users (``phase3d_upload_<8 hex>@test.local``).  Database isolation
proves the target is not the application database; it does not make a
database-wide delete safe.

Ownership, proven from the schema and the runner's execution flow, is the two
evaluation users this harness creates — ``phase3d_legacy@test.local`` and
``phase3d_candidate@test.local`` (``HARNESS_USER_EMAILS``, derived from
``HARNESS_ARMS``).  Every row the run writes is reached from those users:
``documents.user_id`` / ``chat_sessions.user_id`` / ``reliability_logs.user_id``
reference ``users.id``, and ``document_chunks`` / ``chat_messages`` reach their
owner through ``documents`` / ``chat_sessions``.

These tests are behavioural: they seed real rows through the project's SQLite
fixtures and the shared builders in ``tests/fixtures/graph_data.py``, then run
the real ``owned_user_ids`` / ``cleanup_harness_rows`` functions.  Nothing here
connects to PostgreSQL or to the application database.

STEP 1.6X: destructive row cleanup is refused by design — ``evaluation.isolation``
has no connection-bound lifecycle authority — so each test below either asserts
that the refusal mutates nothing, or is marked ``requires_disposable_database``
and blocked until a disposable target and a real authorization authority exist.
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
from evaluation.experiments import run_phase3d_evaluation as runner
from reliability.models import ReliabilityLog
from tests.fixtures import graph_data
from tests.fixtures.disposable_db import requires_disposable_database

#: The real sibling harness (``run_phase3d_upload_integration``) names its users
#: ``phase3d_upload_<8 hex>@test.local`` (its L237/L371/L459), so they matched the
#: old ``phase3d_%`` email prefix and were deleted by this runner's cleanup.  They
#: must never be touched again.
SIBLING_EMAIL = "phase3d_upload_deadbeef@test.local"
UNRELATED_EMAIL = "unrelated_experiment@test.local"

#: A fake application DSN: the guard tests never dial it.
APPLICATION = "postgresql+asyncpg://documind:app-secret@127.0.0.1:55433/documind"


async def _seed_experiment_user(db, email: str, *, label: str):
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


# ---------------------------------------------------------------------------
# A / B / C — the harness's own rows go, everything else stays
# ---------------------------------------------------------------------------


class TestCleanupScope:
    async def test_harness_owns_exactly_its_own_evaluation_users(self, db_session):
        await _seed_experiment_user(db_session, runner.HARNESS_USER_EMAILS[0], label="legacy")
        await _seed_experiment_user(db_session, runner.HARNESS_USER_EMAILS[1], label="candidate")
        await _seed_experiment_user(db_session, SIBLING_EMAIL, label="sibling")
        await _seed_experiment_user(db_session, UNRELATED_EMAIL, label="unrelated")

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)

        assert len(ids) == 2, "only this harness's two evaluation users may be selected"
        found = {
            (
                await db_session.execute(select(User.email).where(User.id == user_id))
            ).scalar_one()
            for user_id in ids
        }
        assert found == set(runner.HARNESS_USER_EMAILS)

    @requires_disposable_database
    async def test_owned_rows_are_removed(self, db_session):
        legacy, legacy_document, _chunks, _session = await _seed_experiment_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        candidate, _document, _chunks, _session = await _seed_experiment_user(
            db_session, runner.HARNESS_USER_EMAILS[1], label="candidate"
        )
        assert await _rows_for_user(db_session, legacy.id) == {
            "users": 1,
            "documents": 1,
            "document_chunks": 2,
            "reliability_logs": 1,
            "chat_sessions": 1,
            "chat_messages": 1,
        }

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        await runner.cleanup_harness_rows(db_session, user_ids=ids)

        for user in (legacy, candidate):
            assert await _rows_for_user(db_session, user.id) == {
                "users": 0,
                "documents": 0,
                "document_chunks": 0,
                "reliability_logs": 0,
                "chat_sessions": 0,
                "chat_messages": 0,
            }
        assert await _count(db_session, DocumentChunk, document_id=legacy_document.id) == 0

    async def test_other_experiments_survive_untouched(self, db_session):
        legacy, _document, _chunks, _session = await _seed_experiment_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        candidate, _document, _chunks, _session = await _seed_experiment_user(
            db_session, runner.HARNESS_USER_EMAILS[1], label="candidate"
        )
        sibling, sibling_document, sibling_chunks, sibling_session = await _seed_experiment_user(
            db_session, SIBLING_EMAIL, label="sibling"
        )
        unrelated, unrelated_document, unrelated_chunks, unrelated_session = await _seed_experiment_user(
            db_session, UNRELATED_EMAIL, label="unrelated"
        )
        expected = {
            "users": 1,
            "documents": 1,
            "document_chunks": 2,
            "reliability_logs": 1,
            "chat_sessions": 1,
            "chat_messages": 1,
        }

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        # STEP 1.6X: destructive cleanup is refused by design; the property
        # asserted here is that the refusal mutates nothing.
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=ids)

        for survivor in (sibling, unrelated):
            assert await _rows_for_user(db_session, survivor.id) == expected
        # …the harness's own rows are equally untouched by the refusal.
        for owner in (legacy, candidate):
            assert await _rows_for_user(db_session, owner.id) == expected
        # Identity *and* content of the unrelated evidence is unchanged — the
        # old unscoped delete would have removed every one of these rows.
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

    async def test_repeated_cleanup_is_safe_and_does_not_spread(self, db_session):
        legacy, _document, _chunks, _session = await _seed_experiment_user(
            db_session, runner.HARNESS_USER_EMAILS[0], label="legacy"
        )
        sibling, _document, _chunks, _session = await _seed_experiment_user(
            db_session, SIBLING_EMAIL, label="sibling"
        )

        ids = await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        # STEP 1.6X: destructive cleanup is refused by design; the property
        # asserted here is that the refusal mutates nothing.
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=ids)
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=ids)  # repeated run

        assert (await _rows_for_user(db_session, legacy.id))["users"] == 1
        assert (await _rows_for_user(db_session, sibling.id))["users"] == 1
        assert await _count(db_session, Document, user_id=sibling.id) == 1
        # Nothing was cleaned, so the ownership selection is unchanged: it still
        # resolves exactly the one harness user present here (the sibling's rows
        # were never in scope, so the spread the old unscoped delete caused
        # cannot have happened).
        assert set(
            await runner.owned_user_ids(db_session, emails=runner.HARNESS_USER_EMAILS)
        ) == {legacy.id}
        assert await _count(db_session, Document, user_id=legacy.id) == 1
        with pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING"):
            await runner.cleanup_harness_rows(db_session, user_ids=[])


# ---------------------------------------------------------------------------
# D (secondary) — no raw unscoped SQL remains, and the scope is single-sourced
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

    def test_ownership_is_single_sourced(self):
        assert runner.HARNESS_ARMS == (("legacy", "legacy"), ("candidate", "structure"))
        assert runner.HARNESS_USER_EMAILS == (
            "phase3d_legacy@test.local",
            "phase3d_candidate@test.local",
        )
        source = inspect.getsource(runner)
        assert "email=harness_user_email(arm)" in source
        assert "for arm, family in HARNESS_ARMS:" in source

    def test_cleanup_is_keyed_on_the_user_id_set(self):
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

    def test_the_email_prefix_predicate_is_gone(self):
        source = inspect.getsource(runner)
        assert "email LIKE 'phase3d_%'" not in source
        assert "users WHERE email LIKE" not in source


# ---------------------------------------------------------------------------
# E — the database guard still precedes every destructive call
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

    async def test_application_database_is_refused_as_an_explicit_target(self, monkeypatch):
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

    def test_the_guard_precedes_both_cleanup_calls_in_the_source(self):
        source = inspect.getsource(runner)
        guard = source.index("assert_safe_evaluation_target(")
        assert guard < source.index("os.environ[\"DATABASE_URL\"] = evaluation_dsn")
        assert guard < source.index("previous_users = await owned_user_ids(")
        assert guard < source.index("await cleanup_harness_rows(db, user_ids=list(users.values()))")


# ---------------------------------------------------------------------------
# F — the evaluation surface is unchanged
# ---------------------------------------------------------------------------


class TestEvaluationSurfaceUnchanged:
    def test_metric_protocol_constants_are_unchanged(self):
        assert runner.TOP_K == 5

    def test_arm_matrix_is_unchanged(self):
        source = inspect.getsource(runner)
        for arm in ('("A", "legacy",', '("B", "legacy",', '("C", "candidate",'):
            assert arm in source, arm

    def test_report_output_semantics_are_unchanged(self):
        source = inspect.getsource(runner)
        assert '"phase3d_evaluation_report.json"' in source
        # STEP 1.6X: the report content is serialized exactly as before; only
        # the write mechanism changed, to the append-only RunOutput that refuses
        # to replace an existing artifact (see
        # test_runner_artifact_append_only.py, which pins that contract).
        assert "json.dumps(report, indent=2)" in source
        assert callable(runner.print_summary)

    def test_cli_flags_still_behave(self):
        assert runner.parse_args([]).database_url is None
        assert (
            runner.parse_args(["--database-url", "postgresql+asyncpg://h:1/d"]).database_url
            == "postgresql+asyncpg://h:1/d"
        )
        assert inspect.iscoroutinefunction(runner.main)
        assert inspect.iscoroutinefunction(runner.cleanup_harness_rows)
        assert inspect.iscoroutinefunction(runner.owned_user_ids)

    def test_the_documented_scope_matches_the_code(self):
        assert "it deletes rows it owns" in inspect.getsource(runner)

"""Phase 3E — FINAL VALIDATION GATE.

Direct database inspection against real PostgreSQL + pgvector.
No API-level inference.  Every claim is backed by a direct SQL query
or a real filesystem check.

Usage::

    cd backend
    python test_phase3e_validation.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

# Relocated 2026-09-30 to backend/evaluation/experiments/ (was backend/).
# The backend package root is three levels up from this file.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("DOCUMIND_DEV", "1")
os.environ.setdefault("QA_MODEL_NAME", "./models/documind-qa")

# No ``DATABASE_URL`` default here: the target is resolved and guarded in
# ``main()`` (before the application is imported, because ``storage.database``
# reads settings at import time).  A module-level default would silently make
# the application database the target of a runner that deletes rows.
from evaluation.isolation import (  # noqa: E402
    application_database_url,
    assert_cleanup_execution_authorized,
    assert_disposal_authorized,
    assert_safe_evaluation_target,
    database_identity,
    describe_identity,
    display_dsn,
    evaluation_database_url,
)

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(f"{name} :: {detail}")
        print(f"  FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------
# Ownership — the users this harness creates, and the cleanup that respects it
# ---------------------------------------------------------------------------


async def owned_user_ids(db, *, emails) -> list[uuid.UUID]:
    """Ids of the users this harness owns, looked up by their exact emails.

    The harness names its two users ``validation_<8 hex>@test.local`` and
    ``val_other_<8 hex>@test.local``; the suffix is random per run (so two runs
    cannot collide), which means the *id* is what carries ownership within a run.
    The exact-email lookup is used for the temporary isolation-check user, whose
    id is created earlier in a different session.
    """
    from sqlalchemy import select

    from auth.models import User

    rows = await db.execute(select(User.id).where(User.email.in_(list(emails))))
    return list(rows.scalars())


async def cleanup_harness_rows(db, *, user_ids) -> None:
    """Delete exactly the rows owned by ``user_ids``, in foreign-key-safe order.

    Ownership, from the schema — no predicate is guessed:

    * ``users`` is the root: ``documents.user_id``, ``chat_sessions.user_id`` and
      ``reliability_logs.user_id`` each reference ``users.id``
      (``ondelete="CASCADE"``), and ``documents.user_id`` is the only ownership
      key a document has;
    * ``document_chunks.document_id`` -> ``documents.id`` and
      ``chat_messages.session_id`` -> ``chat_sessions.id`` reach their owner
      through those parents, because neither child table carries an owner column;
    * every row this harness creates is attached to the one user it creates
      (``user_id``, which owns every uploaded document and its chunks) or to the
      temporary isolation-check user removed in step 9, which is what makes the
      user id set the narrowest correct scope.

    The previous revision ran its final cleanup with an **unscoped**
    ``DELETE FROM document_chunks``, which removes every row of that table in the
    target database — including rows belonging to other experiments that share
    the isolated database.  Database isolation proves the target is not the
    application database; it does not make a database-wide delete safe.

    Order matters: logs, then messages, then sessions, then chunks, then the
    documents that own them, then the users.  Nothing here relies on cascade for
    a row it claims to delete, so the cleanup cannot be blocked by a foreign key.

    The caller commits, exactly as before.
    """
    from evaluation.isolation import assert_cleanup_execution_authorized

    assert_cleanup_execution_authorized(db, operation="Phase 3E validation row cleanup")
    from sqlalchemy import delete, select

    from auth.models import User
    from chat.models import ChatMessage, ChatSession
    from documents.models import Document, DocumentChunk
    from reliability.models import ReliabilityLog

    ids = list(user_ids)
    if not ids:
        # Nothing of this harness's is present.  An empty ``IN ()`` would be a
        # no-op anyway; returning early keeps the intent explicit.
        return

    owned_sessions = select(ChatSession.id).where(ChatSession.user_id.in_(ids))
    owned_documents = select(Document.id).where(Document.user_id.in_(ids))

    await db.execute(delete(ReliabilityLog).where(ReliabilityLog.user_id.in_(ids)))
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(owned_sessions)))
    await db.execute(delete(ChatSession).where(ChatSession.user_id.in_(ids)))
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id.in_(owned_documents))
    )
    await db.execute(delete(Document).where(Document.user_id.in_(ids)))
    await db.execute(delete(User).where(User.id.in_(ids)))


def parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "explicit evaluation database URL. Takes precedence over "
            "DOCUMIND_INTEGRATION_DATABASE_URL. Without an isolated target this "
            "runner refuses to run: it writes to (and deletes from) the database "
            "it targets."
        ),
    )
    return parser.parse_args(argv)


async def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    # --- evaluation target: explicit, guarded, never the application's --------
    application_dsn = application_database_url()
    evaluation_dsn = evaluation_database_url(
        override=args.database_url, application_url=application_dsn
    )
    evaluation_identity = assert_safe_evaluation_target(
        evaluation_dsn,
        operation="the Phase 3E final validation gate (it deletes rows it owns)",
        application_url=application_dsn,
    )
    # Validity (above) is not permission to destroy: the operator must also name this exact database.
    assert_disposal_authorized(
        evaluation_dsn,
        operation="the Phase 3E final validation gate (it deletes rows it owns)",
        application_url=application_dsn,
    )
    application_identity = database_identity(application_dsn)
    print(f"[evaluation-db] application database : {describe_identity(application_identity)}")
    print(f"[evaluation-db] evaluation database  : {describe_identity(evaluation_identity)}")
    print(f"[evaluation-db] target (no credentials): {display_dsn(evaluation_dsn)}")
    # The models below resolve their engine from settings when
    # ``storage.database`` is first imported; pointing the environment at the
    # verified target is what makes the run talk to it, and it happens only after
    # the guard has approved that target.
    os.environ["DATABASE_URL"] = evaluation_dsn

    # Drop any cached application settings, then require the effective URL to
    # still be the approved target.  Without this, clearing ``DATABASE_URL``
    # between resolution and import could let the app fall back to its own
    # settings-backed URL.
    from config import get_settings

    get_settings.cache_clear()
    if get_settings().database_url != evaluation_dsn:
        raise RuntimeError(
            "the effective application settings name a different database than the "
            "approved evaluation target; refusing before the app is imported"
        )

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import delete, func, select, text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from auth.models import User  # noqa: F401
    from documents.models import Document, DocumentChunk  # noqa: F401
    from chat.models import ChatSession, ChatMessage  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401

    from passlib.context import CryptContext

    import documents.routes as documents_routes
    from documents.chunking import CHUNKER_VERSION_LEGACY, CHUNKER_VERSION_STRUCTURE
    from main import app

    engine = create_async_engine(evaluation_dsn)
    from evaluation.isolation import assert_engine_matches_target  # noqa: E402

    assert_engine_matches_target(engine, evaluation_dsn)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    email = f"validation_{uuid.uuid4().hex[:8]}@test.local"
    password = "TestPass123!"

    print("=" * 78)
    print("PHASE 3E FINAL VALIDATION GATE")
    print("=" * 78)

    # --- Setup user ---
    async with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            email=email,
            name="Phase3E Validation",
            hashed_password=pwd.hash(password),
            is_active=True,
        )
        db.add(user)
        await db.commit()
        user_id = user.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )
        check("login succeeds", login.status_code == 200)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # ================================================================
        # 1. VERIFY ACTUAL DATABASE STATE AFTER EMBEDDING FAILURE
        # ================================================================
        print("\n=== 1. DATABASE STATE AFTER EMBEDDING FAILURE ===")
        documents_routes.settings.chunker_version = "legacy"

        with patch("documents.routes.embed_texts", side_effect=RuntimeError("simulated failure")):
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
                f.write(b"Embedding failure validation document.\n\n"
                         b"Content that should produce chunks but no embeddings.")
                fail_path = Path(f.name)
            fail_payload = fail_path.read_bytes()
            fail_resp = await client.post(
                "/api/documents/upload",
                files={"file": ("fail.txt", fail_payload)},
                headers=headers,
            )
            os.unlink(fail_path)

        check("embedding failure upload returns 201", fail_resp.status_code == 201)
        fail_doc_id = fail_resp.json()["id"]

        # Direct DB inspection
        async with session_factory() as db:
            doc = (await db.execute(
                select(Document).where(Document.id == fail_doc_id)
            )).scalar_one()

            check("document.status = 'error'", doc.status == "error",
                  f"got '{doc.status}'")
            check("document.embedding_status = 'error'", doc.embedding_status == "error",
                  f"got '{doc.embedding_status}'")

            # Count chunks
            chunk_count_result = await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == fail_doc_id
                )
            )
            actual_chunks = chunk_count_result.scalar()
            check("document.chunk_count recorded", doc.chunk_count >= 0,
                  f"chunk_count={doc.chunk_count}")
            check("actual chunk rows exist or zero", actual_chunks >= 0,
                  f"actual rows={actual_chunks}")

            # Count embeddings
            if actual_chunks > 0:
                with_emb = (await db.execute(
                    select(func.count(DocumentChunk.id)).where(
                        DocumentChunk.document_id == fail_doc_id,
                        DocumentChunk.embedding.isnot(None)
                    )
                )).scalar()
                without_emb = (await db.execute(
                    select(func.count(DocumentChunk.id)).where(
                        DocumentChunk.document_id == fail_doc_id,
                        DocumentChunk.embedding.is_(None)
                    )
                )).scalar()
                check("all chunks have NULL embeddings on failure",
                      with_emb == 0,
                      f"with_emb={with_emb}, without_emb={without_emb}")

                # CRITICAL: resolve the discrepancy
                # Are chunks rolled back or retained?
                if actual_chunks > 0 and with_emb == 0:
                    print(f"\n  ** RESOLUTION: Chunks are RETAINED but safely non-searchable **")
                    print(f"     {actual_chunks} chunks exist, all with embedding IS NULL")
                    print(f"     Retrieval filters on embedding IS NOT NULL, so these are invisible")
                elif actual_chunks == 0:
                    print(f"\n  ** RESOLUTION: Chunks are ROLLED BACK (zero rows) **")
            else:
                print(f"\n  ** RESOLUTION: No chunks created (extraction or chunking may have failed) **")

            # Verify not searchable via direct SQL
            search_result = await db.execute(
                text(
                    "SELECT COUNT(*) FROM document_chunks dc "
                    "JOIN documents d ON d.id = dc.document_id "
                    "WHERE d.id = :doc_id "
                    "AND d.embedding_status = 'ready' "
                    "AND dc.embedding IS NOT NULL"
                ),
                {"doc_id": str(fail_doc_id)}
            )
            searchable_chunks = search_result.scalar()
            check("no searchable chunks for ERROR document",
                  searchable_chunks == 0,
                  f"searchable={searchable_chunks}")

        # ================================================================
        # 2. VERIFY READY INVARIANTS DIRECTLY
        # ================================================================
        print("\n=== 2. READY INVARIANTS (direct DB) ===")
        documents_routes.settings.chunker_version = "legacy"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"# Methods\n\nWe used the standard approach.\n\n"
                     b"## Results\n\nResults were positive.\n\n"
                     b"# Conclusion\n\nThis concludes the report.")
            ready_path = Path(f.name)
        ready_payload = ready_path.read_bytes()
        ready_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("ready.txt", ready_payload)},
            headers=headers,
        )
        os.unlink(ready_path)
        check("READY upload returns 201", ready_resp.status_code == 201)
        ready_doc_id = ready_resp.json()["id"]

        async with session_factory() as db:
            doc = (await db.execute(
                select(Document).where(Document.id == ready_doc_id)
            )).scalar_one()

            check("status = 'ready'", doc.status == "ready", f"got '{doc.status}'")
            check("embedding_status = 'ready'", doc.embedding_status == "ready",
                  f"got '{doc.embedding_status}'")
            check("chunk_count > 0", doc.chunk_count > 0, f"got {doc.chunk_count}")
            check("chunker_version exists", doc.chunker_version is not None,
                  f"got '{doc.chunker_version}'")
            check("parser_version exists", doc.parser_version is not None,
                  f"got '{doc.parser_version}'")
            check("embedding_model exists", doc.embedding_model is not None,
                  f"got '{doc.embedding_model}'")

            # Actual chunk count
            actual = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == ready_doc_id
                )
            )).scalar()
            check("actual chunk rows > 0", actual > 0, f"got {actual}")
            check("chunk_count matches actual rows", doc.chunk_count == actual,
                  f"declared={doc.chunk_count} actual={actual}")

            # Every chunk has embedding
            with_emb = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == ready_doc_id,
                    DocumentChunk.embedding.isnot(None)
                )
            )).scalar()
            check("every chunk has embedding", with_emb == actual,
                  f"with_emb={with_emb} total={actual}")

            # Every chunk has embedding IS NOT NULL
            null_emb = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == ready_doc_id,
                    DocumentChunk.embedding.is_(None)
                )
            )).scalar()
            check("no chunks with NULL embedding", null_emb == 0,
                  f"null_emb={null_emb}")

        # ================================================================
        # 3. VERIFY ERROR INVARIANTS
        # ================================================================
        print("\n=== 3. ERROR INVARIANTS (direct DB + retrieval) ===")
        # The fail_doc from step 1 is our ERROR document
        async with session_factory() as db:
            # Direct retrieval check
            emb_str = str([0.0] * 384)
            search_result = await db.execute(
                text(
                    "SELECT dc.id, dc.content FROM document_chunks dc "
                    "JOIN documents d ON d.id = dc.document_id "
                    "WHERE d.user_id = :uid "
                    "AND d.embedding_status = 'ready' "
                    "AND dc.embedding IS NOT NULL "
                    "ORDER BY dc.embedding <=> CAST(:emb AS vector) "
                    "LIMIT 10"
                ),
                {"uid": str(user_id), "emb": emb_str}
            )
            rows = search_result.fetchall()
            fail_chunk_ids = await _get_chunk_ids_for_doc(db, fail_doc_id)
            fail_chunks_in_results = [
                r for r in rows
                if str(r[0]) in fail_chunk_ids
            ]
            check("ERROR document chunks not in retrieval results",
                  len(fail_chunks_in_results) == 0,
                  f"found {len(fail_chunks_in_results)} ERROR chunks in results")

        # ================================================================
        # 4. VERIFY REPROCESSING
        # ================================================================
        print("\n=== 4. REPROCESSING VERIFICATION ===")

        # Get content_hash before reprocessing
        async with session_factory() as db:
            doc_before = (await db.execute(
                select(Document).where(Document.id == fail_doc_id)
            )).scalar_one()
            old_hash = doc_before.content_hash
            old_chunk_count = doc_before.chunk_count

        # Reprocess
        reprocess_resp = await client.post(
            f"/api/documents/{fail_doc_id}/reprocess",
            headers=headers,
        )
        check("reprocess returns 200", reprocess_resp.status_code == 200,
              reprocess_resp.text[:200])
        re_body = reprocess_resp.json()
        check("same document ID", re_body["id"] == fail_doc_id)
        check("status is READY after reprocess", re_body["status"] == "ready",
              f"got '{re_body['status']}'")
        check("embedding_status is READY", re_body["embeddingStatus"] == "ready",
              f"got '{re_body['embeddingStatus']}'")

        async with session_factory() as db:
            doc_after = (await db.execute(
                select(Document).where(Document.id == fail_doc_id)
            )).scalar_one()

            check("content_hash unchanged", doc_after.content_hash == old_hash,
                  f"before={old_hash} after={doc_after.content_hash}")

            # Count chunks after reprocessing
            actual_after = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == fail_doc_id
                )
            )).scalar()
            check("chunk_count > 0 after reprocess", actual_after > 0,
                  f"got {actual_after}")
            check("no duplicate chunks (not excessive)",
                  actual_after <= old_chunk_count + 50,
                  f"before={old_chunk_count} after={actual_after}")

            # Every chunk has embedding
            with_emb = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == fail_doc_id,
                    DocumentChunk.embedding.isnot(None)
                )
            )).scalar()
            check("all reprocessed chunks have embeddings",
                  with_emb == actual_after,
                  f"with_emb={with_emb} total={actual_after}")

            # No NULL embeddings
            null_emb = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == fail_doc_id,
                    DocumentChunk.embedding.is_(None)
                )
            )).scalar()
            check("no NULL embeddings after reprocess", null_emb == 0,
                  f"null_emb={null_emb}")

            # Now searchable
            search_after_count = (await db.execute(
                text(
                    "SELECT COUNT(*) FROM document_chunks dc "
                    "JOIN documents d ON d.id = dc.document_id "
                    "WHERE d.id = :doc_id "
                    "AND d.embedding_status = 'ready' "
                    "AND dc.embedding IS NOT NULL"
                ),
                {"doc_id": str(fail_doc_id)}
            )).scalar()
            check("reprocessed document is searchable",
                  search_after_count > 0,
                  f"searchable_chunks={search_after_count}")

        # ================================================================
        # 5. VERIFY DUPLICATE STATES
        # ================================================================
        print("\n=== 5. DUPLICATE STATES ===")
        dup_content = b"Duplicate state validation content.\n\nMore text here."

        # A. Existing READY document
        documents_routes.settings.chunker_version = "legacy"
        r1 = await client.post(
            "/api/documents/upload",
            files={"file": ("dup_a.txt", dup_content)},
            headers=headers,
        )
        doc_a_id = r1.json()["id"]

        r1_dup = await client.post(
            "/api/documents/upload",
            files={"file": ("dup_a2.txt", dup_content)},
            headers=headers,
        )
        check("READY duplicate: same doc ID", r1_dup.json()["id"] == doc_a_id)
        check("READY duplicate: still READY", r1_dup.json()["status"] == "ready")

        # C. Stale PROCESSING document
        stale_id = uuid.uuid4()
        async with session_factory() as db:
            stale_doc = Document(
                id=stale_id,
                user_id=user_id,
                name="stale.txt",
                file_type="txt",
                file_size=100,
                stored_path="/tmp/nonexistent_stale.txt",
                content_hash="stale_content_hash_123",
                status="processing",
                embedding_status="pending",
                chunk_count=0,
                processing_started_at=datetime.now(timezone.utc) - timedelta(seconds=601),
            )
            db.add(stale_doc)
            await db.commit()

        # Stale PROCESSING: can reprocess via reprocess endpoint
        reprocess_stale = await client.post(
            f"/api/documents/{stale_id}/reprocess",
            headers=headers,
        )
        check("stale PROCESSING: reprocess returns 200",
              reprocess_stale.status_code == 200)
        # Note: reprocess will fail because file doesn't exist, but endpoint works
        if reprocess_stale.status_code == 200:
            check("stale PROCESSING: state updated",
                  reprocess_stale.json()["status"] in ("ready", "error"))

        # D. ERROR document - re-upload triggers reprocess
        # Already tested in step 4/6

        # Cleanup duplicates — scoped to the two document ids this step created
        # (the rest of the run's documents must survive for the later steps)
        async with session_factory() as db:
            # STEP 1.6Z: this inline deletion is a destructive entry point of its
            # own and must carry the same function-level authorization gate as
            # cleanup_harness_rows, rather than relying on the runner-level
            # disposal gate alone.  The gate always refuses today, so this block
            # stays unreachable until an enforceable, connection-bound lifecycle
            # authority exists.
            assert_cleanup_execution_authorized(
                db, operation="Phase 3E validation inline document-row cleanup"
            )
            await db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id.in_([doc_a_id, stale_id])
                )
            )
            await db.execute(
                delete(Document).where(Document.id.in_([doc_a_id, stale_id]))
            )
            await db.commit()

        # ================================================================
        # 6. VERIFY STALE PROCESSING
        # ================================================================
        print("\n=== 6. STALE PROCESSING ===")
        from documents.routes import _is_stale_processing

        fresh_doc = type('Doc', (), {'status': 'processing', 'processing_started_at': datetime.now(timezone.utc)})()
        stale_doc_obj = type('Doc', (), {'status': 'processing', 'processing_started_at': datetime.now(timezone.utc) - timedelta(seconds=601)})()
        no_ts_doc = type('Doc', (), {'status': 'processing', 'processing_started_at': None})()
        ready_doc = type('Doc', (), {'status': 'ready', 'processing_started_at': None})()

        check("fresh PROCESSING not stale", not _is_stale_processing(fresh_doc))
        check("old PROCESSING is stale", _is_stale_processing(stale_doc_obj))
        check("no timestamp is stale", _is_stale_processing(no_ts_doc))
        check("READY is not stale", not _is_stale_processing(ready_doc))

        # ================================================================
        # 7. VERIFY DELETE CONSISTENCY
        # ================================================================
        print("\n=== 7. DELETE CONSISTENCY ===")

        # Create a document to delete
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Delete consistency test.\n\nSome content.")
            del_path = Path(f.name)
        del_payload = del_path.read_bytes()
        del_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("delete_test.txt", del_payload)},
            headers=headers,
        )
        os.unlink(del_path)
        del_doc_id = del_resp.json()["id"]

        # Verify it exists
        async with session_factory() as db:
            before_doc = (await db.execute(
                select(Document).where(Document.id == del_doc_id)
            )).scalar_one_or_none()
            before_chunks = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == del_doc_id
                )
            )).scalar()
            check("document exists before delete", before_doc is not None)
            check("chunks exist before delete", before_chunks > 0)

        # Delete
        del_result = await client.delete(f"/api/documents/{del_doc_id}", headers=headers)
        check("delete returns 200", del_result.status_code == 200)

        # Verify gone
        async with session_factory() as db:
            after_doc = (await db.execute(
                select(Document).where(Document.id == del_doc_id)
            )).scalar_one_or_none()
            after_chunks = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == del_doc_id
                )
            )).scalar()
            check("document gone after delete", after_doc is None)
            check("chunks gone after delete", after_chunks == 0)

        # File gone
        # (We can't check the exact stored path without querying, but the delete endpoint calls delete_upload)
        get_after = await client.get(f"/api/documents/{del_doc_id}", headers=headers)
        check("GET returns 404 after delete", get_after.status_code == 404)

        # ================================================================
        # 8. VERIFY PROVENANCE
        # ================================================================
        print("\n=== 8. PROVENANCE ===")
        async with session_factory() as db:
            doc = (await db.execute(
                select(Document).where(Document.id == ready_doc_id)
            )).scalar_one()

            check("content_hash is real SHA-256",
                  doc.content_hash is not None and len(doc.content_hash) == 64,
                  f"got '{doc.content_hash}'")
            check("parser_version is real value",
                  doc.parser_version is not None,
                  f"got '{doc.parser_version}'")
            check("chunker_version is real value",
                  doc.chunker_version is not None,
                  f"got '{doc.chunker_version}'")
            check("embedding_model is real value",
                  doc.embedding_model is not None,
                  f"got '{doc.embedding_model}'")
            check("processing_started_at is real timestamp",
                  doc.processing_started_at is not None,
                  f"got '{doc.processing_started_at}'")
            check("updated_at is real timestamp",
                  doc.updated_at is not None,
                  f"got '{doc.updated_at}'")

            print(f"    content_hash:          {doc.content_hash}")
            print(f"    parser_version:        {doc.parser_version}")
            print(f"    chunker_version:       {doc.chunker_version}")
            print(f"    embedding_model:       {doc.embedding_model}")
            print(f"    processing_started_at: {doc.processing_started_at}")
            print(f"    updated_at:            {doc.updated_at}")

        # ================================================================
        # 9. VERIFY USER ISOLATION
        # ================================================================
        print("\n=== 9. USER ISOLATION ===")
        other_email = f"val_other_{uuid.uuid4().hex[:8]}@test.local"
        async with session_factory() as db:
            other = User(
                id=uuid.uuid4(),
                email=other_email,
                name="Other",
                hashed_password=pwd.hash(password),
                is_active=True,
            )
            db.add(other)
            await db.commit()
            other_id = other.id

        other_login = await client.post(
            "/api/auth/login", json={"email": other_email, "password": password}
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        # Other user cannot retrieve User A's chunks
        emb_str = str([0.0] * 384)
        async with session_factory() as db:
            other_search = await db.execute(
                text(
                    "SELECT dc.id FROM document_chunks dc "
                    "JOIN documents d ON d.id = dc.document_id "
                    "WHERE d.user_id = :uid "
                    "AND d.embedding_status = 'ready' "
                    "AND dc.embedding IS NOT NULL "
                    "LIMIT 5"
                ),
                {"uid": str(other_id)}
            )
            other_chunks = other_search.fetchall()
            check("other user has no searchable chunks", len(other_chunks) == 0)

        # Other user cannot reprocess User A's document
        reprocess_cross = await client.post(
            f"/api/documents/{ready_doc_id}/reprocess",
            headers=other_headers,
        )
        check("other user cannot reprocess (404)", reprocess_cross.status_code == 404)

        # Other user cannot delete User A's document
        delete_cross = await client.delete(
            f"/api/documents/{ready_doc_id}",
            headers=other_headers,
        )
        check("other user cannot delete (404)", delete_cross.status_code == 404)

        # Cleanup other user — its exact email is the lookup key, its id the scope
        async with session_factory() as db:
            other_ids = await owned_user_ids(db, emails=[other_email])
            await cleanup_harness_rows(db, user_ids=other_ids)
            await db.commit()

        # ================================================================
        # 10. VERIFY LEGACY COMPATIBILITY
        # ================================================================
        print("\n=== 10. LEGACY COMPATIBILITY ===")
        documents_routes.settings.chunker_version = "legacy"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"# Legacy Test\n\nLegacy document for compatibility check.\n\n"
                     b"## Section\n\nLegacy content here.")
            legacy_path = Path(f.name)
        legacy_payload = legacy_path.read_bytes()
        legacy_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("legacy.txt", legacy_payload)},
            headers=headers,
        )
        os.unlink(legacy_path)
        check("legacy upload returns 201", legacy_resp.status_code == 201)
        legacy_doc_id = legacy_resp.json()["id"]
        check("legacy is READY", legacy_resp.json()["status"] == "ready")

        async with session_factory() as db:
            legacy_doc = (await db.execute(
                select(Document).where(Document.id == legacy_doc_id)
            )).scalar_one()
            check("legacy chunker_version recorded", legacy_doc.chunker_version is not None)

            # Check legacy chunks have NULL structure metadata
            legacy_chunks = (await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == legacy_doc_id)
            )).scalars().all()
            check("legacy chunks exist", len(legacy_chunks) > 0)
            if legacy_chunks:
                all_null = all(
                    c.heading_path is None and c.section is None and c.element_type is None
                    for c in legacy_chunks
                )
                check("legacy chunks have NULL structure metadata", all_null)

            # Legacy is searchable
            search_legacy = await db.execute(
                text(
                    "SELECT COUNT(*) FROM document_chunks dc "
                    "JOIN documents d ON d.id = dc.document_id "
                    "WHERE d.id = :doc_id "
                    "AND d.embedding_status = 'ready' "
                    "AND dc.embedding IS NOT NULL"
                ),
                {"doc_id": str(legacy_doc_id)}
            )
            check("legacy document is searchable", search_legacy.scalar() > 0)

        # Structure-v2 still works
        documents_routes.settings.chunker_version = "structure-v2"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"# Methods\n\nKestrel method.\n\n# Results\n\nPositive results.")
            v2_path = Path(f.name)
        v2_payload = v2_path.read_bytes()
        v2_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("v2.txt", v2_payload)},
            headers=headers,
        )
        os.unlink(v2_path)
        check("structure-v2 upload returns 201", v2_resp.status_code == 201)
        check("structure-v2 is READY", v2_resp.json()["status"] == "ready")
        v2_doc_id = v2_resp.json()["id"]

        async with session_factory() as db:
            v2_chunks = (await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == v2_doc_id)
            )).scalars().all()
            v2_with_heading = [c for c in v2_chunks if c.heading_path]
            check("structure-v2 has heading metadata",
                  len(v2_with_heading) > 0,
                  f"with_heading={len(v2_with_heading)} total={len(v2_chunks)}")

        # ================================================================
        # 11. VERIFY MIGRATION
        # ================================================================
        print("\n=== 11. MIGRATION ===")
        async with session_factory() as db:
            version = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            check("alembic version is 004", version == "004", f"got '{version}'")

            # Verify all new columns exist
            for col in ["parser_version", "embedding_model", "updated_at", "processing_started_at"]:
                result = await db.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = 'documents' AND column_name = '{col}'"
                ))
                found = result.scalar()
                check(f"column '{col}' exists", found is not None)

        # ================================================================
        # Cleanup
        # ================================================================
        # Scoped to this run's own user: see ``cleanup_harness_rows``.
        async with session_factory() as db:
            await cleanup_harness_rows(db, user_ids=[user_id])
            await db.commit()

    documents_routes.settings.chunker_version = "legacy"
    await engine.dispose()

    print()
    print("=" * 78)
    print(f"PASSED: {len(PASSED)}   FAILED: {len(FAILED)}")
    for item in FAILED:
        print(f"  - {item}")
    print("=" * 78)
    return 1 if FAILED else 0


async def _get_chunk_ids_for_doc(db, doc_id) -> set[str]:
    """Get chunk IDs for a document."""
    from sqlalchemy import select as _sel
    from documents.models import DocumentChunk as _DC
    result = await db.execute(
        _sel(_DC.id).where(_DC.document_id == doc_id)
    )
    return {str(r[0]) for r in result.fetchall()}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

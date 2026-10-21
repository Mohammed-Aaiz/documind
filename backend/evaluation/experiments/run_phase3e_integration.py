"""Phase 3E — processing lifecycle integration test (real PostgreSQL).

Tests the real upload -> process -> READY pipeline, reprocessing,
duplicate handling, delete consistency, stale processing detection,
and version provenance against real PostgreSQL + pgvector.

Usage::

    cd backend
    python test_phase3e_integration.py
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
    assert_engine_matches_target,
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

    The harness names its two users ``phase3e_<8 hex>@test.local`` and
    ``phase3e_other_<8 hex>@test.local``; the suffix is random per run (so two
    runs cannot collide), which means the *id* is what carries ownership within a
    run.  The exact-email lookup is used for the temporary isolation-check user,
    whose id is created three steps earlier in a different session.
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
      (``user_id``) or to the temporary isolation-check user removed in step 8,
      which is what makes the user id set the narrowest correct scope.

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

    assert_cleanup_execution_authorized(db, operation="Phase 3E integration row cleanup")
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
        operation="the Phase 3E processing-lifecycle integration harness (it deletes rows it owns)",
        application_url=application_dsn,
    )
    # Validity (above) is not permission to destroy: the operator must also name this exact database.
    assert_disposal_authorized(
        evaluation_dsn,
        operation="the Phase 3E processing-lifecycle integration harness (it deletes rows it owns)",
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
    # still be the approved target before any database-dependent import.
    from config import get_settings

    get_settings.cache_clear()
    if get_settings().database_url != evaluation_dsn:
        raise RuntimeError(
            "the effective application settings name a different database than the "
            "approved evaluation target; refusing before any database import"
        )

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from auth.models import User  # noqa: F401
    from documents.models import Document, DocumentChunk  # noqa: F401
    from chat.models import ChatSession, ChatMessage  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401

    # The application engine is built from settings when storage.database is first
    # imported.  Verify it targets the approved database before any route runs.
    from storage.database import engine as application_engine

    assert_engine_matches_target(application_engine, evaluation_dsn)

    from passlib.context import CryptContext

    import documents.routes as documents_routes
    from documents.chunking import CHUNKER_VERSION_LEGACY, CHUNKER_VERSION_STRUCTURE
    from main import app

    email = f"phase3e_{uuid.uuid4().hex[:8]}@test.local"
    password = "TestPass123!"

    engine = create_async_engine(evaluation_dsn)
    assert_engine_matches_target(engine, evaluation_dsn)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 78)
    print("PHASE 3E — PROCESSING LIFECYCLE INTEGRATION (real PostgreSQL)")
    print("=" * 78)

    async with session_factory() as db:
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        user = User(
            id=uuid.uuid4(),
            email=email,
            name="Phase3E",
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
        check("login succeeds", login.status_code == 200, login.text[:160])
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # ==================================================================
        # 1. Successful upload -> READY
        # ==================================================================
        print("\n--- 1. Successful upload -> READY ---")
        documents_routes.settings.chunker_version = "legacy"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"# Introduction\n\nThis is a test document with enough content.\n\n"
                     b"## Methods\n\nWe used the standard approach for testing.\n\n"
                     b"## Results\n\nThe results show significant improvement over baseline.")
            txt_path = Path(f.name)

        payload = txt_path.read_bytes()
        upload = await client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", payload)},
            headers=headers,
        )
        check("upload returns 201", upload.status_code == 201, upload.text[:200])
        doc_body = upload.json()
        doc_id = doc_body["id"]

        check("status is READY", doc_body["status"] == "ready", f"got {doc_body['status']}")
        check("embedding_status is READY", doc_body["embeddingStatus"] == "ready",
              f"got {doc_body['embeddingStatus']}")
        check("chunkCount > 0", doc_body["chunkCount"] > 0, str(doc_body["chunkCount"]))

        # Verify version provenance
        async with session_factory() as db:
            doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
            check("parser_version is set", doc.parser_version is not None,
                  str(doc.parser_version))
            check("embedding_model is set", doc.embedding_model is not None,
                  str(doc.embedding_model))
            check("chunker_version is set", doc.chunker_version is not None,
                  str(doc.chunker_version))
            check("updated_at is set", doc.updated_at is not None)
            check("processing_started_at is set", doc.processing_started_at is not None)

        os.unlink(txt_path)

        # ==================================================================
        # 2. Duplicate READY upload returns existing
        # ==================================================================
        print("\n--- 2. Duplicate READY upload ---")
        dup_upload = await client.post(
            "/api/documents/upload",
            files={"file": ("test2.txt", payload)},
            headers=headers,
        )
        check("duplicate upload returns 201", dup_upload.status_code == 201)
        check("duplicate returns same doc ID", dup_upload.json()["id"] == doc_id)

        # ==================================================================
        # 3. Embedding failure -> ERROR
        # ==================================================================
        print("\n--- 3. Embedding failure -> ERROR ---")
        documents_routes.settings.chunker_version = "legacy"
        with patch("documents.routes.embed_texts", side_effect=RuntimeError("model unavailable")):
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
                f.write(b"Content for embedding failure test.\n\nMore content here.")
                fail_path = Path(f.name)
            fail_payload = fail_path.read_bytes()
            fail_upload = await client.post(
                "/api/documents/upload",
                files={"file": ("fail.txt", fail_payload)},
                headers=headers,
            )
            os.unlink(fail_path)

        check("embedding failure upload returns 201", fail_upload.status_code == 201)
        fail_body = fail_upload.json()
        check("status is ERROR after embedding failure",
              fail_body["status"] == "error", f"got {fail_body['status']}")
        check("embedding_status is ERROR after embedding failure",
              fail_body["embeddingStatus"] == "error", f"got {fail_body['embeddingStatus']}")
        check("READY invariant: not READY with embedding error",
              fail_body["status"] != "ready" or fail_body["embeddingStatus"] == "ready")
        fail_doc_id = fail_body["id"]

        # ==================================================================
        # 4. ERROR document is not searchable
        # ==================================================================
        print("\n--- 4. ERROR document not searchable ---")
        search = await client.post(
            "/api/embeddings/search",
            json={"query": "embedding failure test", "topK": 5},
            headers=headers,
        )
        check("search returns 200", search.status_code == 200)
        search_results = search.json().get("results", [])
        error_doc_ids = {r["documentId"] for r in search_results if r["documentId"] == fail_doc_id}
        check("ERROR document not in search results", len(error_doc_ids) == 0)

        # ==================================================================
        # 5. Reprocessing ERROR document succeeds
        # ==================================================================
        print("\n--- 5. Reprocessing ERROR document ---")
        reprocess = await client.post(
            f"/api/documents/{fail_doc_id}/reprocess",
            headers=headers,
        )
        check("reprocess returns 200", reprocess.status_code == 200, reprocess.text[:200])
        re_body = reprocess.json()
        check("reprocessed document is READY", re_body["status"] == "ready",
              f"got {re_body['status']}")
        check("reprocessed embedding_status is READY", re_body["embeddingStatus"] == "ready",
              f"got {re_body['embeddingStatus']}")
        check("reprocessed has chunks", re_body["chunkCount"] > 0)

        # Verify reprocessed document now appears in search
        search2 = await client.post(
            "/api/embeddings/search",
            json={"query": "embedding failure test", "topK": 5},
            headers=headers,
        )
        search2_results = search2.json().get("results", [])
        found_in_search = any(r["documentId"] == fail_doc_id for r in search2_results)
        check("reprocessed document now searchable", found_in_search)

        # ==================================================================
        # 6. Duplicate upload of ERROR document triggers reprocess
        # ==================================================================
        print("\n--- 6. Duplicate upload of ERROR document ---")
        # Create a new error document
        documents_routes.settings.chunker_version = "legacy"
        with patch("documents.routes.embed_texts", side_effect=RuntimeError("fail")):
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
                f.write(b"Error duplicate test content.\n\nMore text here.")
                err_path = Path(f.name)
            err_payload = err_path.read_bytes()
            err_upload = await client.post(
                "/api/documents/upload",
                files={"file": ("err.txt", err_payload)},
                headers=headers,
            )
            os.unlink(err_path)
        err_doc_id = err_upload.json()["id"]
        check("error doc created", err_upload.json()["status"] == "error")

        # Re-upload same content — should reprocess
        reupload = await client.post(
            "/api/documents/upload",
            files={"file": ("err.txt", err_payload)},
            headers=headers,
        )
        check("re-upload of ERROR doc returns 201", reupload.status_code == 201)
        check("re-upload reprocessed to READY",
              reupload.json()["status"] == "ready",
              f"got {reupload.json()['status']}")
        check("same document ID preserved",
              reupload.json()["id"] == err_doc_id)

        # ==================================================================
        # 7. Delete consistency
        # ==================================================================
        print("\n--- 7. Delete consistency ---")
        # Create a document to delete
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Delete me.\n\nSome content for deletion test.")
            del_path = Path(f.name)
        del_payload = del_path.read_bytes()
        del_upload = await client.post(
            "/api/documents/upload",
            files={"file": ("delete.txt", del_payload)},
            headers=headers,
        )
        os.unlink(del_path)
        del_doc_id = del_upload.json()["id"]

        # Delete it
        del_resp = await client.delete(f"/api/documents/{del_doc_id}", headers=headers)
        check("delete returns 200", del_resp.status_code == 200)

        # Verify document is gone
        get_resp = await client.get(f"/api/documents/{del_doc_id}", headers=headers)
        check("deleted document not found", get_resp.status_code == 404)

        # Verify chunks are gone
        async with session_factory() as db:
            chunks = (await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == del_doc_id)
            )).scalars().all()
            check("chunks cascaded on delete", len(chunks) == 0)

        # ==================================================================
        # 8. User isolation
        # ==================================================================
        print("\n--- 8. User isolation ---")
        other_email = f"phase3e_other_{uuid.uuid4().hex[:8]}@test.local"
        async with session_factory() as db:
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
            other_user = User(
                id=uuid.uuid4(),
                email=other_email,
                name="Phase3E Other",
                hashed_password=pwd.hash(password),
                is_active=True,
            )
            db.add(other_user)
            await db.commit()

        other_login = await client.post(
            "/api/auth/login", json={"email": other_email, "password": password}
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        other_ask = await client.post(
            "/api/chat/ask",
            json={"question": "What does the introduction describe?", "topK": 5},
            headers=other_headers,
        )
        check("other user gets no sources",
              other_ask.json().get("sources") == [])
        check("other user gets no answer",
              other_ask.json().get("answer") == "")

        # Cleanup other user — its exact email is the lookup key, its id the scope
        async with session_factory() as db:
            other_ids = await owned_user_ids(db, emails=[other_email])
            await cleanup_harness_rows(db, user_ids=other_ids)
            await db.commit()

        # ==================================================================
        # 9. Stale PROCESSING detection
        # ==================================================================
        print("\n--- 9. Stale PROCESSING detection ---")
        # Create a stale processing document directly in DB
        stale_id = uuid.uuid4()
        async with session_factory() as db:
            stale_doc = Document(
                id=stale_id,
                user_id=user_id,
                name="stale.txt",
                file_type="txt",
                file_size=100,
                stored_path="/tmp/nonexistent.txt",
                content_hash="stale_hash",
                status="processing",
                embedding_status="pending",
                chunk_count=0,
                processing_started_at=datetime.now(timezone.utc) - timedelta(seconds=601),
            )
            db.add(stale_doc)
            await db.commit()

        # Verify the stale document was created
        async with session_factory() as db:
            stale_check = (await db.execute(
                select(Document).where(Document.id == stale_id)
            )).scalar_one_or_none()
            check("stale document created in DB", stale_check is not None)
            if stale_check:
                check("stale document has processing_started_at",
                      stale_check.processing_started_at is not None)
                from documents.routes import _is_stale_processing
                check("stale document detected as stale",
                      _is_stale_processing(stale_check))

        # Cleanup stale — scoped to the one document id this step inserted
        async with session_factory() as db:
            # STEP 1.6Z: this inline deletion is a destructive entry point of its
            # own and must carry the same function-level authorization gate as
            # cleanup_harness_rows, rather than relying on the runner-level
            # disposal gate alone.  The gate always refuses today, so this block
            # stays unreachable until an enforceable, connection-bound lifecycle
            # authority exists.
            assert_cleanup_execution_authorized(
                db, operation="Phase 3E integration inline document-row cleanup"
            )
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == stale_id)
            )
            await db.execute(delete(Document).where(Document.id == stale_id))
            await db.commit()

        # ==================================================================
        # 10. Structure-v2 upload still works
        # ==================================================================
        print("\n--- 10. Structure-v2 still works ---")
        documents_routes.settings.chunker_version = "structure-v2"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"# Methods\n\nWe used the Kestrel method.\n\n"
                     b"## Results\n\nThe results were positive.\n\n"
                     b"# Conclusion\n\nThis concludes the report.")
            v2_path = Path(f.name)
        v2_payload = v2_path.read_bytes()
        v2_upload = await client.post(
            "/api/documents/upload",
            files={"file": ("v2_test.txt", v2_payload)},
            headers=headers,
        )
        os.unlink(v2_path)
        check("structure-v2 upload returns 201", v2_upload.status_code == 201)
        check("structure-v2 is READY", v2_upload.json()["status"] == "ready")
        check("structure-v2 embedding is READY", v2_upload.json()["embeddingStatus"] == "ready")

        # ==================================================================
        # Cleanup
        # ==================================================================
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


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

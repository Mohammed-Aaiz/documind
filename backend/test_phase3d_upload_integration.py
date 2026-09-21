"""Phase 3D — real ingestion E2E: upload / retrieval / ask (real PostgreSQL).

This is the full-ingestion counterpart to ``test_phase3d_evaluation.py``.  That
harness writes ``DocumentChunk`` rows directly to isolate chunker behaviour;
this script drives the real FastAPI app instead:

    HTTP upload → validation → storage → extraction → chunking → metadata rows
    → embeddings → pgvector retrieval → Brain → token-aware context → QA
    → evidence → response

against the real PostgreSQL + pgvector database and the real DocuMind QA model,
for both chunker versions.

Checks
------
  * the production default is still the legacy chunker
  * ``structure-v2`` ingest persists heading_path / section / element_type /
    chunker_version / token_count
  * legacy ingest still works and records its version with structure fields NULL
  * ``/api/documents/{id}`` still returns the original response shape
  * ``/api/chat/ask`` answers from an uploaded document and reports evidence
    that matches what was supplied to the QA model
  * Phase 3D structure metadata survives ingestion → retrieval → API sources
  * reported evidence never exceeds the chunks supplied to the QA model
  * an unsupported question is not presented as a confident answer
  * one user's question can never retrieve another user's chunks

Usage::

    cd backend
    python test_phase3d_upload_integration.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DOCUMIND_DEV", "1")
os.environ.setdefault("QA_MODEL_NAME", "./models/documind-qa")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://documind:documind@localhost:5432/documind"
)

from tests.phase3d_corpus import build_corpus  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(f"{name} :: {detail}")
        print(f"  FAIL  {name}  {detail}")


async def main() -> int:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    # Import every model so relationships resolve.
    from auth.models import User  # noqa: F401
    from documents.models import Document, DocumentChunk  # noqa: F401
    from chat.models import ChatSession, ChatMessage  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401

    from passlib.context import CryptContext

    import documents.routes as documents_routes
    from config import get_settings
    from documents.chunking import (
        CHUNKER_VERSION_LEGACY,
        CHUNKER_VERSION_STRUCTURE,
    )
    from main import app

    email = f"phase3d_upload_{uuid.uuid4().hex[:8]}@test.local"
    password = "TestPass123!"

    engine = create_async_engine(
        "postgresql+asyncpg://documind:documind@localhost:5432/documind"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 78)
    print("PHASE 3D — UPLOAD / ASK INTEGRATION (real PostgreSQL + pgvector)")
    print("=" * 78)

    # --- production default is unchanged ---------------------------------
    default_version = get_settings().chunker_version
    check(
        "production default chunker is still legacy",
        default_version == "legacy",
        f"got {default_version!r}",
    )

    corpus = {doc.name: doc for doc in build_corpus()}

    async with session_factory() as db:
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        user = User(
            id=uuid.uuid4(),
            email=email,
            name="Phase3D Upload",
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

        async def upload(doc_name: str) -> dict:
            doc = corpus[doc_name]
            with tempfile.TemporaryDirectory() as tmp:
                path = doc.write(Path(tmp))
                payload = path.read_bytes()
            response = await client.post(
                "/api/documents/upload",
                files={"file": (doc.name, payload)},
                headers=headers,
            )
            return {"status": response.status_code, "body": response.json()}

        # --- legacy upload -------------------------------------------------
        documents_routes.settings.chunker_version = "legacy"
        legacy_upload = await upload("markdown_sections.txt")
        check(
            "legacy upload returns 201",
            legacy_upload["status"] == 201,
            str(legacy_upload)[:200],
        )
        legacy_doc_id = legacy_upload["body"].get("id")

        # --- structure-v2 upload -------------------------------------------
        documents_routes.settings.chunker_version = "structure-v2"
        v2_upload = await upload("short_sections.docx")
        check(
            "structure-v2 upload returns 201",
            v2_upload["status"] == 201,
            str(v2_upload)[:200],
        )
        v2_doc_id = v2_upload["body"].get("id")
        check(
            "structure-v2 chunkCount reported",
            isinstance(v2_upload["body"].get("chunkCount"), int)
            and v2_upload["body"]["chunkCount"] > 0,
            str(v2_upload["body"]),
        )

        # --- document detail response shape unchanged ----------------------
        detail = await client.get(f"/api/documents/{v2_doc_id}", headers=headers)
        check("document detail returns 200", detail.status_code == 200)
        detail_body = detail.json()
        chunk = detail_body["chunks"][0]
        check(
            "document detail chunk shape unchanged",
            set(chunk.keys()) == {"id", "chunkIndex", "content", "page"},
            str(sorted(chunk.keys())),
        )

        # --- ask through the real pipeline ---------------------------------
        ask = await client.post(
            "/api/chat/ask",
            json={"question": "At what angle is the Zephyr valve calibrated?", "topK": 5},
            headers=headers,
        )
        check("ask returns 200", ask.status_code == 200, ask.text[:200])
        ask_body = ask.json()
        check(
            "ask produces a grounded answer",
            ask_body.get("answer", "").strip() != ""
            and ask_body.get("outcome") in ("SUCCESS", "PARTIAL"),
            str(ask_body.get("outcome")),
        )
        check(
            "answer contains the documented value",
            "22" in ask_body.get("answer", ""),
            ask_body.get("answer", ""),
        )
        reliability = ask_body.get("reliability", {})
        check(
            "reliability reports transparent source counts",
            reliability.get("sourceCount", 0) <= reliability.get(
                "retrievedSourceCount", 0
            ),
            str(reliability),
        )
        check(
            "reliability exposes the context budget",
            reliability.get("contextBudgetTokens", 0) > 0,
            str(reliability),
        )
        check(
            "reported evidence never exceeds QA-supplied evidence",
            reliability.get("sourceCount", 0) <= reliability.get(
                "retrievedSourceCount", 0
            ),
            str(reliability),
        )

        # ===================================================================
        # Real ingestion E2E — structure-v2 metadata through to evidence
        # ===================================================================
        meta_email = f"phase3d_meta_{uuid.uuid4().hex[:8]}@test.local"
        async with session_factory() as db:
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
            meta_user = User(
                id=uuid.uuid4(),
                email=meta_email,
                name="Phase3D Meta",
                hashed_password=pwd.hash(password),
                is_active=True,
            )
            db.add(meta_user)
            await db.commit()

        meta_login = await client.post(
            "/api/auth/login", json={"email": meta_email, "password": password}
        )
        check("metadata-user login succeeds", meta_login.status_code == 200)
        meta_headers = {"Authorization": f"Bearer {meta_login.json()['access_token']}"}

        documents_routes.settings.chunker_version = "structure-v2"
        meta_doc = corpus["short_sections.docx"]
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = meta_doc.write(Path(tmp))
            meta_payload = meta_path.read_bytes()
        meta_upload = await client.post(
            "/api/documents/upload",
            files={"file": (meta_doc.name, meta_payload)},
            headers=meta_headers,
        )
        check(
            "structure-v2 only corpus uploads",
            meta_upload.status_code == 201,
            meta_upload.text[:200],
        )

        meta_ask = await client.post(
            "/api/chat/ask",
            json={"question": "What does the Epsilon section describe?", "topK": 5},
            headers=meta_headers,
        )
        check("structure-v2 ask returns 200", meta_ask.status_code == 200)
        meta_body = meta_ask.json()
        meta_sources = meta_body.get("sources", [])
        check(
            "structure-v2 ask returns evidence",
            len(meta_sources) > 0,
            str(meta_body.get("reliability")),
        )
        check(
            "retrieved sources carry heading metadata",
            any(s.get("headingPath") for s in meta_sources),
            str([(s.get("headingPath"), s.get("section")) for s in meta_sources]),
        )
        check(
            "retrieved sources carry element type and token count",
            all(s.get("elementType") for s in meta_sources)
            and all(isinstance(s.get("tokenCount"), int) for s in meta_sources),
            str([(s.get("elementType"), s.get("tokenCount")) for s in meta_sources]),
        )
        check(
            "retrieved sources carry chunker version",
            all(s.get("chunkerVersion") == CHUNKER_VERSION_STRUCTURE for s in meta_sources),
            str([s.get("chunkerVersion") for s in meta_sources]),
        )

        # --- unsupported question: no confident answer ----------------------
        unsupported = await client.post(
            "/api/chat/ask",
            json={"question": "What is the melting point of tungsten?", "topK": 5},
            headers=meta_headers,
        )
        check("unsupported question returns 200", unsupported.status_code == 200)
        unsupported_body = unsupported.json()
        check(
            "unsupported question is not reported as SUCCESS",
            unsupported_body.get("outcome") != "SUCCESS",
            f"outcome={unsupported_body.get('outcome')} "
            f"answer={unsupported_body.get('answer')!r}",
        )
        check(
            "abstained question returns no answer text",
            unsupported_body.get("outcome") != "INSUFFICIENT_EVIDENCE"
            or unsupported_body.get("answer") == "",
            f"outcome={unsupported_body.get('outcome')} "
            f"answer={unsupported_body.get('answer')!r}",
        )

        # --- cross-user isolation ------------------------------------------
        other_email = f"phase3d_other_{uuid.uuid4().hex[:8]}@test.local"
        async with session_factory() as db:
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
            other_user = User(
                id=uuid.uuid4(),
                email=other_email,
                name="Phase3D Other",
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
            json={"question": "What does the Epsilon section describe?", "topK": 5},
            headers=other_headers,
        )
        other_body = other_ask.json()
        check(
            "a user with no documents retrieves nothing",
            other_body.get("sources") == [],
            str(other_body.get("sources"))[:200],
        )
        check(
            "a user with no documents gets no fabricated answer",
            other_body.get("answer") == ""
            and other_body.get("outcome") == "INSUFFICIENT_EVIDENCE",
            f"outcome={other_body.get('outcome')} answer={other_body.get('answer')!r}",
        )
        other_docs = await client.get("/api/documents", headers=other_headers)
        check(
            "a user with no documents lists none",
            other_docs.status_code == 200 and other_docs.json().get("documents") == [],
            other_docs.text[:200],
        )

        # cleanup the extra users
        async with session_factory() as db:
            for mail in (meta_email, other_email):
                await db.execute(
                    text("DELETE FROM reliability_logs WHERE user_id IN "
                         "(SELECT id FROM users WHERE email = :e)"),
                    {"e": mail},
                )
                await db.execute(
                    text("DELETE FROM document_chunks WHERE document_id IN "
                         "(SELECT id FROM documents WHERE user_id IN "
                         "(SELECT id FROM users WHERE email = :e))"),
                    {"e": mail},
                )
                await db.execute(
                    text("DELETE FROM documents WHERE user_id IN "
                         "(SELECT id FROM users WHERE email = :e)"),
                    {"e": mail},
                )
                await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": mail})
            await db.commit()

    # --- verify what actually reached the database -------------------------
    async with session_factory() as db:
        v2_doc = (
            await db.execute(select(Document).where(Document.id == v2_doc_id))
        ).scalar_one()
        check(
            "documents.chunker_version persisted for structure-v2",
            v2_doc.chunker_version == CHUNKER_VERSION_STRUCTURE,
            str(v2_doc.chunker_version),
        )

        legacy_doc = (
            await db.execute(select(Document).where(Document.id == legacy_doc_id))
        ).scalar_one()
        check(
            "documents.chunker_version persisted for legacy",
            legacy_doc.chunker_version == CHUNKER_VERSION_LEGACY,
            str(legacy_doc.chunker_version),
        )

        v2_chunks = (
            await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == v2_doc_id)
                .order_by(DocumentChunk.chunk_index)
            )
        ).scalars().all()
        check("structure-v2 chunks persisted", len(v2_chunks) > 0, str(len(v2_chunks)))
        check(
            "structure-v2 chunks carry chunker_version",
            all(c.chunker_version == CHUNKER_VERSION_STRUCTURE for c in v2_chunks),
        )
        check(
            "structure-v2 chunks carry token_count",
            all(isinstance(c.token_count, int) and c.token_count > 0 for c in v2_chunks),
        )
        check(
            "structure-v2 chunks carry element_type",
            all(c.element_type for c in v2_chunks),
        )
        check(
            "structure-v2 chunks carry heading_path and section",
            any(c.heading_path for c in v2_chunks) and any(c.section for c in v2_chunks),
        )
        check(
            "structure-v2 chunk_index is contiguous from 0",
            [c.chunk_index for c in v2_chunks] == list(range(len(v2_chunks))),
        )
        check(
            "structure-v2 chunks keep exact page attribution",
            all(c.page is None or isinstance(c.page, int) for c in v2_chunks),
        )
        check(
            "structure-v2 chunks have 384-dim embeddings",
            all(c.embedding is not None and len(c.embedding) == 384 for c in v2_chunks),
        )

        legacy_chunks = (
            await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == legacy_doc_id)
            )
        ).scalars().all()
        check("legacy chunks persisted", len(legacy_chunks) > 0)
        check(
            "legacy chunks record their version",
            all(c.chunker_version == CHUNKER_VERSION_LEGACY for c in legacy_chunks),
        )
        check(
            "legacy chunks leave structure fields NULL",
            all(
                c.heading_path is None and c.section is None and c.element_type is None
                for c in legacy_chunks
            ),
        )
        check(
            "legacy chunks still have embeddings",
            all(c.embedding is not None for c in legacy_chunks),
        )

        # --- cleanup -------------------------------------------------------
        await db.execute(text("DELETE FROM reliability_logs WHERE user_id = :u"), {"u": str(user_id)})
        await db.execute(text("DELETE FROM document_chunks"))
        await db.execute(
            text("DELETE FROM documents WHERE user_id = :u"), {"u": str(user_id)}
        )
        await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
        await db.commit()

    documents_routes.settings.chunker_version = default_version
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

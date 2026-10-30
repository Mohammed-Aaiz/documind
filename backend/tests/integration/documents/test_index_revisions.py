"""Archive ownership and reprocessing atomicity on the isolated SQLite store."""
import hashlib
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from documents.models import Document, DocumentChunk, DocumentIndexRevision


async def indexed_document(client, db, create_user, tmp_path):
    user = await create_user(email=f"archive-{uuid.uuid4().hex}@test.com", password="ArchivePass123!")
    login = await client.post("/api/auth/login", json={"email": user.email, "password": "ArchivePass123!"})
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    path = tmp_path / "source.txt"
    path.write_text("The original uploaded document must remain intact.")
    doc = Document(user_id=user.id, name="source.txt", file_type="txt", file_size=path.stat().st_size,
                   stored_path=str(path), status="ready", embedding_status="ready", chunk_count=1,
                   chunker_version="legacy", embedding_model="baseline-model")
    db.add(doc)
    await db.flush()
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, content="Original evidence at page four.",
                          page=4, embedding=[.01] * 384, heading_path=["Original topic"],
                          section="Original topic", element_type="paragraph", chunker_version="legacy")
    db.add(chunk)
    await db.commit()
    return headers, doc.id, chunk.id, path


def replacement(monkeypatch, *, fail=False):
    from documents import routes
    async def process(doc, *args):
        db = args[-1]
        if fail:
            doc.status = "error"
            return "pipeline_exception"
        db.add(DocumentChunk(document_id=doc.id, chunk_index=0, content="New structured evidence.",
                             page=5, embedding=[.02] * 384, heading_path=["New topic"],
                             chunker_version="structure-v2"))
        doc.status, doc.embedding_status, doc.chunk_count = "ready", "ready", 1
        doc.chunker_version = "structure-v2"
        return None
    monkeypatch.setattr(routes, "_process_document", process)


@pytest.mark.asyncio
async def test_success_archives_old_source_identity_and_keeps_vectors_private(client, db_session, create_test_user, tmp_path, monkeypatch):
    headers, doc_id, old_id, path = await indexed_document(client, db_session, create_test_user, tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    replacement(monkeypatch)
    response = await client.post(f"/api/documents/{doc_id}/reprocess", headers=headers)
    assert response.status_code == 200, response.text
    db_session.expire_all()
    revision = (await db_session.execute(select(DocumentIndexRevision).where(DocumentIndexRevision.document_id == doc_id))).scalar_one()
    archived = revision.payload["tables"]["document_chunks"][0]
    assert archived["id"] == str(old_id) and archived["content"] == "Original evidence at page four."
    assert archived["page"] == 4 and len(archived["embedding"]) == 384
    assert revision.chunker_version == "legacy" and revision.embedding_model == "baseline-model"
    assert revision.payload["schemaVersion"] == 1
    assert (await db_session.execute(select(DocumentChunk).where(DocumentChunk.id == old_id))).scalar_one_or_none() is None
    listed = await client.get(f"/api/documents/{doc_id}/index-revisions", headers=headers)
    assert listed.status_code == 200 and listed.json()["total"] == 1
    source = await client.get(f"/api/documents/{doc_id}/index-revisions/{revision.id}/sources?chunkId={old_id}", headers=headers)
    assert source.status_code == 200, source.text
    body = source.json()
    assert body["sources"][0]["chunkId"] == str(old_id)
    assert body["sources"][0]["headingPath"] == ["Original topic"]
    assert set(body["sources"][0]) == {"chunkId", "chunkIndex", "content", "page", "headingPath",
                                       "section", "elementType", "tokenCount"}
    assert "payload" not in body and "stored_path" not in source.text
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


@pytest.mark.asyncio
async def test_failed_replacement_rolls_back_new_archive_and_preserves_old_index(client, db_session, create_test_user, tmp_path, monkeypatch):
    headers, doc_id, old_id, path = await indexed_document(client, db_session, create_test_user, tmp_path)
    original = path.read_bytes()
    replacement(monkeypatch, fail=True)
    response = await client.post(f"/api/documents/{doc_id}/reprocess", headers=headers)
    assert response.status_code == 500 and "unchanged" in response.json()["detail"]
    db_session.expire_all()
    chunk = (await db_session.execute(select(DocumentChunk).where(DocumentChunk.id == old_id))).scalar_one()
    assert chunk.content == "Original evidence at page four."
    revisions = (await db_session.execute(select(DocumentIndexRevision).where(DocumentIndexRevision.document_id == doc_id))).scalars().all()
    assert revisions == [] and path.read_bytes() == original


@pytest.mark.asyncio
async def test_archive_failure_refuses_reprocessing_before_deleting_sources(client, db_session, create_test_user, tmp_path, monkeypatch):
    from documents import routes
    headers, doc_id, old_id, _ = await indexed_document(client, db_session, create_test_user, tmp_path)
    process = AsyncMock()
    monkeypatch.setattr(routes, "_process_document", process)
    monkeypatch.setattr(routes, "archive_document_index", AsyncMock(side_effect=RuntimeError("private storage failure")))
    response = await client.post(f"/api/documents/{doc_id}/reprocess", headers=headers)
    assert response.status_code == 503 and "private storage failure" not in response.text
    process.assert_not_awaited()
    db_session.expire_all()
    assert (await db_session.execute(select(DocumentChunk).where(DocumentChunk.id == old_id))).scalar_one()


@pytest.mark.asyncio
async def test_other_account_cannot_list_read_or_reprocess_a_revision(client, db_session, create_test_user, tmp_path, monkeypatch):
    headers, doc_id, _, _ = await indexed_document(client, db_session, create_test_user, tmp_path)
    replacement(monkeypatch)
    assert (await client.post(f"/api/documents/{doc_id}/reprocess", headers=headers)).status_code == 200
    listed = (await client.get(f"/api/documents/{doc_id}/index-revisions", headers=headers)).json()
    revision_id = listed["revisions"][0]["revisionId"]
    other = await create_test_user(email=f"other-{uuid.uuid4().hex}@test.com", password="ArchivePass123!")
    login = await client.post("/api/auth/login", json={"email": other.email, "password": "ArchivePass123!"})
    wrong = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert (await client.get(f"/api/documents/{doc_id}/index-revisions", headers=wrong)).status_code == 404
    assert (await client.get(f"/api/documents/{doc_id}/index-revisions/{revision_id}/sources", headers=wrong)).status_code == 404
    assert (await client.post(f"/api/documents/{doc_id}/reprocess", headers=wrong)).status_code == 404

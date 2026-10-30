"""Bounded KG jobs checkpoint validated chunks, including empty completions."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from documents import kg_extraction, routes
from documents.models import DocumentIndexRevision
from documents.kg_extraction import ExtractedRelation
from generation.types import GenerationUnavailableError
from graph.models import KnowledgeGraphExtraction, KnowledgeGraphRelation
from tests.fixtures.graph_data import create_document_with_chunks


@pytest.fixture
def config(monkeypatch):
    settings = SimpleNamespace(groq_model="test-model", groq_context_tokens=8192)
    monkeypatch.setattr(kg_extraction, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    return settings


async def document(db, create_user, count):
    owner = await create_user(email=f"kg-resume-{uuid.uuid4().hex}@test.com")
    doc, chunks = await create_document_with_chunks(db, owner.id, chunks=[
        {"content": f"Sensor {i} uses Rig {i}.", "index": i} for i in range(count)])
    await db.commit()
    return owner, doc, chunks


def relation(text):
    i = text.split()[1]
    return ExtractedRelation(f"Sensor {i}", "sensor", "uses", f"Rig {i}", "rig", text)


async def persisted(db, doc):
    state = (await db.execute(select(KnowledgeGraphExtraction).where(KnowledgeGraphExtraction.document_id == doc.id))).scalar_one()
    rows = (await db.execute(select(KnowledgeGraphRelation).where(KnowledgeGraphRelation.document_id == doc.id))).scalars().all()
    return state, rows


@pytest.mark.asyncio
async def test_resume_reaches_chunks_beyond_twenty_four_and_ready_is_idempotent(db_session, create_test_user, monkeypatch, config):
    owner, doc, chunks = await document(db_session, create_test_user, 30)
    calls = []
    async def extract(_client, *, text, settings):
        calls.append(text)
        return [relation(text)], "groq:test-model"
    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", extract)
    async def batch():
        status = await kg_extraction.replace_document_knowledge_graph(db_session, user_id=owner.id, document_id=doc.id, chunks=chunks, resume=True)
        await db_session.commit()
        return status
    assert await batch() == "partial"
    state, rows = await persisted(db_session, doc)
    assert state.processed_chunk_count == 24 and state.failure_code == "chunk_limit_reached"
    original_ids = {row.id for row in rows}
    assert len(original_ids) == 24
    assert await batch() == "ready"
    state, rows = await persisted(db_session, doc)
    assert state.processed_chunk_count == 30 and state.failure_code is None
    assert len(rows) == 30 and original_ids <= {row.id for row in rows}
    assert calls == [chunk.content for chunk in chunks]
    assert await batch() == "ready" and len(calls) == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid_json", "rate_limit", "model_mismatch"])
async def test_invalid_chunk_does_not_advance_cursor_or_destroy_prior_edges(db_session, create_test_user, monkeypatch, config, failure):
    owner, doc, chunks = await document(db_session, create_test_user, 4)
    calls, fail = [], [True]
    async def extract(_client, *, text, settings):
        calls.append(text)
        index = int(text.split()[1])
        if index == 2 and fail[0]:
            if failure == "invalid_json":
                raise ValueError("Invalid JSON")
            if failure == "rate_limit":
                error = GenerationUnavailableError("rate limited")
                error.status_code = 429
                raise error
            return [relation(text)], "groq:wrong-model"
        return ([] if index == 1 else [relation(text)]), "groq:test-model"
    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", extract)
    args = dict(user_id=owner.id, document_id=doc.id, chunks=chunks, resume=True)
    assert await kg_extraction.replace_document_knowledge_graph(db_session, **args) == "partial"
    await db_session.commit()
    state, before = await persisted(db_session, doc)
    assert state.processed_chunk_count == 2  # validated [] is completed work
    assert len(before) == 1
    assert state.failure_code == {"invalid_json": "invalid_model_output", "rate_limit": "rate_limit", "model_mismatch": "extractor_model_mismatch"}[failure]
    before_ids = {r.id for r in before}
    fail[0] = False
    assert await kg_extraction.replace_document_knowledge_graph(db_session, **args) == "ready"
    state, after = await persisted(db_session, doc)
    assert state.processed_chunk_count == 4 and len(after) == 3
    assert before_ids <= {r.id for r in after}
    assert calls == [c.content for c in chunks[:3]] + [c.content for c in chunks[2:]]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["model", "content"])
async def test_changed_index_or_model_cannot_resume_an_old_cursor(db_session, create_test_user, monkeypatch, config, change):
    owner, doc, chunks = await document(db_session, create_test_user, 3)
    monkeypatch.setattr(kg_extraction, "MAX_CHUNKS_PER_RUN", 1)
    calls = []
    async def extract(_client, *, text, settings):
        calls.append(text)
        return [], f"groq:{settings.groq_model}"
    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", extract)
    args = dict(user_id=owner.id, document_id=doc.id, chunks=chunks, resume=True)
    await kg_extraction.replace_document_knowledge_graph(db_session, **args)
    state, _ = await persisted(db_session, doc)
    previous_version = state.extractor_version
    if change == "model":
        config.groq_model = "replacement-model"
    else:
        chunks[-1].content += " Changed indexed source."
        await db_session.flush()
    await kg_extraction.replace_document_knowledge_graph(db_session, **args)
    state, _ = await persisted(db_session, doc)
    assert state.processed_chunk_count == 1 and calls == [chunks[0].content] * 2
    assert (state.extractor_version != previous_version) == (change == "content")


@pytest.mark.asyncio
async def test_lock_contention_is_409_before_provider_or_archive_work(monkeypatch):
    class Locked(Exception):
        sqlstate = "55P03"
    db = SimpleNamespace(execute=AsyncMock(side_effect=DBAPIError("SELECT", {}, Locked())), rollback=AsyncMock())
    extract = AsyncMock()
    monkeypatch.setattr(routes, "replace_document_knowledge_graph", extract)
    with pytest.raises(HTTPException) as error:
        await routes.rebuild_document_knowledge_graph(uuid.uuid4(), SimpleNamespace(id=uuid.uuid4()), resume=True, db=db)
    assert error.value.status_code == 409
    db.rollback.assert_awaited_once()
    extract.assert_not_awaited()


@pytest.mark.asyncio
async def test_forced_graph_reset_archives_original_edges_but_normal_resume_does_not(client, db_session, create_test_user, monkeypatch, config):
    from auth.routes import create_access_token
    owner, doc, chunks = await document(db_session, create_test_user, 2)
    calls = []
    async def extract(_client, *, text, settings):
        calls.append(text)
        return [relation(text)], "groq:test-model"
    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", extract)
    headers = {"Authorization": "Bearer " + create_access_token(str(owner.id))}
    url = f"/api/documents/{doc.id}/knowledge-graph/rebuild"
    assert (await client.post(url, headers=headers)).status_code == 200
    _, rows = await persisted(db_session, doc)
    original = {str(row.id) for row in rows}
    assert (await client.post(url, headers=headers)).status_code == 200
    assert len(calls) == 2
    assert not (await db_session.execute(select(DocumentIndexRevision).where(DocumentIndexRevision.document_id == doc.id))).scalars().all()
    assert (await client.post(url + "?resume=false", headers=headers)).status_code == 200
    db_session.expire_all()
    await db_session.refresh(doc)
    revision = (await db_session.execute(select(DocumentIndexRevision).where(DocumentIndexRevision.document_id == doc.id))).scalar_one()
    assert {row["id"] for row in revision.payload["tables"]["kg_relations"]} == original
    _, rows = await persisted(db_session, doc)
    assert len(rows) == 2 and {str(row.id) for row in rows}.isdisjoint(original)
    assert len(calls) == 4

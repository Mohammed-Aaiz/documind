"""Authenticated integration tests for rebuilding document entity relations."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from auth.routes import create_access_token
from documents import kg_extraction
from documents.kg_extraction import ExtractedRelation
from tests.fixtures.graph_data import create_document_with_chunks


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": "Bearer " + create_access_token(str(user_id))}


def _result_url(document_id: uuid.UUID) -> str:
    return f"/api/documents/{document_id}/knowledge-graph/rebuild"


@pytest.mark.asyncio
async def test_rebuild_hides_another_owners_document_before_extraction(
    client, db_session, create_test_user, monkeypatch
):
    owner = await create_test_user(email="kg-rebuild-owner@example.com")
    stranger = await create_test_user(email="kg-rebuild-stranger@example.com")
    doc, chunks = await create_document_with_chunks(
        db_session,
        owner.id,
        name="private.txt",
        chunks=[{"content": "Ada founded Analytical Engines.", "index": 0}],
    )
    await db_session.commit()
    extraction = AsyncMock(side_effect=AssertionError("must not inspect foreign document"))
    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", extraction)

    response = await client.post(_result_url(doc.id), headers=_headers(stranger.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}
    extraction.assert_not_awaited()


@pytest.mark.asyncio
async def test_rebuild_requires_persisted_chunks(client, db_session, create_test_user):
    owner = await create_test_user(email="kg-rebuild-empty@example.com")
    from documents.models import Document

    doc = Document(
        id=uuid.uuid4(),
        user_id=owner.id,
        name="empty.txt",
        file_type="txt",
        file_size=0,
        stored_path=f"uploads/{owner.id}/empty.txt",
        chunk_count=0,
        status="ready",
        embedding_status="ready",
    )
    db_session.add(doc)
    await db_session.commit()

    response = await client.post(_result_url(doc.id), headers=_headers(owner.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "Document has no persisted chunks to extract"}


@pytest.mark.asyncio
async def test_rebuild_reports_persisted_status_and_exact_entity_relation_counts(
    client, db_session, create_test_user, monkeypatch
):
    owner = await create_test_user(email="kg-rebuild-counts@example.com")
    doc, chunks = await create_document_with_chunks(
        db_session,
        owner.id,
        name="relations.txt",
        chunks=[
            {"content": "Ada founded Analytical Engines.", "index": 0},
            {"content": "Analytical Engines hired Grace Hopper.", "index": 1},
        ],
    )
    await db_session.commit()
    relations = {
        chunks[0].content: ExtractedRelation(
            subject="Ada",
            subject_type="person",
            predicate="founded",
            object="Analytical Engines",
            object_type="organization",
            evidence_quote=chunks[0].content,
        ),
        chunks[1].content: ExtractedRelation(
            subject="Analytical Engines",
            subject_type="organization",
            predicate="hired",
            object="Grace Hopper",
            object_type="person",
            evidence_quote=chunks[1].content,
        ),
    }
    monkeypatch.setattr(
        kg_extraction,
        "get_settings",
        lambda: SimpleNamespace(
            groq_model="hosted-model",
            groq_context_tokens=8192,
        ),
    )

    async def extract(_client, *, text, settings):
        return [relations[text]], "groq:hosted-model"

    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", extract)

    response = await client.post(_result_url(doc.id), headers=_headers(owner.id))

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ready",
        "model": "groq:hosted-model",
        "version": kg_extraction.extraction_version(chunks, kg_extraction.get_settings()),
        "processedChunks": 2,
        "totalChunks": 2,
        "entityCount": 3,
        "relationCount": 2,
        "failureCode": None,
    }


@pytest.mark.asyncio
async def test_rebuild_reports_answer_provider_unavailable_without_false_counts(
    client, db_session, create_test_user, monkeypatch
):
    owner = await create_test_user(email="kg-rebuild-unavailable@example.com")
    doc, chunks = await create_document_with_chunks(
        db_session,
        owner.id,
        name="groq-unavailable.txt",
        chunks=[{"content": "Ada founded Analytical Engines.", "index": 0}],
    )
    await db_session.commit()
    monkeypatch.setattr(
        kg_extraction,
        "get_settings",
        lambda: SimpleNamespace(
            groq_model="hosted-model",
            groq_context_tokens=8192,
        ),
    )

    async def unavailable(*_args, **_kwargs):
        raise httpx.ConnectError("Groq unavailable")

    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", unavailable)

    response = await client.post(_result_url(doc.id), headers=_headers(owner.id))

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "unavailable",
        "model": "groq:hosted-model",
        "version": kg_extraction.extraction_version(chunks, kg_extraction.get_settings()),
        "processedChunks": 0,
        "totalChunks": 1,
        "entityCount": 0,
        "relationCount": 0,
        "failureCode": "answer_model_unavailable",
    }

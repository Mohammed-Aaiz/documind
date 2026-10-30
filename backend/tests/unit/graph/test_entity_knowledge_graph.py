"""Entity-relation GraphRAG regressions: exact evidence, scope, and hop bounds."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select

from documents import kg_extraction
from documents.kg_extraction import ExtractedRelation, parse_relation_response
from generation import service as generation_service
from generation.providers import ProviderCompletion
from graph.models import KnowledgeGraphExtraction, KnowledgeGraphRelation
from graph.service import retrieve_knowledge_graph_candidates
from tests.fixtures.graph_data import create_document_with_chunks


def test_relation_parser_keeps_only_exact_quotes_with_both_endpoints():
    source = "Ada founded Analytical Engines in 1843."
    payload = {
        "relations": [
            {
                "subject": "Ada",
                "subject_type": "person",
                "predicate": "founded",
                "object": "Analytical Engines",
                "object_type": "organization",
                "evidence_quote": source,
            },
            {
                "subject": "Ada",
                "subject_type": "person",
                "predicate": "invented",
                "object": "Analytical Engines",
                "object_type": "organization",
                "evidence_quote": "Ada invented Analytical Engines.",
            },
            {
                "subject": "Ada",
                "subject_type": "person",
                "predicate": "visited",
                "object": "Paris",
                "object_type": "place",
                "evidence_quote": source,
            },
        ]
    }

    rows = parse_relation_response(json.dumps(payload), source)

    assert rows == [
        ExtractedRelation(
            subject="Ada",
            subject_type="person",
            predicate="founded",
            object="Analytical Engines",
            object_type="organization",
            evidence_quote=source,
        )
    ]


@pytest.mark.asyncio
async def test_relation_extractor_delegates_to_bounded_resilient_structured_provider(monkeypatch):
    source = "Ada founded Analytical Engines."
    extracted = {
        "relations": [
            {
                "subject": "Ada",
                "subject_type": "person",
                "predicate": "founded",
                "object": "Analytical Engines",
                "object_type": "organization",
                "evidence_quote": source,
            }
        ]
    }
    calls = []

    async def complete(messages, **kwargs):
        calls.append((messages, kwargs))
        return ProviderCompletion(text=json.dumps(extracted), provider="groq",
                                  model="hosted-model", finish_reason="stop", fallback_used=True)

    monkeypatch.setattr(kg_extraction, "complete_answer", complete)

    settings = SimpleNamespace(
        answer_provider="groq",
        groq_api_key="must-not-be-sent",
        groq_model="hosted-model",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2:3b",
        ollama_keep_alive="5m",
        ollama_num_ctx=2048,
        ollama_num_thread=4,
    )
    async with httpx.AsyncClient() as client:
        rows, model = await kg_extraction._extract_chunk_relations(
            client, text=source, settings=settings
        )

    assert len(calls) == 1
    messages, kwargs = calls[0]
    assert messages[-1]["content"].endswith(source)
    assert kwargs["settings"] is settings
    assert kwargs["json_mode"] is True
    assert kwargs["purpose"] == "graph-extraction"
    assert kwargs["max_tokens"] == 512
    assert kwargs["timeout_seconds"] <= 30
    assert "must-not-be-sent" not in json.dumps(messages)
    assert model == "groq:hosted-model"
    assert rows[0].evidence_quote == source


@pytest.mark.asyncio
async def test_local_extractor_unavailable_is_persisted_without_fake_edges(
    db_session, create_test_user, monkeypatch
):
    user = await create_test_user(email="kg-unavailable@example.com")
    doc, chunks = await create_document_with_chunks(
        db_session,
        user.id,
        name="unavailable.txt",
        chunks=[{"content": "Ada founded Analytical Engines."}],
    )
    monkeypatch.setattr(
        kg_extraction,
        "get_settings",
        lambda: SimpleNamespace(
            ollama_model="llama3.2:3b",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_keep_alive="5m",
            ollama_num_ctx=2048,
            ollama_num_thread=4,
        ),
    )

    async def unavailable(*_args, **_kwargs):
        raise httpx.ConnectError("test model unavailable")

    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", unavailable)

    status = await kg_extraction.replace_document_knowledge_graph(
        db_session, user_id=user.id, document_id=doc.id, chunks=chunks
    )
    persisted = (
        await db_session.execute(
            select(KnowledgeGraphExtraction).where(
                KnowledgeGraphExtraction.document_id == doc.id
            )
        )
    ).scalar_one()
    relation_count = await db_session.scalar(
        select(func.count()).select_from(KnowledgeGraphRelation).where(
            KnowledgeGraphRelation.document_id == doc.id
        )
    )

    assert status == "unavailable"
    assert persisted.status == "unavailable"
    assert persisted.failure_code == "answer_model_unavailable"
    assert persisted.processed_chunk_count == 0
    assert relation_count == 0


@pytest.mark.asyncio
async def test_graph_retrieval_is_owner_scoped_and_capped_at_three_hops(
    db_session, create_test_user, monkeypatch
):
    owner = await create_test_user(email="kg-owner@example.com")
    other = await create_test_user(email="kg-other@example.com")
    chain = [
        ("Alpha connects to Beta.", "Alpha", "Beta"),
        ("Beta supports Gamma.", "Beta", "Gamma"),
        ("Gamma discovered Delta.", "Gamma", "Delta"),
        ("Delta founded Epsilon.", "Delta", "Epsilon"),
    ]
    docs = []
    for index, (text, _subject, _object) in enumerate(chain):
        doc, chunks = await create_document_with_chunks(
            db_session,
            owner.id,
            name=f"chain-{index}.txt",
            chunks=[{"content": text, "index": 0, "page": index + 1}],
        )
        docs.append((doc, chunks))

    other_doc, other_chunks = await create_document_with_chunks(
        db_session,
        other.id,
        name="private.txt",
        chunks=[{"content": "Alpha controls Secret."}],
    )

    async def extract(_client, *, text, settings):
        for source, subject, object_name in [*chain, ("Alpha controls Secret.", "Alpha", "Secret")]:
            if text == source:
                return [
                    ExtractedRelation(
                        subject=subject,
                        subject_type="concept",
                        predicate="relates to",
                        object=object_name,
                        object_type="concept",
                        evidence_quote=source,
                    )
                ], "llama3.2:3b"
        return [], "llama3.2:3b"

    monkeypatch.setattr(
        kg_extraction,
        "get_settings",
        lambda: SimpleNamespace(ollama_model="llama3.2:3b"),
    )
    monkeypatch.setattr(kg_extraction, "_extract_chunk_relations", extract)

    for doc, chunks in docs:
        assert await kg_extraction.replace_document_knowledge_graph(
            db_session, user_id=owner.id, document_id=doc.id, chunks=chunks
        ) == "ready"
    assert await kg_extraction.replace_document_knowledge_graph(
        db_session, user_id=other.id, document_id=other_doc.id, chunks=other_chunks
    ) == "ready"

    candidates = await retrieve_knowledge_graph_candidates(
        db_session, str(owner.id), "How does Alpha connect through the chain?", max_hops=99
    )
    candidate_doc_ids = {item.document_id for item in candidates}

    assert len(candidates) == 3
    assert candidate_doc_ids == {str(doc.id) for doc, _chunks in docs[:3]}
    assert str(other_doc.id) not in candidate_doc_ids
    assert all(item.hops <= 3 for item in candidates)
    assert all(item.evidence_quote in item.content for item in candidates)
    assert all(item.graph_path.startswith("Alpha ") for item in candidates)

    foreign_candidates = await retrieve_knowledge_graph_candidates(
        db_session, str(other.id), "How does Alpha connect?", max_hops=3
    )
    assert {item.document_id for item in foreign_candidates} == {str(other_doc.id)}


@pytest.mark.asyncio
async def test_answer_retrieval_preserves_kg_quote_and_dense_fallback(
    db_session, monkeypatch,
):
    from chat import rag
    from chat.rag import SourceChunk
    from graph import service as graph_service
    from graph.service import KnowledgeGraphCandidate

    dense = SourceChunk(
        chunk_id="chunk-1",
        content="The source says Alpha connects to Beta.",
        score=0.82,
        document_id="doc-1",
        document_name="alpha.txt",
        page=1,
    )

    async def dense_only(*_args, **_kwargs):
        return [dense]

    monkeypatch.setattr(rag, "retrieve_chunks", dense_only)
    monkeypatch.setattr(rag, "dual_path_enabled", lambda: False)
    monkeypatch.setattr(rag, "table_evidence_enabled", lambda: False)

    async def graph_match(*_args, **_kwargs):
        return [
            KnowledgeGraphCandidate(
                chunk_id="chunk-1",
                content=dense.content,
                document_id="doc-1",
                document_name="alpha.txt",
                page=1,
                heading_path=None,
                section=None,
                predicate="connects to",
                evidence_quote="Alpha connects to Beta.",
                graph_path="Alpha connects to Beta",
                hops=1,
            )
        ]

    monkeypatch.setattr(graph_service, "retrieve_knowledge_graph_candidates", graph_match)
    async def graph_available(*_args, **_kwargs):
        return "available"

    monkeypatch.setattr(graph_service, "knowledge_graph_status", graph_available)
    merged = await generation_service.retrieve_evidence(
        db_session, "owner-1", "What connects Alpha to Beta?"
    )

    assert merged.knowledge_graph_status == "retrieved"
    assert len(merged) == 1
    assert merged[0].retrieval_path == rag.RETRIEVAL_HYBRID
    assert merged[0].knowledge_graph_path == "Alpha connects to Beta"
    assert merged[0].knowledge_graph_hops == 1
    assert merged[0].knowledge_graph_quote == "Alpha connects to Beta."
    assert merged[0].score == pytest.approx(0.82)

    async def graph_unavailable(*_args, **_kwargs):
        raise RuntimeError("graph table unavailable")

    monkeypatch.setattr(graph_service, "retrieve_knowledge_graph_candidates", graph_unavailable)
    fallback = await generation_service.retrieve_evidence(
        db_session, "owner-1", "What connects Alpha to Beta?"
    )

    assert fallback.knowledge_graph_status == "unavailable"
    assert fallback == [dense]

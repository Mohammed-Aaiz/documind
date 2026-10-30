"""Authenticated provider-backed chat HTTP contract; no live LLM calls."""
import pytest

from chat.rag import SourceChunk
from generation.types import GenerationUnavailableError


@pytest.mark.asyncio
async def test_ask_empty_question_returns_400(client, ask_auth, provider_answer):
    response = await client.post("/api/chat/ask", json={"question": "   "}, headers=ask_auth["headers"])
    assert response.status_code == 400
    provider_answer[1].assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_unauthenticated_returns_401(client, provider_answer):
    assert (await client.post("/api/chat/ask", json={"question": "test"})).status_code == 401
    provider_answer[1].assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_unavailable_provider_returns_503(client, ask_auth, provider_answer):
    provider_answer[1].side_effect = GenerationUnavailableError("Groq is unavailable")
    response = await client.post("/api/chat/ask", json={"question": "Explain calibration"}, headers=ask_auth["headers"])
    assert response.status_code == 503 and "Groq" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ask_no_evidence_returns_explicit_abstention(client, ask_auth, provider_answer):
    answer, _ = provider_answer
    answer.answer, answer.insufficient_context, answer.abstained = "", True, True
    answer.verification = {"verified": False, "status": "INSUFFICIENT_EVIDENCE"}
    response = await client.post("/api/chat/ask", json={"question": "Unsupported question"}, headers=ask_auth["headers"])
    body = response.json()
    assert response.status_code == 200 and body["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert body["answer"] == "" and body["insufficientContext"] and body["sources"] == []


@pytest.mark.asyncio
async def test_ask_reports_uncalibrated_provider_confidence_honestly(client, ask_auth, provider_answer):
    answer, _ = provider_answer
    answer.sources = [SourceChunk("c1", "The interval is six months.", .68, "d1", "manual.pdf", 1)]
    response = await client.post("/api/chat/ask", json={"question": "What is the interval?"}, headers=ask_auth["headers"])
    body = response.json()
    assert response.status_code == 200 and body["answer"] == answer.answer
    assert body["confidence"] is None and body["reliability"]["qaConfidence"] is None
    assert body["outcome"] == "PARTIAL" and body["reliability"]["factualGrounded"] is False
    assert body["reliability"]["sourceCount"] == 1 and body["reliability"]["retrievalScore"] == .68


@pytest.mark.asyncio
@pytest.mark.parametrize("structured", [False, True])
async def test_ask_preserves_supplied_source_provenance(client, ask_auth, provider_answer, structured):
    answer, _ = provider_answer
    answer.sources = [SourceChunk("c1", "The coating cures in six hours.", .71, "d1", "manual.pdf", 4,
        heading_path=("Manual", "Coating") if structured else None,
        section="Coating" if structured else None, element_type="paragraph" if structured else None,
        token_count=42 if structured else None, chunker_version="structure-v2" if structured else None,
        knowledge_graph_path="Coating cures in six hours" if structured else None,
        knowledge_graph_quote="The coating cures in six hours." if structured else None)]
    response = await client.post("/api/chat/ask", json={"question": "How long does coating cure?"}, headers=ask_auth["headers"])
    source = response.json()["sources"][0]
    assert source["chunkId"] == "c1" and source["page"] == 4
    assert source["headingPath"] == (["Manual", "Coating"] if structured else None)
    assert source["tokenCount"] == (42 if structured else None)
    assert source["knowledgeGraphQuote"] == ("The coating cures in six hours." if structured else None)

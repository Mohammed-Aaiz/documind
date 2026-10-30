"""The stateless API uses Groq while retaining source and refusal contracts."""
from unittest.mock import AsyncMock

import pytest

from chat.rag import SourceChunk
from generation import providers, service
from generation.providers import ProviderCompletion


def evidence():
    return SourceChunk("chunk-1", "The lidar array requires calibration every 30 days.",
                       0.8, "document-1", "report.pdf", 2)


@pytest.mark.asyncio
async def test_stateless_route_uses_provider_and_owner_scoped_retrieval(monkeypatch):
    retrieve = AsyncMock(return_value=[evidence()])
    complete = AsyncMock(return_value=ProviderCompletion(
        "The lidar array requires calibration every 30 days [1].", "groq", "test-groq-model", "stop"))
    monkeypatch.setattr(service, "retrieve_evidence", retrieve)
    monkeypatch.setattr(providers, "complete_answer", complete)
    monkeypatch.setattr(service, "generate", lambda *a, **k: pytest.fail("Legacy model was called"))
    db = object()
    sources, answer = await service.run_generation(db, "owner-1", "How often is the lidar array calibrated?", 5, "5")
    retrieve.assert_awaited_once_with(db, "owner-1", "How often is the lidar array calibrated?",
                                    top_k=5, answer_format="5", query_routing=True)
    assert complete.await_count == 1
    assert answer.model == "test-groq-model"
    assert answer.verification["verified"] and not answer.abstained
    assert sources[0].content == answer.blocks[0].content
    assert sources[0].page == 2 and sources[0].chunk_id == "chunk-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("draft", ["The lidar array requires calibration every 30 days [99].",
                                   "The lidar array requires calibration every 900 days [1]."])
async def test_invalid_citation_or_invented_number_is_withheld(monkeypatch, draft):
    monkeypatch.setattr(providers, "complete_answer", AsyncMock(return_value=ProviderCompletion(
        draft, "groq", "test-groq-model", "stop")))
    _, answer = await service.answer_from_evidence("How often is the lidar array calibrated?", [evidence()], "5")
    assert answer.abstained and answer.answer == ""


@pytest.mark.asyncio
async def test_no_evidence_does_not_send_a_provider_request(monkeypatch):
    complete = AsyncMock()
    monkeypatch.setattr(providers, "complete_answer", complete)
    sources, answer = await service.answer_from_evidence("What is Kestrel?", [], "5")
    assert sources == [] and answer.abstained
    complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_supported_claim_survives_an_unsupported_closing_sentence(monkeypatch):
    monkeypatch.setattr(providers, "complete_answer", AsyncMock(return_value=ProviderCompletion(
        "The lidar array requires calibration every 30 days [1].\n\nIt is powered by nuclear fuel [1].",
        "groq", "test-groq-model", "stop")))
    _, answer = await service.answer_from_evidence("How often is the lidar array calibrated?", [evidence()], "5")
    assert not answer.abstained and answer.verification["verified"]
    assert "30 days" in answer.answer and "nuclear" not in answer.answer
    assert "[1]" in answer.answer
    assert any("omitted" in warning for warning in answer.warnings)

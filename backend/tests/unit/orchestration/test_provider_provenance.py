"""The saved chat must identify the provider that actually supplied its draft."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from chat.models import ChatMessage, ChatSession
from chat.rag import SourceChunk
from generation import service as generation_service
from generation.providers import ProviderDelta
from generation.service import RetrievedEvidence
from orchestration import service
from reliability import routes as reliability_routes


@pytest.mark.asyncio
@pytest.mark.parametrize("visual_evidence", [False, True])
async def test_groq_provider_and_evidence_provenance_are_reported_and_persisted(
    db_session, create_test_user, monkeypatch, visual_evidence,
):
    user = await create_test_user(email=f"provider-{uuid4()}@example.com")
    session = ChatSession(user_id=user.id, workspace="student")
    db_session.add(session)
    await db_session.flush()
    settings = SimpleNamespace(
        conversation_history_limit=12, answer_provider="groq", groq_context_tokens=8192,
        answer_auto_fallback=False,
        groq_model="hosted-model", groq_api_key="server-only-key",
    )
    monkeypatch.setattr("config.get_settings", lambda: settings)
    text = "The Kestrel platform performs autonomous survey missions in uneven terrain."

    async def retrieve(_db, owner, _query, **kwargs):
        assert owner == str(user.id)
        assert kwargs["query_routing"] is True
        return RetrievedEvidence(
            [SourceChunk("c1", text, .9, "d1", "manual.pdf", 1,
                evidence_kind="visual_patch" if visual_evidence else "chunk",
                spatial_regions=[{"id": "crop1", "bbox": [.1, .2, .7, .8], "visual_embedding": True}]
                    if visual_evidence else None)],
            knowledge_graph_status="empty",
        )

    async def groq_stream(_messages, **_kwargs):
        yield ProviderDelta(text=text + " [1]", model="hosted-model", provider="groq", fallback_used=False)
        yield ProviderDelta(done=True, model="hosted-model", provider="groq", fallback_used=False, finish_reason="stop")

    async def store_reliability(*_args, **_kwargs):
        return None

    monkeypatch.setattr(generation_service, "retrieve_evidence", retrieve)
    monkeypatch.setattr(service, "stream_answer", groq_stream)
    monkeypatch.setattr(reliability_routes, "store_query_reliability", store_reliability)
    events = [event async for event in service.stream_with_memory(
        db_session, user_id=str(user.id), session_id=str(session.id), question="What is the Kestrel platform?",
    )]
    assert events[0]["data"]["provider"] == "groq"
    final = events[-1]["data"]
    assert final.engine == "groq"
    assert final.model == "hosted-model"
    assert final.hosted is True
    assert final.abstained is False
    assert not any("replacement draft" in warning for warning in final.warnings)
    deltas = [event["data"] for event in events if event["event"] == "delta"]
    assert deltas == [{"text": text + " [1]", "provisional": False}]

    saved = (await db_session.execute(select(ChatMessage).where(
        ChatMessage.session_id == session.id, ChatMessage.sender == "oracle",
    ))).scalar_one()
    assert saved.evidence_metadata["engine"] == "groq"
    assert saved.evidence_metadata["model"] == "hosted-model"
    assert saved.evidence_metadata["fallbackUsed"] is False
    assert saved.evidence_metadata["spatialContext"]["learnedVisualEmbeddings"] is visual_evidence
    assert "server-only-key" not in str(saved.evidence_metadata)

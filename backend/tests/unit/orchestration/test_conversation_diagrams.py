"""Text/voice conversation finals preserve diagrams through provider fallback."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from chat.models import ChatMessage, ChatSession
from generation import service as generation_service
from generation.planning import text_diagram_blocks, validate_text_diagram
from generation.providers import ProviderDelta
from generation.service import RetrievedEvidence
from generation.types import GenerationUnavailableError
from generation.verification import verify_with_mode
from orchestration import service
from reliability import routes as reliability_routes
from tests.unit.generation.test_reliable_student_diagrams import process_sources, source_draft


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_unavailable", [False, True])
async def test_final_conversation_diagram_survives_generation_or_provider_fallback(
    db_session, create_test_user, monkeypatch, provider_unavailable,
):
    user = await create_test_user(email=f"diagram-{uuid4()}@example.com")
    session = ChatSession(user_id=user.id, workspace="student")
    db_session.add(session)
    await db_session.flush()
    settings = SimpleNamespace(
        conversation_history_limit=12, answer_provider="groq", groq_context_tokens=16384,
        answer_auto_fallback=False, groq_model="test-model", groq_api_key="server-test-key",
    )
    monkeypatch.setattr("config.get_settings", lambda: settings)
    sources = process_sources()
    question = "Explain VAWT with a neat diagram."
    calls = []

    async def retrieve(_db, owner, _query, **kwargs):
        assert owner == str(user.id) and kwargs["query_routing"]
        return RetrievedEvidence(sources, knowledge_graph_status="empty")

    async def stream(_messages, **kwargs):
        calls.append(kwargs)
        if provider_unavailable:
            raise GenerationUnavailableError("The provider is temporarily unavailable.")
        yield ProviderDelta(text=source_draft(sources), model="test-model", provider="groq")
        yield ProviderDelta(done=True, model="test-model", provider="groq", finish_reason="stop")

    async def ignore_reliability(*args, **kwargs):
        pass

    monkeypatch.setattr(generation_service, "retrieve_evidence", retrieve)
    monkeypatch.setattr(service, "stream_answer", stream)
    monkeypatch.setattr(reliability_routes, "store_query_reliability", ignore_reliability)
    events = [event async for event in service.stream_with_memory(
        db_session, user_id=str(user.id), session_id=str(session.id), question=question,
        workspace="student", answer_format="10",
    )]
    final = events[-1]["data"]
    assert not final.abstained and final.verification["verified"]
    assert len(calls) == 1
    assert text_diagram_blocks(final.answer)
    from generation.provider_prompt import prepare_prompt
    from generation.types import AnswerFormat
    prepared = prepare_prompt(question, sources, [], workspace="student", task="answer",
                              answer_format=AnswerFormat.TEN, context_tokens=16384)
    assert validate_text_diagram(final.answer, prepared.blocks, question=question)
    assert verify_with_mode(final.answer, prepared.blocks, question=question).verified
    assert not any("no evidence-supported figure" in warning for warning in final.warnings)
    assert [event["data"]["text"] for event in events if event["event"] == "delta"] == [final.answer]
    saved = (await db_session.execute(select(ChatMessage).where(
        ChatMessage.session_id == session.id, ChatMessage.sender == "oracle",
    ))).scalar_one()
    assert saved.content == final.answer
    assert saved.evidence_metadata["verification"]["verified"]
    if provider_unavailable:
        assert final.model == "extractive-evidence-fallback"

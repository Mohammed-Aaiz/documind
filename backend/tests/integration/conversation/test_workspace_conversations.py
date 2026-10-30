"""Persisted-session authorization and provider-turn transactions (SQLite only)."""
import json
import uuid
from unittest.mock import AsyncMock

import pytest

from auth.routes import create_access_token
from chat.rag import RETRIEVAL_KNOWLEDGE_GRAPH, SourceChunk
from generation.providers import ProviderDelta
from generation.types import GenerationUnavailableError
import generation.service
import orchestration.service


@pytest.fixture
async def account(client, create_test_user):
    user = await create_test_user(email=f"workspace-{uuid.uuid4().hex}@test.com")
    headers = {"Authorization": "Bearer " + create_access_token(str(user.id))}
    sessions = {}
    for mode in ("student", "research"):
        response = await client.post("/api/chat/sessions", json={"workspace": mode}, headers=headers)
        assert response.status_code == 201, response.text
        sessions[mode] = response.json()["id"]
    return headers, sessions


@pytest.mark.asyncio
async def test_workspace_lists_are_disjoint_and_legacy_defaults_to_student(client, account):
    headers, sessions = account
    for mode in sessions:
        response = await client.get("/api/chat/sessions", params={"workspace": mode}, headers=headers)
        assert response.status_code == 200
        assert {s["id"] for s in response.json()["sessions"]} == {sessions[mode]}
        assert all(s["workspace"] == mode for s in response.json()["sessions"])
    default = await client.get("/api/chat/sessions", headers=headers)
    assert [s["id"] for s in default.json()["sessions"]] == [sessions["student"]]


@pytest.mark.parametrize("action", ["history", "ask", "stream", "clear", "delete-session", "legacy-history"])
@pytest.mark.asyncio
async def test_wrong_workspace_denied_before_provider(client, account, monkeypatch, action):
    headers, sessions = account
    session = sessions["research"]
    retrieval = AsyncMock(side_effect=AssertionError("unauthorized retrieval"))
    monkeypatch.setattr(generation.service, "retrieve_evidence", retrieval)
    base = f"/api/conversation/{session}"
    if action == "history":
        response = await client.get(base, params={"workspace": "student"}, headers=headers)
    elif action in ("ask", "stream"):
        response = await client.post(base + ("/messages" if action == "ask" else "/stream"),
            json={"question": "Explain calibration", "workspace": "student"}, headers=headers)
    elif action == "clear":
        response = await client.delete(base, params={"workspace": "student"}, headers=headers)
    elif action == "delete-session":
        response = await client.delete(f"/api/chat/sessions/{session}", params={"workspace": "student"}, headers=headers)
    else:
        response = await client.get(f"/api/chat/sessions/{session}/messages", params={"workspace": "student"}, headers=headers)
    assert response.status_code == 404, response.text
    retrieval.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_user_cannot_read_or_delete_session(client, account, create_test_user):
    _, sessions = account
    other = await create_test_user(email=f"intruder-{uuid.uuid4().hex}@test.com")
    headers = {"Authorization": "Bearer " + create_access_token(str(other.id))}
    for method, path in (("GET", f"/api/conversation/{sessions['student']}"),
                         ("DELETE", f"/api/chat/sessions/{sessions['student']}")):
        response = await client.request(method, path, headers=headers)
        assert response.status_code == 404


def events(response):
    parsed = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        parsed.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return parsed


def evidence():
    return SourceChunk(chunk_id="source-1", document_id=str(uuid.uuid4()), document_name="manual.pdf", page=4, score=.8,
        content="The lidar calibration interval is six months. Technicians inspect the sensor alignment during scheduled maintenance.")


@pytest.mark.asyncio
async def test_stream_final_persists_single_pair_and_does_not_leak_to_other_mode(client, account, monkeypatch):
    headers, sessions = account
    graph_evidence = evidence()
    graph_evidence.retrieval_path = RETRIEVAL_KNOWLEDGE_GRAPH
    graph_evidence.knowledge_graph_path = "Lidar array uses calibration"
    graph_evidence.knowledge_graph_hops = 2
    graph_evidence.knowledge_graph_predicate = "requires"
    graph_evidence.knowledge_graph_quote = "The lidar array requires calibration every 30 days."
    monkeypatch.setattr(generation.service, "retrieve_evidence", AsyncMock(return_value=[graph_evidence]))
    async def answer(*args, **kwargs):
        yield ProviderDelta(text="The lidar calibration interval is six months [1].", model="test-provider")
        yield ProviderDelta(done=True, model="test-provider", finish_reason="stop")
    monkeypatch.setattr(orchestration.service, "stream_answer", answer)
    response = await client.post(f"/api/conversation/{sessions['student']}/stream",
        json={"question": "What is the lidar calibration interval?", "workspace": "student", "answerFormat": "5"}, headers=headers)
    assert response.status_code == 200
    stream = events(response)
    assert [name for name, _ in stream] == ["meta", "delta", "final"]
    final = stream[-1][1]
    assert final["workspace"] == "student" and final["marks"] == 5
    assert final["memoryBackend"] == "postgresql"
    assert final["sources"][0]["documentName"] == "manual.pdf"
    assert final["firstTokenMs"] is not None
    history = await client.get(f"/api/conversation/{sessions['student']}", headers=headers)
    assert [m["role"] for m in history.json()["messages"]] == ["user", "assistant"]
    stored_messages = await client.get(
        f"/api/chat/sessions/{sessions['student']}/messages", headers=headers
    )
    assert stored_messages.status_code == 200, stored_messages.text
    persisted_evidence = stored_messages.json()["messages"][1]["metadata"]["sources"][0]
    assert persisted_evidence["knowledgeGraphPath"] == "Lidar array uses calibration"
    assert persisted_evidence["knowledgeGraphHops"] == 2
    assert persisted_evidence["knowledgeGraphQuote"] == graph_evidence.knowledge_graph_quote
    assert persisted_evidence["retrievalPath"] == RETRIEVAL_KNOWLEDGE_GRAPH
    # The SSE final and saved chat view must expose the same citation fields.
    assert final["sources"][0]["retrievalPath"] == persisted_evidence["retrievalPath"]
    assert final["sources"][0]["knowledgeGraphPath"] == persisted_evidence["knowledgeGraphPath"]
    assert final["sources"][0]["knowledgeGraphHops"] == persisted_evidence["knowledgeGraphHops"]
    assert final["sources"][0]["knowledgeGraphQuote"] == persisted_evidence["knowledgeGraphQuote"]
    other_history = await client.get(f"/api/conversation/{sessions['research']}", params={"workspace": "research"}, headers=headers)
    assert other_history.json()["messages"] == []


@pytest.mark.asyncio
async def test_failed_stream_sanitizes_error_and_persists_no_partial_turn(client, account, monkeypatch):
    headers, sessions = account
    monkeypatch.setattr(generation.service, "retrieve_evidence", AsyncMock(return_value=[evidence()]))
    async def broken(*args, **kwargs):
        yield ProviderDelta(text="provisional text", model="test-provider")
        raise GenerationUnavailableError("private-provider-key")
    monkeypatch.setattr(orchestration.service, "stream_answer", broken)
    response = await client.post(f"/api/conversation/{sessions['student']}/stream",
        json={"question": "What is the calibration interval?"}, headers=headers)
    stream = events(response)
    assert [name for name, _ in stream] == ["meta", "delta", "error"]
    assert "private-provider-key" not in response.text
    history = await client.get(f"/api/conversation/{sessions['student']}", headers=headers)
    assert history.json()["messages"] == []


@pytest.mark.asyncio
async def test_no_evidence_abstains_without_calling_provider(client, account, monkeypatch):
    headers, sessions = account
    monkeypatch.setattr(generation.service, "retrieve_evidence", AsyncMock(return_value=[]))
    async def forbidden(*args, **kwargs):
        pytest.fail("Provider must not be called without evidence")
        yield
    monkeypatch.setattr(orchestration.service, "stream_answer", forbidden)
    response = await client.post(f"/api/conversation/{sessions['research']}/messages",
        json={"question": "Compare the methods", "workspace": "research", "task": "comparison"}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["abstained"] is True
    assert response.json()["marks"] == 0
    assert response.json()["sources"] == []


@pytest.mark.asyncio
async def test_student_research_task_mismatch_rejected(client, account, monkeypatch):
    headers, sessions = account
    retrieval = AsyncMock(side_effect=AssertionError("invalid-task retrieval"))
    monkeypatch.setattr(generation.service, "retrieve_evidence", retrieval)
    response = await client.post(f"/api/conversation/{sessions['student']}/messages",
        json={"question": "Compare methods", "workspace": "student", "task": "comparison"}, headers=headers)
    assert response.status_code == 400
    retrieval.assert_not_awaited()

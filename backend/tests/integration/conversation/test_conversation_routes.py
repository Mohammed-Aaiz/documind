"""Tests for the conversation API (``/api/conversation``).

The orchestration service is patched at the route boundary, so these tests
verify the HTTP contract, the authentication boundary, identifier validation
and the error mapping — not model inference.  The graph itself is covered by
``tests/unit/orchestration``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

import conversation.routes as conversation_routes
from conversation.routes import ConversationAnswerResponse, ConversationMessageOut
from session.store import ConversationMessage

LOGIN_URL = "/api/auth/login"
BASE = "/api/conversation"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, create_test_user, email: str) -> str:
    await create_test_user(email=email, password="Pass123!", name="Conv")
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "Pass123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _chunk():
    return SimpleNamespace(
        chunk_id="c1",
        content="The lidar calibration interval is six months.",
        score=0.71,
        document_id="d1",
        document_name="manual.pdf",
        page=4,
        heading_path=("Maintenance",),
        section="Maintenance",
        element_type="paragraph",
        token_count=20,
        chunker_version="v2",
        retrieval_path="semantic",
        fusion_score=None,
        structural_hops=None,
        evidence_kind="chunk",
        table_element_id=None,
        row_index=None,
        header_repeated=None,
    )


def _answer(**overrides):
    payload = dict(
        session_id="s1",
        question="What is the calibration interval?",
        retrieval_query="What is the calibration interval?",
        followup_resolved=False,
        answer="Six months [1].",
        engine="generative",
        model="fake-model",
        marks=10,
        verification={"verified": True, "status": "SUPPORTED"},
        warnings=[],
        sources=[_chunk()],
        history=[
            {"role": "user", "content": "What is the calibration interval?", "createdAt": "t1"},
            {"role": "assistant", "content": "Six months [1].", "createdAt": "t2"},
        ],
        rerank={
            "applied": True,
            "signal": "distilbert-span-probability",
            "scored": 1,
            "candidates": 1,
            "scores": [],
            "error": None,
        },
        insufficient_context=False,
        abstained=False,
        latency_ms=42,
        memory_backend="memory",
        memory_error="ConnectionError: redis is not running",
        pipeline_version="langgraph-conversation-v1",
    )
    payload.update(overrides)
    return SimpleNamespace(**payload)


class TestAuth:
    @pytest.mark.asyncio
    async def test_history_requires_authentication(self, client: AsyncClient):
        assert (await client.get(f"{BASE}/s1")).status_code == 401

    @pytest.mark.asyncio
    async def test_ask_requires_authentication(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/s1/messages", json={"question": "Hi?"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_requires_authentication(self, client: AsyncClient):
        assert (await client.delete(f"{BASE}/s1")).status_code == 401


class TestValidation:
    @pytest.mark.asyncio
    async def test_empty_question_is_rejected(self, client: AsyncClient, create_test_user):
        token = await _login(client, create_test_user, "conv-empty@test.com")
        resp = await client.post(f"{BASE}/s1/messages", json={"question": "  "}, headers=_auth(token))
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unsafe_session_id_is_rejected(self, client: AsyncClient, create_test_user):
        token = await _login(client, create_test_user, "conv-id@test.com")
        resp = await client.get(f"{BASE}/bad%3Asession", headers=_auth(token))
        assert resp.status_code == 400
        assert "session id" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_unsupported_answer_format_is_rejected(self, client: AsyncClient, create_test_user):
        token = await _login(client, create_test_user, "conv-format@test.com")
        with patch.object(
            conversation_routes,
            "answer_with_memory",
            AsyncMock(side_effect=ValueError("Unsupported answer format '7'")),
        ):
            resp = await client.post(
                f"{BASE}/s1/messages",
                json={"question": "Anything?", "answerFormat": "7"},
                headers=_auth(token),
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unavailable_engine_is_503(self, client: AsyncClient, create_test_user):
        from generation.types import GenerationUnavailableError

        token = await _login(client, create_test_user, "conv-503@test.com")
        with patch.object(
            conversation_routes,
            "answer_with_memory",
            AsyncMock(side_effect=GenerationUnavailableError("weights missing")),
        ):
            resp = await client.post(
                f"{BASE}/s1/messages", json={"question": "Anything?"}, headers=_auth(token)
            )
        assert resp.status_code == 503
        assert resp.json()["detail"] == (
            "The configured answer provider is unavailable. Check provider setup and try again."
        )
        assert "weights missing" not in resp.text


class TestAsk:
    @pytest.mark.asyncio
    async def test_answer_reports_engine_memory_and_sources(self, client: AsyncClient, create_test_user):
        token = await _login(client, create_test_user, "conv-ask@test.com")
        service = AsyncMock(return_value=_answer())

        with patch.object(conversation_routes, "answer_with_memory", service):
            resp = await client.post(
                f"{BASE}/s1/messages",
                json={"question": "What is the calibration interval?", "topK": 4, "answerFormat": "10"},
                headers=_auth(token),
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["answer"] == "Six months [1]."
        assert body["engine"] == "generative"
        assert body["answerFormat"] == "10"
        assert body["sources"][0]["chunkId"] == "c1"
        assert body["sources"][0]["section"] == "Maintenance"
        assert [m["role"] for m in body["history"]] == ["user", "assistant"]
        assert body["memoryBackend"] == "memory"
        assert body["memoryError"].startswith("ConnectionError")
        assert body["pipelineVersion"] == "langgraph-conversation-v1"

        kwargs = service.await_args.kwargs
        assert kwargs["user_id"]  # taken from the JWT, never the body
        assert kwargs["session_id"] == "s1"
        assert kwargs["top_k"] == 4


class TestHistory:
    @pytest.mark.asyncio
    async def test_history_returns_stored_turns(self, client: AsyncClient, create_test_user):
        token = await _login(client, create_test_user, "conv-history@test.com")
        messages = [
            ConversationMessage("user", "Hello", "t1"),
            ConversationMessage("assistant", "Hi", "t2"),
        ]

        with (
            patch.object(conversation_routes, "conversation_history", AsyncMock(return_value=messages)),
            patch.object(
                conversation_routes,
                "conversation_status",
                AsyncMock(return_value={"memory": {"backend": "postgresql", "error": None}}),
            ),
        ):
            resp = await client.get(f"{BASE}/s1", headers=_auth(token))

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert [m["content"] for m in body["messages"]] == ["Hello", "Hi"]
        assert body["memoryBackend"] == "postgresql"


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_is_idempotent_and_returns_204(self, client: AsyncClient, create_test_user):
        token = await _login(client, create_test_user, "conv-delete@test.com")
        clear = AsyncMock(return_value=None)

        with patch.object(conversation_routes, "clear_conversation", clear):
            first = await client.delete(f"{BASE}/s1", headers=_auth(token))
            second = await client.delete(f"{BASE}/s1", headers=_auth(token))

        assert first.status_code == 204
        assert second.status_code == 204
        assert clear.await_count == 2


class TestStatus:
    @pytest.mark.asyncio
    async def test_status_reports_memory_and_model(self, client: AsyncClient, create_test_user):
        token = await _login(client, create_test_user, "conv-status@test.com")
        with patch.object(
            conversation_routes,
            "conversation_status",
            AsyncMock(
                return_value={
                    "memory": {"backend": "memory", "error": "refused"},
                    "conversationModel": {"configured": False, "model": None},
                    "pipelineVersion": "langgraph-conversation-v1",
                }
            ),
        ):
            resp = await client.get(f"{BASE}/status", headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["memory"]["backend"] == "memory"

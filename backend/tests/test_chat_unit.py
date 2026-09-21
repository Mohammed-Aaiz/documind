"""Unit tests for the chat /api/chat/ask endpoint via Brain orchestration.

Tests mock at the SERVICE level (chat.rag, chat.qa_model) since the
Brain calls services through adapters, not through routes.

Covers:
  • Empty question → 400
  • Unauthenticated → 401
  • Unavailable model → 503
  • No chunks → INSUFFICIENT_EVIDENCE
  • Successful answer → SUCCESS
  • Partial answer → PARTIAL
"""

import uuid
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient


LOGIN_URL = "/api/auth/login"
ASK_URL = "/api/chat/ask"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ask_empty_question_returns_400(client: AsyncClient, create_test_user):
    """Empty question must be rejected with 400."""
    await create_test_user(email="empty@test.com", password="Pass123!", name="Empty")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "empty@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.post(
        ASK_URL,
        json={"question": "   "},
        headers=_auth_header(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ask_unauthenticated_returns_401(client: AsyncClient):
    """Unauthenticated ask must return 401."""
    resp = await client.post(ASK_URL, json={"question": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
@patch("chat.routes.is_model_available", return_value=False)
@patch("chat.routes.get_model_status", return_value={
    "available": False,
    "model_path": "./models/documind-qa",
    "error": "Model not found",
})
@patch("reliability.routes.store_query_reliability", new_callable=AsyncMock)
@patch("brain.Brain.process", new_callable=AsyncMock)
async def test_ask_unavailable_model_returns_503(
    mock_process, mock_store, mock_status, mock_avail,
    client: AsyncClient, create_test_user,
):
    """Unavailable QA model must return 503."""
    await create_test_user(email="noaiml@test.com", password="Pass123!", name="NoAI")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "noaiml@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    # Brain reports UNAVAILABLE (simulates model unavailable)
    from brain.types import ExecutionContext, ErrorRecord
    from outcomes import Outcome
    unavailable_ctx = ExecutionContext(
        user_id="u1", raw_question="What is AI?",
    )
    unavailable_ctx.outcome = Outcome.UNAVAILABLE
    unavailable_ctx.errors.append(
        ErrorRecord(category="service_failure", message="Model unavailable", service="qa_answer")
    )
    from brain.types import BrainResponse
    unavailable_ctx.response = BrainResponse(
        answer="", outcome=Outcome.UNAVAILABLE,
        question="What is AI?",
    )
    mock_process.return_value = unavailable_ctx

    resp = await client.post(
        ASK_URL,
        json={"question": "What is AI?"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
@patch("brain.adapters.qa_adapter", new_callable=AsyncMock)
@patch("brain.adapters.retrieval_adapter", new_callable=AsyncMock)
@patch("brain.adapters.context_adapter", new_callable=AsyncMock)
@patch("reliability.routes.store_query_reliability", new_callable=AsyncMock)
async def test_ask_no_chunks_returns_insufficient_evidence(
    mock_store, mock_ctx, mock_retrieval, mock_qa,
    client: AsyncClient, create_test_user,
):
    """No retrieved chunks → INSUFFICIENT_EVIDENCE outcome."""
    await create_test_user(email="nochunks@test.com", password="Pass123!", name="NoChunks")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "nochunks@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    # Empty retrieval → no sources → insufficient evidence
    mock_retrieval.return_value = []
    mock_qa.return_value = None  # QA not called when no sources

    resp = await client.post(
        ASK_URL,
        json={"question": "What is the meaning of life?"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert body["answer"] == ""
    assert body["insufficientContext"] is True


@pytest.mark.asyncio
@patch("brain.adapters.qa_adapter", new_callable=AsyncMock)
@patch("brain.adapters.retrieval_adapter", new_callable=AsyncMock)
@patch("brain.adapters.context_adapter", new_callable=AsyncMock)
@patch("reliability.routes.store_query_reliability", new_callable=AsyncMock)
async def test_ask_success_returns_outcome(
    mock_store, mock_ctx, mock_retrieval, mock_qa,
    client: AsyncClient, create_test_user,
):
    """Successful RAG answer → SUCCESS outcome with real fields."""
    await create_test_user(email="success@test.com", password="Pass123!", name="Success")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "success@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    # Mock retrieval returns a source
    from brain.types import SourceRef
    mock_retrieval.return_value = [
        SourceRef(
            chunk_id="c1",
            content="Charles Darwin published On the Origin of Species in 1859.",
            score=0.68,
            document_id="d1",
            document_name="darwin.pdf",
            page=1,
        )
    ]

    # Mock context builder
    mock_ctx.return_value = "Charles Darwin published On the Origin of Species in 1859."

    # Mock QA returns a grounded answer
    from brain.types import QaResult
    mock_qa.return_value = QaResult(answer="1859", score=0.82, start=56, end=60)

    resp = await client.post(
        ASK_URL,
        json={"question": "When did Darwin publish?"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "SUCCESS"
    assert body["answer"] == "1859"
    assert body["confidence"] > 0
    assert len(body["sources"]) >= 1
    assert body["reliability"]["qaConfidence"] > 0
    assert body["reliability"]["factualGrounded"] is True


@pytest.mark.asyncio
@patch("brain.adapters.qa_adapter", new_callable=AsyncMock)
@patch("brain.adapters.retrieval_adapter", new_callable=AsyncMock)
@patch("brain.adapters.context_adapter", new_callable=AsyncMock)
@patch("reliability.routes.store_query_reliability", new_callable=AsyncMock)
async def test_ask_partial_answer_returns_partial_outcome(
    mock_store, mock_ctx, mock_retrieval, mock_qa,
    client: AsyncClient, create_test_user,
):
    """Low-confidence answer → PARTIAL outcome."""
    await create_test_user(email="partial@test.com", password="Pass123!", name="Partial")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "partial@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    from brain.types import SourceRef, QaResult
    mock_retrieval.return_value = [
        SourceRef(
            chunk_id="c1", content="Some tangentially related text",
            score=0.55, document_id="d1", document_name="doc.pdf", page=1,
        )
    ]
    mock_ctx.return_value = "Some tangentially related text"
    # Low confidence, not grounded
    mock_qa.return_value = QaResult(answer="maybe something", score=0.15, start=0, end=15)

    resp = await client.post(
        ASK_URL,
        json={"question": "What is obscure?"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "PARTIAL"
    assert body["answer"] == "maybe something"


@pytest.mark.asyncio
@patch("brain.adapters.qa_adapter", new_callable=AsyncMock)
@patch("brain.adapters.retrieval_adapter", new_callable=AsyncMock)
@patch("brain.adapters.context_adapter", new_callable=AsyncMock)
@patch("reliability.routes.store_query_reliability", new_callable=AsyncMock)
async def test_ask_sources_carry_phase3d_metadata(
    mock_store, mock_ctx, mock_retrieval, mock_qa,
    client: AsyncClient, create_test_user,
):
    """Phase 3D metadata must survive retrieval → evidence → API sources."""
    await create_test_user(email="meta@test.com", password="Pass123!", name="Meta")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "meta@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    from brain.types import QaResult, SourceRef
    mock_retrieval.return_value = [
        SourceRef(
            chunk_id="c1",
            content="The Vermilion coating cures in 6 hours.",
            score=0.71,
            document_id="d1",
            document_name="manual.docx",
            page=None,
            heading_path=("Reference Manual", "Epsilon"),
            section="Epsilon",
            element_type="paragraph",
            token_count=42,
            chunker_version="chunk-v2-structure-tokens",
        )
    ]
    mock_ctx.return_value = "The Vermilion coating cures in 6 hours."
    mock_qa.return_value = QaResult(
        answer="6 hours", score=0.81, start=0, end=7,
    )

    resp = await client.post(
        ASK_URL,
        json={"question": "How long does the coating cure?"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["headingPath"] == ["Reference Manual", "Epsilon"]
    assert source["section"] == "Epsilon"
    assert source["elementType"] == "paragraph"
    assert source["tokenCount"] == 42
    assert source["chunkerVersion"] == "chunk-v2-structure-tokens"


@pytest.mark.asyncio
@patch("brain.adapters.qa_adapter", new_callable=AsyncMock)
@patch("brain.adapters.retrieval_adapter", new_callable=AsyncMock)
@patch("brain.adapters.context_adapter", new_callable=AsyncMock)
@patch("reliability.routes.store_query_reliability", new_callable=AsyncMock)
async def test_ask_legacy_sources_report_null_metadata(
    mock_store, mock_ctx, mock_retrieval, mock_qa,
    client: AsyncClient, create_test_user,
):
    """Legacy chunks have no structure metadata and must report null."""
    await create_test_user(email="legacy@test.com", password="Pass123!", name="Legacy")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "legacy@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    from brain.types import QaResult, SourceRef
    mock_retrieval.return_value = [
        SourceRef(
            chunk_id="c1", content="old chunk text", score=0.66,
            document_id="d1", document_name="old.txt", page=3,
        )
    ]
    mock_ctx.return_value = "old chunk text"
    mock_qa.return_value = QaResult(answer="old", score=0.7, start=0, end=3)

    body = (
        await client.post(
            ASK_URL,
            json={"question": "What is old?"},
            headers=_auth_header(token),
        )
    ).json()

    source = body["sources"][0]
    assert source["page"] == 3
    assert source["headingPath"] is None
    assert source["section"] is None
    assert source["elementType"] is None
    assert source["tokenCount"] is None
    assert source["chunkerVersion"] is None

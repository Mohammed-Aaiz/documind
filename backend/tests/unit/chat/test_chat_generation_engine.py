"""Engine selection on the primary chat endpoint (``POST /api/chat/ask``).

The generative engine is opt-in per request.  These tests pin the contract:

* the default stays extractive (the Brain runs, generation does not);
* ``engine="generative"`` delegates to the single shared generation service
  (``generation.service.run_generation`` / ``persist_generation``) and returns
  the documented ``AskResponse`` shape;
* an unknown engine is rejected rather than silently ignored;
* an unavailable model is a 503, never an empty "answer".

Generation is mocked at the service boundary, so no model weights are needed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from generation.service import GenerativeAnswer
from generation.types import EvidenceBlock


LOGIN_URL = "/api/auth/login"
ASK_URL = "/api/chat/ask"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, create_test_user, email: str) -> str:
    await create_test_user(email=email, password="Pass123!", name="Engine")
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "Pass123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


class _Chunk:
    """Minimal SourceChunk stand-in with the provenance the route reports."""

    def __init__(self, chunk_id: str, content: str, path: str = "semantic"):
        self.chunk_id = chunk_id
        self.content = content
        self.score = 0.42
        self.document_id = "doc-1"
        self.document_name = "maintenance.pdf"
        self.page = 4
        self.heading_path = ["Maintenance", "Calibration"]
        self.section = "Calibration"
        self.element_type = "paragraph"
        self.token_count = 30
        self.chunker_version = "v2"
        self.retrieval_path = path
        self.fusion_score = None
        self.structural_hops = None
        self.evidence_kind = "chunk"
        self.table_element_id = None
        self.row_index = None
        self.header_repeated = None


def _generative_answer() -> tuple[list[_Chunk], GenerativeAnswer]:
    chunk = _Chunk("c1", "The lidar calibration interval is 6 months.")
    blocks = [
        EvidenceBlock(
            index=1,
            content=chunk.content,
            document_id=chunk.document_id,
            document_name=chunk.document_name,
            page=chunk.page,
            chunk_id=chunk.chunk_id,
            score=chunk.score,
        )
    ]
    result = GenerativeAnswer(
        answer="The lidar calibration interval is 6 months. [1]",
        abstained=False,
        insufficient_context=False,
        verification={
            "claimCount": 1,
            "supportedClaims": 1,
            "unsupportedClaims": [],
            "uncitedClaims": 0,
            "citationAccuracy": 1.0,
            "verified": True,
            "status": "SUPPORTED",
            "wrongEntityClaims": [],
        },
        warnings=[],
        marks=10,
        model="google/flan-t5-base",
        latency_ms=1234,
        blocks=blocks,
    )
    return [chunk], result


@pytest.mark.asyncio
@patch("chat.routes.is_model_available", return_value=False)
@patch("chat.routes.get_model_status", return_value={"available": False, "error": "Model not found"})
@patch("brain.Brain.process", new_callable=AsyncMock)
@patch("generation.service.run_generation", new_callable=AsyncMock)
async def test_default_engine_is_extractive(
    mock_run_generation, mock_process, _status, _available, client: AsyncClient, create_test_user
):
    """A request without ``engine`` keeps using the extractive Brain path."""
    from brain.types import BrainResponse, ExecutionContext
    from outcomes import Outcome

    token = await _login(client, create_test_user, "default-engine@test.com")

    ctx = ExecutionContext(user_id="u1", raw_question="What is the calibration interval?")
    ctx.outcome = Outcome.UNAVAILABLE
    ctx.response = BrainResponse(answer="", outcome=Outcome.UNAVAILABLE, question="q")
    mock_process.return_value = ctx

    resp = await client.post(
        ASK_URL, json={"question": "What is the calibration interval?"}, headers=_auth_header(token)
    )

    # Unavailable extractive model → 503; the generative service was never used.
    assert resp.status_code == 503
    mock_run_generation.assert_not_awaited()


@pytest.mark.asyncio
@patch("generation.service.persist_generation", new_callable=AsyncMock)
@patch("generation.service.run_generation", new_callable=AsyncMock)
async def test_generative_engine_returns_generative_answer(
    mock_run_generation, mock_persist, client: AsyncClient, create_test_user
):
    """``engine="generative"`` uses the shared service and reports its engine."""
    token = await _login(client, create_test_user, "generative-engine@test.com")
    chunks, result = _generative_answer()
    mock_run_generation.return_value = (chunks, result)

    resp = await client.post(
        ASK_URL,
        json={"question": "What is the lidar calibration interval?", "engine": "generative", "answerFormat": "10"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["engine"] == "generative"
    assert body["answer"] == result.answer
    assert body["marks"] == 10
    assert body["verification"]["status"] == "SUPPORTED"
    assert body["verification"]["verified"] is True
    assert body["insufficientContext"] is False
    assert body["outcome"] == "SUCCESS"
    # Only the evidence actually supplied to the generator is reported.
    assert [s["chunkId"] for s in body["sources"]] == ["c1"]
    assert body["sources"][0]["page"] == 4
    assert body["sources"][0]["section"] == "Calibration"
    # No extractive span exists, so confidence is honestly zero, not invented.
    assert body["confidence"] == 0.0
    assert body["reliability"]["qaConfidence"] == 0.0
    assert body["reliability"]["sourceCount"] == 1
    assert body["reliability"]["pipelineVersion"].startswith("generative-")
    # Persistence runs once, with the same evidence.
    assert mock_persist.await_count == 1


@pytest.mark.asyncio
@patch("generation.service.persist_generation", new_callable=AsyncMock)
@patch("generation.service.run_generation", new_callable=AsyncMock)
async def test_generative_engine_reports_abstention(
    mock_run_generation, _persist, client: AsyncClient, create_test_user
):
    """Abstention is surfaced as INSUFFICIENT_EVIDENCE, not as an answer."""
    token = await _login(client, create_test_user, "abstain-engine@test.com")
    chunks, result = _generative_answer()
    result.answer = ""
    result.abstained = True
    result.insufficient_context = True
    result.verification = {
        "claimCount": 0,
        "supportedClaims": 0,
        "unsupportedClaims": [],
        "uncitedClaims": 0,
        "citationAccuracy": 0.0,
        "verified": False,
        "status": "INSUFFICIENT_EVIDENCE",
        "wrongEntityClaims": [],
    }
    mock_run_generation.return_value = (chunks, result)

    resp = await client.post(
        ASK_URL,
        json={"question": "What is the warranty period?", "engine": "generative"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == ""
    assert body["insufficientContext"] is True
    assert body["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert body["verification"]["verified"] is False
    assert body["verification"]["status"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
async def test_unknown_engine_is_rejected(client: AsyncClient, create_test_user):
    token = await _login(client, create_test_user, "bad-engine@test.com")
    resp = await client.post(
        ASK_URL,
        json={"question": "Anything?", "engine": "magic"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 400
    assert "engine" in resp.json()["detail"].lower()


@pytest.mark.asyncio
@patch("generation.service.run_generation", new_callable=AsyncMock)
async def test_generative_model_unavailable_returns_503(
    mock_run_generation, client: AsyncClient, create_test_user
):
    from generation.types import GenerationUnavailableError

    token = await _login(client, create_test_user, "gen-503@test.com")
    mock_run_generation.side_effect = GenerationUnavailableError("weights missing")

    resp = await client.post(
        ASK_URL,
        json={"question": "What is the interval?", "engine": "generative"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "message" in detail
    assert "weights missing" in detail["message"]

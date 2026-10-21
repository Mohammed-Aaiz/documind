"""Integration tests for the dual-path RAG flow.

Two layers are exercised:

1. **Retrieval adapter** — the semantic half is supplied by a declared test
   double (the pgvector ``<=>`` operator does not exist on the SQLite test
   database), while the structural half runs the *real* queries against the
   *real* graph rows.  That is what this file is actually testing.
2. **HTTP contract** — ``/api/chat/ask`` must expose the additive provenance
   fields and keep every existing field intact, and the reliability payload must
   agree with the sources that were reported.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from chat.rag import RETRIEVAL_HYBRID, RETRIEVAL_STRUCTURAL, SourceChunk
from graph.service import replace_document_graph
from tests.fixtures.graph_data import create_document_with_chunks, views_for

DOCUMENT_CHUNKS = [
    {
        "index": 0,
        "content": "Reference Manual: the vermilion coating cures in six hours.",
        "page": 1,
        "heading_path": ["Reference Manual"],
        "section": "Reference Manual",
    },
    {
        "index": 1,
        "content": "Reference Manual: storage temperature is 21 degrees.",
        "page": 2,
        "heading_path": ["Reference Manual"],
        "section": "Reference Manual",
    },
    {
        "index": 2,
        "content": "Appendix: unrelated boilerplate.",
        "page": 3,
        "heading_path": ["Appendix"],
        "section": "Appendix",
    },
]


async def _seed_graph(db_session, user, *, name="manual.pdf"):
    """Persist a document with chunks and a complete structural graph."""
    doc, rows = await create_document_with_chunks(
        db_session, user.id, name=name, chunks=DOCUMENT_CHUNKS
    )
    await replace_document_graph(db_session, doc.id, views_for(rows))
    await db_session.commit()
    return doc, rows


def _semantic_hit(chunk_id: str, content: str, score: float) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        content=content,
        score=score,
        document_id="doc-1",
        document_name="manual.pdf",
        page=1,
    )


class TestRetrievalAdapterDualPath:
    async def test_adapter_fuses_semantic_and_structural_paths(
        self, db_session, create_test_user
    ):
        from brain.adapters import retrieval_adapter

        user = await create_test_user(email="flow-a@test.com")
        _doc, rows = await _seed_graph(db_session, user)

        # The vector path "finds" the appendix chunk, which is far from the
        # section the question names.  The structural path should add the
        # Reference Manual chunks.
        semantic_hit = _semantic_hit(
            str(rows[2].id), DOCUMENT_CHUNKS[2]["content"], 0.62
        )

        with patch(
            "brain.adapters.retrieve_chunks",
            new=AsyncMock(return_value=[semantic_hit]),
        ):
            refs = await retrieval_adapter(
                db=db_session,
                user_id=str(user.id),
                cleaned_text="What does the Reference Manual say about curing?",
                top_k=5,
            )

        by_id = {ref.chunk_id: ref for ref in refs}
        assert str(rows[0].id) in by_id, "structural path added no evidence"

        structural_refs = [r for r in refs if r.retrieval_path == RETRIEVAL_STRUCTURAL]
        assert structural_refs, "no source was labelled structural"
        for ref in structural_refs:
            assert ref.score == 0.0, "structural evidence got a fabricated similarity"
            assert ref.fusion_score is not None

        assert by_id[str(rows[2].id)].retrieval_path in ("semantic", "hybrid")

    async def test_adapter_without_a_db_session_is_semantic_only(
        self, db_session, create_test_user
    ):
        """The existing ``db=None`` calling convention must keep working."""
        from brain.adapters import retrieval_adapter

        semantic_hit = _semantic_hit("chunk-1", "body", 0.9)
        with patch(
            "brain.adapters.retrieve_chunks",
            new=AsyncMock(return_value=[semantic_hit]),
        ):
            refs = await retrieval_adapter(
                db=None, user_id="u1", cleaned_text="q", top_k=5
            )

        assert [r.chunk_id for r in refs] == ["chunk-1"]
        assert refs[0].retrieval_path == "semantic"
        assert refs[0].fusion_score is None

    async def test_dual_path_can_be_switched_off(self, db_session, create_test_user):
        from brain.adapters import retrieval_adapter

        user = await create_test_user(email="flow-off@test.com")
        await _seed_graph(db_session, user, name="off.pdf")
        semantic_hit = _semantic_hit("chunk-1", "body", 0.9)

        with patch.dict("os.environ", {"DOCUMIND_DUAL_PATH_RAG": "0"}):
            with patch(
                "brain.adapters.retrieve_chunks",
                new=AsyncMock(return_value=[semantic_hit]),
            ):
                refs = await retrieval_adapter(
                    db=db_session,
                    user_id=str(user.id),
                    cleaned_text="Reference Manual curing",
                    top_k=5,
                )

        assert [r.chunk_id for r in refs] == ["chunk-1"]


class TestAskEndpointProvenance:
    async def test_ask_returns_additive_provenance_and_reliability(
        self, client, db_session, create_test_user
    ):
        user = await create_test_user(
            email="ask-flow@test.com", password="Pass123!"
        )
        _doc, rows = await _seed_graph(db_session, user, name="ask.pdf")

        login = await client.post(
            "/api/auth/login",
            json={"email": "ask-flow@test.com", "password": "Pass123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        semantic_hit = _semantic_hit(
            str(rows[0].id), DOCUMENT_CHUNKS[0]["content"], 0.81
        )

        from brain.types import QaResult

        qa_result = QaResult(
            answer="vermilion coating cures in six hours",
            score=0.9,
            start=0,
            end=len("vermilion coating cures in six hours"),
        )

        with patch(
            "brain.adapters.retrieve_chunks",
            new=AsyncMock(return_value=[semantic_hit]),
        ), patch(
            "brain.adapters.qa_adapter",
            new=AsyncMock(return_value=qa_result),
        ):
            resp = await client.post(
                "/api/chat/ask",
                json={
                    "question": "What does the Reference Manual say about curing?",
                    "topK": 5,
                },
                headers=headers,
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Existing contract is untouched.
        assert "answer" in body and "sources" in body and "reliability" in body
        assert body["question"] == "What does the Reference Manual say about curing?"

        # New additive source fields are present and honest.
        for source in body["sources"]:
            assert source["retrievalPath"] in ("semantic", "structural", "hybrid")
            assert source["fusionScore"] is not None
            if source["retrievalPath"] == "structural":
                assert source["score"] == 0.0
                assert source["structuralHops"] is not None

        reliability = body["reliability"]
        for key in (
            "semanticSourceCount",
            "structuralSourceCount",
            "hybridSourceCount",
            "structuralHopMax",
            "pathAgreement",
            "evidenceCoverage",
            "fusionEnabled",
            "pipelineVersion",
        ):
            assert key in reliability, f"reliability is missing {key}"

        assert reliability["pipelineVersion"] == "dual-path-graph-rag-v1"
        assert reliability["fusionEnabled"] is True

        counts = (
            reliability["semanticSourceCount"]
            + reliability["structuralSourceCount"]
            + reliability["hybridSourceCount"]
        )
        assert counts == reliability["sourceCount"], (
            "path counts must partition the reported evidence exactly"
        )

    async def test_reported_sources_match_reliability_sources(
        self, client, db_session, create_test_user
    ):
        """Provenance must agree between the response and the Reliability Center."""
        user = await create_test_user(
            email="rel-flow@test.com", password="Pass123!"
        )
        _doc, rows = await _seed_graph(db_session, user, name="rel.pdf")

        login = await client.post(
            "/api/auth/login",
            json={"email": "rel-flow@test.com", "password": "Pass123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        semantic_hit = _semantic_hit(str(rows[0].id), DOCUMENT_CHUNKS[0]["content"], 0.8)

        from brain.types import QaResult

        qa_result = QaResult(
            answer="vermilion coating cures in six hours",
            score=0.9,
            start=0,
            end=len("vermilion coating cures in six hours"),
        )

        with patch(
            "brain.adapters.retrieve_chunks",
            new=AsyncMock(return_value=[semantic_hit]),
        ), patch(
            "brain.adapters.qa_adapter",
            new=AsyncMock(return_value=qa_result),
        ):
            ask = await client.post(
                "/api/chat/ask",
                json={"question": "Reference Manual curing time", "topK": 5},
                headers=headers,
            )

        assert ask.status_code == 200, ask.text
        ask_body = ask.json()

        last = await client.get("/api/reliability/last-query", headers=headers)
        assert last.status_code == 200
        last_body = last.json()

        assert last_body["question"] == ask_body["question"]
        assert last_body["sourceCount"] == ask_body["reliability"]["sourceCount"]
        assert {s["id"] for s in last_body["sources"]} == {
            s["chunkId"] for s in ask_body["sources"]
        }
        for source in last_body["sources"]:
            assert source["retrievalPath"] in ("semantic", "structural", "hybrid")

    async def test_ask_without_any_evidence_still_abstains_honestly(
        self, client, db_session, create_test_user
    ):
        await create_test_user(email="ask-empty@test.com", password="Pass123!")

        login = await client.post(
            "/api/auth/login",
            json={"email": "ask-empty@test.com", "password": "Pass123!"},
        )
        token = login.json()["access_token"]

        from brain.types import QaResult

        with patch(
            "brain.adapters.retrieve_chunks", new=AsyncMock(return_value=[])
        ), patch(
            "brain.adapters.qa_adapter",
            new=AsyncMock(return_value=QaResult("", 0.0, 0, 0)),
        ):
            resp = await client.post(
                "/api/chat/ask",
                json={"question": "Anything at all?", "topK": 5},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["insufficientContext"] is True
        assert body["sources"] == []
        assert body["reliability"]["sourceCount"] == 0
        assert body["reliability"]["structuralSourceCount"] == 0

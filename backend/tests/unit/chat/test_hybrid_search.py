"""Hybrid retrieval ranks evidence without fabricating cosine measurements."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import DBAPIError

from chat import rag
from chat.rag import SourceChunk


def chunk(cid, score=.8):
    return SourceChunk(cid, f"Content for {cid}.", score, "document-1", "manual.pdf", 3)


def test_dual_match_outweighs_single_matches_without_replacing_cosine():
    dense = [chunk("dense"), chunk("shared", .63)]
    lexical = [chunk("shared", 87), chunk("lexical", 1000)]
    fused = rag.fuse_search_candidates(dense, lexical, top_k=3)
    assert fused[0].chunk_id == "shared" and fused[0].retrieval_path == "hybrid"
    assert fused[0].score == .63 and fused[0].page == 3
    assert next(c for c in fused if c.chunk_id == "lexical").score == 0
    assert next(c for c in fused if c.chunk_id == "lexical").retrieval_path == "lexical"
    assert fused[0].fusion_score > fused[1].fusion_score


def test_duplicate_hits_do_not_gain_extra_fusion_votes_and_ties_are_stable():
    fused = rag.fuse_search_candidates([chunk("b"), chunk("b")], [chunk("a")], top_k=2)
    assert [c.chunk_id for c in fused] == ["a", "b"]
    assert fused[0].fusion_score == fused[1].fusion_score


class Database:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    @asynccontextmanager
    async def begin_nested(self):
        yield

    async def execute(self, sql, params):
        self.calls.append((str(sql), params))
        if self.error:
            raise self.error
        row = SimpleNamespace(chunk_id="lexical", content="Kestrel FR-27 exact term.",
            document_id="document-1", document_name="manual.pdf", page=7,
            heading_path=["Maintenance"], section="Maintenance", element_type="paragraph",
            token_count=None, chunker_version="structure-v2")
        return SimpleNamespace(fetchall=lambda: [row])


@pytest.mark.asyncio
async def test_fts_uses_bound_owner_query_and_a_bounded_candidate_pool(monkeypatch):
    dense = AsyncMock(return_value=[chunk("dense")])
    monkeypatch.setattr(rag, "retrieve_chunks", dense)
    db = Database()
    question = "FR-27 ' OR 1=1 --"
    result = await rag.retrieve_hybrid_chunks(db, "owner-1", question, top_k=5)
    dense.assert_awaited_once_with(db, "owner-1", question, top_k=20, iterative_scan=True)
    sql, params = db.calls[0]
    assert params == {"query": question, "user_id": "owner-1", "candidate_k": 20}
    assert question not in sql and "owner-1" not in sql
    assert "d.user_id = :user_id" in sql
    assert any(c.chunk_id == "lexical" and c.page == 7 for c in result)


@pytest.mark.asyncio
async def test_database_fts_failure_returns_dense_hits(monkeypatch):
    dense = [chunk("dense")]
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=dense))
    db = Database(DBAPIError("SELECT", {}, RuntimeError("FTS unavailable")))
    assert await rag.retrieve_hybrid_chunks(db, "owner-1", "Kestrel", top_k=5) == dense


@pytest.mark.asyncio
async def test_reranker_receives_more_candidates_than_the_final_answer_limit(monkeypatch):
    candidates = [chunk(str(i)) for i in range(40)]
    dense = AsyncMock(return_value=candidates)
    monkeypatch.setattr(rag, "retrieve_chunks", dense)
    result = await rag.retrieve_hybrid_chunks(Database(), "owner", "calibration", top_k=5, candidate_limit=32)
    assert len(result) == 32
    assert dense.await_args.kwargs["top_k"] == 32


@pytest.mark.asyncio
@pytest.mark.parametrize("iterative", [False, True])
async def test_ann_controls_are_transaction_local_and_opt_in(monkeypatch, iterative):
    monkeypatch.setattr(rag, "embed_query", lambda query: [.1] * 384)
    execute = AsyncMock(return_value=SimpleNamespace(fetchall=lambda: []))
    db = SimpleNamespace(execute=execute)
    assert await rag.retrieve_chunks(db, "owner", "query", iterative_scan=iterative) == []
    assert execute.await_count == 1 + int(iterative)
    search = execute.await_args_list[-1]
    assert "d.user_id = :user_id" in str(search.args[0])
    assert search.args[1]["user_id"] == "owner"
    if iterative:
        controls = str(execute.await_args_list[0].args[0])
        assert "'strict_order', true" in controls
        assert "'100', true" in controls

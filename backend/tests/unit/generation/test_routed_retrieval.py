"""Execute only the routed indexes, while preserving a dense rescue path."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from chat import rag
from chat.rag import SourceChunk
from generation import query_router, service, spatial_retrieval, reranking
from generation.query_router import RoutingDecision
from graph import service as graph_service
from graph.service import KnowledgeGraphCandidate
from embeddings import visual, visual_index


@pytest.fixture(autouse=True)
def isolate_neural_reranking(monkeypatch):
    async def retain_order(question, chunks, *, top_k=5):
        return list(chunks)[:top_k], {"status": "test_isolated"}
    monkeypatch.setattr(reranking, "rerank_candidates", retain_order)


def dense_chunk():
    return SourceChunk("dense-1", "Alpha is an autonomous survey platform.", .82, "doc-1", "alpha.txt", 1)


def graph_candidate():
    return KnowledgeGraphCandidate(
        chunk_id="graph-1", content="Alpha supports Beta.", document_id="doc-2",
        document_name="relations.txt", page=1, heading_path=None, section=None,
        predicate="supports", evidence_quote="Alpha supports Beta.",
        graph_path="Alpha supports Beta", hops=1,
    )


def patch_paths(monkeypatch, path, *, graph_status="available", graph_has_match=True):
    calls = {"dense": 0, "graph": 0, "router": 0}

    async def dense(*_args, **_kwargs):
        calls["dense"] += 1
        return [dense_chunk()]

    async def graph(*_args, **kwargs):
        calls["graph"] += 1
        assert kwargs["max_hops"] <= 3
        return [graph_candidate()] if graph_has_match else []

    async def status(*_args):
        return graph_status

    async def route(*_args, **_kwargs):
        calls["router"] += 1
        return RoutingDecision(path, "classified query", "llm", 3)

    async def no_spatial(_db, _owner, _question, values):
        return values, "not_recorded"

    monkeypatch.setattr(rag, "retrieve_chunks", dense)
    monkeypatch.setattr(rag, "dual_path_enabled", lambda: False)
    monkeypatch.setattr(rag, "table_evidence_enabled", lambda: False)
    monkeypatch.setattr(graph_service, "retrieve_knowledge_graph_candidates", graph)
    monkeypatch.setattr(graph_service, "knowledge_graph_status", status)
    monkeypatch.setattr(query_router, "route_query", route)
    monkeypatch.setattr(spatial_retrieval, "enrich_spatial_sources", no_spatial)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("path,expected_dense,expected_graph,expected_ids", [
    ("semantic", 1, 0, {"dense-1"}),
    ("graph", 0, 1, {"graph-1"}),
    ("both", 1, 1, {"dense-1", "graph-1"}),
])
async def test_route_selects_index_execution_and_preserves_metadata(
    db_session, monkeypatch, path, expected_dense, expected_graph, expected_ids,
):
    calls = patch_paths(monkeypatch, path)
    evidence = await service.retrieve_evidence(db_session, "owner", "Explain Alpha", query_routing=True)
    assert calls == {"dense": expected_dense, "graph": expected_graph, "router": 1}
    assert {chunk.chunk_id for chunk in evidence} == expected_ids
    assert evidence.routing["path"] == path
    assert evidence.routing["source"] == "llm"
    assert evidence.spatial_status == "not_recorded"
    if path != "semantic":
        relation = next(chunk for chunk in evidence if chunk.chunk_id == "graph-1")
        assert relation.knowledge_graph_quote == "Alpha supports Beta."
        assert relation.knowledge_graph_hops == 1


@pytest.mark.asyncio
async def test_graph_prediction_with_no_entity_match_gets_dense_rescue(db_session, monkeypatch):
    calls = patch_paths(monkeypatch, "graph", graph_has_match=False)
    evidence = await service.retrieve_evidence(db_session, "owner", "How is Alpha related to Gamma?", query_routing=True)
    assert calls == {"dense": 1, "graph": 1, "router": 1}
    assert evidence.routing["denseRescue"] is True
    assert evidence.knowledge_graph_status == "available_no_match"
    assert [chunk.chunk_id for chunk in evidence] == ["dense-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("question,is_spatial", [("Which figure is below the table?", True), ("Explain Alpha", False)])
async def test_visual_patch_retrieval_only_runs_for_spatial_queries_and_fuses_rank_streams(
    db_session, monkeypatch, question, is_spatial,
):
    patch_paths(monkeypatch, "semantic")
    calls = []
    monkeypatch.setattr("config.get_settings", lambda: SimpleNamespace(visual_embeddings_enabled=True))
    monkeypatch.setattr(visual, "visual_model_status", lambda _: {"available": True, "status": "local_artifact_present"})
    region = {"id": "crop1", "bbox": [.1, .2, .7, .8], "visual_embedding": True}

    async def retrieve(_db, _question, _owner, **kwargs):
        calls.append(kwargs)
        return [SourceChunk("visual:1", "Figure 1. Observed caption.", .1, "doc-1", "alpha.pdf", 1,
            evidence_kind="visual_patch", retrieval_path="visual_spatial", spatial_regions=[region])]

    monkeypatch.setattr(visual_index, "retrieve_visual_patches", retrieve)
    result = await service.retrieve_evidence(db_session, str(uuid4()), question, query_routing=True)
    assert len(calls) == int(is_spatial)
    if is_spatial:
        assert result.routing["visualIndex"] == "retrieved"
        assert [chunk.chunk_id for chunk in result] == ["dense-1", "visual:1"]
        assert result[0].fusion_score == result[1].fusion_score
        assert result[1].spatial_regions == [region]
    else:
        assert [chunk.chunk_id for chunk in result] == ["dense-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["empty", "pending", "unavailable"])
async def test_missing_graph_skips_neural_routing_and_uses_dense_immediately(db_session, monkeypatch, status):
    calls = patch_paths(monkeypatch, "graph", graph_status=status)
    evidence = await service.retrieve_evidence(db_session, "owner", "Explain Alpha", query_routing=True)
    assert calls == {"dense": 1, "graph": 0, "router": 0}
    assert evidence.routing["path"] == "semantic"
    assert evidence.routing["source"] == "index-availability"
    assert evidence.knowledge_graph_status == status

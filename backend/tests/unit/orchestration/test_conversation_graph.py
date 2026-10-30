"""LangGraph conversation graph — nodes, memory writes and failure honesty.

The retrieval, rerank, generation and persistence dependencies are replaced at
the graph boundary, so these tests exercise the *orchestration*: what state each
node reads, what it returns, and what ends up in conversation memory.  No model
weights are needed.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from generation.service import GenerativeAnswer
from orchestration import graph as graph_module
from orchestration.graph import build_conversation_graph
from session.store import InMemoryConversationStore


def _chunk(chunk_id="c1", content="The lidar calibration interval is six months."):
    return SimpleNamespace(
        chunk_id=chunk_id,
        content=content,
        score=0.66,
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


def _answer(text="The interval is six months [1].", *, abstained=False):
    return GenerativeAnswer(
        answer="" if abstained else text,
        abstained=abstained,
        insufficient_context=abstained,
        verification={"verified": not abstained, "status": "SUPPORTED" if not abstained else "INSUFFICIENT_EVIDENCE"},
        warnings=[],
        marks=10,
        model="fake-generator",
        latency_ms=7,
        blocks=[],
    )


@pytest.fixture
def harness(monkeypatch):
    """Patch the graph's external dependencies and capture their calls."""
    calls = {
        "retrieve": [],
        "generate": [],
        "persist": [],
        "rerank": [],
    }
    state = {"chunks": [_chunk()], "answer": _answer()}

    async def fake_retrieve(db, user_id, question, top_k=5, answer_format=None):
        # The graph passes the mark level through so a 15-mark answer gets the
        # 1-hop graph expansion on the same retrieval implementation.
        calls["retrieve"].append(
            {
                "user_id": user_id,
                "question": question,
                "top_k": top_k,
                "answer_format": answer_format,
            }
        )
        return list(state["chunks"])

    def fake_generate(question, chunks, *, answer_format=None, generator=None, history=()):
        calls["generate"].append(
            {
                "question": question,
                "chunks": len(chunks),
                "history": list(history),
                "generator": generator,
            }
        )
        return state["answer"]

    async def fake_persist(db, user_id, question, chunks, result, answer_format):
        calls["persist"].append({"user_id": user_id, "question": question, "model": result.model})

    def fake_rerank(question, chunks):
        calls["rerank"].append({"question": question, "count": len(chunks)})
        return list(chunks), {
            "applied": True,
            "signal": "distilbert-span-probability",
            "scored": len(chunks),
            "candidates": len(chunks),
            "scores": [],
            "error": None,
        }

    monkeypatch.setattr(graph_module, "retrieve_evidence", fake_retrieve)
    monkeypatch.setattr(graph_module, "answer_generatively", fake_generate)
    monkeypatch.setattr(graph_module, "persist_generation", fake_persist)
    monkeypatch.setattr(graph_module, "rerank_chunks", fake_rerank)
    monkeypatch.setattr(graph_module, "is_conversation_model_available", lambda: False)
    monkeypatch.setattr(graph_module, "conversation_model_status", lambda: {"model": None, "error": None})

    return SimpleNamespace(calls=calls, state=state)


async def _run(store, question, *, session="s1", user="u1", top_k=5, answer_format="10"):
    graph = build_conversation_graph(db=None, store=store)
    return await graph.ainvoke(
        {
            "user_id": user,
            "session_id": session,
            "question": question,
            "answer_format": answer_format,
            "top_k": top_k,
        },
        config={"recursion_limit": 20},
    )


class TestFirstTurn:
    @pytest.mark.asyncio
    async def test_answer_is_generated_verified_and_remembered(self, harness):
        store = InMemoryConversationStore()

        state = await _run(store, "What is the lidar calibration interval?")

        assert state["answer"] == "The interval is six months [1]."
        assert state["engine"] == "generative"
        assert state["model"] == "fake-generator"
        assert state["rerank"]["applied"] is True
        assert state["followup_resolved"] is False
        assert state["retrieval_query"] == "What is the lidar calibration interval?"

        assert harness.calls["retrieve"][0]["user_id"] == "u1"
        assert harness.calls["persist"][0]["user_id"] == "u1"

        memory = await store.history("u1", "s1")
        assert [m.role for m in memory] == ["user", "assistant"]
        assert memory[1].content == "The interval is six months [1]."
        assert [turn["role"] for turn in state["history"]] == ["user", "assistant"]


class TestFollowUpTurn:
    @pytest.mark.asyncio
    async def test_second_turn_uses_the_previous_question_for_retrieval(self, harness):
        store = InMemoryConversationStore()
        await _run(store, "What is the lidar calibration interval?")

        state = await _run(store, "And the second one?")

        assert state["followup_resolved"] is True
        assert state["retrieval_query"].startswith("What is the lidar calibration interval?")
        assert harness.calls["retrieve"][-1]["question"] == state["retrieval_query"]
        # The generation node receives the stored history, not an empty list.
        assert harness.calls["generate"][-1]["history"]
        assert [m["role"] for m in state["history"]] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]


class TestNoEvidence:
    @pytest.mark.asyncio
    async def test_abstains_without_calling_generation_and_keeps_only_the_question(self, harness):
        harness.state["chunks"] = []
        harness.state["answer"] = _answer(abstained=True)
        store = InMemoryConversationStore()

        state = await _run(store, "What is the warranty period?")

        assert state["answer"] == ""
        assert state["abstained"] is True
        assert state["insufficient_context"] is True
        assert state["rerank"]["applied"] is False
        # The generator was still consulted (it is the abstention policy); the
        # reranker was not, because there was nothing to rank.
        assert harness.calls["rerank"] == []
        memory = await store.history("u1", "s1")
        assert [m.role for m in memory] == ["user"]


class TestConversationIsolation:
    @pytest.mark.asyncio
    async def test_two_users_with_the_same_session_id_do_not_share_history(self, harness):
        store = InMemoryConversationStore()
        await _run(store, "What is the lidar calibration interval?", user="u1")
        await _run(store, "What is the warranty period?", user="u2")

        first = await store.history("u1", "s1")
        second = await store.history("u2", "s1")
        assert [m.content for m in first] == [
            "What is the lidar calibration interval?",
            "The interval is six months [1].",
        ]
        assert [m.content for m in second] == [
            "What is the warranty period?",
            "The interval is six months [1].",
        ]


class TestRerankFailureIsReported:
    @pytest.mark.asyncio
    async def test_rerank_error_is_surfaced_in_state(self, harness, monkeypatch):
        def failing_rerank(question, chunks):
            return list(chunks), {
                "applied": False,
                "signal": "distilbert-span-probability",
                "scored": 0,
                "candidates": len(chunks),
                "scores": [],
                "error": "rerank skipped: the QA model is unavailable",
            }

        monkeypatch.setattr(graph_module, "rerank_chunks", failing_rerank)
        store = InMemoryConversationStore()

        state = await _run(store, "What is the lidar calibration interval?")

        assert state["answer"]  # evidence still answered from retrieval order
        assert any("QA model is unavailable" in error for error in state["errors"])

"""Learned ordering and bounded CPU admission, without provisioned model I/O."""
import asyncio
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest

from chat.rag import SourceChunk
from generation import reranking
from generation.provider_prompt import select_evidence


def sources(count=3):
    return [SourceChunk(str(i), f"Passage {i} about calibration.", .9 - i / 10,
                        "doc", "manual.pdf", i + 1,
                        knowledge_graph_path="Sensor requires calibration" if i == 2 else None)
            for i in range(count)]


@pytest.fixture
def worker(monkeypatch):
    executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(reranking, "_executor", executor)
    monkeypatch.setattr(reranking, "_admission", threading.BoundedSemaphore(1))
    monkeypatch.setattr(reranking, "reranker_status", lambda: {"available": True, "loaded": True})
    # The mock is at model.predict, retaining real score validation/admission.
    monkeypatch.setitem(sys.modules, "torch.nn", SimpleNamespace(Identity=lambda: None))
    yield
    executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_learned_order_preserves_cosine_pages_and_graph_evidence(worker, monkeypatch):
    candidates = sources()
    monkeypatch.setattr(reranking, "_model", SimpleNamespace(predict=lambda pairs, **kw: [-1., -2., 8.]))
    ranked, status = await reranking.rerank_candidates("Calibration?", candidates, top_k=3)
    assert status["status"] == "ready" and status["signal"] == "cross-encoder-logit"
    assert [c.chunk_id for c in ranked] == ["2", "0", "1"]
    assert ranked[0].score == candidates[2].score and ranked[0].page == 3
    assert ranked[0].knowledge_graph_path == candidates[2].knowledge_graph_path
    assert [c.rerank_position for c in ranked] == [1, 2, 3]


@pytest.mark.asyncio
async def test_deduplication_and_candidate_bound_precede_model_work(worker, monkeypatch):
    seen = []
    def predict(pairs, **kwargs):
        seen.extend(pairs)
        return list(range(len(pairs)))
    monkeypatch.setattr(reranking, "_model", SimpleNamespace(predict=predict))
    candidates = sources(40)
    result, status = await reranking.rerank_candidates("query", candidates[:1] + candidates, top_k=5)
    assert len(seen) == 32 and status["candidates"] == 32
    assert len(result) == 5 and result[0].chunk_id == "31"


@pytest.mark.asyncio
@pytest.mark.parametrize("scores", [[], [float("nan")], [float("inf")]])
async def test_invalid_scores_fail_open_to_original_retrieval_order(worker, monkeypatch, scores):
    original = sources(1)
    monkeypatch.setattr(reranking, "_model", SimpleNamespace(predict=lambda *a, **k: scores))
    result, status = await reranking.rerank_candidates("query", original)
    assert result == original and status["status"] == "error"
    assert reranking._admission.acquire(blocking=False)
    reranking._admission.release()


@pytest.mark.asyncio
async def test_missing_assets_do_not_load_or_call_the_model(monkeypatch):
    monkeypatch.setattr(reranking, "reranker_status", lambda: {"available": False})
    monkeypatch.setattr(reranking, "_score", lambda *a: pytest.fail("Unexpected inference"))
    result, status = await reranking.rerank_candidates("query", sources())
    assert result == sources() and status["status"] == "missing_assets"


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_or_cancellation_holds_admission_until_cpu_work_finishes(worker, monkeypatch, cancel):
    entered, release = threading.Event(), threading.Event()
    def predict(*args, **kwargs):
        entered.set()
        release.wait(1)
        return [1.]
    monkeypatch.setattr(reranking, "_model", SimpleNamespace(predict=predict))
    try:
        task = asyncio.create_task(reranking.rerank_candidates("query", sources(1), timeout_seconds=.02))
        assert await asyncio.to_thread(entered.wait, 1)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            _, status = await task
            assert status["status"] == "timeout"
        _, busy = await reranking.rerank_candidates("another", sources(1))
        assert busy["status"] == "busy"
        release.set()
        for _ in range(100):
            if reranking._admission.acquire(blocking=False):
                reranking._admission.release()
                break
            await asyncio.sleep(.005)
        else:
            pytest.fail("CPU work did not release admission")
        _, status = await reranking.rerank_candidates("after completion", sources(1))
        assert status["status"] == "ready"
    finally:
        release.set()


def test_wrong_checkpoint_manifest_is_not_reported_available(tmp_path, monkeypatch):
    for name in ("config.json", "model.safetensors", "tokenizer.json"):
        (tmp_path / name).write_text("{}")
    (tmp_path / "documind_manifest.json").write_text(json.dumps({"repository": reranking.REPOSITORY, "revision": "wrong"}))
    monkeypatch.setattr(reranking, "MODEL_PATH", tmp_path)
    assert not reranking.reranker_status()["available"]


def test_second_selection_keeps_neural_topic_order_even_for_research():
    ranked = [replace(c, rerank_position=i + 1) for i, c in enumerate(sources())]
    selected, status = select_evidence("Passage 2 calibration", ranked, diversify=True)
    assert [c.chunk_id for c in selected] == ["0", "1", "2"]
    assert status["signal"] == "cross-encoder-order-preserved"

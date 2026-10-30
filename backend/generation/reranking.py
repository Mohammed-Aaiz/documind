"""Bounded local cross-encoder ranking; raw cosine/provenance stay unchanged."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from chat.rag import SourceChunk

REPOSITORY = "cross-encoder/ms-marco-MiniLM-L6-v2"
REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
MODEL_PATH = Path(__file__).resolve().parents[1] / "embeddings" / "assets" / "reranker"
MAX_CANDIDATES = 32
TIMEOUT_SECONDS = 3.0
# ponytail: one CPU worker bounds RAM/threads; add a separate model-serving
# process only when measured concurrent traffic needs more throughput.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="documind-rerank")
_admission = threading.BoundedSemaphore(1)
_model = None
logger = logging.getLogger(__name__)


def reranker_status() -> dict:
    present = all((MODEL_PATH / name).is_file() for name in (
        "config.json", "model.safetensors", "tokenizer.json", "documind_manifest.json"))
    if present:
        try:
            manifest = json.loads((MODEL_PATH / "documind_manifest.json").read_text(encoding="utf-8"))
            present = manifest.get("repository") == REPOSITORY and manifest.get("revision") == REVISION
        except (OSError, ValueError, AttributeError):
            present = False
    return {"available": present, "loaded": _model is not None,
            "model": REPOSITORY, "revision": REVISION, "device": "cpu"}


def _score(question: str, candidates: Sequence[SourceChunk]) -> list[float]:
    global _model
    try:
        if _model is None:
            from sentence_transformers import CrossEncoder
            _model = CrossEncoder(str(MODEL_PATH), device="cpu", local_files_only=True,
                                  trust_remote_code=False, max_length=512)
        from torch.nn import Identity
        values = _model.predict([(question, source.content) for source in candidates],
                                batch_size=8, show_progress_bar=False, activation_fn=Identity())
        scores = [float(value) for value in values]
        if len(scores) != len(candidates) or not all(math.isfinite(score) for score in scores):
            raise ValueError("Invalid reranker scores")
        return scores
    finally:
        _admission.release()


async def rerank_candidates(question: str, candidates: Sequence[SourceChunk], *,
                            top_k: int = 5, timeout_seconds: float | None = None) -> tuple[list[SourceChunk], dict]:
    """Rank up to 32 small candidates off-loop, before parent-topic expansion.

    Cancellation/timeout cannot stop an active torch call. Admission remains
    occupied until that call exits, so subsequent requests never queue behind it.
    Missing/busy/failed models retain RRF order and report that state honestly.
    """
    started = time.perf_counter()
    limit = max(1, min(int(top_k), 20))
    pool, seen = [], set()
    for source in candidates:
        if str(source.chunk_id) not in seen:
            pool.append(source)
            seen.add(str(source.chunk_id))
        if len(pool) == MAX_CANDIDATES:
            break
    status = {**reranker_status(), "status": "empty", "candidates": len(pool),
              "signal": "cross-encoder-logit", "latencyMs": 0}

    def finish(state, result):
        status.update(status=state, signal="cross-encoder-logit" if state == "ready" else "retrieval-order",
                      latencyMs=int((time.perf_counter() - started) * 1000))
        return list(result)[:limit], status

    if not pool:
        return finish("empty", [])
    if not status["available"]:
        return finish("missing_assets", pool)
    if not _admission.acquire(blocking=False):
        return finish("busy", pool)
    try:
        future = asyncio.get_running_loop().run_in_executor(_executor, _score, question, pool)
    except RuntimeError:
        _admission.release()
        return finish("error", pool)
    # Consume a late worker exception after the requesting coroutine timed out.
    future.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
    try:
        timeout = TIMEOUT_SECONDS if timeout_seconds is None else max(.01, min(float(timeout_seconds), 90))
        scores = await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
    except TimeoutError:
        return finish("timeout", pool)
    except Exception:
        logger.warning("Local reranker failed; retaining retrieval order", exc_info=True)
        return finish("error", pool)
    ranked = sorted(range(len(pool)), key=lambda i: (-scores[i], i))
    status["loaded"] = True
    return finish("ready", [replace(pool[i], rerank_position=rank + 1) for rank, i in enumerate(ranked)])


async def warm_reranker() -> dict:
    """Load the provisioned CPU model before accepting requests; never download."""
    from chat.rag import SourceChunk
    _, status = await rerank_candidates("calibration", [SourceChunk(
        "warmup", "The sensor requires calibration.", 0, "warmup", "warmup", None)],
        top_k=1, timeout_seconds=60)
    return status

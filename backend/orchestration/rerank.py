"""Cross-encoder reranking of retrieved evidence with the project QA model.

Role reassignment (Phase C): the fine-tuned DistilBERT QA model is **not** the
answer generator any more — it is the retrieval relevance judge.  For each
retrieved chunk the model is asked the user's question against that single
passage, and its own span probability becomes that chunk's rerank score.

Honesty rules
-------------

* The score is the QA model's probability for the span it extracts from *that
  chunk*.  It is a relevance signal for ordering, not a calibrated probability
  that an eventual answer is correct, and it is never overwritten onto
  ``SourceChunk.score`` (which stays the pgvector similarity).
* If the QA model cannot be loaded the original retrieval order is returned
  unchanged and ``applied=False`` with the reason.  A rerank failure must never
  silently reorder or drop evidence.
* Reranking is bounded: at most ``RERANK_MAX_CANDIDATES`` passages are scored,
  each truncated to ``RERANK_MAX_CHARS`` characters.  Evidence that is not
  scored keeps its own position after the scored passges, in retrieval order.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Sequence

logger = logging.getLogger(__name__)

#: Passages the QA model is run over per question.  Bounds latency: the model is
#: a per-passage forward pass, so this is the dominant cost of reranking.
RERANK_MAX_CANDIDATES = 8

#: Characters per passage handed to the QA model.  The QA window is 384 tokens,
#: and the question shares it, so a longer passage would only be truncated by
#: the tokenizer anyway.
RERANK_MAX_CHARS = 1200


def _chunk_id(chunk: Any) -> str:
    return str(getattr(chunk, "chunk_id", "") or "")


def _passage(chunk: Any) -> str:
    return str(getattr(chunk, "content", "") or "")[:RERANK_MAX_CHARS]


def rerank_chunks(
    question: str,
    chunks: Sequence[Any],
    *,
    top_k: int | None = None,
    max_candidates: int = RERANK_MAX_CANDIDATES,
) -> tuple[list[Any], dict]:
    """Order ``chunks`` by the QA model's relevance judgement.

    Returns ``(ordered_chunks, metadata)`` where ``metadata`` states whether the
    rerank actually ran, which signal produced the scores, and any error.  The
    returned list is always a permutation of the input: reranking can reorder
    evidence but never invent, duplicate or drop it.
    """
    candidates = list(chunks)
    meta: dict = {
        "applied": False,
        "signal": "distilbert-span-probability",
        "scored": 0,
        "candidates": len(candidates),
        "scores": [],
        "error": None,
    }
    if len(candidates) < 2 or not question.strip():
        meta["error"] = "rerank skipped: fewer than two passages" if candidates else "rerank skipped: no evidence"
        return candidates, meta

    from chat.qa_model import answer_question, is_model_available

    if not is_model_available():
        meta["error"] = "rerank skipped: the QA model is unavailable"
        return candidates, meta

    scored: list[tuple[float, int, Any]] = []
    unscored: list[tuple[int, Any]] = []
    limit = max(1, min(int(max_candidates), len(candidates)))

    for index, chunk in enumerate(candidates):
        if index >= limit:
            unscored.append((index, chunk))
            continue
        passage = _passage(chunk)
        if not passage.strip():
            unscored.append((index, chunk))
            continue
        try:
            result = answer_question(question, passage)
        except Exception as exc:  # pragma: no cover - depends on local weights
            logger.warning("Rerank scoring failed (%s); keeping retrieval order", exc)
            meta["error"] = f"rerank skipped: {type(exc).__name__}"
            return candidates, meta

        raw = result.get("score", 0.0)
        try:
            score = float(raw)
        except (TypeError, ValueError):
            score = 0.0
        # A non-finite score would sort arbitrarily; treat it as no signal.
        if not math.isfinite(score):
            score = 0.0
        scored.append((score, index, chunk))

    # Deterministic: score desc, then original rank asc (never a random tie-break).
    scored.sort(key=lambda item: (-item[0], item[1]))
    ordered = [chunk for _score, _index, chunk in scored]
    ordered.extend(chunk for _index, chunk in unscored)

    if top_k is not None and top_k > 0:
        ordered = ordered[:top_k]

    meta["applied"] = True
    meta["scored"] = len(scored)
    meta["scores"] = [
        {"chunkId": _chunk_id(chunk), "rerankScore": round(score, 4)}
        for score, _index, chunk in scored
    ]
    return ordered, meta


__all__ = ["RERANK_MAX_CANDIDATES", "RERANK_MAX_CHARS", "rerank_chunks"]

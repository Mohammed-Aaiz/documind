"""Retrieval metrics: Recall@K, Precision@K, MRR and nDCG@K.

Pure functions over *retrieved id lists* and *gold id sets*, so they can be
verified independently of any pipeline.  Nothing here assumes a retrieval
strategy — the same functions score the vector path, the structural path and the
fused path.
"""

from __future__ import annotations

import math
from typing import Sequence


def _unique_in_order(ids: Sequence[str]) -> list[str]:
    """De-duplicate while preserving rank order (the first occurrence wins)."""
    seen: set[str] = set()
    out: list[str] = []
    for chunk_id in ids:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        out.append(chunk_id)
    return out


def recall_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int) -> float:
    """Fraction of gold chunks present in the first ``k`` retrieved ids.

    ``0.0`` when there is no gold evidence to recall — a question with no gold
    chunks cannot be said to have been recalled.
    """
    gold_set = set(gold)
    if not gold_set or k <= 0:
        return 0.0
    top = set(_unique_in_order(retrieved)[:k])
    return len(top & gold_set) / len(gold_set)


def precision_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int) -> float:
    """Fraction of the first ``k`` retrieved ids that are gold."""
    if k <= 0:
        return 0.0
    top = _unique_in_order(retrieved)[:k]
    if not top:
        return 0.0
    gold_set = set(gold)
    return sum(1 for chunk_id in top if chunk_id in gold_set) / len(top)


def reciprocal_rank(retrieved: Sequence[str], gold: Sequence[str]) -> float:
    """``1 / rank`` of the first gold chunk (rank is 1-based); ``0.0`` if none."""
    gold_set = set(gold)
    if not gold_set:
        return 0.0
    for rank, chunk_id in enumerate(_unique_in_order(retrieved), start=1):
        if chunk_id in gold_set:
            return 1.0 / rank
    return 0.0


def mrr(retrieved_lists: Sequence[Sequence[str]], gold_sets: Sequence[Sequence[str]]) -> float:
    """Mean reciprocal rank across questions."""
    if not retrieved_lists:
        return 0.0
    return sum(
        reciprocal_rank(r, g) for r, g in zip(retrieved_lists, gold_sets)
    ) / len(retrieved_lists)


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    """Discounted cumulative gain with the standard ``log2(rank + 1)`` discount."""
    total = 0.0
    for rank, gain in enumerate(relevances[:k], start=1):
        total += float(gain) / math.log2(rank + 1)
    return total


def ndcg_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int) -> float:
    """Normalised DCG@K with binary relevance.

    Returns ``0.0`` when nothing is relevant (there is no ideal ranking to
    normalise against).
    """
    if k <= 0:
        return 0.0
    gold_set = set(gold)
    if not gold_set:
        return 0.0

    ids = _unique_in_order(retrieved)[:k]
    gains = [1.0 if chunk_id in gold_set else 0.0 for chunk_id in ids]

    ideal = [1.0] * min(len(gold_set), k)
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg == 0.0:
        return 0.0
    return dcg_at_k(gains, k) / ideal_dcg

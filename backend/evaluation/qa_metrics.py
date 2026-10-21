"""Answer- and evidence-level metrics.

The normalisation and F1 convention match the rest of the project exactly
(``" ".join(text.strip().lower().split())`` and token-**set** F1), so numbers
produced here are comparable with the previously recorded measurements instead
of quietly using a different definition.
"""

from __future__ import annotations

from typing import Sequence


def normalize_text(text: str) -> str:
    """Project-wide normalisation: lowercase, collapse whitespace, strip."""
    return " ".join((text or "").strip().lower().split())


def exact_match(predicted: str, expected: str) -> bool:
    """Normalised exact match."""
    return normalize_text(predicted) == normalize_text(expected)


def exact_match_any(predicted: str, expected_any: Sequence[str]) -> bool:
    """Normalised exact match against any acceptable answer."""
    return any(exact_match(predicted, candidate) for candidate in expected_any)


def token_f1(predicted: str, expected: str) -> float:
    """Token-set F1 (the project's convention), in ``[0, 1]``."""
    pred_tokens = set(normalize_text(predicted).split())
    gold_tokens = set(normalize_text(expected).split())

    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0

    overlap = len(pred_tokens & gold_tokens)
    if overlap == 0:
        return 0.0

    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def token_f1_any(predicted: str, expected_any: Sequence[str]) -> float:
    """Best token-set F1 over the acceptable answers."""
    if not expected_any:
        return 0.0
    return max(token_f1(predicted, candidate) for candidate in expected_any)


def answer_accuracy(
    results: Sequence[dict],
    *,
    threshold: float = 0.5,
) -> float:
    """Fraction of *answerable* questions answered above ``threshold`` F1.

    ``results`` items need ``answerable``, ``predicted`` and ``expected``.
    Abstentions on answerable questions are failures, which is the honest
    reading: the system was asked something the corpus supports.
    """
    answerable = [r for r in results if r.get("answerable", True)]
    if not answerable:
        return 0.0
    hits = sum(
        1
        for r in answerable
        if token_f1_any(r.get("predicted", ""), r.get("expected") or [""]) >= threshold
    )
    return hits / len(answerable)


def unsupported_answer_rate(results: Sequence[dict]) -> float:
    """Fraction of *unanswerable* questions that nevertheless got an answer.

    Lower is better.  ``1.0`` when there were no unanswerable questions is
    wrong to report, so an empty population returns ``0.0`` and the caller is
    expected to record that the population was empty.
    """
    unanswerable = [r for r in results if not r.get("answerable", True)]
    if not unanswerable:
        return 0.0
    answered = sum(
        1
        for r in unanswerable
        if normalize_text(r.get("predicted", "")) and not r.get("insufficient_context", False)
    )
    return answered / len(unanswerable)


def factual_grounding_rate(results: Sequence[dict]) -> float:
    """Fraction of *answered* questions whose answer span occurs in the context."""
    answered = [r for r in results if normalize_text(r.get("predicted", ""))]
    if not answered:
        return 0.0
    return sum(1 for r in answered if r.get("factual_grounded", False)) / len(answered)


def evidence_coverage(supplied: Sequence[str], selected: Sequence[str]) -> float:
    """QA-supplied evidence / final selected evidence.

    ``1.0`` when nothing was selected at all (nothing was dropped).
    """
    total = len(set(selected))
    if total == 0:
        return 1.0
    return len(set(supplied) & set(selected)) / total


def path_agreement(source_paths: Sequence[str]) -> float:
    """``1.0`` when at least one source was supported by both retrieval paths."""
    return 1.0 if any(path == "hybrid" for path in source_paths) else 0.0


def path_counts(source_paths: Sequence[str]) -> dict[str, int]:
    """Exact partition of sources across the two retrieval paths."""
    semantic = sum(1 for p in source_paths if p == "semantic")
    structural = sum(1 for p in source_paths if p == "structural")
    hybrid = sum(1 for p in source_paths if p == "hybrid")
    return {
        "semanticSourceCount": semantic,
        "structuralSourceCount": structural,
        "hybridSourceCount": hybrid,
        "sourceCount": semantic + structural + hybrid,
    }

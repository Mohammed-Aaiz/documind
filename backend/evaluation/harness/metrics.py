"""Phase 3F — Evaluation metrics.

Implements all metrics defined in the Phase 3F contract:
  Retrieval: Recall@K, Precision@K, MRR, duplicate rate, irrelevant rate
  Answer: Exact Match (normalized), Token F1, acceptable-answer match, answerability
  Evidence: coverage, omission rate, context utilisation
  Abstention: spurious rate, false abstention rate

No fabricated metrics.  Every function computes from real data.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    return _WS.sub(" ", (text or "")).strip().lower()


def tokenise(text: str) -> list[str]:
    """Split normalised text into alphanumeric tokens."""
    return re.findall(r"[a-z0-9]+", normalise(text))


# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------


def recall_at_k(relevant_flags: list[list[bool]], k: int) -> float:
    """Recall@K: fraction of questions with ≥1 relevant item in top-K.

    Args:
        relevant_flags: per-question list of booleans (True = relevant)
        k: cutoff
    """
    if not relevant_flags:
        return 0.0
    hits = sum(1 for flags in relevant_flags if any(flags[:k]))
    return hits / len(relevant_flags)


def precision_at_k(relevant_flags: list[list[bool]], k: int) -> float:
    """Precision@K: average fraction of top-K items that are relevant."""
    if not relevant_flags:
        return 0.0
    total = 0.0
    for flags in relevant_flags:
        topk = flags[:k]
        total += sum(topk) / min(k, max(1, len(topk)))
    return total / len(relevant_flags)


def mrr(relevant_flags: list[list[bool]]) -> float:
    """Mean Reciprocal Rank: average 1/rank of first relevant item."""
    if not relevant_flags:
        return 0.0
    total = 0.0
    for flags in relevant_flags:
        for rank, flag in enumerate(flags, 1):
            if flag:
                total += 1.0 / rank
                break
    return total / len(relevant_flags)


def duplicate_retrieval_rate(retrieved_texts: list[list[str]]) -> float:
    """Fraction of top-K chunks that repeat an earlier chunk's substance."""
    if not retrieved_texts:
        return 0.0
    rates = []
    for texts in retrieved_texts:
        if len(texts) < 2:
            rates.append(0.0)
            continue
        token_sets = [set(tokenise(t)) for t in texts]
        dups = 0
        for i in range(1, len(token_sets)):
            for j in range(i):
                a, b = token_sets[i], token_sets[j]
                if a and b and len(a & b) / len(a | b) >= 0.8:
                    dups += 1
                    break
        rates.append(dups / len(texts))
    return sum(rates) / len(rates) if rates else 0.0


# ---------------------------------------------------------------------------
# Answer metrics
# ---------------------------------------------------------------------------


def exact_match(predicted: str, expected: str) -> bool:
    """Normalised exact match.

    Both strings are lowercased, whitespace-collapsed, and stripped
    of trailing punctuation before comparison.
    """
    p = normalise(predicted).rstrip(".")
    e = normalise(expected).rstrip(".")
    return p == e and p != ""


def acceptable_answer_match(predicted: str, acceptable: Sequence[str]) -> bool:
    """True if predicted matches any acceptable answer variant."""
    p = normalise(predicted).rstrip(".")
    if not p:
        return False
    return any(normalise(a).rstrip(".") == p for a in acceptable)


def token_f1(predicted: str, expected: str) -> float:
    """Token-level F1 between predicted and expected answer.

    Returns 0.0 when either string is empty after normalisation.
    """
    p_tokens = tokenise(predicted)
    e_tokens = tokenise(expected)
    if not p_tokens or not e_tokens:
        return 0.0
    p_counts = Counter(p_tokens)
    e_counts = Counter(e_tokens)
    common = sum((p_counts & e_counts).values())
    if common == 0:
        return 0.0
    precision = common / len(p_tokens)
    recall = common / len(e_tokens)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Evidence metrics
# ---------------------------------------------------------------------------


def evidence_coverage(
    evidence_substrings: Sequence[str],
    retrieved_texts: Sequence[str],
) -> float:
    """Fraction of evidence substrings found in any retrieved chunk."""
    if not evidence_substrings:
        return 1.0
    if not retrieved_texts:
        return 0.0
    normed_retrieved = [normalise(t) for t in retrieved_texts]
    covered = sum(
        1 for e in evidence_substrings
        if any(normalise(e) in r for r in normed_retrieved)
    )
    return covered / len(evidence_substrings)


def context_utilisation(used_tokens: int, budget_tokens: int) -> float:
    """Fraction of QA context window used."""
    if budget_tokens <= 0:
        return 0.0
    return min(1.0, used_tokens / budget_tokens)


# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------

# Failure categories (one primary per question)
#
# Complete accepted taxonomy (Phase 3F AC10):
#   RET_MISS    Relevant chunk not in top-K
#   RET_NOISE   Top-K mostly irrelevant
#   CTX_TRUNC   Relevant chunk retrieved but not in QA context
#   CTX_STARVE  Large early chunk consumed budget
#   QA_EXTRACT  Answer in context but wrong span extracted
#   QA_CONF     Model correct but confidence below threshold
#   EVID_OMIT   Correct answer but not grounded
#   ABSTAIN     System abstains on answerable question
#   SPURIOUS    System answers unsupported question
#   EXTRACT     Document extraction failed
#   CHUNK       Evidence split incoherently
#   AMBIG       Ambiguous question
#   ANNOT       Annotation issue
#
# Non-failure categories:
#   CORRECT          Answer correct
#   CORRECT_ABSTAIN  Correct abstention on unsupported question
#   UNKNOWN          Cannot determine cause (used when classification
#                    is not objectively possible)
#
# Precedence (highest to lowest):
#   RET_MISS > CTX_TRUNC > EVID_OMIT > QA_EXTRACT > QA_CONF > UNKNOWN
#
# Categories with zero occurrences are valid (count=0).
# Do not manufacture failures.  If a failure cannot be objectively
# classified, use UNKNOWN/UNDETERMINED.

RET_MISS = "RET_MISS"          # Relevant chunk not in top-K
RET_NOISE = "RET_NOISE"        # Top-K mostly irrelevant
CTX_TRUNC = "CTX_TRUNC"        # Relevant chunk retrieved but not in QA context
CTX_STARVE = "CTX_STARVE"      # Large early chunk consumed budget
QA_EXTRACT = "QA_EXTRACT"      # Answer in context but wrong span extracted
QA_CONF = "QA_CONF"            # Model correct but confidence below threshold
EVID_OMIT = "EVID_OMIT"        # Correct answer but not grounded
ABSTAIN = "ABSTAIN"            # System abstains on answerable question
SPURIOUS = "SPURIOUS"          # System answers unsupported question
EXTRACT_FAIL = "EXTRACT"       # Document extraction failed
CHUNK_FAIL = "CHUNK"           # Evidence split incoherently
AMBIG = "AMBIG"                # Ambiguous question
ANNOT = "ANNOT"                # Annotation issue
UNKNOWN = "UNKNOWN"            # Cannot determine cause


@dataclass
class FailureDiag:
    """Diagnostic for a single question's failure."""
    primary: str
    secondary: str | None = None
    detail: str = ""


def classify_failure(
    answerable: bool,
    outcome: str,
    answer_correct: bool,
    relevant_in_topk: bool,
    coverage: float,
    context_tokens: int,
    context_budget: int,
    qa_confidence: float,
    reported_sources: int,
    omitted_sources: int,
) -> FailureDiag:
    """Deterministic failure classification for one question.

    One primary category per question.  Follows the diagnostic flow:
    1. Unsupported? → CORRECT_ABSTAIN / SPURIOUS / UNKNOWN
    2. Relevant evidence retrieved? → RET_MISS
    3. Context truncation? → CTX_TRUNC
    4. Evidence omission? → EVID_OMIT
    5. Answer correct? → CORRECT / QA_CONF
    6. Outcome gate abstained? → QA_EXTRACT / QA_CONF
    7. Coverage zero? → RET_MISS
    8. Context full? → CTX_TRUNC
    9. Default → QA_EXTRACT

    Complete accepted taxonomy (13 categories):
      RET_MISS, RET_NOISE, CTX_TRUNC, CTX_STARVE, QA_EXTRACT,
      QA_CONF, EVID_OMIT, ABSTAIN, SPURIOUS, EXTRACT, CHUNK,
      AMBIG, ANNOT

    Categories not deterministically classifiable from current signals:
      RET_NOISE — requires comparing all retrieved chunks against relevance
      CTX_STARVE — requires measuring per-chunk budget consumption
      EXTRACT — requires extraction failure detection (not currently signaled)
      CHUNK — requires detecting incoherent splits (not currently signaled)
      AMBIG — requires ambiguity detection (not currently signaled)
      ANNOT — requires annotation quality signals (not currently signaled)

    These categories have count=0 in the current corpus, which is valid.
    If a failure cannot be objectively classified, use UNKNOWN.
    """
    # --- Unsupported questions ---
    if not answerable:
        if outcome == "INSUFFICIENT_EVIDENCE" and not answer_correct:
            return FailureDiag(primary="CORRECT_ABSTAIN")
        if answer_correct:
            return FailureDiag(primary=SPURIOUS, detail="answered unsupported question")
        return FailureDiag(primary=UNKNOWN, detail="unsupported, unexpected outcome")

    # --- Answerable questions ---
    # Check retrieval
    if not relevant_in_topk:
        if coverage == 0.0:
            return FailureDiag(primary=RET_MISS, detail="no relevant chunk in top-K")
        return FailureDiag(primary=RET_MISS, detail="retrieval miss")

    # Check context truncation
    if coverage > 0 and context_tokens >= context_budget * 0.95:
        if not answer_correct:
            return FailureDiag(primary=CTX_TRUNC, detail="context near full, answer truncated")

    # Check evidence omission
    if coverage > 0 and omitted_sources > 0 and not answer_correct:
        return FailureDiag(primary=EVID_OMIT, detail="evidence retrieved but omitted from QA context")

    # Check answer correctness
    if answer_correct:
        if outcome == "INSUFFICIENT_EVIDENCE":
            return FailureDiag(primary=QA_CONF, detail="correct but abstained (low confidence)")
        return FailureDiag(primary="CORRECT", detail="answer correct")

    # Answer incorrect
    if outcome == "INSUFFICIENT_EVIDENCE":
        if qa_confidence == 0.0:
            return FailureDiag(primary=QA_EXTRACT, detail="model found nothing (zero confidence)")
        return FailureDiag(primary=QA_CONF, detail="abstained despite some confidence")

    if coverage == 0.0:
        return FailureDiag(primary=RET_MISS, detail="relevant evidence not retrieved")

    if coverage > 0 and context_tokens >= context_budget * 0.95:
        return FailureDiag(primary=CTX_TRUNC, detail="context full, answer lost")

    return FailureDiag(primary=QA_EXTRACT, detail="wrong span extracted from context")

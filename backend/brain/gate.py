"""
Evidence gate for the DocuMind Brain.

Decides whether the Brain is allowed to return an answer.
Uses the existing EvidenceBundle and Outcome contract.

The gate does NOT invent new thresholds.  It encodes the evidence
semantics already established by the project:
  • No evidence → INSUFFICIENT_EVIDENCE
  • Empty answer → INSUFFICIENT_EVIDENCE
  • Zero-confidence span (the model produced no answer it can score)
    → INSUFFICIENT_EVIDENCE
  • Grounded answer with strong signals → SUCCESS
  • Otherwise, an answer that is present but weakly supported → PARTIAL
  • Model / capability unavailable → UNAVAILABLE
  • Execution error → FAILED

The SUCCESS thresholds are the ones the project already used before the Brain
existed (``chat.rag.rag_answer``): an answer is only treated as strongly
supported when the QA model is at least 0.30 confident AND the best retrieved
chunk scores at least 0.50.  Reusing them keeps the outcome matrix a faithful
re-encoding of established behaviour rather than a new, invented policy.

Why abstention keys on zero confidence
--------------------------------------
Phase 3D correction: the previous implementation returned PARTIAL for *every*
case with a non-empty span, so a question the corpus cannot support was reported
as a partially-supported answer (measured: abstention on unsupported questions
0/3, spurious answers 3/3).

A broader rule — "ungrounded span with weak signals → INSUFFICIENT_EVIDENCE" —
was implemented first and then rejected on measured evidence: on the Phase 3D
corpus it abstained on answerable questions that the system had previously
answered *correctly* (``answerability`` fell 0.769 → 0.718 in the candidate arm).
The underlying reason is that QA confidence is not calibrated on this corpus:
answers the grader marks correct occur at scores as low as 0.0001, interleaved
with unsupported questions and with wrong answers at every level.  Therefore no
positive threshold can separate supported from unsupported without discarding
correct answers, and inventing one would be threshold-fitting to the corpus.

What is left is the only boundary that is not a tuned parameter: a softmax
product of exactly 0 means the model assigned no probability to any span, i.e.
it found nothing it can answer.  Measured on the Phase 3D corpus this abstains
on 3/3 unsupported questions and on 0/3 of the questions that previously had
correct answers.  It is deliberately narrow: it makes unsupported questions
honest without pretending the confidence signal is more informative than it is.
"""

from brain.types import (
    ExecutionContext,
    EvidenceBundle,
    ErrorRecord,
)
from outcomes import Outcome

# --- Evidence policy thresholds (provenance: legacy chat.rag.rag_answer) ---
QA_CONFIDENCE_STRONG = 0.30
"""QA confidence at or above which an answer counts as strongly supported."""

RETRIEVAL_STRONG = 0.50
"""Best-chunk similarity at or above which retrieval counts as strong."""

QA_CONFIDENCE_NONE = 0.0
"""At or below this the QA model assigned no probability to any span.

Not a tuned parameter: it is the minimum of the score range, and it is the one
boundary that does not discard correct low-confidence answers (see module
docstring for the measured justification).
"""


def evaluate(ctx: ExecutionContext) -> Outcome:
    """Classify the final outcome from the execution context.

    Examines errors, evidence, and QA results to produce an honest
    outcome classification.  Abstention (INSUFFICIENT_EVIDENCE) is a
    correct, successful outcome — not a failure.
    """
    # --- Priority 1: Errors ---
    if ctx.errors:
        return _classify_error(ctx.errors)

    # --- Priority 2: Evidence evaluation ---
    evidence = ctx.evidence
    return _classify_evidence(evidence)


def _classify_error(errors: list[ErrorRecord]) -> Outcome:
    """Map the most significant error to an Outcome."""
    # Sort by priority: capability_unavailable > service_failure > unexpected
    _PRIORITY = {
        "capability_unavailable": 0,
        "model_unavailable": 1,
        "service_failure": 2,
        "unexpected_error": 3,
        "invalid_request": 4,
    }

    most_significant = min(
        errors,
        key=lambda e: _PRIORITY.get(e.category, 99),
    )

    if most_significant.category in ("capability_unavailable", "model_unavailable"):
        return Outcome.UNAVAILABLE

    return Outcome.FAILED


def _classify_evidence(evidence: EvidenceBundle) -> Outcome:
    """Classify outcome based on evidence signals."""
    # --- No evidence at all ---
    if not evidence.sources:
        return Outcome.INSUFFICIENT_EVIDENCE

    # --- No QA result (search-only or retrieval-only) ---
    if evidence.qa_result is None:
        # Retrieval-only intent: sources found = success
        return Outcome.SUCCESS

    # --- QA produced an answer ---
    answer = evidence.qa_result.answer
    score = evidence.qa_result.score
    grounded = evidence.factual_grounded

    # Empty answer → insufficient
    if not answer.strip():
        return Outcome.INSUFFICIENT_EVIDENCE

    # --- The model produced no answer it can score ------------------------
    # A zero-probability span is the extractive model's de-facto "no answer":
    # it found nothing in the supplied context it is willing to stand behind.
    # This is the only abstention boundary that does not cost correct answers
    # (see the module docstring), so it is applied before any other rule.
    if score <= QA_CONFIDENCE_NONE:
        return Outcome.INSUFFICIENT_EVIDENCE

    # Best retrieval score over the chunks that were actually supplied to QA.
    best_score = (
        max(evidence.retrieval_scores)
        if evidence.retrieval_scores
        else 0.0
    )

    # --- Grounded answer with strong signals ---
    if grounded and score >= QA_CONFIDENCE_STRONG and best_score >= RETRIEVAL_STRONG:
        return Outcome.SUCCESS

    # --- An answer exists but is weakly supported ---
    # Kept as PARTIAL rather than flattened into abstention: the span is
    # present in the evidence, and the reported confidence marks how weak the
    # support is.  Silencing it would discard answers the system does have
    # evidence for.
    return Outcome.PARTIAL

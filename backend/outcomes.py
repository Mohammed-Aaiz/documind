"""
Application outcome types for DocuMind.

A small, reusable representation for classifying the result of any
application operation — especially AI/RAG responses.  The future
DocuMind Brain will consume these outcomes to make routing decisions.

Every important AI result must eventually be traceable to one of these
outcomes.  No fabricated success.
"""

from enum import Enum


class Outcome(str, Enum):
    """Classify the result of an application operation."""

    SUCCESS = "SUCCESS"
    """Operation completed successfully with full results."""

    PARTIAL = "PARTIAL"
    """Operation completed but returned less than requested
    (e.g., fewer sources than top_k requested)."""

    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    """Operation could not produce a meaningful result because the
    available evidence was not strong enough to support an answer.
    This is distinct from failure — the system correctly determined
    that it does not have enough information."""

    UNAVAILABLE = "UNAVAILABLE"
    """The capability required for this operation is not available
    (e.g., QA model not loaded, embedding model missing)."""

    FAILED = "FAILED"
    """An unexpected error occurred during the operation."""


def outcome_from_rag(
    *,
    answer: str,
    confidence: float,
    best_retrieval_score: float,
    insufficient_context: bool,
    is_model_available: bool,
) -> Outcome:
    """Derive an Outcome from the RAG pipeline results.

    This encodes the existing answerability logic without changing
    thresholds — it is a classification layer on top of the current
    behaviour.
    """
    if not is_model_available:
        return Outcome.UNAVAILABLE

    if insufficient_context:
        return Outcome.INSUFFICIENT_EVIDENCE

    if not answer.strip():
        return Outcome.INSUFFICIENT_EVIDENCE

    # If we got this far, we have a real answer grounded in evidence.
    # Distinguish full success from partial (low confidence but still
    # grounded).
    if confidence >= 0.30 and best_retrieval_score >= 0.50:
        return Outcome.SUCCESS

    return Outcome.PARTIAL

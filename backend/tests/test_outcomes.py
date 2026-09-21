"""Tests for the application outcome types.

Verifies that:
  • Outcome enum has all required values
  • outcome_from_rag classifies results correctly
  • No fabricated outcomes — every classification is grounded in real signals
"""

import pytest
from outcomes import Outcome, outcome_from_rag


class TestOutcomeEnum:
    """Verify the Outcome enum is complete."""

    def test_all_outcomes_exist(self):
        assert Outcome.SUCCESS.value == "SUCCESS"
        assert Outcome.PARTIAL.value == "PARTIAL"
        assert Outcome.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"
        assert Outcome.UNAVAILABLE.value == "UNAVAILABLE"
        assert Outcome.FAILED.value == "FAILED"

    def test_outcome_is_string(self):
        """Outcome values must be JSON-serialisable strings."""
        assert isinstance(Outcome.SUCCESS, str)
        assert Outcome.SUCCESS.value == "SUCCESS"


class TestOutcomeFromRag:
    """Verify RAG outcome classification logic."""

    def test_unavailable_model(self):
        """QA model not loaded → UNAVAILABLE."""
        result = outcome_from_rag(
            answer="test answer",
            confidence=0.8,
            best_retrieval_score=0.7,
            insufficient_context=False,
            is_model_available=False,
        )
        assert result == Outcome.UNAVAILABLE

    def test_insufficient_context(self):
        """Insufficient context → INSUFFICIENT_EVIDENCE."""
        result = outcome_from_rag(
            answer="",
            confidence=0.0,
            best_retrieval_score=0.1,
            insufficient_context=True,
            is_model_available=True,
        )
        assert result == Outcome.INSUFFICIENT_EVIDENCE

    def test_empty_answer_insufficient(self):
        """Empty answer (even without flag) → INSUFFICIENT_EVIDENCE."""
        result = outcome_from_rag(
            answer="",
            confidence=0.0,
            best_retrieval_score=0.6,
            insufficient_context=False,
            is_model_available=True,
        )
        assert result == Outcome.INSUFFICIENT_EVIDENCE

    def test_success_with_good_signals(self):
        """High QA confidence + high retrieval → SUCCESS."""
        result = outcome_from_rag(
            answer="Darwin published in 1859",
            confidence=0.75,
            best_retrieval_score=0.65,
            insufficient_context=False,
            is_model_available=True,
        )
        assert result == Outcome.SUCCESS

    def test_partial_with_low_confidence(self):
        """Low confidence but non-empty answer → PARTIAL."""
        result = outcome_from_rag(
            answer="some answer",
            confidence=0.15,
            best_retrieval_score=0.55,
            insufficient_context=False,
            is_model_available=True,
        )
        assert result == Outcome.PARTIAL

    def test_partial_with_low_retrieval(self):
        """Good QA confidence but low retrieval → PARTIAL."""
        result = outcome_from_rag(
            answer="some answer",
            confidence=0.50,
            best_retrieval_score=0.30,
            insufficient_context=False,
            is_model_available=True,
        )
        assert result == Outcome.PARTIAL

    def test_success_boundary_confidence(self):
        """Confidence exactly 0.30 with good retrieval → SUCCESS."""
        result = outcome_from_rag(
            answer="answer text",
            confidence=0.30,
            best_retrieval_score=0.50,
            insufficient_context=False,
            is_model_available=True,
        )
        assert result == Outcome.SUCCESS

    def test_partial_below_confidence_threshold(self):
        """Confidence 0.29 with good retrieval → PARTIAL."""
        result = outcome_from_rag(
            answer="answer text",
            confidence=0.29,
            best_retrieval_score=0.50,
            insufficient_context=False,
            is_model_available=True,
        )
        assert result == Outcome.PARTIAL

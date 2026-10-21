"""Tests for the evaluation metric library and the runner's honesty rules.

Metric code that nothing checks is exactly where a fabricated number would go
unnoticed, so the retrieval metrics, the answer metrics and the runner's
"refuse to invent" behaviour are all pinned here.
"""

from __future__ import annotations

import math

import pytest

from evaluation import qa_metrics, retrieval_metrics
from evaluation.runner import reranker_available, run_baseline
from evaluation.schemas import Baseline, EvalQuestion, QuestionCategory

RETRIEVED = ["c1", "c2", "c3", "c4", "c5"]
GOLD = ["c2", "c4"]


# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------


class TestRecall:
    def test_full_recall(self):
        assert retrieval_metrics.recall_at_k(RETRIEVED, GOLD, 5) == 1.0

    def test_partial_recall_is_capped_by_k(self):
        assert retrieval_metrics.recall_at_k(RETRIEVED, GOLD, 2) == 0.5

    def test_no_gold_means_nothing_to_recall(self):
        assert retrieval_metrics.recall_at_k(RETRIEVED, [], 5) == 0.0

    def test_missing_gold_is_zero(self):
        assert retrieval_metrics.recall_at_k(["x", "y"], GOLD, 5) == 0.0

    def test_duplicates_do_not_inflate_recall(self):
        assert retrieval_metrics.recall_at_k(["c2", "c2", "c2"], GOLD, 3) == 0.5


class TestPrecision:
    def test_precision_over_five(self):
        assert retrieval_metrics.precision_at_k(RETRIEVED, GOLD, 5) == pytest.approx(0.4)

    def test_precision_over_two(self):
        assert retrieval_metrics.precision_at_k(RETRIEVED, GOLD, 2) == pytest.approx(0.5)

    def test_empty_retrieval_is_zero(self):
        assert retrieval_metrics.precision_at_k([], GOLD, 5) == 0.0


class TestReciprocalRank:
    def test_first_gold_at_rank_two(self):
        assert retrieval_metrics.reciprocal_rank(RETRIEVED, GOLD) == pytest.approx(0.5)

    def test_first_gold_at_rank_one(self):
        assert retrieval_metrics.reciprocal_rank(GOLD, GOLD) == pytest.approx(1.0)

    def test_no_gold_found(self):
        assert retrieval_metrics.reciprocal_rank(["x"], GOLD) == 0.0

    def test_mean_reciprocal_rank(self):
        value = retrieval_metrics.mrr([["c2"], ["x"]], [["c2"], ["c2"]])
        assert value == pytest.approx(0.5)


class TestNdcg:
    def test_matches_hand_computed_value(self):
        dcg = 1 / math.log2(3) + 1 / math.log2(5)
        ideal = 1 / math.log2(2) + 1 / math.log2(3)
        assert retrieval_metrics.ndcg_at_k(RETRIEVED, GOLD, 5) == pytest.approx(dcg / ideal)

    def test_perfect_ranking_is_one(self):
        assert retrieval_metrics.ndcg_at_k(GOLD, GOLD, 2) == pytest.approx(1.0)

    def test_no_relevant_document_is_zero(self):
        assert retrieval_metrics.ndcg_at_k(["x", "y"], GOLD, 5) == 0.0

    def test_no_gold_is_zero(self):
        assert retrieval_metrics.ndcg_at_k(RETRIEVED, [], 5) == 0.0


# ---------------------------------------------------------------------------
# Answer metrics
# ---------------------------------------------------------------------------


class TestAnswerMetrics:
    def test_exact_match_normalises_case_and_whitespace(self):
        assert qa_metrics.exact_match("  Hello   WORLD ", "hello world") is True

    def test_exact_match_rejects_different_text(self):
        assert qa_metrics.exact_match("hello", "hello there") is False

    def test_exact_match_any_accepts_alternatives(self):
        assert qa_metrics.exact_match_any("142.6 million", ["142.6", "142.6 million"])

    def test_token_f1_is_set_based_and_order_independent(self):
        assert qa_metrics.token_f1("Darwin 1859", "1859 Darwin") == pytest.approx(1.0)

    def test_token_f1_partial_overlap(self):
        assert qa_metrics.token_f1("a b", "a c") == pytest.approx(0.5)

    def test_token_f1_both_empty_is_one(self):
        assert qa_metrics.token_f1("", "") == 1.0

    def test_token_f1_one_empty_is_zero(self):
        assert qa_metrics.token_f1("a", "") == 0.0

    def test_token_f1_any_takes_the_best_candidate(self):
        assert qa_metrics.token_f1_any("142.6", ["142.6", "unrelated"]) == pytest.approx(1.0)


class TestPopulationMetrics:
    def test_unsupported_answer_rate_counts_answered_unanswerables(self):
        results = [
            {"answerable": False, "predicted": "Paris", "insufficient_context": False},
            {"answerable": False, "predicted": "", "insufficient_context": True},
        ]
        assert qa_metrics.unsupported_answer_rate(results) == pytest.approx(0.5)

    def test_unsupported_answer_rate_ignores_answerable_questions(self):
        results = [{"answerable": True, "predicted": "x", "insufficient_context": False}]
        assert qa_metrics.unsupported_answer_rate(results) == 0.0

    def test_factual_grounding_rate_counts_only_answered_questions(self):
        results = [
            {"predicted": "a", "factual_grounded": True},
            {"predicted": "b", "factual_grounded": False},
            {"predicted": "", "factual_grounded": False},
        ]
        assert qa_metrics.factual_grounding_rate(results) == pytest.approx(0.5)

    def test_answer_accuracy_counts_abstention_on_answerable_as_failure(self):
        results = [
            {"answerable": True, "predicted": "darwin 1859", "expected": ["Darwin 1859"]},
            {"answerable": True, "predicted": "", "expected": ["Darwin 1859"]},
        ]
        assert qa_metrics.answer_accuracy(results) == pytest.approx(0.5)


class TestEvidenceMetrics:
    def test_evidence_coverage_is_supplied_over_selected(self):
        assert qa_metrics.evidence_coverage(["a", "b"], ["a", "b", "c"]) == pytest.approx(2 / 3)

    def test_evidence_coverage_of_nothing_selected_is_one(self):
        assert qa_metrics.evidence_coverage([], []) == 1.0

    def test_path_agreement_true_when_any_hybrid_source(self):
        assert qa_metrics.path_agreement(["semantic", "hybrid"]) == 1.0

    def test_path_agreement_false_without_a_hybrid_source(self):
        assert qa_metrics.path_agreement(["semantic", "structural"]) == 0.0

    def test_path_counts_partition_the_sources_exactly(self):
        counts = qa_metrics.path_counts(["semantic", "hybrid", "structural"])
        assert counts == {
            "semanticSourceCount": 1,
            "structuralSourceCount": 1,
            "hybridSourceCount": 1,
            "sourceCount": 3,
        }


# ---------------------------------------------------------------------------
# Runner honesty
# ---------------------------------------------------------------------------


def _question() -> EvalQuestion:
    return EvalQuestion(
        question_id="q1",
        question="Reference Manual curing time?",
        category=QuestionCategory.SECTION_DEPENDENT,
        document_id="doc-1",
        gold_answers=("six hours",),
        gold_chunk_ids=("c1",),
    )


class TestRunnerDoesNotFabricate:
    def test_no_reranker_exists_in_this_project(self):
        available, reason = reranker_available()
        assert available is False
        assert RERANKER_PLACEHOLDER_MARKER in reason or "reranker" in reason

    async def test_b2_is_reported_as_not_measured(self):
        async def _retrieve(_question):
            return ["c1"]

        async def _answer(_question, _ids):
            return {"answer": "six hours"}

        report = await run_baseline(
            Baseline.B2_VECTOR_RERANK, [_question()], _retrieve, _answer
        )

        assert report.not_measured, "B2 must be declared not measured, not guessed"
        assert report.metrics == {}
        assert report.results == []

    async def test_measured_run_records_real_values(self):
        async def _retrieve(_question):
            return ["c1", "c2"]

        async def _answer(_question, _ids):
            return {
                "answer": "six hours",
                "confidence": 0.9,
                "insufficient_context": False,
                "factual_grounded": True,
                "supplied_chunk_ids": ["c1"],
                "retrieval_paths": ["hybrid", "structural"],
                "structural_hops": [0, 1],
            }

        report = await run_baseline(
            Baseline.B4_DUAL_PATH, [_question()], _retrieve, _answer
        )

        assert report.question_count == 1
        assert report.metrics["recall@5"] == pytest.approx(1.0)
        assert report.metrics["precision@5"] == pytest.approx(0.5)
        assert report.metrics["exact_match"] == pytest.approx(1.0)
        assert report.metrics["evidence_coverage"] == pytest.approx(0.5)
        assert report.metrics["path_agreement"] == pytest.approx(1.0)
        assert report.latency_ms["total_mean"] >= 0.0
        assert report.results[0].detail["retrieval_paths"] == ["hybrid", "structural"]
        assert report.by_category["section_dependent"]["recall@5"] == pytest.approx(1.0)


# Marker used to keep the reranker assertion readable without pinning prose.
RERANKER_PLACEHOLDER_MARKER = "no reranker module"

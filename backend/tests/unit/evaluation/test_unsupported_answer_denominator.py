"""Regression tests for the ``unsupported_answer`` population denominator.

``unsupported_answer`` (``unsupported_answer_rate``) is defined over the
**unanswerable-question** population only.  A previous revision averaged the
per-question 0/1 indicator over *every* question, which reported the fraction of
all questions that failed rather than the unsupported-answer rate — for example
phase3d reported 3/42 = 0.0714 where the correct value is 3/3 = 1.0.

These tests pin the population semantics, mirroring
:func:`evaluation.qa_metrics.unsupported_answer_rate`, and the rule that an empty
unanswerable population yields ``None`` (unavailable) rather than ``0.0``.
"""

from __future__ import annotations

import pytest

from evaluation.runner import run_baseline
from evaluation.schemas import Baseline, EvalQuestion, QuestionCategory

#: Question ids the fake pipeline answers; everything else abstains.
ANSWERED_IDS: set[str] = set()


def _question(qid: str, answerable: bool) -> EvalQuestion:
    return EvalQuestion(
        question_id=qid,
        question=f"Q {qid}",
        category=QuestionCategory.DIRECT,
        answerable=answerable,
    )


async def _retrieve(_question: EvalQuestion) -> list[str]:
    return []


async def _answer(question: EvalQuestion, _chunk_ids) -> dict:
    answered = question.question_id in ANSWERED_IDS
    return {
        "answer": "a produced answer" if answered else "",
        "confidence": 0.5,
        "insufficient_context": not answered,
        "factual_grounded": answered,
        "supplied_chunk_ids": [],
    }


async def _measure(questions, answered_ids: set[str]):
    global ANSWERED_IDS
    ANSWERED_IDS = set(answered_ids)
    return await run_baseline(Baseline.B4_DUAL_PATH, questions, _retrieve, _answer)


def _unanswerable(n: int) -> list[EvalQuestion]:
    return [_question(f"u{i}", False) for i in range(n)]


def _answerable(n: int) -> list[EvalQuestion]:
    return [_question(f"a{i}", True) for i in range(n)]


class TestUnsupportedAnswerDenominator:
    async def test_case_a_all_unanswerable_answered_is_one(self):
        """10 questions, 2 unanswerable, both answered → 1.0, not 2/10 = 0.2."""
        questions = _answerable(8) + _unanswerable(2)
        report = await _measure(questions, {"u0", "u1"})
        assert report.metrics["unsupported_answer"] == pytest.approx(1.0)

    async def test_case_b_no_unanswerable_answered_is_zero(self):
        """2 unanswerable, both abstain → 0.0."""
        questions = _answerable(8) + _unanswerable(2)
        report = await _measure(questions, set())
        assert report.metrics["unsupported_answer"] == pytest.approx(0.0)

    async def test_case_c_one_of_four_unanswerable_answered_is_quarter(self):
        """4 unanswerable, 1 answered → 0.25."""
        questions = _answerable(6) + _unanswerable(4)
        report = await _measure(questions, {"u2"})
        assert report.metrics["unsupported_answer"] == pytest.approx(0.25)

    async def test_case_d_zero_unanswerable_is_none_with_reason(self):
        """No unanswerable questions → ``None`` (unavailable), never ``0.0``."""
        report = await _measure(_answerable(5), {"a0", "a1"})
        assert report.metrics["unsupported_answer"] is None
        assert "unsupported_answer" in report.not_measured
        assert report.not_measured["unsupported_answer"]

    async def test_case_e_answerable_questions_do_not_change_denominator(self):
        """Adding answerable questions must not move the unsupported-answer rate."""
        unanswerable = _unanswerable(2)
        small = await _measure(unanswerable, {"u0"})
        large = await _measure(_answerable(30) + unanswerable, {"u0"})
        assert small.metrics["unsupported_answer"] == pytest.approx(0.5)
        assert large.metrics["unsupported_answer"] == pytest.approx(0.5)

    async def test_by_category_uses_the_unanswerable_denominator(self):
        """Category aggregation follows the same population rule."""
        questions = _answerable(3) + _unanswerable(2)
        report = await _measure(questions, {"u0", "u1"})
        assert report.by_category["direct_textual"]["unsupported_answer"] == pytest.approx(1.0)

    async def test_answerable_only_category_is_none(self):
        """A category with no unanswerable questions reports ``None``."""
        report = await _measure(_answerable(4), set())
        assert report.by_category["direct_textual"]["unsupported_answer"] is None

    async def test_matches_qa_metrics_population_semantics(self):
        """The runner's value agrees with the documented population function."""
        from evaluation import qa_metrics

        questions = _answerable(4) + _unanswerable(4)
        report = await _measure(questions, {"u0", "u3"})
        rows = [
            {
                "answerable": r.answerable,
                "predicted": r.detail["predicted"],
                "insufficient_context": r.detail["insufficient_context"],
            }
            for r in report.results
        ]
        expected = qa_metrics.unsupported_answer_rate(rows)
        assert report.metrics["unsupported_answer"] == pytest.approx(expected)
        assert expected == pytest.approx(0.5)

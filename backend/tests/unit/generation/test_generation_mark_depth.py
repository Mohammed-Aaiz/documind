"""Measured answerability policy and mark-aware depth.

Two behaviours are pinned here, both changed on 2026-10-17 as a result of the
frozen-benchmark diagnosis:

* the answerability gate no longer refuses a question merely because its
  wording does not repeat the evidence's vocabulary (that rule rejected 72 of
  140 answerable P3 rows);
* 10/15-mark answers are deeper than 5-mark answers because they add further
  *evidence sentences*, never because the model was asked to write more.
"""

import pytest

from generation import service
from generation.planning import AnswerFormat, compose_answer, plan_support_points
from generation.types import EvidenceBlock
from generation.verification import answerability


LIDAR = (
    "The sensor array is recalibrated every 90 days. "
    "The lidar array requires calibration every 30 days. "
    "The power rail operates at 12 volts. "
    "Lidar calibration records are stored in the maintenance log for five years. "
    "The lidar array is inspected monthly by the field team. "
    "Lidar calibration uses the manufacturer reference target. "
    "A failed lidar check requires a full recalibration."
)


def _block(content: str, index: int = 1) -> EvidenceBlock:
    return EvidenceBlock(index=index, content=content, document_name="manual.pdf")


# ---------------------------------------------------------------------------
# Answerability policy
# ---------------------------------------------------------------------------

class TestAnswerabilityPolicy:
    def test_generic_question_wording_does_not_block_a_quantity_question(self):
        """'What was the reported monetary value?' must not be rejected."""
        decision = answerability(
            "What was the reported monetary value?",
            "Net income attributable to shareholders was $142.6 million.",
        )
        assert decision.allowed is True

    def test_missing_one_distinctive_term_is_tolerated(self):
        decision = answerability(
            "What is the maximum number of items per request?",
            "Maximum of 200 items per request",
        )
        assert decision.allowed is True
        assert decision.missing == ("number",)

    def test_missing_two_distinctive_terms_is_refused(self):
        decision = answerability(
            "What machine learning framework is used for embeddings?",
            "The system uses sentence transformer models for 768-dimensional vectors.",
        )
        assert decision.allowed is False
        assert "framework" in decision.missing
        assert "machine" in decision.missing or "learning" in decision.missing

    def test_quantity_question_is_answerable_when_evidence_has_a_number(self):
        decision = answerability(
            "How much is the IPO proceeds?",
            "The company went public on NASDAQ in 2006 and raised $185 million.",
        )
        assert decision.allowed is True

    def test_question_without_distinctive_terms_is_allowed(self):
        decision = answerability("What does the document say?", "Anything at all.")
        assert decision.allowed is True

    def test_answer_shape_words_are_not_treated_as_topic_terms(self):
        """'compare', 'steps' and 'procedure' describe the answer, not the topic."""
        decision = answerability(
            "What are the steps of the calibration procedure?",
            "Calibration follows four steps: park the robot, record the sweep, write offsets, sign off.",
        )
        assert decision.allowed is True
        decision = answerability(
            "Compare manual and automated calibration.",
            "Manual calibration takes two hours; automated calibration finishes in twelve minutes.",
        )
        assert decision.allowed is True

    def test_section_question_is_not_blocked_by_structural_wording(self):
        """'Describe the content of the ... section' names structure, not topic.

        The frozen benchmark's section questions were all refused because
        "content" and "section" are absent from a paragraph that *is* the
        section's content; the gold answer was inside that paragraph.
        """
        decision = answerability(
            "Describe the content of the Transformation Era (2011-2020) section?",
            "The Transformation Era began in 2015 with the launch of Apex Cloud, "
            "a SaaS version of the enterprise suite.",
        )
        assert decision.allowed is True

    def test_boundary_question_is_not_blocked_by_question_framing(self):
        """'near the boundary between X and Y' is a location cue, not a topic."""
        decision = answerability(
            "What value is mentioned near the boundary between Authentication and "
            "Rate Limits?",
            "Authentication Rate Limits: 1,000 requests per minute for the "
            "Enterprise tier.",
        )
        assert decision.allowed is True

    def test_ordinal_stays_a_topic_term(self):
        """'first' in 'the first version' is the question, not framing.

        Treating ordinals as structural made this unanswerable row pass the gate
        and answer with the document's "as of" date instead of a release date.
        """
        decision = answerability(
            "When was the first version released?",
            "The latest stable version as of September 2025 is Docker Engine 27.3.1.",
        )
        assert decision.allowed is False

    def test_gate_refuses_before_the_model_is_called(self, monkeypatch):
        calls = []
        monkeypatch.setattr(service, "generate", lambda *a, **k: calls.append(1))
        result = service.answer_generatively(
            "What is the battery chemistry?",
            [_block("The lidar array requires calibration every 30 days.")],
        )
        assert calls == []
        assert result.abstained is True


# ---------------------------------------------------------------------------
# Elaboration planning
# ---------------------------------------------------------------------------

class TestShortAnswersAreClaims:
    """A one-word answer is a claim and must be verifiable.

    The benchmark's gold answers include ``2010``, ``45`` and ``Endpoints``.
    Requiring two content words withheld them as "too short to verify".
    """

    def test_single_number_answer_is_supported(self):
        from generation.verification import check_claim

        block = EvidenceBlock(index=1, content="The company was founded in 2010 in Boston.")
        check = check_claim("2010", [block])
        assert check.supported is True

    def test_single_word_answer_is_supported(self):
        from generation.verification import check_claim

        block = EvidenceBlock(index=1, content="Endpoints are documented in the API guide.")
        check = check_claim("Endpoints", [block])
        assert check.supported is True

    def test_single_number_absent_from_evidence_is_still_rejected(self):
        from generation.verification import check_claim

        block = EvidenceBlock(index=1, content="The company was founded in 2010 in Boston.")
        check = check_claim("2014", [block])
        assert check.supported is False


class TestPlanSupportPoints:
    def test_five_marks_adds_nothing(self):
        assert plan_support_points("How often is the lidar calibrated?", [_block(LIDAR)], 5) == []

    def test_ten_marks_adds_supporting_points(self):
        points = plan_support_points(
            "How often is the lidar calibrated?", [_block(LIDAR)], 10, answer="every 30 days"
        )
        assert 1 <= len(points) <= 3

    def test_fifteen_marks_covers_more_than_ten(self):
        ten = plan_support_points(
            "How is the lidar maintained?", [_block(LIDAR)], 10, answer="every 30 days"
        )
        fifteen = plan_support_points(
            "How is the lidar maintained?", [_block(LIDAR)], 15, answer="every 30 days"
        )
        assert len(fifteen) > len(ten)

    def test_points_never_restate_the_direct_answer(self):
        points = plan_support_points(
            "How often is the lidar calibrated?",
            [_block(LIDAR)],
            15,
            answer="every 30 days",
        )
        assert all("every 30 days" not in point.text.lower() for point in points)

    def test_irrelevant_evidence_is_not_padded_in(self):
        blocks = [
            _block(LIDAR, index=1),
            _block("The office cafeteria serves lunch between noon and two.", index=2),
        ]
        points = plan_support_points("How often is the lidar calibrated?", blocks, 15)
        assert all("cafeteria" not in point.text for point in points)

    def test_wrong_entity_numeric_sentence_is_excluded(self):
        """The sensor array's 90 days must not be added to a lidar answer."""
        points = plan_support_points(
            "How often does the lidar array require calibration?",
            [_block(LIDAR)],
            15,
            answer="every 30 days",
        )
        assert all("sensor array" not in point.text.lower() for point in points)

    def test_points_carry_the_index_of_the_block_they_came_from(self):
        blocks = [
            _block("Unrelated first block about the office cafeteria lunch menu.", index=1),
            _block("The lidar array requires calibration every 30 days.", index=2),
        ]
        points = plan_support_points("How often is the lidar calibrated?", blocks, 15)
        assert points
        assert all(point.citation == 2 for point in points)


class TestComposeAnswer:
    def test_five_marks_is_the_direct_answer_only(self):
        points = plan_support_points("How often is the lidar calibrated?", [_block(LIDAR)], 5)
        assert compose_answer("every 30 days", points, 5) == "every 30 days"

    def test_ten_marks_appends_prose_with_citations(self):
        points = plan_support_points(
            "How is the lidar maintained?", [_block(LIDAR)], 10, answer="every 30 days"
        )
        composed = compose_answer("every 30 days", points, 10)
        assert composed.startswith("every 30 days")
        assert "\n- " not in composed
        assert "[1]" in composed

    def test_fifteen_marks_produces_a_list(self):
        points = plan_support_points(
            "How is the lidar maintained?", [_block(LIDAR)], 15, answer="every 30 days"
        )
        composed = compose_answer("every 30 days", points, 15)
        assert "\n- " in composed

    def test_no_points_returns_the_direct_answer(self):
        assert compose_answer("every 30 days", [], 15) == "every 30 days"


# ---------------------------------------------------------------------------
# Service integration: depth is real and stays grounded
# ---------------------------------------------------------------------------

def _engine_result(answer: str, marks: int):
    from generation.types import GenerationResult, VerificationReport

    report = VerificationReport(
        claims=[],
        citation_accuracy=1.0,
        supported_claims=1,
        unsupported_claims=[],
        uncited_claims=0,
        verified=True,
        status="SUPPORTED",
    )
    return GenerationResult(
        answer=answer,
        abstained=False,
        verification=report,
        model="test-model",
        marks=marks,
        latency_ms=1,
    )


@pytest.mark.parametrize("marks", ["5", "10", "15"])
def test_service_answers_become_deeper_with_marks(monkeypatch, marks):
    monkeypatch.setattr(
        service, "generate", lambda *a, **k: _engine_result("every 30 days", int(marks))
    )
    result = service.answer_generatively(
        "How is the lidar array maintained?", [_block(LIDAR)], answer_format=marks
    )
    assert result.answer.startswith("every 30 days")
    assert result.marks == int(marks)
    if marks == "5":
        assert result.answer == "every 30 days"
    else:
        assert len(result.answer) > len("every 30 days")
    # Added points are evidence sentences, so the whole answer stays supported.
    assert result.verification["status"] == "SUPPORTED"
    assert result.verification["verified"] is True


def test_depth_shortfall_is_reported_honestly(monkeypatch):
    """With one supporting sentence, 15 marks says so instead of padding."""
    thin = [_block("The lidar array requires calibration every 30 days.")]
    monkeypatch.setattr(service, "generate", lambda *a, **k: _engine_result("every 30 days", 15))
    result = service.answer_generatively(
        "How often is the lidar array calibrated?", thin, answer_format="15"
    )
    assert any("shorter than a 15-mark answer" in warning for warning in result.warnings)


def test_five_marks_has_no_depth_shortfall_warning(monkeypatch):
    thin = [_block("The lidar array requires calibration every 30 days.")]
    monkeypatch.setattr(service, "generate", lambda *a, **k: _engine_result("every 30 days", 5))
    result = service.answer_generatively(
        "How often is the lidar array calibrated?", thin, answer_format="5"
    )
    assert not any("shorter than" in warning for warning in result.warnings)


def test_fifteen_mark_answer_is_longer_than_ten_mark_answer(monkeypatch):
    outputs = {}
    for marks in ("10", "15"):
        monkeypatch.setattr(
            service, "generate", lambda *a, m=marks, **k: _engine_result("every 30 days", int(m))
        )
        outputs[marks] = service.answer_generatively(
            "How is the lidar array maintained?", [_block(LIDAR)], answer_format=marks
        ).answer
    assert len(outputs["15"]) > len(outputs["10"])

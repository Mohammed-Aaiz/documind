"""Tests for the relation-aware claim verifier and the verifier switch.

The claim-verification dataset (`evaluation/datasets/claim_verification_v1.py`)
measures aggregate behaviour; these tests pin the individual decisions and the
integration contract, including the cases the production lexical verifier gets
wrong (paraphrase rejected, contradiction not distinguished).
"""

import time

import pytest

from generation.types import EvidenceBlock
from generation.verification import verify_answer, verify_with_mode, verifier_mode
from generation.verification_relations import (
    LABEL_CONTRADICTED,
    LABEL_INSUFFICIENT,
    LABEL_SUPPORTED,
    verify_claim,
)


def _block(content: str, index: int = 1) -> EvidenceBlock:
    return EvidenceBlock(index=index, content=content, document_name="manual.pdf")


LIDAR_EVIDENCE = (
    "The sensor array is recalibrated every 90 days. "
    "The lidar array requires calibration every 30 days."
)


class TestParaphraseAcceptance:
    def test_supported_paraphrase_is_accepted(self):
        verdict = verify_claim(
            "A technician spends roughly two hours on manual calibration.",
            [_block("Manual calibration needs a technician and takes about two hours.")],
        )
        assert verdict.label == LABEL_SUPPORTED

    def test_baseline_rejects_the_same_paraphrase(self):
        """Establishes that the test above is a real difference, not a tautology."""
        report = verify_answer(
            "A technician spends roughly two hours on manual calibration.",
            [_block("Manual calibration needs a technician and takes about two hours.")],
        )
        assert report.supported_claims == 0

    def test_paraphrase_with_number_words_is_accepted(self):
        verdict = verify_claim(
            "Records are kept for 5 years.",
            [_block("Calibration records are retained for five years.")],
        )
        assert verdict.label == LABEL_SUPPORTED


class TestNumericsAndEntities:
    def test_wrong_number_for_the_same_entity_is_contradicted(self):
        verdict = verify_claim("The lidar array requires calibration every 90 days.", [_block(LIDAR_EVIDENCE)])
        assert verdict.label == LABEL_CONTRADICTED

    def test_wrong_unit_is_contradicted(self):
        verdict = verify_claim(
            "The lidar array requires calibration every 30 weeks.",
            [_block("The lidar array requires calibration every 30 days.")],
        )
        assert verdict.label == LABEL_CONTRADICTED

    def test_unmentioned_entity_is_insufficient_not_contradicted(self):
        verdict = verify_claim(
            "The sensor array requires calibration every 30 days.",
            [_block("The lidar array requires calibration every 30 days.")],
        )
        assert verdict.label == LABEL_INSUFFICIENT

    def test_correct_value_for_the_question_entity_is_supported(self):
        verdict = verify_claim(
            "The lidar array requires calibration every 30 days.", [_block(LIDAR_EVIDENCE)]
        )
        assert verdict.label == LABEL_SUPPORTED


class TestRelationsAndNegation:
    def test_reversed_negation_is_contradicted(self):
        verdict = verify_claim(
            "Calibration can correct a physically damaged lidar unit.",
            [_block("Calibration cannot correct a physically damaged lidar unit.")],
        )
        assert verdict.label == LABEL_CONTRADICTED

    def test_paraphrased_negation_is_not_a_contradiction(self):
        """'cannot be dispatched' vs 'blocks dispatch' say the same thing."""
        verdict = verify_claim(
            "The robot cannot be dispatched while a calibration failure is unresolved.",
            [_block("A failed calibration check blocks the robot from dispatch until it is resolved.")],
        )
        assert verdict.label == LABEL_SUPPORTED

    def test_reversed_comparison_is_contradicted(self):
        verdict = verify_claim(
            "Manual calibration is cheaper than automated calibration.",
            [_block(
                "Manual calibration is more accurate on damaged hardware, while "
                "automated calibration is cheaper for a large fleet."
            )],
        )
        assert verdict.label == LABEL_CONTRADICTED

    def test_reversed_role_assignment_is_contradicted(self):
        verdict = verify_claim(
            "Elena Vasquez is the CFO.",
            [_block("CTO: James Whitfield, CFO: Robert Tanaka, COO: Elena Vasquez.")],
        )
        assert verdict.label == LABEL_CONTRADICTED

    def test_unsupported_causal_claim_is_not_supported_by_an_indicator(self):
        verdict = verify_claim(
            "A worn bearing causes repeated failures on the same axis.",
            [_block("Repeated failures on the same axis indicate a worn bearing.")],
        )
        assert verdict.label != LABEL_SUPPORTED

    def test_unmentioned_proper_noun_downgrades_support(self):
        verdict = verify_claim(
            "The system uses TensorFlow.",
            [_block("The system uses sentence transformer models.")],
        )
        assert verdict.label == LABEL_INSUFFICIENT


class TestSingleValueAnswers:
    """Gate 7: short factual answers must keep working (regression, measured)."""

    def test_value_only_answer_is_supported_when_the_question_names_the_entity(self):
        verdict = verify_claim(
            "every 30 days",
            [_block("The lidar array requires calibration every 30 days.")],
            question="How often is the lidar array calibrated?",
        )
        assert verdict.label == LABEL_SUPPORTED

    def test_value_only_answer_keeps_its_unit(self):
        verdict = verify_claim("30 days", [_block("The lidar array requires calibration every 30 days.")])
        assert verdict.label == LABEL_SUPPORTED

    def test_bare_number_without_a_question_is_not_attributed(self):
        verdict = verify_claim("1", [_block("The lidar array requires calibration every 30 days.")])
        assert verdict.label == LABEL_INSUFFICIENT

    def test_bare_number_for_an_unrelated_question_is_not_attributed(self):
        verdict = verify_claim(
            "1",
            [_block("The lidar array requires calibration every 30 days.")],
            question="What was the population of Norway in 1998?",
        )
        assert verdict.label == LABEL_INSUFFICIENT

    def test_value_only_answer_with_the_wrong_number_is_not_supported(self):
        verdict = verify_claim(
            "every 90 days",
            [_block("The lidar array requires calibration every 30 days.")],
            question="How often is the lidar array calibrated?",
        )
        assert verdict.label != LABEL_SUPPORTED


class TestGuardsAgainstSimilarityLaundering:
    """Similarity may bridge wording; it must not bridge an addition."""

    def test_universal_claim_is_not_supported_by_a_narrower_passage(self):
        verdict = verify_claim(
            "Manual calibration is always more accurate than automated calibration.",
            [_block("Manual calibration is more accurate on damaged hardware.")],
        )
        assert verdict.label == LABEL_INSUFFICIENT

    def test_added_qualifier_on_a_value_is_not_accepted(self):
        verdict = verify_claim(
            "Calibration records are kept for the warranty period of five years.",
            [_block("Calibration records are stored in the maintenance log for five years.")],
        )
        assert verdict.label != LABEL_SUPPORTED

    def test_matching_value_with_the_same_qualifier_is_still_supported(self):
        verdict = verify_claim(
            "Calibration records are kept for five years.",
            [_block("Calibration records are stored in the maintenance log for five years.")],
        )
        assert verdict.label == LABEL_SUPPORTED


class TestQuestionAttributeBinding:
    """The asked attribute decides which cell a value-only claim must match.

    The evidence rows below are the benchmark rows behind the actual generated
    answers in ``answer_claims_v1``; each test names the label the frozen reference
    set gives that claim.
    """

    WIND = (
        "Variable | Unit | Min | Max | Mean | Missing %\n"
        "Wind Speed | m/s | 0.0 | 58.4 | 4.2 | 0.2%"
    )
    PAYMENT = "Payment Schedule | Amount (USD) | Due Date\nQ2 2025 | $61,250 | July 15, 2025"
    DIVISION = (
        "Division | Q3 2025 Revenue | Q3 2024 Revenue | YoY Growth\n"
        "Enterprise Solutions | $412.5M | $348.7M | +18.3%"
    )
    AUTH = "Method | Endpoint | Description | Auth Required\nPOST | /auth/token | Obtain access token | No"

    def test_asked_column_with_the_value_is_supported(self):
        verdict = verify_claim("4.2", [_block(self.WIND)], question="What is the mean for Wind Speed?")
        assert verdict.label == LABEL_SUPPORTED

    def test_value_under_another_column_with_a_competing_value_is_contradicted(self):
        """``0.0`` is the minimum; the asked mean is stated as ``4.2``."""
        verdict = verify_claim(
            "0.0.", [_block(self.WIND)], question="What is the mean for Wind Speed?"
        )
        assert verdict.label == LABEL_CONTRADICTED

    def test_value_under_another_column_without_a_competing_value_is_insufficient(self):
        verdict = verify_claim(
            "m/s.", [_block(self.WIND)], question="What is the variable for Wind Speed?"
        )
        assert verdict.label == LABEL_INSUFFICIENT
        assert "different attribute" in verdict.explanation

    def test_money_under_a_label_column_is_not_a_contradiction(self):
        verdict = verify_claim(
            "$412.5M",
            [_block(self.DIVISION)],
            question="According to the table, what is the division for Enterprise Solutions?",
        )
        assert verdict.label == LABEL_INSUFFICIENT

    def test_value_question_selects_the_amount_column(self):
        """``Q2 2025`` is the row key; the asked value is the amount beside it."""
        verdict = verify_claim(
            "$61,250.",
            [_block(self.PAYMENT)],
            question="How much is the payment schedule of Q2 2025?",
        )
        assert verdict.label == LABEL_SUPPORTED

    def test_derivative_amount_is_contradicted_for_a_total_question(self):
        """``$3`` is per-share; the reported net income is ``$142.6 million``."""
        verdict = verify_claim(
            "$3",
            [_block("Net income attributable to shareholders was $142.6 million, or $3.")],
            question="What was the reported monetary value?",
        )
        assert verdict.label == LABEL_CONTRADICTED

    def test_percentage_change_is_not_the_base_percentage(self):
        verdict = verify_claim(
            "1",
            [_block("1 percent from 20.3 percent.")],
            question="What does the document say about percentage?",
        )
        assert verdict.label == LABEL_CONTRADICTED

    def test_table_cell_negation_is_not_prose_negation(self):
        """``No`` in the Auth Required cell does not deny the endpoint row."""
        verdict = verify_claim(
            "/auth/token, Obtain access token.",
            [_block(self.AUTH)],
            question="What are all the values for POST?",
        )
        assert verdict.label == LABEL_SUPPORTED


class TestEvidenceAbbreviations:
    """Evidence-side titles must not break entity support (Mission 3 regression)."""

    CONTEXT = (
        "Current Leadership\n"
        "CEO: Dr. Sarah Chen (since January 2022)\n"
        "CTO: James Whitfield (co-founder, since 1998)"
    )

    def test_title_in_evidence_does_not_split_the_entity(self):
        from generation.verification import split_sentences

        assert "CEO: Dr. Sarah Chen (since January 2022)" in split_sentences(self.CONTEXT)

    def test_entity_with_a_title_is_supported(self):
        verdict = verify_claim(
            "Dr. Sarah Chen", [_block(self.CONTEXT)], question="Who is the CEO?"
        )
        assert verdict.label == LABEL_SUPPORTED


class TestMultiPassageAndCitations:
    def test_claim_supported_by_two_passages(self):
        verdict = verify_claim(
            "The lidar array is calibrated every 30 days and the records are kept for five years.",
            [
                _block("The lidar array requires calibration every 30 days.", index=1),
                _block("Calibration records are retained for five years.", index=2),
            ],
        )
        assert verdict.label == LABEL_SUPPORTED
        assert verdict.supporting_blocks == [1, 2]

    def test_wrong_citation_is_flagged_but_claim_truth_is_unchanged(self):
        verdict = verify_claim(
            "The lidar array requires calibration every 30 days.",
            [
                _block("The lidar array requires calibration every 30 days.", index=1),
                _block("The power rail operates at 12 volts.", index=2),
            ],
            stated_citations=(2,),
        )
        assert verdict.label == LABEL_SUPPORTED
        assert verdict.citation_ok is False

    def test_correct_citation_is_accepted(self):
        verdict = verify_claim(
            "The lidar array requires calibration every 30 days.",
            [_block("The lidar array requires calibration every 30 days.", index=1)],
            stated_citations=(1,),
        )
        assert verdict.citation_ok is True


class TestDegenerateInputs:
    def test_empty_evidence_is_insufficient(self):
        assert verify_claim("The lidar is calibrated monthly.", []).label == LABEL_INSUFFICIENT

    def test_empty_claim_is_insufficient(self):
        assert verify_claim("   ", [_block(LIDAR_EVIDENCE)]).label == LABEL_INSUFFICIENT

    def test_large_evidence_is_processed_quickly(self):
        """A 400-sentence evidence block must not blow up verification time."""
        evidence = " ".join(
            f"Sentence number {index} describes a maintenance step for module {index}."
            for index in range(400)
        )
        started = time.perf_counter()
        verdict = verify_claim("The lidar array requires calibration every 30 days.", [_block(evidence)])
        elapsed = time.perf_counter() - started
        assert verdict.label == LABEL_INSUFFICIENT
        assert elapsed < 5.0


class TestVerifierMode:
    def test_default_mode_is_lexical(self, monkeypatch):
        monkeypatch.delenv("DOCUMIND_VERIFIER", raising=False)
        assert verifier_mode() == "lexical"

    def test_unknown_mode_falls_back_to_lexical(self, monkeypatch):
        monkeypatch.setenv("DOCUMIND_VERIFIER", "something-else")
        assert verifier_mode() == "lexical"

    def test_relations_mode_is_selected_and_used(self, monkeypatch):
        monkeypatch.setenv("DOCUMIND_VERIFIER", "relations")
        assert verifier_mode() == "relations"
        report = verify_with_mode(
            "A technician spends roughly two hours on manual calibration.",
            [_block("Manual calibration needs a technician and takes about two hours.")],
        )
        assert report.verified is True
        assert report.status == "SUPPORTED"

    def test_relations_mode_reports_contradicted_claims(self, monkeypatch):
        monkeypatch.setenv("DOCUMIND_VERIFIER", "relations")
        report = verify_with_mode(
            "The sensor array is recalibrated every 30 days.",
            [_block("The sensor array is recalibrated every 90 days.")],
        )
        assert report.status == "UNSUPPORTED"
        assert report.contradicted_claims
        assert report.summary()["contradictedClaims"]

    def test_mixed_answer_is_partially_supported(self, monkeypatch):
        monkeypatch.setenv("DOCUMIND_VERIFIER", "relations")
        report = verify_with_mode(
            "The lidar array requires calibration every 30 days. The power rail operates at 240 volts.",
            [_block(LIDAR_EVIDENCE)],
        )
        assert report.status == "PARTIALLY_SUPPORTED"
        assert report.supported_claims == 1
        assert report.unsupported_claims

    def test_lexical_mode_still_uses_the_production_verifier(self, monkeypatch):
        monkeypatch.delenv("DOCUMIND_VERIFIER", raising=False)
        report = verify_with_mode(
            "A technician spends roughly two hours on manual calibration.",
            [_block("Manual calibration needs a technician and takes about two hours.")],
        )
        # The production verifier is unchanged: it rejects this paraphrase.
        assert report.supported_claims == 0


@pytest.mark.parametrize(
    "claim,expected",
    [
        ("The lidar array requires calibration every 30 days.", LABEL_SUPPORTED),
        ("The lidar array requires calibration every 45 days.", LABEL_CONTRADICTED),
        ("The camera array requires calibration every 30 days.", LABEL_INSUFFICIENT),
    ],
)
def test_verdict_ladder(claim, expected):
    assert verify_claim(claim, [_block(LIDAR_EVIDENCE)]).label == expected

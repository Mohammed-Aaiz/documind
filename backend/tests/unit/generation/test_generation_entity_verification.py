"""Regression tests for wrong-entity numbers and the required edge cases.

The motivating failure (measured 2026-10-17): for *"How often is the lidar array
recalibrated?"* the extractive model answered **every 90 days** — the *sensor*
array's interval — because both numbers occur in the same retrieved passage.
Lexical support alone accepts that; entity alignment must not.
"""

from generation.types import (
    CLAIM_INSUFFICIENT,
    CLAIM_PARTIALLY_SUPPORTED,
    CLAIM_SUPPORTED,
    CLAIM_UNSUPPORTED,
    EvidenceBlock,
)
from generation.verification import (
    check_claim,
    numeric_entity_alignment,
    verify_answer,
)

CALIBRATION = EvidenceBlock(
    index=1,
    content=(
        "The sensor array is recalibrated every 90 days. "
        "The lidar array requires calibration every 30 days. "
        "The power rail operates at 12 volts."
    ),
    document_name="sample.txt",
)

LIDAR_QUESTION = "How often is the lidar array recalibrated?"


class TestEntityAlignment:
    def test_value_for_the_question_entity_matches(self):
        assert (
            numeric_entity_alignment(LIDAR_QUESTION, "every 30 days", CALIBRATION.content)
            == "matched"
        )

    def test_value_for_a_different_entity_is_a_mismatch(self):
        assert (
            numeric_entity_alignment(LIDAR_QUESTION, "every 90 days", CALIBRATION.content)
            == "mismatch"
        )

    def test_non_numeric_claim_is_not_entity_checked(self):
        assert (
            numeric_entity_alignment(LIDAR_QUESTION, "The lidar array needs calibration", CALIBRATION.content)
            == "not_applicable"
        )


class TestWrongEntity:
    def test_correct_value_is_supported(self):
        check = check_claim("every 30 days", [CALIBRATION], question=LIDAR_QUESTION)
        assert check.supported is True
        assert check.state == CLAIM_SUPPORTED
        assert check.entity_check == "matched"

    def test_wrong_entity_value_is_rejected_even_though_it_is_in_the_text(self):
        """The exact failure the extractive model produced."""
        check = check_claim("every 90 days", [CALIBRATION], question=LIDAR_QUESTION)
        assert check.supported is False
        assert check.entity_check == "mismatch"
        assert "different entity" in check.reason

    def test_answer_level_state_reports_unsupported(self):
        report = verify_answer("every 90 days", [CALIBRATION], question=LIDAR_QUESTION)
        assert report.verified is False
        assert report.status == CLAIM_UNSUPPORTED
        assert report.wrong_entity_claims == ["every 90 days"]

    def test_line_wrapped_evidence_is_not_split_mid_sentence(self):
        """Extracted text wraps mid-sentence; that must not cause a mismatch.

        Live regression (2026-10-17): "The lidar array requires\ncalibration
        every 30 days." was split into two sentences, the entity anchor lost its
        value, and the correct answer was withheld as a wrong entity.
        """
        wrapped = EvidenceBlock(
            index=1,
            content=(
                "The sensor array is recalibrated every 90 days. The lidar array requires\n"
                "calibration every 30 days. The power rail operates at 12 volts."
            ),
        )
        assert (
            numeric_entity_alignment(LIDAR_QUESTION, "every 30 days", wrapped.content)
            == "matched"
        )
        assert verify_answer("every 30 days", [wrapped], question=LIDAR_QUESTION).verified is True

    def test_sensor_question_accepts_90_days(self):
        check = check_claim(
            "every 90 days",
            [CALIBRATION],
            question="How often is the sensor array recalibrated?",
        )
        assert check.supported is True


class TestNumericAndCitation:
    def test_invented_value_is_unsupported(self):
        check = check_claim("every 45 days", [CALIBRATION], question=LIDAR_QUESTION)
        assert check.supported is False

    def test_incorrect_citation_identifier_is_unsupported(self):
        check = check_claim("The power rail operates at 12 volts [2].", [CALIBRATION])
        assert check.supported is False
        assert "non-existent evidence number" in check.reason

    def test_citation_to_a_block_that_does_not_contain_the_claim(self):
        other = EvidenceBlock(index=2, content="Semantic retrieval uses pgvector.")
        check = check_claim("The power rail operates at 12 volts [2].", [CALIBRATION, other])
        assert check.supported is False
        assert "does not contain it" in check.reason

    def test_missing_citation_is_uncited(self):
        report = verify_answer("The power rail operates at 12 volts.", [CALIBRATION])
        assert report.status == CLAIM_SUPPORTED  # attributed deterministically
        check = check_claim("The power rail operates at 12 volts.", [CALIBRATION])
        assert check.citation_indices == [1]

    def test_claim_with_no_supporting_evidence(self):
        check = check_claim("The battery is lithium iron phosphate.", [CALIBRATION])
        assert check.supported is False
        assert check.state == CLAIM_UNSUPPORTED


class TestAnswerStates:
    def test_correct_short_answer_is_supported(self):
        report = verify_answer("every 30 days", [CALIBRATION], question=LIDAR_QUESTION)
        assert report.status == CLAIM_SUPPORTED
        assert report.verified is True

    def test_mixed_support_is_partially_supported(self):
        answer = (
            "The lidar array requires calibration every 30 days. "
            "The battery is lithium iron phosphate."
        )
        report = verify_answer(answer, [CALIBRATION], question=LIDAR_QUESTION)
        assert report.status == CLAIM_PARTIALLY_SUPPORTED
        assert report.verified is False
        assert len(report.unsupported_claims) == 1

    def test_unsupported_additional_claim_blocks_verification(self):
        answer = "The power rail operates at 12 volts. The warranty lasts five years."
        report = verify_answer(answer, [CALIBRATION])
        assert report.verified is False
        assert report.status == CLAIM_PARTIALLY_SUPPORTED

    def test_no_evidence_is_insufficient(self):
        report = verify_answer("every 30 days", [], question=LIDAR_QUESTION)
        assert report.status == CLAIM_INSUFFICIENT
        assert report.verified is False

    def test_empty_answer_is_insufficient_not_verified(self):
        report = verify_answer("", [CALIBRATION], question=LIDAR_QUESTION)
        assert report.status == CLAIM_INSUFFICIENT


class TestTableEntityAlignment:
    """A table's header names the column; its first cell names the row.

    Mission 5 regression: the prose anchor used the header sentence (because a
    column name such as "limit" is the question's rarest term), so exact gold
    answers were withheld as wrong-entity values.
    """

    TIERS = (
        "Tier | Rate Limit | Burst Limit | Monthly Quota\n"
        "Premium | 1,000 req/min | 1,500 req/min | 5,000,000 requests\n"
        "Standard | 100 req/min | 150 req/min | 500,000 requests"
    )
    REVENUE = (
        "Division | Q3 2025 Revenue | Q3 2024 Revenue | YoY Growth\n"
        "Professional Services | $147.7M | $141.8M | +4.2%\n"
        "Enterprise Solutions | $412.5M | $348.7M | +18.3%\n"
        "Other | $0.0M | $1.6M | -100.0%"
    )
    CLIMATE = (
        "Variable | Unit | Min | Max | Mean | Missing %\n"
        "Wind Speed | m/s | 0.0 | 58.4 | 4.2 | 0.2%"
    )

    def test_value_in_the_asked_column_is_matched(self):
        assert (
            numeric_entity_alignment("What is Premium's rate limit?", "1,000 req/min", self.TIERS)
            == "matched"
        )
        assert (
            numeric_entity_alignment(
                "How much is the monthly quota of Standard?", "500,000 requests", self.TIERS
            )
            == "matched"
        )
        assert (
            numeric_entity_alignment(
                "What yoy growth does Professional Services have?", "+4.2%", self.REVENUE
            )
            == "matched"
        )

    def test_value_in_a_different_column_is_a_mismatch(self):
        """The mean is asked; the claim gives the minimum."""
        assert (
            numeric_entity_alignment("What is the mean for Wind Speed?", "0.0", self.CLIMATE)
            == "mismatch"
        )

    def test_value_from_a_different_row_is_a_mismatch(self):
        assert (
            numeric_entity_alignment(
                "What is Premium's rate limit?", "100 req/min", self.TIERS
            )
            == "mismatch"
        )

    def test_compound_value_spanning_columns_is_a_mismatch(self):
        """A correct cell plus an adjacent year is not a single-column answer."""
        assert (
            numeric_entity_alignment(
                "How much is the q3 2025 revenue of Other?", "$0.0M and $1.6M", self.REVENUE
            )
            == "mismatch"
        )

    def test_table_title_does_not_bind_the_label_column(self):
        """'Payment Schedule' is the table title, not the amount column."""
        table = (
            "Payment Schedule | Amount (USD) | Due Date\n"
            "Q2 2025 | $61,250 | July 15, 2025"
        )
        assert (
            numeric_entity_alignment(
                "How much is the payment schedule of Q2 2025?", "$61,250", table
            )
            == "matched"
        )

    def test_non_table_evidence_keeps_the_prose_rule(self):
        assert (
            numeric_entity_alignment(LIDAR_QUESTION, "every 30 days", CALIBRATION.content)
            == "matched"
        )
        assert (
            numeric_entity_alignment(LIDAR_QUESTION, "every 90 days", CALIBRATION.content)
            == "mismatch"
        )


class TestConflictingEvidence:
    def test_conflicting_passages_still_bind_the_claim_to_the_entity(self):
        conflicting = EvidenceBlock(
            index=2,
            content=(
                "The lidar array requires calibration every 60 days. "
                "The lidar array requires calibration every 30 days."
            ),
        )
        # Both values are present for the right entity; the claim is supported by
        # the block, and the conflict is visible in the sources (not resolved by
        # the verifier).  This documents the limit instead of hiding it.
        report = verify_answer("every 30 days", [CALIBRATION, conflicting], question=LIDAR_QUESTION)
        assert report.status == CLAIM_SUPPORTED
        assert report.citation_accuracy == 1.0

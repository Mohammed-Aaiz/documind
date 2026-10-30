"""Evidence verification — deterministic lexical attribution."""

from generation.types import EvidenceBlock
from generation.verification import (
    check_claim,
    support_ratio,
    verify_answer,
)

BLOCKS = [
    EvidenceBlock(
        index=1,
        content=(
            "The sensor array is recalibrated every 90 days. "
            "The lidar array requires calibration every 30 days. "
            "The power rail operates at 12 volts."
        ),
        document_name="sample.txt",
    ),
    EvidenceBlock(
        index=2,
        content="Semantic retrieval uses pgvector cosine similarity over 384-dimensional embeddings.",
        document_name="sample.txt",
    ),
]


class TestAttribution:
    def test_answer_present_in_evidence_is_supported(self):
        check = check_claim("The lidar array requires calibration every 30 days.", BLOCKS)
        assert check.supported is True
        assert check.citation_indices == [1]

    def test_short_factual_answer_is_supported_by_the_block_containing_it(self):
        check = check_claim("every 30 days", BLOCKS)
        assert check.supported is True
        assert check.citation_indices == [1]

    def test_invented_value_is_unsupported(self):
        check = check_claim("The sensor array is recalibrated every 45 days.", BLOCKS)
        assert check.supported is False
        assert "value absent" in check.reason

    def test_a_bare_number_matches_when_the_evidence_ends_the_sentence_with_it(self):
        # The token regex allows "." inside a token, so "... in 1859." tokenised
        # as "1859." while the answer was "1859".  The claim then scored 0.0 and
        # the correct one-word answer was withheld (measured 2026-10-24).
        blocks = [
            EvidenceBlock(
                index=1,
                content="Charles Darwin published On the Origin of Species in 1859.",
                document_name="darwin_proper.pdf",
                page=1,
            )
        ]
        check = check_claim("1859", blocks)
        assert check.supported is True
        assert check.support_ratio == 1.0

    def test_a_number_absent_from_the_evidence_is_still_unsupported(self):
        blocks = [
            EvidenceBlock(
                index=1,
                content="Charles Darwin published On the Origin of Species in 1859.",
                document_name="darwin_proper.pdf",
                page=1,
            )
        ]
        assert check_claim("1873", blocks).supported is False

    def test_wrong_model_citation_is_reported(self):
        check = check_claim("The power rail operates at 12 volts [2].", BLOCKS)
        assert check.supported is False
        assert "cites evidence that does not contain it" in check.reason

    def test_nonexistent_citation_number_is_reported(self):
        check = check_claim("The power rail operates at 12 volts [9].", BLOCKS)
        assert check.supported is False
        assert "non-existent evidence number" in check.reason

    def test_claim_too_short_is_not_accepted(self):
        assert check_claim("volts", BLOCKS).supported is False

    def test_support_ratio_is_content_word_overlap(self):
        assert support_ratio("pgvector cosine similarity", BLOCKS[1].content) > 0.9
        assert support_ratio("quantum entanglement", BLOCKS[1].content) == 0.0


class TestVerificationReport:
    def test_fully_supported_answer_is_verified(self):
        report = verify_answer("The lidar array requires calibration every 30 days.", BLOCKS)
        assert report.verified is True
        assert report.citation_accuracy == 1.0
        assert report.unsupported_claims == []

    def test_one_unsupported_claim_blocks_verification(self):
        answer = (
            "The lidar array requires calibration every 30 days. "
            "The sensor uses a lithium battery."
        )
        report = verify_answer(answer, BLOCKS)
        assert report.verified is False
        assert len(report.unsupported_claims) == 1
        assert report.citation_accuracy == 0.5

    def test_empty_answer_is_not_a_vacuous_pass(self):
        assert verify_answer("", BLOCKS).verified is False

    def test_no_evidence_is_not_a_vacuous_pass(self):
        assert verify_answer("The lidar array requires calibration every 30 days.", []).verified is False

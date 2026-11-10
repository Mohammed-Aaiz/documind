import pytest

from generation.planning import extract_citations, split_claims, strip_citations
from generation.types import EvidenceBlock
from generation.verification import verify_with_mode
from orchestration.service import _build_extractive_fallback


def test_duplicate_evidence_keeps_all_source_citations():
    sentence = "Wind turbines convert wind energy into useful mechanical power."
    answer = _build_extractive_fallback(
        "Explain wind turbines", [EvidenceBlock(1, sentence), EvidenceBlock(2, sentence)], 10
    )
    assert strip_citations(answer).count(sentence) == 1
    assert "[1]" in answer and "[2]" in answer


def test_named_entity_remains_the_focus_after_an_instruction_word():
    unrelated = "The calibration procedure involves checking measurements with the reference rig."
    relevant = "The Kestrel frame is calibrated against a stable geometric reference rig."
    answer = _build_extractive_fallback(
        "Explain Kestrel calibration", [EvidenceBlock(1, unrelated), EvidenceBlock(2, relevant)], 10
    )
    assert relevant in strip_citations(answer)
    assert unrelated not in strip_citations(answer)


@pytest.mark.parametrize("marks", [5, 10, 15])
def test_duplicate_fallback_citations_remain_attached_to_one_verified_claim(marks):
    sentence = "Wind turbines convert wind energy into useful mechanical power."
    blocks = [EvidenceBlock(1, sentence), EvidenceBlock(10, sentence)]
    answer = _build_extractive_fallback("Explain wind turbines", blocks, marks)
    claims = split_claims(answer)
    assert len(claims) == 1
    assert strip_citations(claims[0]) == sentence
    assert extract_citations(claims[0]) == [1, 10]
    report = verify_with_mode(answer, blocks, question="Explain wind turbines")
    assert report.verified, report.summary()
    assert report.claim_count == 1 and report.uncited_claims == 0

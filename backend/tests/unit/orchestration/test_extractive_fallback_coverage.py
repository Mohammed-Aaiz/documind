"""Coverage safeguards for the grounded extractive answer fallback."""

import pytest

from generation.planning import extract_citations, strip_citations
from generation.types import EvidenceBlock
from generation.verification import verify_with_mode
from orchestration.service import _build_extractive_fallback


def excerpts(answer):
    return [(strip_citations(line.removeprefix("- ")), extract_citations(line))
            for line in answer.splitlines()]


def quoted_text(answer):
    return "\n".join(sentence for sentence, _ in excerpts(answer))


@pytest.mark.parametrize("marks", [5, 10, 15])
def test_process_explanation_keeps_connected_generator_endpoint(marks):
    sentences = [
        "Wind energy is renewable energy captured from the movement of air.",
        "Wind energy drives turbine blades so that the rotor begins to turn.",
        "The rotor transfers its rotation through a shaft to the generator.",
        "The generator converts the mechanical rotation into electrical power.",
    ]
    answer = _build_extractive_fallback(
        "Explain wind energy", [EvidenceBlock(2, " ".join(sentences))], marks
    )
    plain = quoted_text(answer)
    assert all(sentence in plain for sentence in sentences)
    assert [plain.index(sentence) for sentence in sentences] == sorted(
        plain.index(sentence) for sentence in sentences
    )
    assert all(citations == [2] for _, citations in excerpts(answer))


@pytest.mark.parametrize("marks", [5, 10, 15])
def test_each_requested_part_survives_many_matches_for_the_first_part(marks):
    wind = " ".join(
        f"Wind energy turbine {index} captures moving air and produces useful electric power."
        for index in range(20)
    )
    tidal = "Tidal energy uses the rise and fall of seawater to generate electricity."
    answer = _build_extractive_fallback(
        "Explain:\n(a) wind energy\n(b) tidal energy",
        [EvidenceBlock(1, wind), EvidenceBlock(2, tidal)], marks,
    )
    assert "Wind energy turbine" in answer
    assert (tidal, [2]) in excerpts(answer)


def test_sparse_evidence_is_not_padded_to_mark_depth():
    sentence = "Wind turbines convert wind energy into useful mechanical power."
    answers = [
        _build_extractive_fallback("Explain wind energy", [EvidenceBlock(1, sentence)], marks)
        for marks in [5, 10, 15]
    ]
    assert [excerpts(answer) for answer in answers] == [[(sentence, [1])]] * 3


def test_proper_name_in_one_part_does_not_hide_the_other_requested_part():
    kestrel = "The Kestrel platform conducts autonomous surveys across uneven terrain."
    wind = "Wind turbines convert wind energy into useful mechanical power."
    answer = _build_extractive_fallback(
        "Explain:\n(a) Kestrel surveys\n(b) wind energy",
        [EvidenceBlock(1, kestrel), EvidenceBlock(2, wind)], 5,
    )
    assert (kestrel, [1]) in excerpts(answer)
    assert (wind, [2]) in excerpts(answer)


def test_contradictory_source_claims_remain_separately_cited():
    first = "The Kestrel turbine has a rated electrical output of 15 kilowatts."
    second = "The Kestrel turbine has a rated electrical output of 20 kilowatts."
    answer = _build_extractive_fallback(
        "Explain the Kestrel turbine output",
        [EvidenceBlock(1, first), EvidenceBlock(2, second)], 10,
    )
    assert (first, [1]) in excerpts(answer)
    assert (second, [2]) in excerpts(answer)
    assert len(answer.splitlines()) == 2


def test_connected_intervening_sentence_is_quoted_with_its_source():
    first = "The wind turbine rotor captures wind energy and turns the rotor shaft."
    bridge = "The rotor shaft drives a generator that produces electrical power."
    last = "The generator supplies electrical power from wind energy to the grid."
    answer = _build_extractive_fallback(
        "Explain wind energy", [EvidenceBlock(2, f"{first} {bridge} {last}")], 10
    )
    plain = quoted_text(answer)
    assert first in plain and bridge in plain and last in plain
    assert all(citations == [2] for _, citations in excerpts(answer))


def test_unrelated_intervening_sentence_is_not_added():
    first = "Wind energy moves the blades of the turbine and rotates the shaft."
    unrelated = "The maintenance manual recommends inspecting the building roof every year."
    last = "Wind energy generates electricity when the rotor drives the turbine generator."
    answer = _build_extractive_fallback(
        "Explain wind energy", [EvidenceBlock(1, f"{first} {unrelated} {last}")], 10
    )
    plain = quoted_text(answer)
    assert first in plain and last in plain
    assert unrelated not in plain


def test_shared_generic_words_alone_do_not_connect_irrelevant_sentences():
    first = "Wind energy systems can produce electricity in a suitable operating environment."
    unrelated = "The system includes a separate maintenance record for storage buildings."
    last = "Wind energy systems are useful when the operating conditions are suitable."
    answer = _build_extractive_fallback(
        "Explain wind energy", [EvidenceBlock(1, f"{first} {unrelated} {last}")], 10
    )
    assert unrelated not in quoted_text(answer)


def test_bridge_is_not_inferred_across_independent_source_blocks():
    first = "The wind turbine rotor captures wind energy and turns the rotor shaft."
    bridge = "The rotor shaft drives a generator that produces electrical power."
    last = "The generator supplies electrical power from wind energy to the grid."
    answer = _build_extractive_fallback(
        "Explain wind energy", [EvidenceBlock(1, first), EvidenceBlock(2, bridge), EvidenceBlock(3, last)], 10
    )
    plain = quoted_text(answer)
    assert first in plain and last in plain
    assert bridge not in plain
    assert "[1]" in answer and "[3]" in answer and "[2]" not in answer


@pytest.mark.parametrize("marks", [5, 10, 15])
def test_vawt_steps_split_under_matching_parent_keep_mechanical_conversion_chain(marks):
    parent = "Vertical Axis Wind Turbines (VAWT)"
    steps = [
        "Wind strikes the rotor and approaches the vertically arranged blades or buckets.",
        "The aerodynamic force produced by the wind causes the rotor to rotate around its vertical shaft.",
        "The rotating shaft transfers the mechanical power to the generator.",
        "The generator converts the mechanical rotational energy into electrical energy.",
    ]
    blocks = [
        EvidenceBlock(index, sentence, document_id="energy-notes", document_name="energy.pdf", page=12,
                      heading_path=(parent, f"Working step {index}"))
        for index, sentence in enumerate(steps, 1)
    ]
    unrelated = "The maintenance team cleans the warehouse storage building every Monday."
    blocks.append(EvidenceBlock(5, unrelated, document_id="warehouse", document_name="warehouse.pdf", page=2,
                                heading_path=("Warehouse maintenance",)))
    crowded_matches = [
        EvidenceBlock(20 + index,
                      f"Wind turbine rotor number {index} captures moving air for mechanical power.",
                      document_id="energy-notes", document_name="energy.pdf", page=10,
                      heading_path=("Horizontal Axis Wind Turbines (HAWT)", f"Detail {index}"))
        for index in range(12)
    ]
    answer = _build_extractive_fallback(
        "Explain Vertical Axis Wind Turbines (VAWT) with a neat diagram.", crowded_matches + blocks, marks,
    )
    for index, sentence in enumerate(steps, 1):
        assert (sentence, [index]) in excerpts(answer)
    plain = quoted_text(answer)
    assert [plain.index(sentence) for sentence in steps] == sorted(plain.index(sentence) for sentence in steps)
    assert unrelated not in plain and "[5]" not in answer
    report = verify_with_mode(answer, crowded_matches + blocks,
                              question="Explain Vertical Axis Wind Turbines (VAWT) with a neat diagram.")
    assert report.verified, report.summary()


@pytest.mark.parametrize(("marks", "maximum"), [(5, 6), (10, 10), (15, 14)])
def test_marks_bound_number_of_source_cited_excerpts(marks, maximum):
    sentences = [
        f"Wind energy uses turbine component number {i} for converting motion into electric power."
        for i in range(1, 21)
    ]
    answer = _build_extractive_fallback("Explain wind energy", [EvidenceBlock(3, " ".join(sentences))], marks)
    lines = answer.splitlines()
    assert len(lines) == maximum
    assert all(citations == [3] for _, citations in excerpts(answer))

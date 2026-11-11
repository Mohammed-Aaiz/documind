"""Final answers retain useful, source-supported figures without another LLM call.

These exercise real evidence verification and both supplied process types. A
passing label matcher alone cannot justify an arrow between unrelated objects.
"""
from unittest.mock import AsyncMock
from dataclasses import replace
import json

import pytest

from chat.rag import SourceChunk
from generation import providers, service
from generation.planning import (
    extract_citations, filter_text_diagrams, split_claims,
    text_diagram_blocks, validate_text_diagram,
)
from generation.providers import ProviderCompletion
from generation.types import EvidenceBlock
from generation.verification import verify_with_mode


def process_sources(kind="VAWT"):
    heading = "Vertical Axis Wind Turbines (VAWT)" if kind == "VAWT" else "Horizontal Axis Wind Turbines (HAWT)"
    sentences = (
        [
            "Wind strikes the rotor and approaches the vertically arranged blades or buckets.",
            "The aerodynamic force produced by the wind causes the rotor to rotate around its vertical shaft.",
            "The rotating shaft transfers the mechanical power to the generator.",
            "The generator converts the mechanical rotational energy into electrical energy.",
        ] if kind == "VAWT" else [
            "Wind flows over the aerodynamic blades and produces lift force around the blades.",
            "The lift force causes the blades and rotor to rotate around the horizontal shaft.",
            "The rotating rotor is connected to a low-speed shaft that transfers mechanical power to the drivetrain.",
            "A gearbox increases the rotational speed suitable for the generator.",
            "The high-speed shaft drives the generator, which converts mechanical energy into electrical energy.",
        ]
    )
    return [SourceChunk(
        f"{kind}-{index}", f"{index}. {sentence}", .9, "energy-notes", "energy.pdf", index + 10,
        heading_path=("Wind Energy", heading, f"Working step {index}"),
        section=heading,
    ) for index, sentence in enumerate(sentences, 1)]


def source_draft(sources):
    return "\n\n".join(
        f"{source.content.rstrip('.')} [{index}]."
        for index, source in enumerate(sources, 1)
    )


def mock_completion(monkeypatch, draft):
    complete = AsyncMock(return_value=ProviderCompletion(draft, "groq", "test-model", "stop"))
    monkeypatch.setattr(providers, "complete_answer", complete)
    return complete


@pytest.mark.asyncio
@pytest.mark.parametrize("marks", [5, 10, 15])
@pytest.mark.parametrize("kind", ["VAWT", "HAWT"])
async def test_final_verified_answer_adds_a_missing_supported_process_figure(monkeypatch, kind, marks):
    sources = process_sources(kind)
    complete = mock_completion(monkeypatch, source_draft(sources))
    question = f"Explain {sources[0].heading_path[-2]} with a neat diagram."
    _, result = await service.answer_from_evidence(
        question, sources, marks,
    )
    assert not result.abstained
    figures = text_diagram_blocks(result.answer)
    assert figures, "Supported process evidence must yield a usable final figure even if the draft omitted it"
    assert validate_text_diagram(result.answer, result.blocks, question=question)
    assert result.verification["verified"]
    assert verify_with_mode(result.answer, result.blocks, question=question).verified
    assert not any("no evidence-supported figure" in note for note in result.warnings)
    # A diagram fallback must not add inference latency with a second provider call.
    assert complete.await_count == 1
    for figure in figures:
        claims = split_claims(f"```text\n{figure}\n```")
        assert len(claims) >= 2
        assert all(extract_citations(claim) for claim in claims)


@pytest.mark.parametrize("connector", ["  v", "  |"])
def test_supported_labels_do_not_justify_an_unsupported_connection(connector):
    sources = [EvidenceBlock(1, "Wind is moving air. A generator is stored in the warehouse.")]
    figure = f"```text\nWind [1]\n{connector}\nGenerator [1]\n```"
    clean, retained, omitted = filter_text_diagrams(figure, sources)
    assert not validate_text_diagram(figure, sources)
    assert retained == 0 and omitted == 1
    assert not text_diagram_blocks(clean)


def test_reversed_relation_is_not_justified_by_the_same_supported_label_set():
    evidence = [EvidenceBlock(1, "Wind drives the rotor. The rotor turns the shaft.")]
    reversed_figure = "```text\nShaft [1]\n  v\nWind [1]\n```"
    assert not validate_text_diagram(reversed_figure, evidence)


def test_relation_from_another_source_cannot_justify_a_false_figure_reference():
    evidence = [
        EvidenceBlock(1, "Wind is moving air. The rotor is a turbine component."),
        EvidenceBlock(2, "Wind drives the rotor through aerodynamic force."),
    ]
    figure = "```text\nWind [1]\n  v\nRotor [1]\n```"
    assert not validate_text_diagram(figure, evidence)


@pytest.mark.parametrize("source", [
    "Wind and generator power are listed in the glossary.",
    "Wind turns the rotor; the generator is stored in the warehouse.",
])
def test_relation_words_must_describe_the_link_between_the_drawn_nodes(source):
    figure = "```text\nWind [1]\n  v\nGenerator [1]\n```"
    assert not validate_text_diagram(figure, [EvidenceBlock(1, source)])


def test_box_borders_and_cited_caption_do_not_hide_supported_conversion_labels():
    evidence = [EvidenceBlock(1, "Wind energy → Mechanical energy → Electrical energy.")]
    figure = (
        "Figure: energy conversion [1]\n```ascii\n"
        "+------------------+\n| Wind energy |\n+------------------+\n  |\n  v\n"
        "+------------------+\n| Mechanical energy |\n+------------------+\n  |\n  v\n"
        "+------------------+\n| Electrical energy |\n+------------------+\n```"
    )
    clean, retained, omitted = filter_text_diagrams(figure, evidence)
    assert retained == 1 and omitted == 0
    assert validate_text_diagram(clean, evidence)


@pytest.mark.asyncio
async def test_exact_source_conversion_chain_is_available_as_a_verified_figure(monkeypatch):
    source = SourceChunk(
        "conversion", "The working principle is the conversion: Wind energy → Mechanical energy → Electrical energy.",
        .9, "notes", "energy.pdf", 12, heading_path=("VAWT", "Working principle"),
    )
    mock_completion(monkeypatch, "Wind energy is converted to mechanical energy and electrical energy [1].")
    _, result = await service.answer_from_evidence("Explain VAWT energy conversion with a diagram.", [source], 10)
    assert not result.abstained
    figures = text_diagram_blocks(result.answer)
    assert figures and len(figures) == 1
    assert "Wind energy" in figures[0]
    assert "Mechanical energy" in figures[0]
    assert "Electrical energy" in figures[0]
    assert verify_with_mode(result.answer, result.blocks, question="Explain VAWT energy conversion").verified


@pytest.mark.asyncio
async def test_each_supported_requested_subtopic_gets_its_own_figure(monkeypatch):
    sources = process_sources("VAWT") + process_sources("HAWT")
    mock_completion(monkeypatch, source_draft(sources))
    question = "Explain with neat diagrams:\n(a) VAWT\n(b) HAWT"
    _, result = await service.answer_from_evidence(question, sources, 15)
    assert not result.abstained
    figures = text_diagram_blocks(result.answer)
    assert figures and len(figures) >= 2
    # Each figure remains attributable to its own subject's source sentences.
    # Prompt assembly promotes a passage for each requested part, so fitted
    # citation numbers need not follow the original input-list positions.
    subject_indices = {
        kind: {block.index for block in result.blocks
               if any(f"({kind})" in heading for heading in (block.heading_path or ()))}
        for kind in ("VAWT", "HAWT")
    }
    citation_sets = [set(extract_citations(figure)) for figure in figures]
    assert all(subject_indices.values())
    assert all(any(indices and indices <= allowed for indices in citation_sets)
               for allowed in subject_indices.values())
    assert result.verification["verified"]


@pytest.mark.asyncio
async def test_missing_subtopic_is_reported_without_inventing_its_figure(monkeypatch):
    sources = process_sources("VAWT")
    mock_completion(monkeypatch, source_draft(sources) + "\nEVIDENCE_GAPS: 2")
    question = "Explain with neat diagrams:\n(a) VAWT\n(b) tidal barrage operation"
    _, result = await service.answer_from_evidence(question, sources, 15)
    assert not result.abstained
    figures = text_diagram_blocks(result.answer)
    assert figures and len(figures) == 1
    assert "barrage" not in " ".join(figures).lower()
    assert any("tidal barrage operation" in note for note in result.warnings)


@pytest.mark.asyncio
async def test_prose_repair_preserves_a_supported_figure_and_omits_false_claim(monkeypatch):
    sources = process_sources()
    draft = source_draft(sources) + "\n\nA nuclear reactor supplies the turbine with uranium fuel [1]."
    mock_completion(monkeypatch, draft)
    _, result = await service.answer_from_evidence("Explain VAWT with a neat diagram.", sources, 10)
    assert not result.abstained and result.verification["verified"]
    assert "uranium" not in result.answer and "nuclear reactor" not in result.answer.lower()
    assert text_diagram_blocks(result.answer), "Repairing prose must keep the valid final diagram"


@pytest.mark.asyncio
async def test_unrelated_facts_cannot_be_promoted_into_a_process_diagram(monkeypatch):
    source = SourceChunk(
        "unrelated", "Wind was recorded at the field site. A generator is stored in the warehouse.",
        .8, "doc", "inventory.pdf", 1,
    )
    mock_completion(monkeypatch, "Wind was recorded at the field site [1]. A generator is stored in the warehouse [1].")
    _, result = await service.answer_from_evidence("Explain wind energy with a diagram.", [source], 5)
    assert not text_diagram_blocks(result.answer)
    assert not result.answer or "-->" not in result.answer
    assert result.abstained or any("diagram" in note.lower() for note in result.warnings)


@pytest.mark.asyncio
async def test_numbered_steps_from_independent_documents_are_not_joined_into_a_sequence(monkeypatch):
    sources = [
        SourceChunk("a", "1. Wind approaches the vertically arranged blades and begins turning the rotor.",
                    .9, "doc-a", "a.pdf", 1, heading_path=("VAWT", "Working steps")),
        SourceChunk("b", "2. The generator produces electrical power while the control system monitors output.",
                    .8, "doc-b", "b.pdf", 1, heading_path=("VAWT", "Working steps")),
    ]
    mock_completion(monkeypatch, source_draft(sources))
    _, result = await service.answer_from_evidence("Explain VAWT with a neat diagram.", sources, 10)
    # No supplied source describes the bridge from this rotor to that generator.
    for figure in text_diagram_blocks(result.answer) or []:
        assert not {1, 2} <= set(extract_citations(figure))


@pytest.mark.asyncio
async def test_numbering_inventory_facts_does_not_establish_a_process(monkeypatch):
    sources = [
        SourceChunk("wind", "1. Wind energy was recorded at the field site.", .9,
                    "doc", "inventory.pdf", 1,
                    heading_path=("Wind Energy", "Site inventory", "Item 1")),
        SourceChunk("generator", "2. A generator is stored safely in the warehouse.", .8,
                    "doc", "inventory.pdf", 1,
                    heading_path=("Wind Energy", "Site inventory", "Item 2")),
    ]
    mock_completion(monkeypatch, source_draft(sources))
    _, result = await service.answer_from_evidence("Explain wind energy with a diagram.", sources, 10)
    assert not text_diagram_blocks(result.answer)
    assert result.abstained or any("diagram" in note.lower() for note in result.warnings)


def test_unrelated_numbered_fact_under_conversion_heading_does_not_break_process_sequence():
    from generation.diagrams import _step_groups

    blocks = [
        EvidenceBlock(1, "1. Wind strikes the rotor and begins turning the blades.",
                      document_id="notes", heading_path=("Wind Energy", "CONVERSION", "Step 1")),
        EvidenceBlock(2, "2. The rotor turns the shaft and transfers mechanical power.",
                      document_id="notes", heading_path=("Wind Energy", "CONVERSION", "Step 2")),
        EvidenceBlock(3, "3. A generator converts mechanical energy into electrical energy.",
                      document_id="notes", heading_path=("Wind Energy", "CONVERSION", "Step 3")),
        # Legacy heading extraction can place an unrelated design fact under
        # the same broad chapter root. It must not conflict with process step 3.
        EvidenceBlock(4, "3. Strong supporting structures withstand wind loads.",
                      document_id="notes", heading_path=("Wind Energy", "CONVERSION", "Design notes")),
    ]

    groups = _step_groups(blocks)
    assert len(groups) == 1
    assert [number for number, _, _ in groups[0]] == [1, 2, 3]


@pytest.mark.asyncio
async def test_small_multipart_context_keeps_working_evidence_for_both_named_topics(monkeypatch):
    """One long recovered section must not exhaust the other part's context.

    This models the measured HAWT/Vawt capture shape: thirty short chunks from
    the first section followed by ten from the second, with a five-mark input cap.
    """
    from types import SimpleNamespace

    sources = []
    for kind, count in (("HAWT", 30), ("VAWT", 10)):
        heading = "Horizontal Axis Wind Turbines (HAWT)" if kind == "HAWT" else "Vertical Axis Wind Turbines (VAWT)"
        group = f"energy-notes:{kind}-window"
        topic = [SourceChunk(
            f"{kind}-definition", f"{heading}: This turbine uses wind energy to generate useful electrical power.",
            .9, "energy-notes", "energy.pdf", 10 if kind == "HAWT" else 12,
            heading_path=("Wind Energy", heading), section=heading,
        )] + process_sources(kind)
        for index in range(count - len(topic)):
            topic.append(SourceChunk(
                f"{kind}-detail-{index}",
                f"Supporting {kind} detail {index}: The course notes discuss inspection, installation, maintenance, "
                "site conditions, operating requirements, documentation and practical considerations for this "
                "wind turbine system. These details supplement the working explanation rather than replacing its essential steps.",
                .8, "energy-notes", "energy.pdf", 11 if kind == "HAWT" else 13,
                heading_path=("Wind Energy", heading, f"Supporting detail {index}"), section=heading,
            ))
        sources.extend(replace(source, topic_context_id=group, topic_context_kind="section_window",
                               topic_context_complete=False) for source in topic)

    def draft(messages, **kwargs):
        labels = [json.loads(line) for line in messages[-1]["content"].split("Source data (JSON):\n", 1)[1].splitlines()]
        source = next(label for label in labels if "Wind flows over the aerodynamic blades" in label.get("text", ""))
        return ProviderCompletion(
            f"Wind flows over the aerodynamic blades and produces lift force around the blades [{source['source']}].",
            "groq", "test-model", "stop",
        )

    complete = AsyncMock(side_effect=draft)
    monkeypatch.setattr(providers, "complete_answer", complete)
    question = "Explain (a) the working of HAWT and (b) the working of VAWT, with a separate neat diagram for each."
    _, result = await service.answer_from_evidence(
        question, sources, 5, settings=SimpleNamespace(groq_context_tokens=8192),
    )
    assert not result.abstained
    figures = text_diagram_blocks(result.answer)
    assert figures and len(figures) >= 2
    for kind in ("HAWT", "VAWT"):
        allowed = {block.index for block in result.blocks if block.chunk_id.startswith(f"{kind}-")}
        assert any((cites := set(extract_citations(figure))) and cites <= allowed for figure in figures)
    assert verify_with_mode(result.answer, result.blocks, question=question).verified
    assert complete.await_count == 1
    assert any("shortened" in note or "partial" in note for note in result.warnings)

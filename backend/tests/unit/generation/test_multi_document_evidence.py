"""Preserve document provenance when passages overlap or disagree."""
import json
from dataclasses import replace

from chat.rag import SourceChunk
from generation.provider_prompt import prepare_prompt, select_evidence
from generation.types import AnswerFormat
from generation.verification import verify_with_mode


def source(chunk_id, document_id, title, page, content, rank):
    return SourceChunk(
        chunk_id, content, 0.9, document_id, title, page,
        heading_path=("Calibration",), section="Calibration",
        rerank_position=rank,
    )


def test_repeated_passages_keep_each_document_and_page_reference():
    text = "The calibration interval is thirty days according to the maintenance plan."
    first = source("a1", "a", "Report A.pdf", 1, text, 1)
    other_page = source("a2", "a", "Report A.pdf", 2, text, 2)
    other_document = source("b1", "b", "Report B.pdf", 3, text, 3)
    selected, _ = select_evidence("Explain calibration", [first, first, other_page, other_document])

    assert [(s.chunk_id, s.document_id, s.page) for s in selected] == [
        ("a1", "a", 1), ("a2", "a", 2), ("b1", "b", 3),
    ]


def test_comparison_retains_both_sources_and_distinct_conflicting_values():
    a = source("a1", "a", "Report A.pdf", 1,
               "The calibration interval is thirty days for the field instrument.", 1)
    a_second = replace(a, chunk_id="a2", page=2,
                       content="The instrument calibration procedure uses a stable reference rig.",
                       rerank_position=2)
    b = source("b1", "b", "Report B.pdf", 5,
               "The calibration interval is ninety days for the field instrument.", 3)
    question = "Compare Report A.pdf and Report B.pdf calibration intervals."
    selected, _ = select_evidence(question, [a, a_second, b], diversify=True)

    assert [s.document_id for s in selected[:2]] == ["a", "b"]
    prepared = prepare_prompt(question, selected, [], workspace="research", task="comparison",
                              answer_format=AnswerFormat.TEN, context_tokens=8192)
    rows = [json.loads(line) for line in prepared.messages[-1]["content"].split("Source data (JSON):\n", 1)[1].splitlines() if line]
    assert [(b.document_id, b.document_name, b.page) for b in prepared.blocks[:2]] == [
        ("a", "Report A.pdf", 1), ("b", "Report B.pdf", 5),
    ]
    assert "thirty" in rows[0]["text"] and "ninety" in rows[1]["text"]
    assert [row["source"] for row in rows[:2]] == [1, 2]


def test_exact_repeated_text_is_sent_once_with_separate_citable_sources():
    text = "The calibration interval is thirty days for the field instrument."
    first = source("a1", "a", "Report A.pdf", 1, text, 1)
    second = source("b1", "b", "Report B.pdf", 5, text, 2)
    prepared = prepare_prompt("Compare the reports", [first, second], [],
                              workspace="research", task="comparison",
                              answer_format=AnswerFormat.TEN, context_tokens=8192)
    prompt = prepared.messages[-1]["content"]
    rows = [json.loads(line) for line in prompt.split("Source data (JSON):\n", 1)[1].splitlines() if line]

    assert prompt.count(text) == 1
    assert rows[0]["text"] == text
    assert rows[1]["sameTextAsSource"] == 1 and "text" not in rows[1]
    assert [(block.index, block.document_id, block.page, block.content) for block in prepared.blocks] == [
        (1, "a", 1, text), (2, "b", 5, text),
    ]
    assert [(item.document_id, item.page, item.content) for item in prepared.sources] == [
        ("a", 1, text), ("b", 5, text),
    ]
    for index in (1, 2):
        report = verify_with_mode(f"The calibration interval is thirty days for the field instrument [{index}].", prepared.blocks)
        assert report.verified and report.claims[0].citation_indices == [index]


def test_reference_never_points_to_a_truncated_source():
    text = "The calibration reference is a stable geometric frame. " * 400
    first = source("a1", "a", "Report A.pdf", 1, text, 1)
    second = source("b1", "b", "Report B.pdf", 5, text, 2)
    prepared = prepare_prompt("Compare the reports", [first, second], [],
                              workspace="research", task="comparison",
                              answer_format=AnswerFormat.TEN, context_tokens=2048)
    rows = [json.loads(line) for line in prepared.messages[-1]["content"].split("Source data (JSON):\n", 1)[1].splitlines() if line]

    assert prepared.blocks and prepared.blocks[0].truncated
    assert all("sameTextAsSource" not in row for row in rows)
    assert prepared.blocks[0].content == rows[0]["text"]


def test_a_claim_cannot_cite_both_sides_of_a_numeric_conflict():
    a = source("a1", "a", "Report A.pdf", 1,
               "The calibration interval is 30 days for the field instrument.", 1)
    b = source("b1", "b", "Report B.pdf", 5,
               "The calibration interval is 90 days for the field instrument.", 2)
    prepared = prepare_prompt("Compare the reports", [a, b], [],
                              workspace="research", task="comparison",
                              answer_format=AnswerFormat.TEN, context_tokens=8192)
    claim = "The calibration interval is 30 days for the field instrument [1] [2]."

    report = verify_with_mode(claim, prepared.blocks)
    assert not report.verified

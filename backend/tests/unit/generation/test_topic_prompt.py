"""Student context completeness and honest overflow, independent of a live LLM."""
import json

import pytest

from chat.rag import SourceChunk
from generation.provider_prompt import estimated_tokens, prepare_prompt
from generation.types import AnswerFormat


def paragraph(words, marker="calibration"):
    return " ".join([marker] + ["sensor"] * (words - 2) + ["complete."])


def source(index, content):
    return SourceChunk(f"chunk-{index}", content, .9, "doc-1", "manual.pdf", index,
                       heading_path=("Sensor calibration",), section="Sensor calibration")


def prompt(chunks, marks=AnswerFormat.TEN, context=8192, history=()):
    return prepare_prompt("Explain sensor calibration.", chunks, history, workspace="student",
                          task="answer", answer_format=marks, context_tokens=context)


def source_data(prepared):
    raw = prepared.messages[-1]["content"].split("Source data (JSON):\n", 1)[1]
    return [json.loads(line) for line in raw.splitlines() if line]


@pytest.mark.parametrize("words", [100, 317, 500, 733])
@pytest.mark.parametrize("marks", [AnswerFormat.FIVE, AnswerFormat.TEN, AnswerFormat.FIFTEEN])
def test_variable_length_topic_is_preserved_when_it_fits(words, marks):
    text = paragraph(words)
    prepared = prompt([source(1, text)], marks)
    assert [block.content for block in prepared.blocks] == [text]
    assert prepared.sources[0].content == text
    assert source_data(prepared)[0]["text"] == text
    assert not prepared.blocks[0].truncated
    assert not any("shortened" in warning or "omitted" in warning for warning in prepared.warnings)


def test_a_topic_spanning_more_than_eight_chunks_keeps_every_source_when_it_fits():
    chunks = [source(i, paragraph(45, f"calibration{i}")) for i in range(1, 13)]
    prepared = prompt(chunks)
    assert [block.chunk_id for block in prepared.blocks] == [chunk.chunk_id for chunk in chunks]
    assert [row["text"] for row in source_data(prepared)] == [chunk.content for chunk in chunks]
    assert [row["page"] for row in source_data(prepared)] == list(range(1, 13))
    assert [block.index for block in prepared.blocks] == list(range(1, 13))


def test_unicode_text_metadata_history_and_provider_output_share_a_bounded_context():
    text = ("Sensor calibration uses 測定 and αβγ reference values. " * 250)
    prepared = prompt([source(1, text), source(2, paragraph(200))], context=2048,
                      history=[{"role": "user", "content": "prior question " * 300}])
    prompt_cost = sum(estimated_tokens(message["content"]) + 16 for message in prepared.messages)
    assert prompt_cost + prepared.max_tokens + 256 <= 2048
    assert any("shortened" in warning or "omitted" in warning or "partial" in warning.lower()
               for warning in prepared.warnings)
    assert all(block.content in text or block.content == paragraph(200) for block in prepared.blocks)
    assert all(block.content.rstrip().endswith((".", "!", "?")) for block in prepared.blocks)
    assert [row["text"] for row in source_data(prepared)] == [s.content for s in prepared.sources]

"""Workspace prompts preserve evidence and direct answer depth by mark format.

These checks exercise prompt construction; they do not grade model answers.
"""
import pytest

from chat.rag import SourceChunk
from generation.provider_prompt import estimated_tokens, prepare_prompt
from generation.types import AnswerFormat


def _source():
    return SourceChunk(
        "source-1", "A turbine uses moving air to turn a rotor. The rotor drives a generator to produce electricity.",
        0.9, "document-1", "wind.pdf", 1, heading_path=("Wind power",), section="Wind power",
    )


def _prepare(question, marks, *, workspace="student"):
    return prepare_prompt(question, [_source()], [], workspace=workspace, task="answer",
                          answer_format=marks, context_tokens=20000)


def test_marks_change_guidance_without_discarding_the_supplied_evidence():
    prompts = [_prepare("Explain wind power.", marks) for marks in AnswerFormat]
    system = [result.messages[0]["content"] for result in prompts]
    assert len(set(system)) == 3
    assert "5 marks" in system[0] and "10 marks" in system[1] and "15-mark" in system[2]
    # The shorter format still explains concepts; higher marks add supported depth.
    assert "complete explanations over a list of bare facts" in system[0]
    assert "mechanisms, steps or relationships" in system[1]
    assert "when supported" in system[0] and "when supported" in system[1]
    assert all([block.content for block in result.blocks] == [_source().content] for result in prompts)
    assert prompts[0].max_tokens < prompts[1].max_tokens < prompts[2].max_tokens


@pytest.mark.parametrize("marks", list(AnswerFormat))
def test_multipart_and_missing_evidence_instructions_survive_each_format(marks):
    question = "Explain:\n(a) wind capture\n(b) electricity generation"
    prompt = _prepare(question, marks)
    system = prompt.messages[0]["content"]
    user = prompt.messages[-1]["content"]
    assert "EVIDENCE_GAPS" in system
    assert "parts the sources leave unanswered" in system
    assert "wind capture" in user and "electricity generation" in user
    assert "same line as its claim" in system


@pytest.mark.parametrize("marks", list(AnswerFormat))
def test_diagram_request_keeps_grounding_instructions(marks):
    system = _prepare("Explain wind power with a diagram.", marks).messages[0]["content"]
    assert "diagram" in system
    assert "components and relationships supported" in system
    assert "If the evidence cannot support" in system


def test_research_prompt_is_independent_of_student_mark_format():
    prompts = [_prepare("Explain wind power.", marks, workspace="research") for marks in AnswerFormat]
    assert len({item.messages[0]["content"] for item in prompts}) == 1
    assert len({item.max_tokens for item in prompts}) == 1


@pytest.mark.parametrize(("marks", "previous_limit"), [
    (AnswerFormat.FIVE, 320), (AnswerFormat.TEN, 640), (AnswerFormat.FIFTEEN, 1024),
])
def test_detailed_answers_have_room_beyond_previous_output_ceiling(marks, previous_limit):
    prepared = _prepare("Explain wind power.", marks)
    assert prepared.max_tokens > previous_limit
    assert prepared.max_tokens <= 2048


@pytest.mark.parametrize("marks", list(AnswerFormat))
@pytest.mark.parametrize("context", [2048, 4096, 8192])
def test_more_output_does_not_overflow_context_or_consume_all_evidence(marks, context):
    prepared = prepare_prompt(
        "Explain wind power.", [_source()], [], workspace="student", task="answer",
        answer_format=marks, context_tokens=context,
    )
    assert prepared.blocks, "A larger answer allowance must still leave space for source evidence"
    prompt_cost = sum(estimated_tokens(message["content"]) + 16 for message in prepared.messages)
    assert prompt_cost + prepared.max_tokens + 256 <= context
    assert prepared.blocks[0].content == _source().content

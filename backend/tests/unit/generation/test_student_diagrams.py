"""Regression checks for multipart planning and independent diagram filtering."""
from types import SimpleNamespace

from generation.planning import filter_text_diagrams, text_diagram_blocks
from generation.provider_prompt import asks_for_diagram, student_question_plan
from generation.types import EvidenceBlock


def test_question_plan_preserves_explicit_subtopics():
    question = "Explain with neat diagrams:\n(a) charging a capacitor\n(b) discharging a capacitor"
    command, parts = student_question_plan(question)
    assert command == "explain"
    assert parts == ("charging a capacitor", "discharging a capacitor")
    assert asks_for_diagram(question)


def test_each_figure_is_checked_and_only_invalid_figure_is_removed(monkeypatch):
    monkeypatch.setattr(
        "generation.verification.verify_with_mode",
        lambda *args, **kwargs: SimpleNamespace(verified=True, uncited_claims=0),
    )
    figure = "```text\nSource [1]\n  |\nLoad [1]\n```"
    invalid = "```text\nUnknown [9]\n  |\nLoad [9]\n```"
    answer = f"First explanation [1].\n\n{figure}\n\nSecond explanation [1].\n\n{invalid}"
    clean, retained, omitted = filter_text_diagrams(answer, [EvidenceBlock(1, "source load")])
    assert (retained, omitted) == (1, 1)
    assert text_diagram_blocks(clean) == ["Source [1]\n  |\nLoad [1]"]
    assert "First explanation" in clean and "Second explanation" in clean
    assert "Unknown" not in clean


def test_unclosed_diagram_is_not_retained(monkeypatch):
    answer = "Supported opening [1].\n```text\nSource [1]\nLoad [1]"
    clean, retained, omitted = filter_text_diagrams(answer, [EvidenceBlock(1, "source load")])
    assert (retained, omitted) == (0, 1)
    assert clean == "Supported opening [1]."

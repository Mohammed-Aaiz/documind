"""Follow-up resolution: deterministic, history-aware, never a fact source."""

from __future__ import annotations

from orchestration.followup import (
    MAX_RETRIEVAL_QUERY_CHARS,
    is_followup,
    last_user_question,
    resolve_followup,
)

HISTORY = [
    {"role": "user", "content": "What is the lidar calibration interval?"},
    {"role": "assistant", "content": "Six months [1]."},
]


class TestIsFollowup:
    def test_short_question_is_a_followup(self):
        assert is_followup("And the second one?") is True

    def test_cue_opener_is_a_followup(self):
        assert is_followup("What about the warranty coverage for the sensor module") is True

    def test_standalone_question_is_not_a_followup(self):
        assert (
            is_followup(
                "Which maintenance procedure applies to the lidar array during winter operation?"
            )
            is False
        )

    def test_empty_question_is_not_a_followup(self):
        assert is_followup("   ") is False


class TestResolveFollowup:
    def test_first_turn_is_used_verbatim(self):
        query, resolved = resolve_followup("What is the calibration interval?", [])
        assert query == "What is the calibration interval?"
        assert resolved is False

    def test_followup_includes_the_previous_question(self):
        query, resolved = resolve_followup("And the second one?", HISTORY)
        assert resolved is True
        assert query.startswith("What is the lidar calibration interval?")
        assert query.endswith("And the second one?")

    def test_standalone_question_ignores_history(self):
        question = "Which maintenance procedure applies to the lidar array during winter operation?"
        query, resolved = resolve_followup(question, HISTORY)
        assert query == question
        assert resolved is False

    def test_identical_question_is_not_duplicated(self):
        query, resolved = resolve_followup("What is the lidar calibration interval?", HISTORY)
        assert preview(query) == "What is the lidar calibration interval?"
        assert resolved is False

    def test_query_length_is_bounded(self):
        long_history = [{"role": "user", "content": "x" * 2000}]
        query, resolved = resolve_followup("and more?", long_history)
        assert resolved is True
        assert len(query) <= MAX_RETRIEVAL_QUERY_CHARS

    def test_history_without_a_user_turn_is_ignored(self):
        query, resolved = resolve_followup("and more?", [{"role": "assistant", "content": "text"}])
        assert query == "and more?"
        assert resolved is False


class TestLastUserQuestion:
    def test_skips_assistant_turns(self):
        assert last_user_question(HISTORY) == "What is the lidar calibration interval?"

    def test_empty_history(self):
        assert last_user_question([]) == ""

    def test_accepts_objects_with_role_and_content(self):
        class Turn:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        assert last_user_question([Turn("user", "hello")]) == "hello"


def preview(text: str) -> str:
    return " ".join(text.split())

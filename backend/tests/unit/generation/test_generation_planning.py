"""Planning and prompt construction — deterministic, no model required."""

import pytest

from generation.planning import (
    build_prompt,
    classify_question,
    extract_citations,
    plan_answer,
    split_claims,
)
from generation.types import AnswerFormat, EvidenceBlock


def _block(index=1, text="The lidar array requires calibration every 30 days."):
    return EvidenceBlock(index=index, content=text, document_name="sample.txt")


class TestAnswerFormat:
    def test_marks_map_to_the_three_formats(self):
        assert AnswerFormat.coerce(5).marks == 5
        assert AnswerFormat.coerce("10").marks == 10
        assert AnswerFormat.coerce(15).marks == 15

    def test_default_is_ten_marks(self):
        assert AnswerFormat.coerce(None) == AnswerFormat.TEN

    def test_unknown_format_is_rejected(self):
        with pytest.raises(ValueError):
            AnswerFormat.coerce("7")


class TestClassification:
    @pytest.mark.parametrize(
        "question,expected",
        [
            ("What is pgvector?", "definition"),
            ("Compare semantic and structural retrieval", "comparison"),
            ("Calculate the calibration interval", "derivation"),
            ("How does the structural path work?", "process"),
            ("List the retrieval paths", "enumeration"),
            ("Why does the gate abstain?", "explanation"),
        ],
    )
    def test_question_type(self, question, expected):
        assert classify_question(question) == expected


class TestPlan:
    def test_marks_change_depth_not_claim(self):
        five = plan_answer("What is pgvector?", 5)
        fifteen = plan_answer("What is pgvector?", 15)
        assert five.marks == 5 and fifteen.marks == 15
        assert five.max_new_tokens < fifteen.max_new_tokens
        # No directive may promise a word count.
        for directive in (*five.directives, *fifteen.directives):
            assert "words" not in directive.lower()

    def test_plan_is_deterministic(self):
        assert plan_answer("Compare A and B", 10) == plan_answer("Compare A and B", 10)


class TestPrompt:
    def test_evidence_is_numbered_and_question_precedes_context(self):
        prompt = build_prompt("How often?", plan_answer("How often?", 5), [_block(), _block(2)])
        assert prompt.startswith("Question: How often?")
        assert "Context:" in prompt
        assert "[1] (sample.txt)" in prompt and "[2] (sample.txt)" in prompt
        assert prompt.rstrip().endswith("Answer in one sentence:")

    def test_abstention_marker_is_absent_from_the_prompt(self):
        # The model is not asked to emit a marker it rarely produces; abstention
        # is decided by verification (see test_generation_service).
        prompt = build_prompt("How often?", plan_answer("How often?", 10), [_block()])
        assert "INSUFFICIENT_EVIDENCE" not in prompt


class TestCitations:
    def test_extract_and_dedupe(self):
        assert extract_citations("A [2]. B [1][2].") == [2, 1]

    def test_split_claims_handles_lists(self):
        claims = split_claims("- First point.\n- Second point!")
        assert claims == ["First point.", "Second point!"]


class TestSplitClaimsRobustness:
    """What the splitter must not break (the evaluation depends on these)."""

    def test_decimal_and_currency_stay_in_one_claim(self):
        assert split_claims("Revenue was $4.2 million.") == ["Revenue was $4.2 million."]

    def test_two_real_sentences_are_split(self):
        assert split_claims("Revenue reached $8.3M. It grew 9.7 percent.") == [
            "Revenue reached $8.3M.",
            "It grew 9.7 percent.",
        ]

    def test_table_lines_are_kept_as_separate_pieces(self):
        answer = (
            "Variable | Unit | Min | Max | Mean | Missing %\n"
            "Wind Speed | m/s | 0.0 | 58.4 | 4.2 | 0.2%"
        )
        assert split_claims(answer) == [
            "Variable | Unit | Min | Max | Mean | Missing %",
            "Wind Speed | m/s | 0.0 | 58.4 | 4.2 | 0.2%",
        ]

    def test_honorific_is_not_a_sentence_boundary(self):
        assert split_claims("Dr. Sarah Chen is the CEO.") == ["Dr. Sarah Chen is the CEO."]

    def test_honorific_does_not_merge_a_following_sentence(self):
        assert split_claims(
            "Dr. Sarah Chen joined the organization. She later became its CEO."
        ) == [
            "Dr. Sarah Chen joined the organization.",
            "She later became its CEO.",
        ]

    def test_country_initialism_is_not_a_sentence_boundary(self):
        assert split_claims("The U.S. team completed the review.") == [
            "The U.S. team completed the review."
        ]

    def test_initialism_does_not_merge_a_following_sentence(self):
        assert split_claims("The system uses U.S. standards. The report describes the results.") == [
            "The system uses U.S. standards.",
            "The report describes the results.",
        ]

    def test_latin_abbreviation_is_not_a_sentence_boundary(self):
        assert split_claims("The value is approximately 3.5, e.g., 3.5 units per second.") == [
            "The value is approximately 3.5, e.g., 3.5 units per second."
        ]
        assert split_claims("e.g. 3.5 units were recorded.") == ["e.g. 3.5 units were recorded."]

    def test_initial_is_not_a_sentence_boundary(self):
        assert split_claims("J. Smith led the audit. It closed in May.") == [
            "J. Smith led the audit.",
            "It closed in May.",
        ]

    def test_dotted_abbreviation_before_a_lowercase_word_is_not_a_boundary(self):
        assert split_claims("Acme Inc. filed the report. It was late.") == [
            "Acme Inc. filed the report.",
            "It was late.",
        ]

    def test_abbreviation_before_a_capital_still_splits(self):
        """``etc.`` can close a sentence; the guard must not merge two claims."""
        assert split_claims("The equipment was checked, etc. Nothing failed.") == [
            "The equipment was checked, etc.",
            "Nothing failed.",
        ]
        assert split_claims("Acme Inc. The report was late.") == [
            "Acme Inc.",
            "The report was late.",
        ]

    def test_unit_suffix_is_not_an_initial(self):
        """``m/s.`` ends a sentence; the capital ``V`` starts the next one."""
        assert split_claims("m/s. Variable | Unit | Min | Max | Mean | Missing % [1]") == [
            "m/s.",
            "Variable | Unit | Min | Max | Mean | Missing % [1]",
        ]

    def test_numeric_values_and_units_survive_splitting(self):
        answer = (
            "Revenue was $142.6 million. It grew 20.3 percent. "
            "The sample lasts 86400 seconds."
        )
        assert split_claims(answer) == [
            "Revenue was $142.6 million.",
            "It grew 20.3 percent.",
            "The sample lasts 86400 seconds.",
        ]

    def test_splitter_neither_drops_nor_duplicates_text(self):
        answer = (
            "Dr. Chen reviewed the U.S. filing, e.g. the 3.5 percent change. "
            "It passed. No claims were lost."
        )
        claims = split_claims(answer)
        assert " ".join(claims) == " ".join(answer.split())
        assert claims == split_claims(answer)  # deterministic

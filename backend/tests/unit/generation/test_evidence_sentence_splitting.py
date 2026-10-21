"""Tests for the evidence-side sentence splitter and the shared abbreviation rule.

The claim splitter and the evidence splitter must agree on what is not a sentence
end.  Mission 2 fixed only the claim side, which made ``Dr. Sarah Chen`` a false
rejection for the relation-aware verifier: the evidence was split into
``CEO: Dr.`` and ``Sarah Chen …``.  These tests pin the corrected behavior.
"""

from generation.sentence_boundaries import is_non_terminal_boundary
from generation.verification import split_sentences


class TestAbbreviationBoundaryRule:
    def test_titles_do_not_end_a_sentence(self):
        assert is_non_terminal_boundary("CEO: Dr.", "Sarah Chen (since 2022)") is True

    def test_initialisms_do_not_end_a_sentence(self):
        assert is_non_terminal_boundary("The U.S.", "team completed it.") is True

    def test_initial_before_a_surname_is_not_a_boundary(self):
        assert is_non_terminal_boundary("J.", "Smith led the audit.") is True

    def test_latin_abbreviations_are_not_boundaries(self):
        assert is_non_terminal_boundary("3.5, e.g.", "3.5 units") is True

    def test_abbreviation_before_a_capital_is_a_boundary(self):
        assert is_non_terminal_boundary("Acme Inc.", "The report was late.") is False

    def test_unit_suffix_is_not_an_initial(self):
        assert is_non_terminal_boundary("m/s.", "Variable | Unit") is False

    def test_ellipsis_is_always_a_boundary(self):
        assert is_non_terminal_boundary("Wait...", "what happened?") is False


class TestEvidenceSentences:
    def test_dr_sarah_chen_stays_together(self):
        assert split_sentences("CEO: Dr. Sarah Chen (since January 2022)") == [
            "CEO: Dr. Sarah Chen (since January 2022)"
        ]

    def test_country_initialism_stays_together(self):
        assert split_sentences("The U.S. team completed the review. It passed.") == [
            "The U.S. team completed the review.",
            "It passed.",
        ]

    def test_initial_stays_with_the_surname(self):
        assert split_sentences("J. Smith led the audit. It closed in May.") == [
            "J. Smith led the audit.",
            "It closed in May.",
        ]

    def test_corporate_suffix_before_a_lowercase_word_stays_together(self):
        assert split_sentences("Acme Inc. filed the report. It was late.") == [
            "Acme Inc. filed the report.",
            "It was late.",
        ]

    def test_corporate_suffix_before_a_capital_ends_the_sentence(self):
        assert split_sentences("Acme Inc. The report was late.") == [
            "Acme Inc.",
            "The report was late.",
        ]

    def test_latin_abbreviation_does_not_split(self):
        assert split_sentences(
            "The value is approximately 3.5, e.g., 3.5 units per second."
        ) == ["The value is approximately 3.5, e.g., 3.5 units per second."]
        assert split_sentences("Use the first option, i.e. the default.") == [
            "Use the first option, i.e. the default."
        ]

    def test_ordinary_sentences_still_split(self):
        assert split_sentences("The model is accurate. The report confirms it.") == [
            "The model is accurate.",
            "The report confirms it.",
        ]

    def test_sentence_ending_abbreviation_still_splits(self):
        assert split_sentences("The equipment was checked, etc. Nothing failed.") == [
            "The equipment was checked, etc.",
            "Nothing failed.",
        ]

    def test_numbers_currency_percentages_and_units_survive(self):
        text = (
            "Revenue was $142.6 million. It grew 20.3 percent. "
            "The sample lasts 86400 seconds."
        )
        assert split_sentences(text) == [
            "Revenue was $142.6 million.",
            "It grew 20.3 percent.",
            "The sample lasts 86400 seconds.",
        ]

    def test_table_rows_keep_their_lines(self):
        text = "Variable | Unit | Min | Max\nWind Speed | m/s | 0.0 | 58.4"
        assert split_sentences(text) == [
            "Variable | Unit | Min | Max",
            "Wind Speed | m/s | 0.0 | 58.4",
        ]

    def test_line_wrapped_sentence_continues(self):
        assert split_sentences("The lidar array requires\ncalibration every 30 days.") == [
            "The lidar array requires calibration every 30 days."
        ]

    def test_empty_and_whitespace_input_is_safe(self):
        assert split_sentences("") == []
        assert split_sentences("   \n  ") == []

    def test_text_and_order_are_preserved(self):
        text = (
            "CEO: Dr. Sarah Chen (since 2022). The U.S. team reviewed it. "
            "J. Smith signed off."
        )
        pieces = split_sentences(text)
        assert " ".join(pieces) == " ".join(text.split())
        assert pieces == split_sentences(text)  # deterministic

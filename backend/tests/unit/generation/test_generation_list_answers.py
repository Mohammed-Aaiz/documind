"""Ordered-list resolution and list membership in the entity check.

Pinned behaviours (Mission 7, 2026-10-21).  Each corresponds to a measured
failure on the frozen P3 benchmark:

* the generative engine answered 2 of 20 ``LIST_ITEM`` questions correctly — it
  returned the wrong item, a truncated item, or two concatenated items;
* ten correct items were withheld because the entity check anchored on the list
  *heading* and required the heading's words inside the item;
* three more were withheld because the claim splitter fragments citation lines
  (``R.T. (2025).``, ``45-67. DOI:``) and the fragments were compared to
  sentences rather than to the list's items.
"""

import pytest

from generation import service
from generation.lists import parse_lists, requested_position, resolve_list_answer
from generation.types import EvidenceBlock
from generation.verification import check_claim

LEADERSHIP = (
    "Current Leadership\n"
    "CEO: Dr. Sarah Chen (since January 2022)\n"
    "CTO: James Whitfield (co-founder, since 1998)\n"
    "CFO: Robert Tanaka (since March 2019)\n"
    "COO: Elena Vasquez (since June 2021)"
)

FINANCIALS = (
    "Key Financial Highlights\n"
    "Revenue: $847.3 million (+12.4% YoY)\n"
    "Net Income: $142.6 million (+20.6% YoY)\n"
    "EPS (Diluted): $3.47\n"
    "Operating Margin: 22.1%\n"
    "Free Cash Flow: $189.4 million"
)

CITATION = (
    "Citation\n"
    "Smith, J.A., Johnson, M.K., and Williams, R.T. (2025).\n"
    "GeoClimate-2024: A Comprehensive Meteorological Dataset for the Continental United States.\n"
    "Journal of Climate Data, 12(3), 45-67. DOI: 10.1234/jcd.2025.0123"
)


def _block(content: str, index: int = 1) -> EvidenceBlock:
    return EvidenceBlock(index=index, content=content, document_name="report.pdf")


class _Chunk:
    def __init__(self, content: str) -> None:
        self.chunk_id = "chunk-1"
        self.content = content
        self.score = 0.0
        self.document_id = "doc"
        self.document_name = "report.pdf"
        self.page = None
        self.heading_path = None
        self.section = None


class TestParseLists:
    def test_heading_and_items_are_recovered(self):
        blocks = parse_lists(LEADERSHIP)
        assert len(blocks) == 1
        assert blocks[0].heading == "Current Leadership"
        assert len(blocks[0].items) == 4

    def test_prose_paragraphs_are_not_a_list(self):
        text = "The lidar array requires calibration every 30 days.\n\nThe power rail runs at 12 volts."
        assert parse_lists(text) == []

    def test_blank_line_ends_the_list(self):
        text = "Permitted Uses\nInternal analysis\nInternal reporting\n\nSome unrelated paragraph."
        blocks = parse_lists(text)
        assert len(blocks) == 1 and len(blocks[0].items) == 2

    def test_a_table_is_not_a_list(self):
        table = "Tier | Rate Limit\nStandard | 100 req/min"
        assert parse_lists(table) == []

    def test_a_label_with_terminal_punctuation_is_not_a_heading(self):
        assert parse_lists("Revenue: $847.3 million\nNet Income: $142.6 million") == []

    def test_single_item_run_is_not_a_list(self):
        assert parse_lists("Citation\nSmith, J.A. (2025).") == []


class TestRequestedPosition:
    @pytest.mark.parametrize(
        "question,expected",
        [
            ("What citation is listed second?", 2),
            ("What comes first in the citation?", 1),
            ("Name the fifth key financial highlights?", 5),
            ("What key financial highlights is listed eighth?", 8),
            ("What is the last permitted use?", -1),
        ],
    )
    def test_ordinals_are_recognised(self, question, expected):
        assert requested_position(question) == expected

    def test_no_ordinal_is_none(self):
        assert requested_position("Which key financial highlights handles cash?") is None

    def test_two_ordinals_are_ambiguous(self):
        assert requested_position("What is the first and third permitted use?") is None


class TestResolveListAnswer:
    def test_positional_question_returns_that_item_verbatim(self):
        answer = resolve_list_answer("What is the fourth current leadership?", [_block(LEADERSHIP)])
        assert answer is not None
        assert answer.text == "COO: Elena Vasquez (since June 2021)"
        assert answer.position == 4
        assert answer.matched_by == "position"

    def test_item_is_not_truncated_to_its_value(self):
        """The model answered ``Elena Vasquez``; the item carries the role and date."""
        answer = resolve_list_answer("What is the fourth current leadership?", [_block(LEADERSHIP)])
        assert answer is not None
        assert "COO" in answer.text and "June 2021" in answer.text

    def test_first_item_of_a_citation_list(self):
        answer = resolve_list_answer("What comes first in the citation?", [_block(CITATION)])
        assert answer is not None
        assert answer.text == "Smith, J.A., Johnson, M.K., and Williams, R.T. (2025)."

    def test_last_item_resolves_to_the_end_of_the_list(self):
        answer = resolve_list_answer("What is the last key financial highlight?", [_block(FINANCIALS)])
        assert answer is not None
        assert answer.text == "Free Cash Flow: $189.4 million"

    def test_position_beyond_the_list_abstains(self):
        assert resolve_list_answer("What is the ninth key financial highlight?", [_block(FINANCIALS)]) is None

    def test_content_question_selects_the_named_item(self):
        answer = resolve_list_answer(
            "Which current leadership handles cfo: robert tanaka?", [_block(LEADERSHIP)]
        )
        assert answer is not None
        assert answer.text == "CFO: Robert Tanaka (since March 2019)"
        assert answer.matched_by == "content"

    def test_content_match_requires_a_unique_best_item(self):
        """Two items share every question term, so the choice is ambiguous.

        The heading must actually be named by the question, otherwise the test
        would pass before the tie logic ran (a vacuous pass).
        """
        ambiguous = "Options\nInternal data analysis\nInternal data reporting"
        question = "Which option is internal data?"
        blocks = parse_lists(ambiguous)
        assert blocks and blocks[0].heading == "Options"
        assert resolve_list_answer(question, [_block(ambiguous)]) is None

    def test_heading_must_be_named_by_the_question(self):
        """A question about something else is not answered from a nearby list."""
        assert resolve_list_answer("What is the second employee count?", [_block(LEADERSHIP)]) is None

    def test_two_positions_in_one_question_abstain(self):
        """"the first and third" cannot be answered with one item."""
        assert resolve_list_answer("What is the first and third permitted use?", [_block(LEADERSHIP)]) is None

    def test_a_truncated_block_never_answers_a_position(self):
        """The excerpt dropped the tail, so position 2 may not be position 2."""
        block = EvidenceBlock(
            index=1, content=LEADERSHIP, document_name="report.pdf", truncated=True
        )
        assert resolve_list_answer("What is the second current leadership?", [block]) is None

    def test_a_truncated_block_can_still_answer_a_content_question(self):
        block = EvidenceBlock(
            index=1, content=LEADERSHIP, document_name="report.pdf", truncated=True
        )
        answer = resolve_list_answer("Which current leadership handles cfo: robert tanaka?", [block])
        assert answer is not None
        assert answer.text == "CFO: Robert Tanaka (since March 2019)"

    def test_wrong_item_is_never_returned_for_a_position(self):
        answer = resolve_list_answer("What citation is listed third?", [_block(CITATION)])
        assert answer is not None
        assert "Journal of Climate Data" in answer.text
        assert "Smith" not in answer.text


class TestListMembershipVerification:
    """A correct item must not be rejected because the heading is not in it."""

    def test_item_is_supported_by_its_own_list(self):
        check = check_claim(
            "COO: Elena Vasquez (since June 2021)",
            [_block(LEADERSHIP)],
            question="What is the fourth current leadership?",
        )
        assert check.supported is True

    def test_fragmented_citation_piece_is_supported(self):
        """The splitter turns ``R.T. (2025).`` into two claims; both are in item 1."""
        block = _block(CITATION)
        for fragment in (
            "Smith, J.A., Johnson, M.K., and Williams, R.T.",
            "(2025).",
        ):
            assert check_claim(fragment, [block], question="What comes first in the citation?").supported

    def test_doi_fragment_is_supported(self):
        check = check_claim(
            "DOI: 10.1234/jcd.2025.0123",
            [_block(CITATION)],
            question="What citation is listed third?",
        )
        assert check.supported is True

    def test_value_outside_the_named_list_is_still_rejected(self):
        """The loosening is membership in the *named* list, not presence anywhere."""
        check = check_claim(
            "Revenue: $847.3 million",
            [_block(LEADERSHIP)],
            question="What is the fourth current leadership?",
        )
        assert check.supported is False


class TestListAnswerThroughTheService:
    def test_list_lookup_does_not_call_the_model(self, monkeypatch):
        calls = []

        def _boom(*args, **kwargs):
            calls.append(1)
            raise AssertionError("the model must not be called for a list lookup")

        monkeypatch.setattr(service, "generate", _boom)
        result = service.answer_generatively(
            "What is the third key financial highlights?", [_Chunk(FINANCIALS)], answer_format="10"
        )
        assert calls == []
        assert result.answer == "EPS (Diluted): $3.47"
        assert result.model == service.DETERMINISTIC_LIST_ENGINE
        assert result.verification["verified"] is True

    def test_list_answer_is_not_elaborated(self, monkeypatch):
        monkeypatch.setattr(service, "generate", lambda *a, **k: None)
        result = service.answer_generatively(
            "Name the fifth key financial highlights?", [_Chunk(FINANCIALS)], answer_format="15"
        )
        assert result.answer == "Free Cash Flow: $189.4 million"

    def test_unresolved_list_falls_back_to_generation(self, monkeypatch):
        from generation.types import GenerationResult, VerificationReport

        report = VerificationReport(claims=[], supported_claims=1, verified=True, status="SUPPORTED")
        monkeypatch.setattr(
            service,
            "generate",
            lambda *a, **k: GenerationResult(
                answer="Elena Vasquez", abstained=False, verification=report,
                model="test-model", marks=10, latency_ms=1,
            ),
        )
        result = service.answer_generatively(
            "What is the seventh current leadership?", [_Chunk(LEADERSHIP)]
        )
        assert result.model == "test-model"

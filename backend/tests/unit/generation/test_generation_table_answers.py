"""Table grounding, stopword claims and the fiscal-year gate normalisation.

Pinned behaviours (Mission 6, 2026-10-21).  Each corresponds to a measured
failure on the frozen P3 benchmark:

* the generative engine answered **0 of 40** table questions correctly, so a
  row/column lookup is resolved from the table instead of guessed;
* a one-word answer that is a stopword (``Other``) could never be verified;
* ``FY2024`` was counted as two absent question terms against evidence that
  says "fiscal year 2024";
* a table header render was appended to a complete answer as a "supporting
  point", and an echoed prompt marker leaked into the answer text.
"""

import pytest

from generation import service
from generation.engine import _clean_output
from generation.planning import is_propositional, plan_support_points
from generation.tables import parse_tables, resolve_table_answer
from generation.types import EvidenceBlock
from generation.verification import answerability, check_claim

RATE_TABLE = (
    "Tier | Rate Limit | Burst Limit | Monthly Quota\n"
    "Standard | 100 req/min | 150 req/min | 500,000 requests\n"
    "Premium | 1,000 req/min | 1,500 req/min | 5,000,000 requests"
)

YEAR_TABLE = (
    "Year | Revenue (USD) | Employees | Key Milestone\n"
    "2010 | $178.0M | 650 | Revenue exceeds $150M\n"
    "2006 | $52.1M | 280 | IPO on NASDAQ"
)

WEATHER_TABLE = (
    "Variable | Unit | Min | Max | Mean | Missing %\n"
    "Pressure | hPa | 954.2 | 1083.8 | 1013.2 | 0.1%\n"
    "Precipitation | mm | 0.0 | 127.3 | 0.8 | 1.2%"
)

DIVISION_TABLE = (
    "Division | Q3 2025 Revenue | Q3 2024 Revenue | YoY Growth\n"
    "Professional Services | $147.7M | $141.8M | +4.2%\n"
    "Other | $0.0M | $1.6M | -100.0%"
)


def _block(content: str, index: int = 1) -> EvidenceBlock:
    return EvidenceBlock(index=index, content=content, document_name="report.pdf")


class _Chunk:
    """Minimal SourceChunk-shaped evidence record."""

    def __init__(self, content: str) -> None:
        self.chunk_id = "chunk-1"
        self.content = content
        self.score = 0.0
        self.document_id = "doc"
        self.document_name = "report.pdf"
        self.page = None
        self.heading_path = None
        self.section = None


class TestParseTables:
    def test_header_and_rows_are_recovered(self):
        tables = parse_tables(RATE_TABLE)
        assert len(tables) == 1
        assert tables[0].header[0] == "Tier"
        assert len(tables[0].rows) == 2

    def test_prose_without_pipes_is_not_a_table(self):
        assert parse_tables("The lidar array requires calibration every 30 days.") == []

    def test_unequal_width_row_is_not_a_table_row(self):
        text = "A | B | C\n1 | 2 | 3\n4 | 5"
        tables = parse_tables(text)
        assert len(tables) == 1
        assert len(tables[0].rows) == 1


class TestResolveTableAnswer:
    def test_cell_uses_the_requested_column(self):
        """The reported defect: 'employees for 2010' answered 'Revenue exceeds $150M'."""
        answer = resolve_table_answer("What is the employees for 2010?", [_block(YEAR_TABLE)])
        assert answer is not None
        assert answer.text == "650"
        assert answer.kind == "cell"
        assert answer.column == "Employees"

    def test_cell_is_never_a_neighbouring_column_value(self):
        answer = resolve_table_answer("What is the employees for 2010?", [_block(YEAR_TABLE)])
        assert answer is not None
        assert "Revenue exceeds" not in answer.text
        assert "$178.0M" not in answer.text

    def test_cell_resolves_a_dollar_prefixed_header(self):
        answer = resolve_table_answer(
            "According to the table, what is the revenue (usd) for 2010?", [_block(YEAR_TABLE)]
        )
        assert answer is not None
        assert answer.text == "$178.0M"

    def test_row_question_returns_the_whole_row(self):
        answer = resolve_table_answer(
            "What are all the values for Pressure?", [_block(WEATHER_TABLE)]
        )
        assert answer is not None
        assert answer.kind == "row"
        assert answer.text == "Pressure | hPa | 954.2 | 1083.8 | 1013.2 | 0.1%"

    def test_information_row_question_returns_the_whole_row(self):
        answer = resolve_table_answer(
            "What information is recorded for Premium?", [_block(RATE_TABLE)]
        )
        assert answer is not None
        assert answer.text == "Premium | 1,000 req/min | 1,500 req/min | 5,000,000 requests"

    def test_row_label_that_is_a_stopword_still_resolves(self):
        answer = resolve_table_answer(
            "Looking at the table, what division value does Other show?",
            [_block(DIVISION_TABLE)],
        )
        assert answer is not None
        assert answer.text == "Other"

    def test_unknown_row_abstains(self):
        assert resolve_table_answer("What is the employees for 1999?", [_block(YEAR_TABLE)]) is None

    def test_non_lookup_question_abstains(self):
        """Naming a header term is not asking for a lookup."""
        assert resolve_table_answer("Where is the Premium tier described?", [_block(RATE_TABLE)]) is None
        assert resolve_table_answer("When was the Premium tier added?", [_block(RATE_TABLE)]) is None

    def test_ambiguous_column_abstains(self):
        table = "Name | Value A | Value B\nWidget | 1 | 2"
        assert resolve_table_answer("What is the value for Widget?", [_block(table)]) is None

    def test_row_question_without_a_value_cue_abstains(self):
        """No column resolves and the question does not ask for the row."""
        assert resolve_table_answer("Where is the Premium tier described?", [_block(RATE_TABLE)]) is None

    def test_prose_evidence_is_never_tabularised(self):
        assert resolve_table_answer("How often is the lidar calibrated?", [_block(
            "The lidar array requires calibration every 30 days."
        )]) is None

    def test_citation_is_the_block_the_table_came_from(self):
        answer = resolve_table_answer(
            "What is Premium's rate limit?",
            [_block("Unrelated prose.", index=1), _block(RATE_TABLE, index=2)],
        )
        assert answer is not None
        assert answer.citation == 2


class TestTableAnswerThroughTheService:
    def test_table_lookup_does_not_call_the_model(self, monkeypatch):
        calls = []

        def _boom(*args, **kwargs):
            calls.append(1)
            raise AssertionError("the model must not be called for a table lookup")

        monkeypatch.setattr(service, "generate", _boom)
        result = service.answer_generatively(
            "How much is the monthly quota of Standard?", [_Chunk(RATE_TABLE)], answer_format="10"
        )
        assert calls == []
        assert result.answer == "500,000 requests"
        assert result.model == service.DETERMINISTIC_TABLE_ENGINE
        assert result.abstained is False
        assert result.verification["verified"] is True

    def test_table_answer_is_not_padded_with_further_evidence(self, monkeypatch):
        monkeypatch.setattr(service, "generate", lambda *a, **k: None)
        result = service.answer_generatively(
            "What are all the values for Pressure?", [_Chunk(WEATHER_TABLE)], answer_format="15"
        )
        assert result.answer == "Pressure | hPa | 954.2 | 1083.8 | 1013.2 | 0.1%"

    def test_unresolved_question_falls_back_to_generation(self, monkeypatch):
        from generation.types import GenerationResult, VerificationReport

        report = VerificationReport(
            claims=[], supported_claims=1, verified=True, status="SUPPORTED"
        )
        monkeypatch.setattr(
            service,
            "generate",
            lambda *a, **k: GenerationResult(
                answer="30 days", abstained=False, verification=report,
                model="test-model", marks=10, latency_ms=1,
            ),
        )
        result = service.answer_generatively(
            "How often is the lidar calibrated?",
            [_Chunk("The lidar array requires calibration every 30 days.")],
        )
        assert result.model == "test-model"
        assert result.answer.startswith("30 days")


class TestStopwordClaims:
    def test_single_stopword_answer_is_verifiable(self):
        """``Other`` is a real gold answer for a division table row."""
        check = check_claim("Other", [_block("Other | $0.0M | $1.6M | -100.0%")])
        assert check.supported is True

    def test_stopword_absent_from_evidence_is_still_rejected(self):
        check = check_claim("Other", [_block("Standard | 100 req/min | 150 req/min")])
        assert check.supported is False


class TestFiscalYearGate:
    def test_fiscal_year_notation_is_not_a_missing_term(self):
        decision = answerability(
            "What is the current FY2024 revenue?",
            "Annual revenue of $1.24 billion for fiscal year 2024",
        )
        assert decision.allowed is True
        assert "2024" not in decision.missing

    def test_fiscal_year_does_not_rescue_an_unrelated_question(self):
        decision = answerability(
            "What is the FY2024 carbon offset of the Tokyo office?",
            "Annual revenue of $1.24 billion for fiscal year 2024",
        )
        assert decision.allowed is False


class TestNonPropositionalElaboration:
    def test_table_header_is_not_propositional(self):
        assert is_propositional("Tier | Rate Limit | Burst Limit | Monthly Quota") is False
        assert is_propositional("The lidar array requires calibration every 30 days.") is True

    def test_table_render_is_not_added_as_a_support_point(self):
        block = _block("The lidar array requires calibration every 30 days. Tier | Rate Limit")
        points = plan_support_points("How often is the lidar calibrated?", [block], 15)
        assert all("|" not in point.text for point in points)


class TestEchoedPromptMarker:
    def test_echoed_evidence_prefix_is_removed(self):
        assert _clean_output("[1] (benchmark-context) Revenue: $847.3 million") == (
            "Revenue: $847.3 million"
        )

    def test_an_inline_citation_is_preserved(self):
        assert _clean_output("Revenue was $847.3 million [1].") == "Revenue was $847.3 million [1]."

    def test_a_marker_only_answer_becomes_empty(self):
        assert _clean_output("[1] (report.pdf)") == ""

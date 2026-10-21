"""The Phase 3 table-evidence gate, row selection and band ordering.

These are pure-logic tests: no database, no model, no I/O.  They pin the two
properties the design depends on:

* a question only activates table evidence when it names a persisted table
  *dimension* (a header cell) — a question whose words merely appear inside a
  cell must not activate anything;
* when the gate is closed, or nothing matches, or a row is oversized, the
  function returns no evidence at all, so the evidence stream (and therefore the
  QA context) is exactly what it was before the band existed.

The fixture table is generic product vocabulary; no demo document strings,
ids, page numbers or row indices appear in the production code under test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from chat.rag import (
    EVIDENCE_KIND_TABLE_ROW,
    TABLE_EVIDENCE_ENV,
    order_evidence_bands,
    select_table_row_evidence,
    table_evidence_enabled,
    table_gate_open,
)
from graph.service import terms_from_question

DOC_A = "11111111-1111-1111-1111-111111111111"
TABLE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOC_B = "22222222-2222-2222-2222-222222222222"
TABLE_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

HEADER = ("Part", "Service Interval", "Wear Limit")

#: A question about a table dimension ("service interval") and a row label.
GATE_OPEN_QUESTION = "What service interval does the manual give for pump A?"
#: A question that merely contains a word from a cell ("pump") and a word that
#: shares a stem with a header ("service" from "servicing") but never names a
#: header dimension — the Q3-shaped trap.
GATE_CLOSED_QUESTION = "Which power rail supplies the pump controller servo unit?"


@dataclass
class Row:
    """Stand-in for a persisted ``document_table_rows`` record."""

    document_id: str
    table_element_id: str
    row_index: int
    cells: list[str]
    content: str
    is_header: bool = False
    header_repeated: bool = True
    page_number: int | None = 3
    heading_path: list[str] | None = field(default_factory=lambda: ["Section Seven"])
    section: str | None = "Section Seven"
    token_count: int | None = None
    header_repeated_flag: bool | None = None

    def __post_init__(self) -> None:
        if self.token_count is None:
            self.token_count = max(1, len(self.content) // 4)


def _table_rows(
    document_id: str = DOC_A, table_element_id: str = TABLE_A
) -> list[Row]:
    """Header row + two body rows, each with the header repeated."""
    header = " | ".join(HEADER)
    return [
        Row(
            document_id=document_id,
            table_element_id=table_element_id,
            row_index=0,
            cells=list(HEADER),
            content=header,
            is_header=True,
            header_repeated=False,
        ),
        Row(
            document_id=document_id,
            table_element_id=table_element_id,
            row_index=1,
            cells=["Pump A", "250 h", "2.5 mm"],
            content=f"{header}\nPump A | 250 h | 2.5 mm",
        ),
        Row(
            document_id=document_id,
            table_element_id=table_element_id,
            row_index=2,
            cells=["Valve C", "500 h", "1.0 mm"],
            content=f"{header}\nValve C | 500 h | 1.0 mm",
        ),
    ]


class TestGate:
    def test_two_terms_of_a_multi_word_header_open_the_gate(self):
        terms = terms_from_question(GATE_OPEN_QUESTION)

        assert "service" in terms and "interval" in terms
        assert table_gate_open([list(HEADER)], terms) is True

    def test_a_single_shared_term_does_not_open_the_gate(self):
        """Q3-shaped: shares a stem with a header but names no dimension."""
        terms = terms_from_question(GATE_CLOSED_QUESTION)

        assert "service" not in terms, "fixture assumption drifted"
        assert table_gate_open([list(HEADER)], terms) is False

    def test_a_word_that_only_appears_in_a_cell_does_not_open_the_gate(self):
        rows = _table_rows()
        terms = terms_from_question("Which pump unit needs servicing first?")

        assert "pump" in terms
        assert table_gate_open([r.cells for r in rows if r.is_header], terms) is False

    def test_single_word_header_is_matched_by_that_word(self):
        terms = terms_from_question("Which component is the spare?")

        assert table_gate_open([["Component", "Notes"]], terms) is True

    def test_empty_headers_or_no_terms_never_open(self):
        assert table_gate_open([], terms_from_question(GATE_OPEN_QUESTION)) is False
        assert table_gate_open([list(HEADER)], []) is False

    def test_gate_is_deterministic(self):
        terms = terms_from_question(GATE_OPEN_QUESTION)

        assert {table_gate_open([list(HEADER)], terms) for _ in range(5)} == {True}


class TestSelection:
    def test_gate_open_selects_the_matching_row_with_full_provenance(self):
        selected = select_table_row_evidence(
            _table_rows(),
            question=GATE_OPEN_QUESTION,
            document_names={DOC_A: "manual.pdf"},
        )

        assert len(selected) == 1
        row = selected[0]
        assert row.evidence_kind == EVIDENCE_KIND_TABLE_ROW
        assert row.chunk_id == f"{EVIDENCE_KIND_TABLE_ROW}:{TABLE_A}:1"
        assert row.table_element_id == TABLE_A
        assert row.row_index == 1
        assert row.header_repeated is True
        assert row.document_id == DOC_A
        assert row.document_name == "manual.pdf"
        assert row.page == 3
        assert row.section == "Section Seven"
        assert row.heading_path == ("Section Seven",)
        assert row.element_type == "table"
        assert row.retrieval_path == "structural"
        assert row.score == 0.0, "table evidence must never carry a similarity"
        assert row.fusion_score is None, "table evidence must never enter RRF"
        assert row.content.startswith("Part | Service Interval | Wear Limit\n")
        assert row.content.endswith("Pump A | 250 h | 2.5 mm")

    def test_gate_closed_selects_nothing_even_when_a_cell_matches(self):
        selected = select_table_row_evidence(
            _table_rows(), question=GATE_CLOSED_QUESTION
        )

        assert selected == []

    def test_selection_order_is_deterministic_under_input_reordering(self):
        rows = _table_rows()

        forward = select_table_row_evidence(
            rows, question=GATE_OPEN_QUESTION
        )
        backward = select_table_row_evidence(
            list(reversed(rows)), question=GATE_OPEN_QUESTION
        )

        assert [c.chunk_id for c in forward] == [c.chunk_id for c in backward]

    def test_label_matches_exclude_rows_that_only_share_a_cell_word(self):
        """A question that names a row is about that row, not every row sharing a
        word with it — the band stays narrow and deterministic."""
        header = "Part | Service Interval"
        rows = [
            Row(DOC_A, TABLE_A, 0, ["Part", "Service Interval"], header, is_header=True),
            Row(DOC_A, TABLE_A, 1, ["Pump B", "250 h"], f"{header}\nPump B | 250 h"),
            Row(
                DOC_A,
                TABLE_A,
                2,
                ["Filter Cartridge", "Pump seal 250 h"],
                f"{header}\nFilter Cartridge | Pump seal 250 h",
            ),
        ]

        selected = select_table_row_evidence(
            rows, question="What service interval applies to pump B on the 250 h line?"
        )

        assert [c.row_index for c in selected] == [1], (
            "only the row whose own label matches may be offered"
        )

    def test_cell_matches_rank_by_match_count_when_no_row_label_matches(self):
        """Fallback: with no row label matching, a question that names a value still
        reaches the row holding it, and the better cell match is offered first."""
        header = "Part | Service Interval"
        rows = [
            Row(DOC_A, TABLE_A, 0, ["Part", "Service Interval"], header, is_header=True),
            Row(DOC_A, TABLE_A, 1, ["Pump B", "250 h"], f"{header}\nPump B | 250 h"),
            Row(
                DOC_A,
                TABLE_A,
                2,
                ["Filter Cartridge", "Pump seal 250 h"],
                f"{header}\nFilter Cartridge | Pump seal 250 h",
            ),
        ]
        question = "Which service interval is listed for the 250 h shaft seal?"

        assert table_gate_open([list(HEADER)], terms_from_question(question)) is True
        selected = select_table_row_evidence(rows, question=question, max_rows=1)

        # "Filter Cartridge" matches no question term, so the only row that matches
        # is reached through its cells.
        assert [c.row_index for c in selected] == [2]

    def test_row_and_table_bounds_are_enforced(self):
        rows = _table_rows() + [
            Row(DOC_B, TABLE_B, 1, ["Pump A", "250 h", "9 mm"],
                "Part | Service Interval\nPump A | 250 h | 9 mm"),
        ]

        assert len(
            select_table_row_evidence(rows, question=GATE_OPEN_QUESTION, max_rows=1)
        ) == 1
        selected = select_table_row_evidence(
            rows, question=GATE_OPEN_QUESTION, max_tables=1
        )
        assert {c.table_element_id for c in selected} == {TABLE_A}

    def test_oversized_row_is_skipped_whole_never_truncated(self):
        header = "Part | Service Interval"
        oversized = "x" * 4000
        rows = [
            Row(DOC_A, TABLE_A, 0, ["Part", "Service Interval"], header, is_header=True),
            Row(
                DOC_A,
                TABLE_A,
                1,
                ["Pump A", oversized],
                f"{header}\nPump A | {oversized}",
                token_count=9999,
            ),
        ]

        selected = select_table_row_evidence(rows, question=GATE_OPEN_QUESTION)

        assert selected == [], "an oversized row must be dropped, not clipped"

    def test_missing_or_blank_content_is_never_invented(self):
        header = "Part | Service Interval"
        rows = [
            Row(DOC_A, TABLE_A, 0, ["Part", "Service Interval"], header, is_header=True),
            Row(DOC_A, TABLE_A, 1, ["Pump A", "250 h"], ""),
        ]

        assert select_table_row_evidence(rows, question=GATE_OPEN_QUESTION) == []

    def test_selected_content_is_exactly_the_persisted_row(self):
        rows = _table_rows()

        selected = select_table_row_evidence(rows, question=GATE_OPEN_QUESTION)

        persisted = next(r for r in rows if r.row_index == 1)
        assert selected[0].content == persisted.content
        assert selected[0].token_count == persisted.token_count

    def test_each_selected_row_keeps_its_own_document_and_table_provenance(self):
        rows = _table_rows() + _table_rows(DOC_B, TABLE_B)

        selected = select_table_row_evidence(
            rows, question=GATE_OPEN_QUESTION, max_rows=4
        )

        assert {(c.document_id, c.table_element_id) for c in selected} == {
            (DOC_A, TABLE_A),
            (DOC_B, TABLE_B),
        }
        # A row is never attributed to another document's table.
        for row in selected:
            expected_table = TABLE_A if row.document_id == DOC_A else TABLE_B
            assert row.table_element_id == expected_table

    def test_row_slots_are_filled_deterministically(self):
        """With the default row bound, ties resolve by document and table id,
        so one matching row per document is offered instead of two rows from
        whichever document happens to be read first."""
        rows = _table_rows(DOC_B, TABLE_B) + _table_rows()

        selected = select_table_row_evidence(rows, question=GATE_OPEN_QUESTION)

        assert [c.document_id for c in selected] == [DOC_A, DOC_B]
        assert [c.row_index for c in selected] == [1, 1]
        assert [c.table_element_id for c in selected] == [TABLE_A, TABLE_B]


class TestKillSwitch:
    def test_default_is_off(self, monkeypatch):
        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)

        assert table_evidence_enabled() is False

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "  ", "2"])
    def test_falsey_values_keep_it_off(self, monkeypatch, value):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, value)

        assert table_evidence_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
    def test_truthy_values_enable_it(self, monkeypatch, value):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, value)

        assert table_evidence_enabled() is True


class TestBandOrdering:
    @dataclass
    class _Chunk:
        chunk_id: str
        evidence_kind: str = "chunk"
        content: str = ""

    def _stream(self):
        # ``evidence_kind`` is the granularity ("chunk" / "structure_element" /
        # "table_row"); semantic vs hybrid is ``retrieval_path``, so every
        # chunk-level entry is evidence_kind "chunk" regardless of its path.
        return [
            self._Chunk("chunk-1"),
            self._Chunk("chunk-2"),
            self._Chunk("element-1", evidence_kind="structure_element"),
            self._Chunk("element-2", evidence_kind="structure_element"),
        ]

    def test_no_table_evidence_returns_the_stream_unchanged(self):
        stream = self._stream()

        ordered = order_evidence_bands(stream, [])

        assert [c.chunk_id for c in ordered] == [c.chunk_id for c in stream]
        assert ordered == stream
        assert ordered is not stream, "must not alias the caller's list"

    def test_table_band_sits_between_chunks_and_the_element_tail(self):
        stream = self._stream()
        table = [self._Chunk("row-1", evidence_kind=EVIDENCE_KIND_TABLE_ROW)]

        ordered = order_evidence_bands(stream, table)

        assert [c.chunk_id for c in ordered] == [
            "chunk-1",
            "chunk-2",
            "row-1",
            "element-1",
            "element-2",
        ]

    def test_existing_items_keep_their_relative_order(self):
        stream = self._stream()
        table = [self._Chunk("row-1", evidence_kind=EVIDENCE_KIND_TABLE_ROW)]

        ordered = order_evidence_bands(stream, table)
        positions = [
            [c.chunk_id for c in ordered].index(c.chunk_id) for c in stream
        ]

        assert positions == sorted(positions), "ranked evidence was reordered"
        assert len(ordered) == len(stream) + len(table)

    def test_stream_of_elements_only_puts_table_evidence_first(self):
        stream = [self._Chunk("element-1", evidence_kind="structure_element")]
        table = [self._Chunk("row-1", evidence_kind=EVIDENCE_KIND_TABLE_ROW)]

        ordered = order_evidence_bands(stream, table)

        assert [c.chunk_id for c in ordered] == ["row-1", "element-1"]

"""Table row/cell evidence: extractor -> parser contract -> row projection.

These tests draw real ruled tables into real PDFs (``tests/fixtures/pdf_layout``)
and assert against the real extractor and the real public parser, so the row
evidence under test is genuine PyMuPDF ``find_tables()`` output rather than a
hand-built fixture.  No production behaviour is stubbed here.

Scope: the parser boundary and the pure projection in ``documents/tables.py``.
Persistence is covered by ``tests/integration/documents/test_table_row_persistence.py``.
"""

from __future__ import annotations

from documents.parser import (
    ParsedDocument,
    ParsedElement,
    ParserValidationError,
    parse_pdf,
    validate_parsed_document,
)
from documents.tables import (
    rows_for_document,
    serialize_row,
    table_row_records,
    table_rows_by_source_id,
    total_row_records,
)
from tests.fixtures.pdf_layout import add_text, draw_ruled_table, new_page, new_pdf


def _pdf_bytes(pages: list[list[tuple]]) -> bytes:
    """Build a PDF from per-page layout items.

    Each item is ``("text", y, text, size)`` or ``("table", y, rows)``.
    """
    doc = new_pdf()
    for items in pages:
        page = new_page(doc)
        for item in items:
            if item[0] == "text":
                _, y, text, size = item
                add_text(page, 50, y, text, size=size)
            else:
                _, y, rows = item
                draw_ruled_table(page, 50, y, rows)
    data = doc.tobytes()
    doc.close()
    return data


ONE_TABLE = [
    [
        ("text", 60, "Maintenance Schedule", 16),
        (
            "table",
            110,
            [
                ["Component", "Interval"],
                ["Lidar Array", "250 h"],
                ["Thermal Enclosure", "1500 h"],
            ],
        ),
    ]
]

TWO_TABLES = [
    [
        ("table", 90, [["A", "B"], ["1", "2"]]),
        ("table", 260, [["C", "D"], ["3", "4"]]),
    ]
]


def _table_elements(parsed: ParsedDocument) -> list[ParsedElement]:
    return [e for e in parsed.elements if e.element_type == "table"]


class TestParserCarriesTableCells:
    def test_extractor_cells_survive_the_parser_boundary(self):
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE))
        tables = _table_elements(parsed)

        assert len(tables) == 1, "a single table must stay a single element"
        grid = tables[0].table_data
        assert grid is not None
        assert [len(row) for row in grid] == [2, 2, 2]
        flat = [cell for row in grid for cell in row]
        # Verbatim: the extracted cell text is present exactly as drawn.
        for expected in ("Component", "Interval", "Lidar Array", "250 h",
                         "Thermal Enclosure", "1500 h"):
            assert expected in flat, f"cell {expected!r} was lost or altered"

    def test_only_table_elements_carry_cell_data(self):
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE))

        assert sum(1 for e in parsed.elements if e.table_data is not None) == 1
        for element in parsed.elements:
            if element.element_type != "table":
                assert element.table_data is None

    def test_one_aggregate_table_element_per_table(self):
        parsed = parse_pdf(_pdf_bytes(TWO_TABLES))

        assert len(_table_elements(parsed)) == 2
        # No row/cell *elements* are ever synthesised into the element stream.
        assert not [
            e for e in parsed.elements
            if e.element_type in ("table_row", "table_cell")
        ]

    def test_element_sequence_is_unchanged_by_cell_data(self):
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE))

        assert [e.sequence_index for e in parsed.elements] == list(
            range(len(parsed.elements))
        )
        # The cell grid is carried on the element, not expanded into extra
        # elements: the element count equals the extractor's element count.
        assert len(parsed.elements) == len({e.source_id for e in parsed.elements})

    def test_parser_version_is_recorded(self):
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE))

        assert parsed.parser_version and parsed.parser_version != "unknown"

    def test_structural_dict_is_deterministic_and_carries_cells(self):
        first = parse_pdf(_pdf_bytes(ONE_TABLE))
        second = parse_pdf(_pdf_bytes(ONE_TABLE))

        assert first.structural_dict() == second.structural_dict()
        table_dict = next(
            e.structural_dict() for e in first.elements if e.element_type == "table"
        )
        assert table_dict["table_data"] is not None
        assert table_dict["table_data"][0] == ["Component", "Interval"]


class TestParserValidationOfCellData:
    def _document(self, element: ParsedElement) -> ParsedDocument:
        return ParsedDocument(
            parser_version="test-parser",
            source="<test>",
            page_count=1,
            elements=[element],
        )

    def test_non_table_element_cannot_carry_cells(self):
        element = ParsedElement(
            source_id="paragraph:1:0",
            element_type="paragraph",
            page_number=1,
            sequence_index=0,
            content="text",
            table_data=[["a", "b"]],
        )

        try:
            validate_parsed_document(self._document(element))
        except ParserValidationError as exc:
            assert "table_data" in str(exc)
        else:  # pragma: no cover - the contract must reject this
            raise AssertionError("paragraph element with table_data was accepted")

    def test_non_string_cell_is_rejected(self):
        element = ParsedElement(
            source_id="table:1:0",
            element_type="table",
            page_number=1,
            sequence_index=0,
            content="a",
            table_data=[["a", 3]],  # type: ignore[list-item]
        )

        try:
            validate_parsed_document(self._document(element))
        except ParserValidationError as exc:
            assert "not a string" in str(exc)
        else:  # pragma: no cover - the contract must reject this
            raise AssertionError("non-string table cell was accepted")


class TestRowProjection:
    def _parsed_table(self) -> ParsedElement:
        return _table_elements(parse_pdf(_pdf_bytes(ONE_TABLE)))[0]

    def test_header_row_is_marked_and_not_repeated(self):
        records = table_row_records(self._parsed_table())

        header = records[0]
        assert header.row_index == 0
        assert header.is_header is True
        assert header.header_repeated is False
        assert header.cells == ("Component", "Interval")
        assert header.content == "Component | Interval"

    def test_body_rows_repeat_the_header_verbatim(self):
        records = table_row_records(self._parsed_table())
        header_cells = records[0].cells

        assert len(records) == 3
        for record in records[1:]:
            assert record.is_header is False
            assert record.header_repeated is True
            header_text, _, row_text = record.content.partition("\n")
            assert header_text == serialize_row(header_cells)
            assert row_text == serialize_row(record.cells)
            # Self-contained: the row's own cells are all present.
            for cell in record.cells:
                assert cell in record.content

    def test_row_and_cell_order_is_deterministic(self):
        first = table_row_records(self._parsed_table())
        second = table_row_records(self._parsed_table())

        assert [r.row_index for r in first] == [0, 1, 2]
        assert [r.cells for r in first] == [r.cells for r in second]
        assert [r.content for r in first] == [r.content for r in second]
        assert [r.token_count for r in first] == [r.token_count for r in second]

    def test_content_is_derived_only_from_extracted_cells(self):
        element = self._parsed_table()
        grid = element.table_data
        assert grid is not None
        source_cells = {cell for row in grid for cell in row}

        for record in table_row_records(element):
            assert set(record.cells) <= source_cells
            # Reconstructing the serialisation from the cells must reproduce the
            # content exactly: nothing was added, normalised or summarised.
            expected = (
                serialize_row(grid[0]) + "\n" + serialize_row(record.cells)
                if record.header_repeated
                else serialize_row(record.cells)
            )
            assert record.content == expected

    def test_token_count_is_measured_with_the_given_counter(self):
        element = self._parsed_table()

        records = table_row_records(element, count_tokens=len)

        assert records, "expected rows"
        for record in records:
            assert record.token_count == len(record.content)

    def test_single_row_table_gets_no_invented_header(self):
        element = ParsedElement(
            source_id="table:1:0",
            element_type="table",
            page_number=1,
            sequence_index=0,
            content="Only | Row",
            table_data=[["Only", "Row"]],
        )

        records = table_row_records(element)

        assert len(records) == 1
        assert records[0].is_header is False
        assert records[0].header_repeated is False
        assert records[0].content == "Only | Row"

    def test_blank_rows_are_skipped_without_renumbering(self):
        element = ParsedElement(
            source_id="table:1:0",
            element_type="table",
            page_number=1,
            sequence_index=0,
            content="H1 | H2\nA | B\nC | D",
            table_data=[["H1", "H2"], ["A", "B"], ["", "  "], ["C", "D"]],
        )

        records = table_row_records(element)

        assert [r.row_index for r in records] == [0, 1, 3]
        assert records[-1].cells == ("C", "D")

    def test_no_cell_grid_produces_no_rows(self):
        element = ParsedElement(
            source_id="table:1:0",
            element_type="table",
            page_number=1,
            sequence_index=0,
            content="aggregate only",
            table_data=None,
        )

        assert table_row_records(element) == []

    def test_non_table_elements_produce_no_rows(self):
        element = ParsedElement(
            source_id="paragraph:1:0",
            element_type="paragraph",
            page_number=1,
            sequence_index=0,
            content="prose",
        )

        assert table_row_records(element) == []

    def test_rows_by_source_id_only_lists_tables_with_rows(self):
        parsed = parse_pdf(_pdf_bytes(TWO_TABLES))

        by_source = table_rows_by_source_id(parsed)

        table_sources = [e.source_id for e in _table_elements(parsed)]
        assert sorted(by_source) == sorted(table_sources)
        assert all(by_source[source] for source in by_source)
        assert total_row_records(parsed) == sum(
            len(rows) for rows in by_source.values()
        )
        # Flat helper keeps element order.
        flat = rows_for_document(parsed.elements)
        assert [r.row_index for r in flat] == [0, 1, 0, 1]

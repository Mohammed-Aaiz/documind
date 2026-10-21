"""Regression tests for PDF read-order and table-to-heading attribution.

The audited failure: ``extract_pdf`` emitted *all* tables before walking any
text blocks, so a table inherited the heading state as of the page start (or
the previous page) instead of the heading immediately above it in read order.
These tests draw real PDFs — real headings at explicit coordinates and real
ruled tables detected by ``page.find_tables()`` — and assert the attribution
and ordering produced by the real extractor and the real ``parse_pdf``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from documents.parser import parse_pdf
from documents.processing import extract_text
from tests.fixtures.pdf_layout import add_text, draw_ruled_table, new_pdf, new_page


def _pdf_bytes(pages: list[list[tuple]]) -> bytes:
    """Build a PDF from per-page layout item lists.

    Each item is ``("text", y, text, size)`` or ``("table", y, rows)`` and is
    drawn top-to-bottom at fixed coordinates in the given order.
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


def _extract(pdf_bytes: bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(pdf_bytes)
        tmp = Path(handle.name)
    try:
        return extract_text(tmp, "pdf")
    finally:
        os.unlink(tmp)


TWO_SECTIONS_ONE_PAGE = [
    [
        ("text", 60, "Primary Loop", 16),
        ("text", 110, "Pump Specifications", 13),
        ("table", 150, [["Pump A", "42 L/s"]]),
        ("text", 260, "Secondary Loop", 16),
        ("text", 310, "Pump Specifications", 13),
        ("table", 350, [["Pump B", "95 L/s"]]),
    ]
]

TWO_SECTIONS_TWO_PAGES = [
    [
        ("text", 60, "Primary Loop", 16),
        ("text", 110, "Pump Specifications", 13),
        ("table", 150, [["Pump A", "42 L/s"]]),
    ],
    [
        ("text", 60, "Secondary Loop", 16),
        ("text", 110, "Pump Specifications", 13),
        ("table", 150, [["Pump B", "95 L/s"]]),
    ],
]


def _tables(elements) -> list:
    return [e for e in elements if e.element_type == "table"]


class TestTableHeadingAttribution:
    def test_table_receives_the_heading_at_its_read_position(self):
        """Regression: a table under the *second* heading must not inherit
        the first heading's context."""
        elements = _extract(_pdf_bytes(TWO_SECTIONS_ONE_PAGE))
        tables = _tables(elements)

        assert len(tables) == 2, f"expected 2 detected tables, got {len(tables)}"
        assert tables[0].heading_path == ["Primary Loop", "Pump Specifications"]
        assert tables[1].heading_path == ["Secondary Loop", "Pump Specifications"]
        assert tables[1].section == "Pump Specifications"

    def test_table_heading_attribution_is_not_stale_across_pages(self):
        """Regression: page 2's table must use page 2's heading state, not the
        heading context left over from page 1."""
        elements = _extract(_pdf_bytes(TWO_SECTIONS_TWO_PAGES))
        tables = _tables(elements)

        assert len(tables) == 2, f"expected 2 detected tables, got {len(tables)}"
        assert tables[0].page == 1
        assert tables[1].page == 2
        assert tables[1].heading_path == ["Secondary Loop", "Pump Specifications"]

    def test_element_order_matches_page_read_order(self):
        elements = _extract(_pdf_bytes(TWO_SECTIONS_ONE_PAGE))

        assert [e.content for e in elements] == [
            "Primary Loop",
            "Pump Specifications",
            "Pump A | 42 L/s",
            "Secondary Loop",
            "Pump Specifications",
            "Pump B | 95 L/s",
        ]

    def test_heading_context_is_absent_before_the_first_heading(self):
        """A table above every heading legitimately has no heading context."""
        elements = _extract(
            _pdf_bytes(
                [
                    [
                        ("table", 60, [["Pump A", "42 L/s"]]),
                        ("text", 160, "Primary Loop", 16),
                    ]
                ]
            )
        )

        tables = _tables(elements)
        assert len(tables) == 1
        assert tables[0].heading_path == []
        assert tables[0].section is None


class TestParserContract:
    def test_parse_pdf_resolves_table_parent_to_the_current_section(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(_pdf_bytes(TWO_SECTIONS_ONE_PAGE))
            tmp = Path(handle.name)
        try:
            parsed = parse_pdf(tmp)
        finally:
            os.unlink(tmp)

        table_elements = [e for e in parsed.elements if e.element_type == "table"]
        sections = [e for e in parsed.elements if e.element_type == "section"]

        secondary_spec = next(
            e
            for e in sections
            if e.heading_path == ["Secondary Loop", "Pump Specifications"]
        )
        assert table_elements[1].parent_source_id == secondary_spec.source_id
        assert table_elements[1].heading_path == [
            "Secondary Loop",
            "Pump Specifications",
        ]

    def test_sequence_indices_are_contiguous_and_order_is_deterministic(self):
        pdf_bytes = _pdf_bytes(TWO_SECTIONS_ONE_PAGE)

        first = parse_pdf(pdf_bytes, source="<bytes>")
        second = parse_pdf(pdf_bytes, source="<bytes>")

        assert [e.sequence_index for e in first.elements] == list(
            range(len(first.elements))
        )
        assert first.structural_dict() == second.structural_dict()

    def test_element_vocabulary_is_unchanged(self):
        parsed = parse_pdf(_pdf_bytes(TWO_SECTIONS_ONE_PAGE), source="<bytes>")
        types = {e.element_type for e in parsed.elements}

        assert types <= {"section", "paragraph", "table", "text_block"}

    def test_malformed_pdf_still_raises(self):
        """Malformed-input behaviour is preserved: extraction errors are not
        swallowed by the read-order fix."""
        with pytest.raises(Exception):
            parse_pdf(b"this is not a pdf", source="<bytes>")

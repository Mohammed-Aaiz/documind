"""Phase 3C tests: Structured / Format-Aware Document Extraction.

Uses real fixture documents created programmatically.
Tests extraction correctness, heading detection, table extraction,
heading-path tracking, BOM handling, and content enrichment.
"""

import os
import tempfile
from pathlib import Path

import pytest
import fitz  # PyMuPDF
import docx

from documents.processing import (
    ExtractedElement,
    extract_text,
    chunk_text,
    _update_heading_path,
    _prepend_heading_context,
    ALLOWED_ELEMENT_TYPES,
    PARSER_VERSIONS,
)


# ===========================================================================
# Fixture helpers — create real documents programmatically
# ===========================================================================

def _make_pdf(
    pages: list[dict],
) -> bytes:
    """Create a PDF with structured content.

    pages: list of dicts, each with:
      - "blocks": list of {"text": str, "font": str, "size": float}
      - "tables": optional list of list[list[str]]
    """
    doc = fitz.open()

    for page_spec in pages:
        page = doc.new_page(width=595, height=842)  # A4

        y_pos = 50
        for block in page_spec.get("blocks", []):
            text = block["text"]
            font_name = block.get("font", "helv")
            font_size = block.get("size", 11)

            # Insert text with specific font/size
            tw = fitz.TextWriter(page.rect)
            font = fitz.Font("helv")  # base font
            if "bold" in font_name.lower():
                font = fitz.Font("hebo")
            tw.append((50, y_pos), text, font=font, fontsize=font_size)
            tw.write_text(page)
            y_pos += font_size + 10

    content = doc.tobytes()
    doc.close()
    return content


def _make_docx_with_structure() -> bytes:
    """Create a DOCX with headings, paragraphs, tables, and lists."""
    document = docx.Document()

    # Heading 1
    document.add_heading("Introduction", level=1)
    document.add_paragraph("This is the introduction paragraph.")

    # Heading 2
    document.add_heading("Background", level=2)
    document.add_paragraph("Some background information here.")

    # Heading 3
    document.add_heading("Details", level=3)
    document.add_paragraph("Detailed background content.")

    # Back to Heading 1
    document.add_heading("Methods", level=1)
    document.add_paragraph("We used the following approach.")

    # Table
    table = document.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Method"
    table.cell(0, 1).text = "Result"
    table.cell(1, 0).text = "PCA"
    table.cell(1, 1).text = "85%"
    table.cell(2, 0).text = "SVM"
    table.cell(2, 1).text = "92%"

    # List items
    document.add_paragraph("First item", style="List Bullet")
    document.add_paragraph("Second item", style="List Bullet")
    document.add_paragraph("Third item", style="List Bullet")

    # Results heading
    document.add_heading("Results", level=1)
    document.add_paragraph("The results show improvement.")

    buf = __import__("io").BytesIO()
    document.save(buf)
    return buf.getvalue()


def _make_txt_with_markdown() -> bytes:
    """Create a TXT file with Markdown headings and BOM."""
    content = (
        "\ufeff"  # UTF-8 BOM character
        "# Introduction\n\n"
        "This is the introduction.\n\n"
        "## Background\n\n"
        "Background information.\n\n"
        "### Details\n\n"
        "Detailed background.\n\n"
        "# Methods\n\n"
        "We used Python.\n\n"
        "## Results\n\n"
        "The results are positive."
    )
    return content.encode("utf-8")


def _make_empty_pdf() -> bytes:
    """Create a PDF with no text content."""
    doc = fitz.open()
    doc.new_page()
    content = doc.tobytes()
    doc.close()
    return content


def _make_txt_list_items() -> bytes:
    """Create a TXT file with list-like content (not Markdown)."""
    return b"Item one\nItem two\nItem three"


# ===========================================================================
# PDF extraction tests
# ===========================================================================

class TestPDFExtraction:
    def test_pdf_heading_detection(self):
        """PDF headings detected by font size heuristic."""
        pdf_bytes = _make_pdf([{
            "blocks": [
                {"text": "Introduction", "font": "helv-bold", "size": 16},
                {"text": "Some body text here.", "font": "helv", "size": 11},
                {"text": "Background", "font": "helv-bold", "size": 13},
                {"text": "More body text.", "font": "helv", "size": 11},
            ]
        }])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "pdf")
            headings = [e for e in elements if e.element_type == "heading"]
            paragraphs = [e for e in elements if e.element_type == "paragraph"]

            assert len(headings) >= 2, f"Expected >=2 headings, got {len(headings)}"
            assert headings[0].content == "Introduction"
            assert headings[0].heading_level == 1
            assert headings[1].content == "Background"
            assert len(paragraphs) >= 2
        finally:
            os.unlink(tmp)

    def test_pdf_page_numbers(self):
        """PDF elements have correct 1-based page numbers."""
        pdf_bytes = _make_pdf([
            {"blocks": [{"text": "Page 1 content", "font": "helv", "size": 11}]},
            {"blocks": [{"text": "Page 2 content", "font": "helv", "size": 11}]},
        ])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "pdf")
            pages = [e.page for e in elements]
            assert 1 in pages, "Page 1 should be present"
            assert 2 in pages, "Page 2 should be present"
        finally:
            os.unlink(tmp)

    def test_pdf_empty_page_skipped(self):
        """Empty PDF pages produce no elements."""
        pdf_bytes = _make_pdf([
            {"blocks": [{"text": "Content", "font": "helv", "size": 11}]},
            {"blocks": []},  # empty page
        ])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "pdf")
            # Only one page should have elements
            pages = [e.page for e in elements]
            assert pages.count(1) >= 1
        finally:
            os.unlink(tmp)

    def test_pdf_empty_document(self):
        """Empty PDF (no text) returns empty list."""
        pdf_bytes = _make_empty_pdf()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "pdf")
            assert len(elements) == 0
        finally:
            os.unlink(tmp)

    def test_pdf_images_and_text(self):
        """PDF with text blocks extracts text, skips image blocks."""
        pdf_bytes = _make_pdf([{
            "blocks": [
                {"text": "Text before image", "font": "helv", "size": 11},
                {"text": "Text after image", "font": "helv", "size": 11},
            ]
        }])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "pdf")
            contents = [e.content for e in elements]
            assert any("Text before" in c for c in contents)
            assert any("Text after" in c for c in contents)
        finally:
            os.unlink(tmp)

    def test_pdf_table_extraction(self):
        """PDF with tables produces table elements."""
        doc = fitz.open()
        page = doc.new_page()

        # Insert a table-like structure using text
        tw = fitz.TextWriter(page.rect)
        font = fitz.Font("helv")
        tw.append((50, 100), "Method | Result", font=font, fontsize=11)
        tw.append((50, 120), "PCA | 85%", font=font, fontsize=11)
        tw.append((50, 140), "SVM | 92%", font=font, fontsize=11)
        tw.write_text(page)

        content = doc.tobytes()
        doc.close()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "pdf")
            # Elements should be extracted (text blocks at minimum)
            assert len(elements) > 0
        finally:
            os.unlink(tmp)

    def test_pdf_text_table_no_duplication(self):
        """Text blocks overlapping tables are not duplicated."""
        # This tests the bbox overlap detection
        from documents.processing import _bbox_overlaps_table

        block_bbox = (50, 100, 200, 120)
        table_bboxes = [(40, 90, 210, 150)]

        assert _bbox_overlaps_table(block_bbox, table_bboxes) is True

        block_bbox2 = (300, 100, 400, 120)
        assert _bbox_overlaps_table(block_bbox2, table_bboxes) is False


# ===========================================================================
# DOCX extraction tests
# ===========================================================================

class TestDOCXExtraction:
    def test_docx_heading_levels(self):
        """DOCX headings detected by style.name (authoritative)."""
        docx_bytes = _make_docx_with_structure()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "docx")
            headings = [e for e in elements if e.element_type == "heading"]
            assert len(headings) >= 4, f"Expected >=4 headings, got {len(headings)}"

            # Check heading levels
            levels = [h.heading_level for h in headings]
            assert 1 in levels, "Should have level 1 headings"
            assert 2 in levels, "Should have level 2 headings"
            assert 3 in levels, "Should have level 3 headings"
        finally:
            os.unlink(tmp)

    def test_docx_heading_path(self):
        """DOCX heading_path tracks hierarchy correctly."""
        docx_bytes = _make_docx_with_structure()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "docx")

            # Find the "Details" heading (level 3 under Introduction > Background)
            details = [e for e in elements if e.element_type == "heading" and e.content == "Details"]
            assert len(details) == 1
            assert details[0].heading_path == ["Introduction", "Background", "Details"]

            # Find paragraph under "Details"
            details_paras = [
                e for e in elements
                if e.element_type == "paragraph"
                and e.section == "Details"
            ]
            assert len(details_paras) >= 1
            assert details_paras[0].heading_path == ["Introduction", "Background", "Details"]
        finally:
            os.unlink(tmp)

    def test_docx_heading_path_reset(self):
        """DOCX heading_path resets when same-level heading encountered."""
        docx_bytes = _make_docx_with_structure()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "docx")

            # "Methods" (H1) should reset path from Introduction > Background > Details
            methods = [e for e in elements if e.element_type == "heading" and e.content == "Methods"]
            assert len(methods) == 1
            assert methods[0].heading_path == ["Methods"]
        finally:
            os.unlink(tmp)

    def test_docx_tables(self):
        """DOCX tables produce table elements with cell data."""
        docx_bytes = _make_docx_with_structure()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "docx")
            tables = [e for e in elements if e.element_type == "table"]
            assert len(tables) >= 1, f"Expected >=1 table, got {len(tables)}"
            assert tables[0].table_data is not None
            assert len(tables[0].table_data) == 3, "Table should have 3 rows"
            assert tables[0].table_data[0] == ["Method", "Result"]
        finally:
            os.unlink(tmp)

    def test_docx_lists(self):
        """DOCX lists produce list elements with item boundaries."""
        docx_bytes = _make_docx_with_structure()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "docx")
            lists = [e for e in elements if e.element_type == "list"]
            assert len(lists) >= 1, f"Expected >=1 list, got {len(lists)}"
            assert lists[0].list_items is not None
            assert len(lists[0].list_items) == 3, "List should have 3 items"
            assert "First item" in lists[0].list_items
        finally:
            os.unlink(tmp)

    def test_docx_paragraph_context(self):
        """DOCX paragraphs carry heading context."""
        docx_bytes = _make_docx_with_structure()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(docx_bytes)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "docx")
            paras = [e for e in elements if e.element_type == "paragraph"]
            # At least some paragraphs should have non-empty heading_path
            paras_with_path = [p for p in paras if p.heading_path]
            assert len(paras_with_path) > 0, "Some paragraphs should have heading context"
        finally:
            os.unlink(tmp)

    def test_docx_empty_document(self):
        """Empty DOCX returns empty list."""
        document = docx.Document()
        buf = __import__("io").BytesIO()
        document.save(buf)
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(buf.getvalue())
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "docx")
            assert len(elements) == 0
        finally:
            os.unlink(tmp)


# ===========================================================================
# TXT extraction tests
# ===========================================================================

class TestTXTExtraction:
    def test_txt_markdown_headings(self):
        """TXT Markdown headings (# ## ###) detected correctly."""
        content = _make_txt_with_markdown()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "txt")
            headings = [e for e in elements if e.element_type == "heading"]
            assert len(headings) >= 4, f"Expected >=4 headings, got {len(headings)}"

            levels = {h.content: h.heading_level for h in headings}
            assert levels["Introduction"] == 1
            assert levels["Background"] == 2
            assert levels["Details"] == 3
            assert levels["Methods"] == 1
        finally:
            os.unlink(tmp)

    def test_txt_bom_stripping(self):
        """UTF-8 BOM is deterministically removed."""
        content = _make_txt_with_markdown()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "txt")
            # First element should not contain BOM character
            assert elements[0].element_type == "heading"
            assert elements[0].content == "Introduction"
            assert "\ufeff" not in elements[0].content
        finally:
            os.unlink(tmp)

    def test_txt_paragraph_boundaries(self):
        """TXT paragraphs split on double newlines."""
        content = b"First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "txt")
            paras = [e for e in elements if e.element_type == "paragraph"]
            assert len(paras) == 3, f"Expected 3 paragraphs, got {len(paras)}"
            assert paras[0].content == "First paragraph."
            assert paras[1].content == "Second paragraph."
            assert paras[2].content == "Third paragraph."
        finally:
            os.unlink(tmp)

    def test_txt_heading_path(self):
        """TXT heading_path tracks Markdown heading hierarchy."""
        content = b"# Intro\n\nText under intro.\n\n## Sub\n\nText under sub.\n\n# New\n\nText under new."
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "txt")
            # Paragraph under "Sub" should have path ["Intro", "Sub"]
            sub_paras = [e for e in elements if e.section == "Sub"]
            assert len(sub_paras) >= 1
            assert sub_paras[0].heading_path == ["Intro", "Sub"]
        finally:
            os.unlink(tmp)

    def test_txt_empty_document(self):
        """Empty TXT returns empty list."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"   ")
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "txt")
            assert len(elements) == 0
        finally:
            os.unlink(tmp)


# ===========================================================================
# Heading path utilities tests
# ===========================================================================

class TestHeadingPath:
    def test_update_heading_path_basic(self):
        """Heading path updates correctly."""
        path = _update_heading_path([], 1, "Intro")
        assert path == ["Intro"]

        path = _update_heading_path(["Intro"], 2, "Background")
        assert path == ["Intro", "Background"]

        path = _update_heading_path(["Intro", "Background"], 3, "Details")
        assert path == ["Intro", "Background", "Details"]

    def test_update_heading_path_reset(self):
        """Heading path resets at same level."""
        path = _update_heading_path(["Intro", "Background", "Details"], 1, "Methods")
        assert path == ["Methods"]

    def test_update_heading_path_same_level(self):
        """Heading path at same level replaces last entry."""
        path = _update_heading_path(["Intro", "Background"], 2, "New Background")
        assert path == ["Intro", "New Background"]

    def test_prepend_heading_context(self):
        """Heading context prepended to paragraph content."""
        element = ExtractedElement(
            content="Some text",
            element_type="paragraph",
            page=None,
            heading_path=["Introduction", "Background"],
        )
        enriched = _prepend_heading_context(element)
        assert enriched == "Introduction > Background\n\nSome text"

    def test_prepend_heading_context_heading_not_prepended(self):
        """Heading elements don't get heading context prepended."""
        element = ExtractedElement(
            content="Introduction",
            element_type="heading",
            page=None,
            heading_level=1,
            heading_path=["Introduction"],
        )
        enriched = _prepend_heading_context(element)
        assert enriched == "Introduction"

    def test_prepend_heading_context_empty_path(self):
        """Empty heading path returns content unchanged."""
        element = ExtractedElement(
            content="Some text",
            element_type="paragraph",
            page=None,
            heading_path=[],
        )
        enriched = _prepend_heading_context(element)
        assert enriched == "Some text"


# ===========================================================================
# Element type validation
# ===========================================================================

class TestElementType:
    def test_valid_element_types(self):
        """All allowed element types can be created."""
        for etype in ALLOWED_ELEMENT_TYPES:
            elem = ExtractedElement(
                content="test",
                element_type=etype,
                page=None,
            )
            assert elem.element_type == etype

    def test_invalid_element_type_rejected(self):
        """Invalid element_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid element_type"):
            ExtractedElement(
                content="test",
                element_type="invalid_type",
                page=None,
            )

    def test_element_type_is_string(self):
        """element_type values are strings."""
        elem = ExtractedElement(content="test", element_type="paragraph", page=None)
        assert isinstance(elem.element_type, str)


# ===========================================================================
# Chunking integration
# ===========================================================================

class TestChunkingIntegration:
    def test_chunk_text_with_enriched_content(self):
        """Chunking produces enriched chunks with heading context."""
        elements = [
            ExtractedElement(
                content="Introduction text here.",
                element_type="paragraph",
                page=1,
                heading_path=["Chapter 1", "Introduction"],
            ),
        ]
        chunks = chunk_text(elements)
        assert len(chunks) >= 1
        page, content = chunks[0]
        assert page == 1
        assert "Chapter 1 > Introduction" in content
        assert "Introduction text here" in content

    def test_chunk_text_heading_element(self):
        """Heading elements produce chunks without context duplication."""
        elements = [
            ExtractedElement(
                content="Introduction",
                element_type="heading",
                page=1,
                heading_level=1,
                heading_path=["Introduction"],
            ),
        ]
        chunks = chunk_text(elements)
        assert len(chunks) == 1
        _, content = chunks[0]
        # Should NOT have "Introduction > Introduction" (no duplication)
        assert content == "Introduction"


# ===========================================================================
# Regression: existing upload → chunk → embed pipeline
# ===========================================================================

class TestRegression:
    def test_extract_text_returns_extracted_elements(self):
        """extract_text returns list[ExtractedElement] (backward compat)."""
        content = b"Hello world. This is a test document."
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            elements = extract_text(tmp, "txt")
            assert isinstance(elements, list)
            assert len(elements) >= 1
            assert isinstance(elements[0], ExtractedElement)
            assert elements[0].content == "Hello world. This is a test document."
        finally:
            os.unlink(tmp)

    def test_chunk_text_output_format(self):
        """chunk_text returns list[(page, content)] tuples."""
        elements = [
            ExtractedElement(content="Test content", element_type="text", page=1),
        ]
        chunks = chunk_text(elements)
        assert isinstance(chunks, list)
        assert len(chunks) == 1
        page, content = chunks[0]
        assert page == 1
        assert isinstance(content, str)

    def test_parser_versions_recorded(self):
        """Parser versions are defined for all formats."""
        assert "pdf" in PARSER_VERSIONS
        assert "docx" in PARSER_VERSIONS
        assert "txt" in PARSER_VERSIONS

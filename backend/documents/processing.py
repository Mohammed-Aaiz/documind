"""
Structured document extraction for DocuMind.

Phase 3C: Format-aware extraction with structural metadata.

Extractors produce ExtractedElement instances that carry:
  - content text
  - element type (paragraph, heading, table, list, text)
  - page number (PDF only)
  - heading hierarchy (heading_path)
  - table cell data (where available)
  - list items (where available)

The chunking stage consumes ExtractedElement and produces chunks
with heading context prepended for downstream embedding quality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from copy import deepcopy

import fitz  # PyMuPDF
import docx


# ===========================================================================
# Parser version constants
# ===========================================================================

PARSER_VERSIONS = {
    "pdf": "pymupdf-1.28.2",
    "docx": "docx-1.2.0",
    "txt": "txt-utf8-v1",
}

ALLOWED_ELEMENT_TYPES = frozenset({"paragraph", "heading", "table", "list", "text"})


# ===========================================================================
# Intermediate representation
# ===========================================================================

@dataclass
class ExtractedElement:
    """One atomic unit of extracted content from a document.

    Backward-compatible with RawChunk: content + page are the primary fields.
    New fields carry structural metadata for richer embeddings and retrieval.
    """

    content: str
    """The text content of this element."""

    element_type: str
    """What kind of element: "paragraph", "heading", "table", "list", "text"."""

    page: int | None
    """1-based page number (PDF), None for DOCX/TXT."""

    heading_level: int | None = None
    """Heading level 1-9 if element_type="heading", else None."""

    heading_path: list[str] = field(default_factory=list)
    """Full heading hierarchy from document root to this element."""

    section: str | None = None
    """Nearest ancestor heading text, or None."""

    table_data: list[list[str]] | None = None
    """Table cell data if element_type="table", else None."""

    list_items: list[str] | None = None
    """List item texts if element_type="list", else None."""

    def __post_init__(self):
        if self.element_type not in ALLOWED_ELEMENT_TYPES:
            raise ValueError(
                f"Invalid element_type '{self.element_type}'. "
                f"Must be one of: {sorted(ALLOWED_ELEMENT_TYPES)}"
            )

    @property
    def has_structural_context(self) -> bool:
        """True if this element carries meaningful structural metadata."""
        return (
            self.heading_path is not None
            and len(self.heading_path) > 0
        )


# ===========================================================================
# Heading path utilities
# ===========================================================================

def _update_heading_path(
    current_path: list[str],
    level: int,
    heading_text: str,
) -> list[str]:
    """Update heading path when a new heading is encountered.

    Rules:
      - Truncate path at the heading's level (remove deeper entries)
      - Append the new heading text
      - Returns a new list (does not mutate input)
    """
    # Truncate to level-1 entries, then append new heading
    new_path = current_path[: level - 1] + [heading_text]
    return new_path


def _prepend_heading_context(element: ExtractedElement) -> str:
    """Prepend heading path to element content for embedding context.

    Format: "Section > Subsection\n\nContent text"

    Only prepends if heading_path is non-empty and element is not itself
    a heading (to avoid duplicating the heading text in the chunk).
    """
    if not element.heading_path or element.element_type == "heading":
        return element.content

    prefix = " > ".join(element.heading_path)
    return f"{prefix}\n\n{element.content}"


# ===========================================================================
# PDF extraction
# ===========================================================================

# Font-size thresholds for heading detection (heuristic, not authoritative).
# These are conservative defaults for typical academic/business PDFs.
_H1_FONT_SIZE = 14.0
_H2_FONT_SIZE = 12.0
_H3_FONT_SIZE_MIN = 10.5


def _classify_pdf_heading(span_font: str, span_size: float) -> int | None:
    """Heuristic heading level from PDF font properties.

    Returns heading level (1-3) or None if not a heading.
    This is INFERRED, not authoritative — conservative thresholds.
    """
    is_bold = "bold" in span_font.lower() if span_font else False

    if span_size >= _H1_FONT_SIZE:
        return 1
    if span_size >= _H2_FONT_SIZE:
        return 2
    if span_size >= _H3_FONT_SIZE_MIN and is_bold:
        return 3
    return None


def extract_pdf(path: Path) -> list[ExtractedElement]:
    """Extract structured content from a PDF.

    Uses page.get_text("dict") for block-level extraction with
    font metadata for heading detection. Tables are extracted
    separately via find_tables() to avoid duplication.
    """
    doc = fitz.open(str(path))
    elements: list[ExtractedElement] = []
    heading_path: list[str] = []

    # Collect table bounding boxes per page to avoid text/table overlap
    page_tables: dict[int, list[tuple[float, float, float, float]]] = {}

    for page_num in range(len(doc)):
        page = doc[page_num]

        # --- Extract tables first to know their bounding boxes ---
        try:
            tables = page.find_tables()
            for table in tables:
                # table.bbox = (x0, y0, x1, y1)
                bbox = table.bbox
                if page_num not in page_tables:
                    page_tables[page_num] = []
                page_tables[page_num].append(bbox)

                # Extract table content
                table_data: list[list[str]] = []
                for row in table.extract():
                    table_data.append([str(cell) if cell else "" for cell in row])

                if any(any(cell.strip() for cell in row) for row in table_data):
                    section = heading_path[-1] if heading_path else None
                    elements.append(ExtractedElement(
                        content="\n".join(
                            " | ".join(row) for row in table_data
                        ),
                        element_type="table",
                        page=page_num + 1,
                        heading_path=list(heading_path),
                        section=section,
                        table_data=table_data,
                    ))
        except Exception:
            # find_tables() may not be available in all PyMuPDF versions
            pass

        # --- Extract text blocks ---
        try:
            page_dict = page.get_text("dict")
        except Exception:
            # Fallback to plain text if dict extraction fails
            text = page.get_text("text")
            if text.strip():
                elements.append(ExtractedElement(
                    content=text.strip(),
                    element_type="text",
                    page=page_num + 1,
                    heading_path=list(heading_path),
                ))
            continue

        page_bbox_list = page_tables.get(page_num, [])

        for block in page_dict.get("blocks", []):
            # Skip image blocks (type 1)
            if block.get("type") == 1:
                continue

            # Skip blocks that overlap with extracted tables
            block_bbox = block.get("bbox", (0, 0, 0, 0))
            if _bbox_overlaps_table(block_bbox, page_bbox_list):
                continue

            # Extract text from block lines/spans
            block_lines: list[str] = []
            block_font = ""
            block_size = 0.0
            span_count = 0

            for line in block.get("lines", []):
                line_parts: list[str] = []
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if text.strip():
                        line_parts.append(text.strip())
                        # Track dominant font/size for heading detection
                        block_font = span.get("font", block_font)
                        block_size = max(block_size, span.get("size", 0))
                        span_count += 1
                if line_parts:
                    block_lines.append(" ".join(line_parts))

            if not block_lines:
                continue

            block_text = "\n".join(block_lines).strip()
            if not block_text:
                continue

            # --- Classify element type ---
            heading_level = _classify_pdf_heading(block_font, block_size)

            if heading_level is not None:
                # Update heading path
                heading_path = _update_heading_path(
                    heading_path, heading_level, block_text
                )
                section = heading_path[-1] if heading_path else None
                elements.append(ExtractedElement(
                    content=block_text,
                    element_type="heading",
                    page=page_num + 1,
                    heading_level=heading_level,
                    heading_path=list(heading_path),
                    section=section,
                ))
            else:
                section = heading_path[-1] if heading_path else None
                elements.append(ExtractedElement(
                    content=block_text,
                    element_type="paragraph",
                    page=page_num + 1,
                    heading_path=list(heading_path),
                    section=section,
                ))

    doc.close()
    return elements


def _bbox_overlaps_table(
    block_bbox: tuple,
    table_bboxes: list[tuple[float, float, float, float]],
    threshold: float = 0.5,
) -> bool:
    """Check if a text block substantially overlaps with any table.

    Uses IoU-like check: if >threshold of the block area is inside
    a table, the block is considered part of the table.
    """
    if not table_bboxes:
        return False

    bx0, by0, bx1, by1 = block_bbox
    block_area = max(0, bx1 - bx0) * max(0, by1 - by0)
    if block_area == 0:
        return False

    for tx0, ty0, tx1, ty1 in table_bboxes:
        # Intersection
        ix0 = max(bx0, tx0)
        iy0 = max(by0, ty0)
        ix1 = min(bx1, tx1)
        iy1 = min(by1, ty1)
        inter_area = max(0, ix1 - ix0) * max(0, iy1 - iy0)
        if inter_area / block_area > threshold:
            return True

    return False


# ===========================================================================
# DOCX extraction
# ===========================================================================

def extract_docx(path: Path) -> list[ExtractedElement]:
    """Extract structured content from a DOCX file.

    Extracts:
      - Headings via style.name ("Heading 1".."Heading 9")
      - Paragraphs with heading context
      - Tables with cell data
      - Lists via style.name ("List Bullet", "List Number")
    """
    document = docx.Document(str(path))
    elements: list[ExtractedElement] = []
    heading_path: list[str] = []

    # Track table positions in the body to interleave with paragraphs
    # python-docx doesn't provide a unified body iterator, so we
    # process paragraphs and tables in order by walking the XML body.
    try:
        _extract_docx_body(document, elements, heading_path)
    except Exception:
        # Fallback: extract paragraphs only
        for para in document.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            elements.append(ExtractedElement(
                content=text,
                element_type="paragraph",
                page=None,
                heading_path=list(heading_path),
                section=heading_path[-1] if heading_path else None,
            ))

    return elements


def _extract_docx_body(
    document: docx.Document,
    elements: list[ExtractedElement],
    heading_path: list[str],
) -> None:
    """Walk the DOCX body elements in document order."""
    # Build a map of table XML elements to their content
    body = document.element.body

    # Collect all tables indexed by their XML element
    table_map: dict[int, docx.table.Table] = {}
    for table in document.tables:
        table_map[id(table._tbl)] = table

    # Track which tables we've already processed
    processed_tables: set[int] = set()

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            # It's a paragraph
            _process_docx_paragraph(child, document, elements, heading_path)

        elif tag == "tbl":
            # It's a table
            tbl_id = id(child)
            if tbl_id not in processed_tables:
                processed_tables.add(tbl_id)
                table = table_map.get(tbl_id)
                if table is None:
                    # Try to find by matching XML
                    for t in document.tables:
                        if t._tbl is child:
                            table = t
                            break
                if table is not None:
                    _process_docx_table(table, elements, heading_path)


def _process_docx_paragraph(
    para_element,
    document: docx.Document,
    elements: list[ExtractedElement],
    heading_path: list[str],
) -> None:
    """Process a single DOCX paragraph element."""
    # Find the matching Paragraph object
    para = None
    for p in document.paragraphs:
        if p._element is para_element:
            para = p
            break

    if para is None:
        return

    text = para.text.strip()
    if not text:
        return

    style_name = para.style.name if para.style else ""

    # --- Heading detection (authoritative from DOCX styles) ---
    if style_name.startswith("Heading"):
        level_str = style_name.replace("Heading", "").strip()
        try:
            level = int(level_str)
        except (ValueError, TypeError):
            level = 1

        heading_path[:] = _update_heading_path(heading_path, level, text)
        section = heading_path[-1] if heading_path else None
        elements.append(ExtractedElement(
            content=text,
            element_type="heading",
            page=None,
            heading_level=level,
            heading_path=list(heading_path),
            section=section,
        ))
        return

    # --- List detection ---
    if style_name.startswith("List"):
        # Collect consecutive list items
        # Check if previous element was also a list — if so, append items
        if (elements
                and elements[-1].element_type == "list"
                and elements[-1].list_items is not None):
            elements[-1].list_items.append(text)
            # Update content to include new item
            elements[-1].content = "\n".join(elements[-1].list_items)
        else:
            section = heading_path[-1] if heading_path else None
            elements.append(ExtractedElement(
                content=text,
                element_type="list",
                page=None,
                heading_path=list(heading_path),
                section=section,
                list_items=[text],
            ))
        return

    # --- Regular paragraph ---
    section = heading_path[-1] if heading_path else None
    elements.append(ExtractedElement(
        content=text,
        element_type="paragraph",
        page=None,
        heading_path=list(heading_path),
        section=section,
    ))


def _process_docx_table(
    table: docx.table.Table,
    elements: list[ExtractedElement],
    heading_path: list[str],
) -> None:
    """Process a DOCX table into an ExtractedElement."""
    table_data: list[list[str]] = []
    for row in table.rows:
        row_cells = []
        for cell in row.cells:
            cell_text = cell.text.strip()
            row_cells.append(cell_text)
        table_data.append(row_cells)

    # Build text representation
    content_lines = []
    for row in table_data:
        content_lines.append(" | ".join(row))
    content = "\n".join(content_lines)

    if not content.strip():
        return

    section = heading_path[-1] if heading_path else None
    elements.append(ExtractedElement(
        content=content,
        element_type="table",
        page=None,
        heading_path=list(heading_path),
        section=section,
        table_data=table_data,
    ))


# ===========================================================================
# TXT extraction
# ===========================================================================

# Markdown heading pattern: ^#{1,6}\s+(.+)$
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def extract_txt(path: Path) -> list[ExtractedElement]:
    """Extract structured content from a plain TXT file.

    Features:
      - UTF-8 BOM stripping
      - Markdown heading detection (# through ######)
      - Paragraph splitting on double newlines
    """
    raw_bytes = path.read_bytes()

    # Strip UTF-8 BOM deterministically
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]

    text = raw_bytes.decode("utf-8", errors="replace")

    if not text.strip():
        return []

    # Split into paragraphs on double newlines
    paragraphs = re.split(r"\n\s*\n", text)

    elements: list[ExtractedElement] = []
    heading_path: list[str] = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check for Markdown heading (only single-line paragraphs)
        match = _MD_HEADING_RE.match(para)
        if match:
            hashes = match.group(1)
            heading_text = match.group(2).strip()
            level = len(hashes)

            heading_path[:] = _update_heading_path(
                heading_path, level, heading_text
            )
            section = heading_path[-1] if heading_path else None
            elements.append(ExtractedElement(
                content=heading_text,
                element_type="heading",
                page=None,
                heading_level=level,
                heading_path=list(heading_path),
                section=section,
            ))
        else:
            section = heading_path[-1] if heading_path else None
            elements.append(ExtractedElement(
                content=para,
                element_type="paragraph",
                page=None,
                heading_path=list(heading_path),
                section=section,
            ))

    return elements


# ===========================================================================
# Extraction dispatch
# ===========================================================================

EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "txt": extract_txt,
}


def extract_text(path: Path, file_type: str) -> list[ExtractedElement]:
    """Extract structured content from a document.

    Dispatches to the appropriate format extractor.
    Returns a list of ExtractedElement with structural metadata.
    """
    extractor = EXTRACTORS.get(file_type)
    if extractor is None:
        raise ValueError(f"Unsupported file type: {file_type}")
    return extractor(path)


# ===========================================================================
# Chunking
# ===========================================================================

CHUNK_SIZE = 1000   # characters per chunk
CHUNK_OVERLAP = 200  # overlap between consecutive chunks


def chunk_text(elements: list[ExtractedElement]) -> list[tuple[int | None, str]]:
    """Split extracted elements into overlapping text chunks.

    Phase 3C: Preserves existing sliding-window algorithm.
    Enriches chunks with heading context prepended for downstream
    embedding quality.

    Each element's content is enriched with its heading path before
    chunking, giving the embedding model structural context.

    Returns list of (page_number, enriched_chunk_text).
    """
    result: list[tuple[int | None, str]] = []

    for element in elements:
        # Enrich content with heading context
        enriched = _prepend_heading_context(element)
        text = enriched

        if len(text) <= CHUNK_SIZE:
            result.append((element.page, text))
            continue

        # Sliding window over the enriched text
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end]

            # Try to break at a sentence or newline boundary
            if end < len(text):
                last_period = chunk.rfind(".")
                last_newline = chunk.rfind("\n")
                boundary = max(last_period, last_newline)
                if boundary > CHUNK_SIZE // 2:
                    chunk = chunk[: boundary + 1]
                    end = start + boundary + 1

            if chunk.strip():
                result.append((element.page, chunk.strip()))

            start = end - CHUNK_OVERLAP
            if start >= len(text):
                break

    return result

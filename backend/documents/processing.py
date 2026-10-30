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

import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from copy import deepcopy

import fitz  # PyMuPDF
import docx
from documents.spatial import display_bbox, native_page_layout, native_page_size, native_text_blocks, page_layout

logger = logging.getLogger(__name__)

from documents.ocr import (
    MAX_PIXELS,
    OcrBudgetExhausted,
    OcrPageFailed,
    OcrPolicy,
    OcrSession,
    OcrUnavailable,
)


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

    bbox_x0: float | None = None
    bbox_y0: float | None = None
    bbox_x1: float | None = None
    bbox_y1: float | None = None

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
# Phase 1a — per-page completeness accounting
# ===========================================================================

#: Minimum usable text for one page to count as *accounted for*: the number of
#: non-whitespace alphanumeric characters its final text must contain.
#:
#: Owner decision (gate 24, 2026-10-15): the value is **4** and its home is this
#: module — no configuration surface, so a deployment cannot silently change
#: document verdicts.  The rule this constant encodes is the one the R5 plan
#: states once (§7.2.1): a page is usable when its final text carries at least
#: this many non-whitespace alphanumeric characters **and** its extraction did
#: not raise.
#:
#: Why 4 — measured, not round.  The evidence set is **not** the two-population
#: set an earlier revision of this comment claimed; measured with this module's
#: own measure, it has three regions:
#:
#:   0         punctuation-only, whitespace-only, blank and image-only (scanned)
#:             pages — no text layer at all;
#:   2         a bare folio or page number ("17", "iv") — text, but no content;
#:   5 .. 17   legitimate sparse pages: "Part I" (5), "Figure 1" (7),
#:             "Chapter 1" (8), "Appendix A" (9), "References" (10),
#:             "Introduction" / "Bibliography" (12), "Lecture 3: Attention" (17);
#:   82 ..     an ordinary digital page (one substantive paragraph; the shipped
#:             fixture ``tests/fixtures/darwin_proper.pdf`` measures 206-271).
#:
#: The value sits inside the measured gap between the largest text-bearing page
#: that carries no content (2) and the shortest legitimate sparse page (5), so a
#: short page is never reported as missing content merely for being short, while
#: a page that yielded only a folio still cannot make a document usable.  The
#: evidence is a corpus of generated pages plus one shipped digital fixture, not
#: a universal guarantee; any value in 3-4 is equally supported by it.
#:
#: What it deliberately does **not** do: it is not a quality measure.  A
#: low-quality or garbage text layer carries plenty of characters and is *not*
#: detected here, so Phase 1a does not fix — and does not claim to fix — a scan
#: that ships junk text.  That case belongs to Phase 1b's OCR quality work.
MIN_USABLE_CHARS = 4


def count_usable_chars(text: str) -> int:
    """Count the non-whitespace alphanumeric characters in ``text``.

    This is the measure §7.2.1 defines for page usability.  Punctuation,
    whitespace and control characters do not count: a page carrying only a
    rule, a page number of dashes or stray whitespace has produced no usable
    content and must not be able to make a document ``ready``.
    """
    return sum(1 for char in text if char.isalnum())


@dataclass(frozen=True)
class PageExtraction:
    """How one page's text was obtained, for persistence and display.

    ``failure_reason`` uses a fixed vocabulary so a client can render it without
    interpreting free text: ``no_text_layer`` (nothing usable and no OCR
    attempt), ``ocr_disabled``, ``ocr_unavailable``, ``ocr_failed`` or
    ``ocr_budget_exhausted``.
    """

    page_number: int
    method: str
    """``native`` | ``ocr`` | ``none``."""
    text_chars: int
    """Non-whitespace alphanumeric characters the page's final text carries."""
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None
    ocr_confidence: float | None = None
    ocr_rotation: int | None = None
    ocr_seconds: float | None = None
    failure_reason: str | None = None
    spatial_layout: dict | None = None


@dataclass(frozen=True)
class PageCoverage:
    """Per-page completeness accounting for a paged format (PDF).

    Carries only facts the extraction actually observed: how many pages the
    source document has, how many of them produced usable text, and which ones
    did not.  It is not a quality score and it makes no claim about pages it
    could not read beyond "unaccounted".

    The ``ocr_*`` fields record what the OCR fallback did, because "this page
    has no text" and "this page has no text and OCR could not read it either"
    are different facts and the verdict must not conflate them.
    """

    pages_total: int
    pages_usable: int
    unusable_pages: tuple[int, ...]
    """1-based page numbers that produced no usable text, in document order."""

    ocr_pages: tuple[int, ...] = ()
    """Pages whose usable text came from OCR, in document order."""

    ocr_failed_pages: tuple[int, ...] = ()
    """Pages handed to OCR that it could not read, in document order."""

    ocr_attempted: bool = False
    """True when at least one page was actually handed to the OCR engine."""

    ocr_unavailable: bool = False
    """True when the configured engine could not run at all (not installed)."""

    ocr_engine: str | None = None
    """Engine that produced :attr:`ocr_pages`, or None when none ran."""

    pages: tuple[PageExtraction, ...] = ()
    """Every page, in document order — the durable per-page provenance."""

    @property
    def complete(self) -> bool:
        """True when every page of the document produced usable content."""
        return self.pages_usable == self.pages_total

    @property
    def no_usable_pages(self) -> bool:
        """True when no page produced usable content (zero usable pages)."""
        return self.pages_usable == 0


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


def _pdf_table_element(
    page_num: int,
    heading_path: list[str],
    table_data: list[list[str]],
    bbox: tuple | None = None,
) -> ExtractedElement:
    """One aggregate table element carrying the heading context in effect."""
    section = heading_path[-1] if heading_path else None
    return ExtractedElement(
        content="\n".join(" | ".join(row) for row in table_data),
        element_type="table",
        page=page_num + 1,
        heading_path=list(heading_path),
        section=section,
        table_data=table_data,
        bbox_x0=bbox[0] if bbox else None,
        bbox_y0=bbox[1] if bbox else None,
        bbox_x1=bbox[2] if bbox else None,
        bbox_y1=bbox[3] if bbox else None,
    )


def _render_page_for_ocr(page: "fitz.Page", dpi: int):
    """Render one page to an RGB numpy array for OCR, bounded by ``MAX_PIXELS``.

    The pixmap is the page as a reader sees it: PyMuPDF rasterises the page at
    the requested resolution, so vector text and embedded scans are treated the
    same way.  Nothing is pre-processed (no binarisation, no deskew) — the
    engine's own detector handles that, and inventing a filter here would make
    the measured engine behaviour unreproducible.
    """
    import numpy as np

    predicted_pixels = float(page.rect.width) * float(page.rect.height) * (dpi / 72.0) ** 2
    if predicted_pixels > MAX_PIXELS:
        # Bound before allocating a pixmap; rendering first can already OOM on
        # a very large engineering drawing even if we downscale afterwards.
        scale = (MAX_PIXELS / predicted_pixels) ** 0.5
        matrix = fitz.Matrix(scale * dpi / 72.0, scale * dpi / 72.0)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
    else:
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    buffer = np.frombuffer(pix.samples, dtype=np.uint8)
    return buffer.reshape(pix.height, pix.width, 3)


def _ocr_page_element(
    page_num: int,
    heading_path: list[str],
    text: str,
) -> ExtractedElement:
    """One element carrying a page's OCR text, tagged as plain text.

    OCR cannot recover heading levels, tables or list structure reliably, so
    none is invented here: the page becomes one ``text`` element with the page
    number and the heading context that is current for the document.  Downstream
    chunking then treats it exactly like native text.
    """
    return ExtractedElement(
        content=text.strip(),
        element_type="text",
        page=page_num,
        heading_path=list(heading_path),
        section=heading_path[-1] if heading_path else None,
    )


def _extract_pdf_with_coverage(
    path: Path,
    ocr_policy: OcrPolicy | None = None,
) -> tuple[list[ExtractedElement], PageCoverage]:
    """Extract structured content from a PDF **and** its per-page coverage.

    Uses page.get_text("dict") for block-level extraction with
    font metadata for heading detection. Tables are extracted
    separately via find_tables() to avoid duplication.

    Read order: detected tables and text blocks are merged into one per-page
    event stream ordered by their actual PyMuPDF bounding boxes ``(y0, x0)``
    *before* the heading state is applied, so a table inherits the heading
    context that is current at its own position on the page — never a stale
    page-start heading.  Ties at identical coordinates are broken
    deterministically (text blocks before tables, then original extraction
    index).  No layout information is invented: every coordinate comes from
    PyMuPDF.  Text blocks that substantially overlap a detected table are
    still skipped, so table text is never duplicated.

    Every page is accounted for individually (Phase 1a): the returned
    :class:`PageCoverage` records how many pages produced usable text and which
    ones did not, so the caller never has to infer completeness from "some
    element was extracted somewhere".
    """
    doc = fitz.open(str(path))
    elements: list[ExtractedElement] = []
    heading_path: list[str] = []
    pages_total = 0
    pages_usable = 0
    unusable_pages: list[int] = []
    ocr_pages: list[int] = []
    ocr_failed_pages: list[int] = []
    ocr_attempted = False
    ocr_unavailable = False
    ocr_engine: str | None = None
    page_records: list[PageExtraction] = []

    ocr_session = OcrSession(ocr_policy)
    if not ocr_session.enabled:
        ocr_session = None

    for page_num in range(len(doc)):
        page = doc[page_num]

        # --- Per-page completeness accounting (Phase 1a, §7.2.1) ---
        #
        # The measure is the page's own native text, taken from the same
        # engine and independently of the structural pipeline below (which
        # deliberately drops blocks overlapping detected tables).  A page
        # whose own text extraction raises is *unaccounted*: a page-level
        # failure degrades coverage, it does not abort the document.
        pages_total += 1
        try:
            page_chars = count_usable_chars(page.get_text("text"))
        except Exception:
            page_chars = 0
        if page_chars >= MIN_USABLE_CHARS:
            pages_usable += 1
            page_records.append(
                PageExtraction(
                    page_number=page_num + 1,
                    method="native",
                    text_chars=page_chars,
                )
            )
        else:
            # The failure vocabulary is decided below; the default is the plain
            # fact that this page carried no usable text layer.
            failure_reason = "no_text_layer"
            if ocr_unavailable:
                failure_reason = "ocr_unavailable"
            elif ocr_session is None:
                failure_reason = "ocr_disabled"
            # --- No usable text layer: the case OCR exists for ---------------
            #
            # OCR runs only here, so a digital page never pays for it.  A page
            # OCR reads successfully contributes one text element and skips the
            # native block pass (it had no usable text to contribute).  A page
            # OCR cannot read stays unaccounted, exactly as before.
            if ocr_session is not None and not ocr_unavailable:
                ocr_attempted = True
                try:
                    ocr_image = _render_page_for_ocr(page, ocr_session.policy.dpi)
                    result = ocr_session.read(ocr_image)
                except OcrUnavailable as exc:
                    ocr_unavailable = True
                    failure_reason = "ocr_unavailable"
                    logger.warning(
                        "OCR unavailable for document %s (%s); pages without "
                        "a text layer will be reported unaccounted",
                        path.name,
                        exc,
                    )
                except OcrBudgetExhausted as exc:
                    ocr_failed_pages.append(page_num + 1)
                    failure_reason = "ocr_budget_exhausted"
                    logger.warning(
                        "document %s page %s: %s; page stays unaccounted",
                        path.name,
                        page_num + 1,
                        exc,
                    )
                except OcrPageFailed as exc:
                    ocr_failed_pages.append(page_num + 1)
                    failure_reason = "ocr_failed"
                    logger.warning(
                        "document %s page %s: %s; page stays unaccounted",
                        path.name,
                        page_num + 1,
                        exc,
                    )
                else:
                    if count_usable_chars(result.text) >= MIN_USABLE_CHARS:
                        spatial_layout = None
                        ocr_text = result.text
                        detected_regions = list(getattr(result, "regions", ()))
                        if detected_regions:
                            spatial_layout = page_layout(float(page.rect.width), float(page.rect.height),
                                detected_regions, method="rendered-page-ocr")
                            spatial_layout["reading_coordinates"] = "orientation-corrected-normalized"
                            spatial_layout["ocr_rotation"] = result.rotation
                            ocr_text = "\n".join(r["text"] for r in spatial_layout["regions"])
                        element = _ocr_page_element(page_num + 1, heading_path, ocr_text)
                        if detected_regions:
                            element.bbox_x0 = min(r["bbox"][0] for r in detected_regions) * float(page.rect.width)
                            element.bbox_y0 = min(r["bbox"][1] for r in detected_regions) * float(page.rect.height)
                            element.bbox_x1 = max(r["bbox"][2] for r in detected_regions) * float(page.rect.width)
                            element.bbox_y1 = max(r["bbox"][3] for r in detected_regions) * float(page.rect.height)
                        elements.append(element)
                        pages_usable += 1
                        ocr_pages.append(page_num + 1)
                        ocr_engine = result.engine
                        page_records.append(
                            PageExtraction(
                                page_number=page_num + 1,
                                method="ocr",
                                text_chars=count_usable_chars(result.text),
                                ocr_engine=result.engine,
                                ocr_engine_version=result.engine_version,
                                ocr_confidence=result.mean_confidence,
                                ocr_rotation=result.rotation,
                                ocr_seconds=result.seconds,
                                spatial_layout=spatial_layout,
                            )
                        )
                        logger.info(
                            "document %s page %s read by OCR (%s, %s lines, "
                            "confidence %.3f, rotation %s, %.2fs)",
                            path.name,
                            page_num + 1,
                            result.engine,
                            result.lines,
                            result.mean_confidence,
                            result.rotation,
                            result.seconds,
                        )
                        continue
                    ocr_failed_pages.append(page_num + 1)
                    failure_reason = "ocr_failed"

            unusable_pages.append(page_num + 1)
            page_records.append(
                PageExtraction(
                    page_number=page_num + 1,
                    method="none",
                    text_chars=page_chars,
                    failure_reason=failure_reason,
                )
            )

        # --- Collect tables (content + real bounding boxes) ---
        table_events: list[tuple[tuple, list[list[str]]]] = []
        table_bboxes: list[tuple] = []
        try:
            for table in page.find_tables():
                # table.bbox = (x0, y0, x1, y1)
                bbox = table.bbox
                table_bboxes.append(bbox)

                # Extract table content
                table_data: list[list[str]] = []
                for row in table.extract():
                    table_data.append([str(cell) if cell else "" for cell in row])

                if any(any(cell.strip() for cell in row) for row in table_data):
                    table_events.append((bbox, table_data))
        except Exception:
            # find_tables() may not be available in all PyMuPDF versions
            pass

        # --- Collect text blocks ---
        try:
            page_dict = page.get_text("dict")
        except Exception:
            # Fallback to plain text if dict extraction fails.  No block
            # coordinates exist here, so the historical deterministic order is
            # preserved: tables first, then the page text blob.
            for bbox, table_data in sorted(
                table_events, key=lambda event: (event[0][1], event[0][0])
            ):
                elements.append(_pdf_table_element(page_num, heading_path, table_data, display_bbox(page, bbox)))
            text = page.get_text("text")
            if text.strip():
                elements.append(ExtractedElement(
                    content=text.strip(),
                    element_type="text",
                    page=page_num + 1,
                    heading_path=list(heading_path),
                ))
            continue

        # Geometry is persisted once at ingestion. Multi-column ordering uses
        # the same regions later returned as evidence, so chunking does not
        # interleave the left and right columns row-by-row.
        layout_rank: dict[str, int] = {}
        try:
            layout = native_page_layout(page, page_dict, table_events)
            page_records[-1] = replace(page_records[-1], spatial_layout=layout)
            layout_rank = {r["id"]: r["reading_order"] for r in layout["regions"]}
        except (AttributeError, TypeError, ValueError):
            logger.warning("Native page geometry unavailable for %s page %d", path.name, page_num + 1)

        # Event stream entries are ``((reading_order,y0,x0,kind,index),kind,payload)``
        # where kind 0 = text block, 1 = table.  Sorting uses only real
        # PyMuPDF coordinates, so the order is the page's read order.
        events: list[tuple[tuple, int, tuple]] = []
        for index, (bbox, table_data) in enumerate(table_events):
            events.append(((layout_rank.get(f"table-{index}", 0), bbox[1], bbox[0], 1, index), 1, (table_data, bbox)))

        for index, (region_id, block) in enumerate(native_text_blocks(page_dict, native_page_size(page)[0])):
            # Skip image blocks (type 1)
            if block.get("type") == 1:
                continue

            # Skip blocks that overlap with extracted tables
            block_bbox = block.get("bbox", (0, 0, 0, 0))
            if _bbox_overlaps_table(block_bbox, table_bboxes):
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

            events.append(
                (
                    (layout_rank.get(region_id, 0), block_bbox[1], block_bbox[0], 0, index),
                    0,
                    (block_text, block_font, block_size, block_bbox),
                )
            )

        events.sort(key=lambda event: event[0])

        for _key, kind, payload in events:
            if kind == 1:
                table_data, bbox = payload
                elements.append(_pdf_table_element(page_num, heading_path, table_data, display_bbox(page, bbox)))
                continue

            block_text, block_font, block_size, block_bbox = payload
            block_bbox = display_bbox(page, block_bbox)

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
                    bbox_x0=block_bbox[0], bbox_y0=block_bbox[1],
                    bbox_x1=block_bbox[2], bbox_y1=block_bbox[3],
                ))
            else:
                section = heading_path[-1] if heading_path else None
                elements.append(ExtractedElement(
                    content=block_text,
                    element_type="paragraph",
                    page=page_num + 1,
                    heading_path=list(heading_path),
                    section=section,
                    bbox_x0=block_bbox[0], bbox_y0=block_bbox[1],
                    bbox_x1=block_bbox[2], bbox_y1=block_bbox[3],
                ))

    doc.close()
    return elements, PageCoverage(
        pages_total=pages_total,
        pages_usable=pages_usable,
        unusable_pages=tuple(unusable_pages),
        ocr_pages=tuple(ocr_pages),
        ocr_failed_pages=tuple(ocr_failed_pages),
        ocr_attempted=ocr_attempted,
        ocr_unavailable=ocr_unavailable,
        ocr_engine=ocr_engine,
        pages=tuple(page_records),
    )


def extract_pdf(path: Path) -> list[ExtractedElement]:
    """Extract structured content from a PDF (elements only).

    Backward-compatible wrapper.  Use :func:`extract_document` when the
    document's per-page coverage is needed as well (the ingestion verdict does
    need it).  OCR is applied by :func:`extract_document`, which carries the
    policy; this wrapper uses the default policy.
    """
    elements, _coverage = _extract_pdf_with_coverage(path)
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


def extract_document(
    path: Path, file_type: str, ocr_policy: OcrPolicy | None = None
) -> tuple[list[ExtractedElement], PageCoverage | None]:
    """Extract a document together with its per-page coverage (Phase 1a).

    Returns ``(elements, coverage)``.  ``coverage`` is ``None`` for formats
    that have no pages (DOCX/TXT): there is no page denominator to be honest
    about, so the verdict for those formats is decided by the pipeline steps
    alone (§7.2.1).

    ``ocr_policy`` decides whether pages with no usable text layer are read
    with the OCR fallback (``documents.ocr``).  ``None`` resolves the policy
    from application settings; pass ``OcrPolicy.disabled()`` to account for
    pages without ever attempting OCR.

    This is the extraction entry point the ingestion pipeline uses.  The
    legacy :func:`extract_text` entry point is preserved unchanged for callers
    that only need the element stream.
    """
    if file_type == "pdf":
        return _extract_pdf_with_coverage(path, ocr_policy)
    extractor = EXTRACTORS.get(file_type)
    if extractor is None:
        raise ValueError(f"Unsupported file type: {file_type}")
    return extractor(path), None


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

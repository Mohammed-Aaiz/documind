"""Explicit public parser API: PDF path/bytes -> ``ParsedDocument``.

This module is a **typed, database-independent boundary** over the existing
structure-aware extraction in :mod:`documents.processing`.  It does not
re-implement or alter extraction — :func:`parse_pdf` delegates to
``documents.processing.extract_pdf`` and then normalises the result into the
public schema below.  Upload integration, persistence, chunking and graph-edge
generation are deliberately out of scope.

Contract
--------
* database-independent — no ORM, no session, no persistence (this module does
  not import ``graph.models`` or any database object; the structure-graph
  vocabulary is mirrored as plain string constants);
* deterministic — identical input bytes produce identical output, including
  ``source_id`` values, ordering and serialised structure;
* synchronous — extraction is CPU-bound, so this stays a plain function;
* free of API/HTTP and persistence concerns.

Ordering
--------
``ParsedElement.sequence_index`` is the global, zero-based document order:
``0 <= sequence_index < len(elements)``, contiguous and without duplicates.  It
is assigned here from the extractor's element order and never from database
insertion order; the extractor's deterministic reading order is preserved and
elements are never reordered to fit the schema.

Source IDs
----------
``source_id`` is deterministic and stable for identical parser output, so the
later persistence layer can connect ``ParsedElement.parent_source_id`` to
``ParsedElement.source_id`` without database-generated ids.  The scheme is::

    {element_type}:{page_number}:{sequence_index}

e.g. ``section:1:0``, ``paragraph:1:1``, ``table:2:7``.  When the format has no
page number the page token is ``x`` (e.g. ``paragraph:x:0``).  It contains only
stable structural information — no random UUIDs, no timestamps, no Python
object ids, and no dependence on temporary filesystem paths.

Element-type vocabulary
-----------------------
The public schema supports exactly the structure-graph vocabulary::

    page, section, paragraph, text_block, table, table_row, table_cell,
    figure, list, list_item

The current PDF extractor emits a smaller subset — ``section`` (a heading),
``paragraph``, ``table`` and ``text_block`` (the extractor's ``text``).
``page``, ``list``, ``table_row``, ``table_cell``, ``figure`` and
``list_item`` are part of the supported vocabulary but are **not** emitted for
PDF, because ``extract_pdf`` does not produce them (``list`` is emitted only by
the DOCX extractor, and the other types by no extractor yet).  They are never
fabricated — no synthetic ``page`` nodes are created.  See
:data:`EMITTED_ELEMENT_TYPES`.

Internal -> public mapping
--------------------------
============================ ================= ====
``ExtractedElement`` type    public type       PDF?
============================ ================= ====
``heading``                  ``section``       yes
``paragraph``                ``paragraph``     yes
``table``                    ``table``         yes
``text``                     ``text_block``    yes
``list``                     ``list``          no (DOCX only)
============================ ================= ====

The ``heading`` -> ``section`` mapping is semantic (a heading *is* a section);
``text`` -> ``text_block`` is a terminology alignment.  An internal type with
no documented public mapping is a contract violation: it raises
:class:`ParserValidationError` rather than being silently reclassified as
``text_block``.

Table cell grid
---------------
A ``table`` element additionally carries ``table_data`` — the extractor's own
rows of cell strings, verbatim and in source order.  It is *not* a set of extra
elements: one table remains exactly one ``ParsedElement`` with one
``sequence_index``, so the element sequence, its ordering and the persisted
``document_structure_elements`` rows are unchanged.  ``table_data`` exists so
row-level evidence can be persisted separately (``documents/tables.py`` ->
``document_table_rows``) without re-parsing the aggregate content string.
``table_row`` / ``table_cell`` remain unsupported *element* types for PDF: no
such element is ever synthesised.

Hierarchy
---------
Hierarchy is exposed only through ``parent_source_id`` (``None`` at the root),
derived deterministically from the extractor's ``heading_path``:

* a top-level section (one-element ``heading_path``) has
  ``parent_source_id = None``;
* a subsection points to the most recent section whose ``heading_path`` is its
  own ``heading_path`` without the last element;
* paragraphs / tables / text blocks point to the most recent section whose
  ``heading_path`` equals their own ``heading_path``;
* elements with no heading ancestry (empty ``heading_path``) have
  ``parent_source_id = None``.

This module never creates database ``DocumentStructureEdge`` records; the later
graph-building task derives ``PARENT_OF`` / ``CONTAINS`` / ``NEXT`` /
``REFERENCES`` / ``BELONGS_TO_PAGE`` from this output.

Provenance
----------
* ``parser_version`` — the extractor version string from
  ``documents.processing.PARSER_VERSIONS`` for the parsed format.
* ``source`` — a stable human-readable provenance label: the original path
  string when parsed from a path, or ``"<bytes>"`` when parsed from a byte
  buffer.  It is never a temporary filesystem path.
* ``page_number`` — 1-based PDF page number.
* ``bbox_x0/y0/x1/y1`` — PDF user-space coordinates (points, origin top-left,
  y increasing downward).  The current extractor does **not** retain bounding
  boxes on ``ExtractedElement``, so these are always ``None`` today;
  coordinates are never fabricated.
* ``content`` — the extracted text of the element.
* ``heading_path`` — the actual heading ancestry (root -> nearest ancestor), or
  ``None`` when the extractor reports no heading context.  The extractor uses an
  empty list ``[]`` for "no heading"; the public schema normalises that to
  ``None`` so "absent" has a single representation.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import fitz  # PyMuPDF

from documents.processing import (
    PARSER_VERSIONS,
    ExtractedElement,
    extract_pdf,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Element-type vocabulary (mirrors graph.models.ELEMENT_TYPES as plain strings;
# deliberately NOT imported from the database package so parsing stays
# database-independent).
# ---------------------------------------------------------------------------

ELEMENT_TYPE_PAGE = "page"
ELEMENT_TYPE_SECTION = "section"
ELEMENT_TYPE_PARAGRAPH = "paragraph"
ELEMENT_TYPE_TEXT_BLOCK = "text_block"
ELEMENT_TYPE_TABLE = "table"
ELEMENT_TYPE_TABLE_ROW = "table_row"
ELEMENT_TYPE_TABLE_CELL = "table_cell"
ELEMENT_TYPE_FIGURE = "figure"
ELEMENT_TYPE_LIST = "list"
ELEMENT_TYPE_LIST_ITEM = "list_item"

#: Full supported public vocabulary, in a stable order.
SUPPORTED_ELEMENT_TYPES: tuple[str, ...] = (
    ELEMENT_TYPE_PAGE,
    ELEMENT_TYPE_SECTION,
    ELEMENT_TYPE_PARAGRAPH,
    ELEMENT_TYPE_TEXT_BLOCK,
    ELEMENT_TYPE_TABLE,
    ELEMENT_TYPE_TABLE_ROW,
    ELEMENT_TYPE_TABLE_CELL,
    ELEMENT_TYPE_FIGURE,
    ELEMENT_TYPE_LIST,
    ELEMENT_TYPE_LIST_ITEM,
)

#: The subset the current **PDF** extractor actually emits.  ``list`` is
#: deliberately absent: ``extract_pdf`` never emits it (only DOCX does).
EMITTED_ELEMENT_TYPES: frozenset[str] = frozenset(
    {
        ELEMENT_TYPE_SECTION,
        ELEMENT_TYPE_PARAGRAPH,
        ELEMENT_TYPE_TABLE,
        ELEMENT_TYPE_TEXT_BLOCK,
    }
)

#: Internal ``ExtractedElement.element_type`` -> public element type.  Every
#: type in the extractor's ``ALLOWED_ELEMENT_TYPES`` is mapped; an unmapped
#: type is a contract violation and raises (never a silent reclassification).
ELEMENT_TYPE_MAP: dict[str, str] = {
    "heading": ELEMENT_TYPE_SECTION,
    "paragraph": ELEMENT_TYPE_PARAGRAPH,
    "table": ELEMENT_TYPE_TABLE,
    "text": ELEMENT_TYPE_TEXT_BLOCK,
    "list": ELEMENT_TYPE_LIST,
}

PDF_PARSER_VERSION = PARSER_VERSIONS.get("pdf", "unknown")


class ParserValidationError(ValueError):
    """Raised when a parsed result violates the public parser contract."""


# ---------------------------------------------------------------------------
# Public schema
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedElement:
    """One structural element of a parsed document.

    All fields are immutable.  ``sequence_index`` is the global document order;
    ``parent_source_id`` is the only hierarchy link and resolves to another
    element's ``source_id`` (or ``None`` for a root element).  ``source_id`` is
    parser-local identity and is deliberately unrelated to any future database
    UUID.
    """

    source_id: str
    element_type: str
    page_number: int | None
    sequence_index: int
    parent_source_id: str | None = None
    heading_level: int | None = None
    heading_path: list[str] | None = None
    content: str | None = None
    bbox_x0: float | None = None
    bbox_y0: float | None = None
    bbox_x1: float | None = None
    bbox_y1: float | None = None

    # Extractor row/cell data for ``table`` elements only, verbatim and in
    # source order (``table_data`` from ``documents.processing``).  It is carried
    # here so row evidence survives the parser boundary and can be persisted to
    # ``document_table_rows``; it is deliberately **not** expanded into extra
    # ``ParsedElement`` entries, so one table stays exactly one structural
    # element and the element sequence/ordering is unchanged.  ``None`` means
    # "the extractor reported no cell grid" (every non-table element, and any
    # table the extractor could not decompose); no grid is ever synthesised.
    # Declared last so existing positional construction stays valid.
    table_data: list[list[str]] | None = None

    def structural_dict(self) -> dict:
        """Deterministic, serialisable structural view."""
        return {
            "source_id": self.source_id,
            "element_type": self.element_type,
            "page_number": self.page_number,
            "sequence_index": self.sequence_index,
            "parent_source_id": self.parent_source_id,
            "heading_level": self.heading_level,
            "heading_path": list(self.heading_path) if self.heading_path else None,
            "content": self.content,
            "bbox_x0": self.bbox_x0,
            "bbox_y0": self.bbox_y0,
            "bbox_x1": self.bbox_x1,
            "bbox_y1": self.bbox_y1,
            "table_data": (
                [list(row) for row in self.table_data] if self.table_data else None
            ),
        }


@dataclass(frozen=True)
class ParsedDocument:
    """The full, typed parser result for one document."""

    parser_version: str
    source: str
    page_count: int
    elements: list[ParsedElement] = field(default_factory=list)

    def structural_dict(self) -> dict:
        """Deterministic, serialisable structural view of the whole document."""
        return {
            "parser_version": self.parser_version,
            "source": self.source,
            "page_count": self.page_count,
            "elements": [element.structural_dict() for element in self.elements],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _coerce_page(page: object) -> int | None:
    """Normalise the extractor's page value to ``int`` or ``None``."""
    if page is None:
        return None
    try:
        value = int(page)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


def _public_element_type(raw: str) -> str:
    """Map an internal extractor type to the public vocabulary.

    An internal type with no documented mapping is a contract violation, not a
    ``text_block``: raise rather than silently reclassify a structural element.
    """
    try:
        return ELEMENT_TYPE_MAP[raw]
    except KeyError:
        raise ParserValidationError(
            f"unmapped extractor element_type {raw!r}; add an explicit mapping "
            "before exposing it through the public parser contract"
        ) from None


def _norm_heading_path(path: object) -> list[str] | None:
    """Normalise the extractor's heading path; empty -> ``None``."""
    if not path:
        return None
    if isinstance(path, str):
        return [path]
    values = [str(part) for part in path]
    return values or None


def _make_source_id(page_number: int | None, sequence_index: int, element_type: str) -> str:
    page_token = str(page_number) if page_number is not None else "x"
    return f"{element_type}:{page_token}:{sequence_index}"


def _pdf_page_count(raw: bytes | None, path: Path | None) -> int:
    """True PDF page count, read once from the source before extraction.

    Read from the document itself rather than inferred from extracted elements,
    so empty/trailing pages are counted correctly.
    """
    if raw is not None:
        doc = fitz.open(stream=raw, filetype="pdf")
    else:
        doc = fitz.open(str(path))
    try:
        return int(doc.page_count)
    finally:
        doc.close()


def _norm_table_data(element_type: str, raw: object) -> list[list[str]] | None:
    """Normalise extractor cell data into verbatim ``str`` cells, or ``None``.

    Cell strings are passed through unchanged — no trimming, case folding,
    unit conversion or value inference — so persisted row evidence is exactly
    what the extractor read.  A non-``table`` element carrying cell data is a
    contract violation: it raises rather than being silently dropped.  Malformed
    input (not a sequence of rows of cells) likewise raises; an empty grid
    normalises to ``None`` so "no cells" has a single representation.
    """
    if raw is None:
        return None
    if element_type != ELEMENT_TYPE_TABLE:
        raise ParserValidationError(
            f"element_type {element_type!r} cannot carry table_data; only "
            f"{ELEMENT_TYPE_TABLE!r} elements have a cell grid"
        )
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        raise ParserValidationError(
            f"table_data must be a sequence of rows, got {type(raw).__name__}"
        )
    rows: list[list[str]] = []
    for row in raw:
        if isinstance(row, (str, bytes)) or not isinstance(row, (list, tuple)):
            raise ParserValidationError(
                f"table_data row must be a sequence of cells, got {type(row).__name__}"
            )
        rows.append(["" if cell is None else str(cell) for cell in row])
    return rows or None


def _build_elements(extracted: list[ExtractedElement]) -> list[ParsedElement]:
    """Convert extractor output into the public schema, deriving parents.

    No elements are synthesised: the public list is a one-to-one, ordered view
    of the extractor's output.  Parent links come from ``heading_path`` using
    the most recent section seen at each path (deterministic given reading
    order).
    """
    elements: list[ParsedElement] = []
    # Most recent section source_id for each heading path tuple.
    section_by_path: dict[tuple[str, ...], str] = {}

    for seq, raw in enumerate(extracted):
        page_number = _coerce_page(raw.page)
        element_type = _public_element_type(raw.element_type)
        heading_path = _norm_heading_path(raw.heading_path)
        heading_level = raw.heading_level if isinstance(raw.heading_level, int) else None
        source_id = _make_source_id(page_number, seq, element_type)

        parent_source_id: str | None = None
        if heading_path:
            path_tuple = tuple(heading_path)
            if element_type == ELEMENT_TYPE_SECTION:
                parent_path = path_tuple[:-1]
                parent_source_id = section_by_path.get(parent_path) if parent_path else None
                section_by_path[path_tuple] = source_id
            else:
                parent_source_id = section_by_path.get(path_tuple)

        elements.append(
            ParsedElement(
                source_id=source_id,
                element_type=element_type,
                page_number=page_number,
                sequence_index=seq,
                parent_source_id=parent_source_id,
                heading_level=heading_level,
                heading_path=heading_path,
                content=raw.content if raw.content is not None else None,
                table_data=_norm_table_data(element_type, raw.table_data),
            )
        )

    return elements


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_pdf(
    path_or_bytes: Union[str, Path, bytes, bytearray],
    *,
    source: str | None = None,
) -> ParsedDocument:
    """Parse a PDF into a typed :class:`ParsedDocument`.

    ``path_or_bytes`` may be a filesystem path (``str``/``Path``) or the raw PDF
    bytes.  Extraction is delegated to the existing
    ``documents.processing.extract_pdf``; this function only normalises and
    validates the result.  Byte input is adapted through a transient temporary
    file (the existing extractor is path-based) that is removed on the way out;
    if that removal fails, the failure is logged and does not affect the result.

    ``source`` overrides the provenance label; by default it is the input path
    string, or ``"<bytes>"`` for byte input.  It is never a temporary path.

    Raises :class:`ParserValidationError` if the result violates the contract.
    The underlying extractor's own exceptions (e.g. a malformed PDF raising from
    PyMuPDF) propagate unchanged.
    """
    if isinstance(path_or_bytes, (bytes, bytearray)):
        raw = bytes(path_or_bytes)
        label = source if source is not None else "<bytes>"
        page_count = _pdf_page_count(raw, None)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(raw)
            tmp_path = Path(handle.name)
        try:
            extracted = extract_pdf(tmp_path)
        finally:
            # STEP 1.6AB: removing our own transient copy is best effort.  A bare
            # ``os.unlink`` here turned a *successful* parse into an exception (and
            # replaced the extractor's own error) whenever the file could not be
            # removed -- an antivirus or indexer holding the handle is enough on
            # Windows.  The failure is logged, not swallowed silently, and the
            # original outcome still propagates; ``voice.py`` handles its temp audio
            # file the same way.
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning(
                    "Failed to remove the temporary PDF copy for %s", label
                )
    else:
        path = Path(path_or_bytes)
        label = source if source is not None else str(path)
        page_count = _pdf_page_count(None, path)
        extracted = extract_pdf(path)

    document = ParsedDocument(
        parser_version=PDF_PARSER_VERSION,
        source=label,
        page_count=page_count,
        elements=_build_elements(extracted),
    )
    validate_parsed_document(document)
    return document


# ---------------------------------------------------------------------------
# Validation at the parser-result boundary
# ---------------------------------------------------------------------------

def validate_parsed_document(document: ParsedDocument) -> None:
    """Lightweight contract validation for a parsed document.

    Checks only the public contract — page count, 1-based in-range page numbers,
    deterministic contiguous ordering, unique non-empty source ids, resolvable
    non-self parents, supported element types.  It deliberately does not
    duplicate database-level validation and introduces no validation framework.
    """
    elements = document.elements

    if document.page_count < 0:
        raise ParserValidationError(f"page_count must be >= 0, got {document.page_count}")

    seen_ids: set[str] = set()

    for position, element in enumerate(elements):
        if not element.source_id:
            raise ParserValidationError(
                f"element at position {position} has an empty source_id"
            )
        if element.source_id in seen_ids:
            raise ParserValidationError(f"duplicate source_id: {element.source_id!r}")
        seen_ids.add(element.source_id)

        # sequence_index is the global order: it must equal the position.
        if element.sequence_index != position:
            raise ParserValidationError(
                f"sequence_index {element.sequence_index} != position {position} "
                f"for {element.source_id!r}"
            )

        if element.element_type not in SUPPORTED_ELEMENT_TYPES:
            raise ParserValidationError(
                f"unsupported element_type {element.element_type!r} "
                f"for {element.source_id!r}"
            )

        # Row/cell data belongs to tables only, and every cell must already be
        # a string: a fabricated or non-textual cell would become fabricated
        # evidence downstream.
        if element.table_data is not None:
            if element.element_type != ELEMENT_TYPE_TABLE:
                raise ParserValidationError(
                    f"element {element.source_id!r} of type "
                    f"{element.element_type!r} carries table_data"
                )
            for row_index, row in enumerate(element.table_data):
                if isinstance(row, (str, bytes)) or not isinstance(row, (list, tuple)):
                    raise ParserValidationError(
                        f"table_data row {row_index} of {element.source_id!r} is "
                        "not a sequence of cells"
                    )
                for cell in row:
                    if not isinstance(cell, str):
                        raise ParserValidationError(
                            f"table_data cell in row {row_index} of "
                            f"{element.source_id!r} is not a string"
                        )

        if element.page_number is not None:
            if element.page_number < 1:
                raise ParserValidationError(
                    f"page_number must be >= 1, got {element.page_number} "
                    f"for {element.source_id!r}"
                )
            if element.page_number > document.page_count:
                raise ParserValidationError(
                    f"page_number {element.page_number} exceeds page_count "
                    f"{document.page_count} for {element.source_id!r}"
                )

    # Parents must resolve to another element and never to themselves.
    for element in elements:
        parent = element.parent_source_id
        if parent is None:
            continue
        if parent == element.source_id:
            raise ParserValidationError(f"element {element.source_id!r} is its own parent")
        if parent not in seen_ids:
            raise ParserValidationError(
                f"parent_source_id {parent!r} of {element.source_id!r} "
                f"does not resolve to any element"
            )


__all__ = [
    "ParsedDocument",
    "ParsedElement",
    "ParserValidationError",
    "parse_pdf",
    "validate_parsed_document",
    "SUPPORTED_ELEMENT_TYPES",
    "EMITTED_ELEMENT_TYPES",
    "ELEMENT_TYPE_MAP",
    "ELEMENT_TYPE_PAGE",
    "ELEMENT_TYPE_SECTION",
    "ELEMENT_TYPE_PARAGRAPH",
    "ELEMENT_TYPE_TEXT_BLOCK",
    "ELEMENT_TYPE_TABLE",
    "ELEMENT_TYPE_TABLE_ROW",
    "ELEMENT_TYPE_TABLE_CELL",
    "ELEMENT_TYPE_FIGURE",
    "ELEMENT_TYPE_LIST",
    "ELEMENT_TYPE_LIST_ITEM",
    "PDF_PARSER_VERSION",
]

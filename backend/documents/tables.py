"""Faithful, compact row evidence derived from extracted table cells.

Why this module exists
----------------------
A PDF table is persisted as **one** aggregate ``table`` structure element whose
content is the whole serialised grid.  For the teacher-demo document that
aggregate is ~230 tokens, against a 362-token QA context budget that the five
ranked retrieval chunks already fill to 266 — so the aggregate can never be
supplied to the QA model intact (``266 + 230 = 496 > 362``).  The extractor,
however, already has the real cell grid (``ExtractedElement.table_data``); it
was simply discarded at the parser boundary.

This module projects that grid into compact per-row evidence records that
``documents.structure`` persists to ``document_table_rows``.  It is a pure,
database-independent, deterministic projection — the same boundary discipline as
``documents/parser.py``: no ORM, no session, no I/O, no randomness.

Faithfulness contract
---------------------
* **Verbatim cells only.**  ``cells`` are the extractor's own strings, in source
  order.  Nothing is trimmed, normalised, unit-converted, rounded, summarised or
  inferred, and no cell is ever fabricated (an empty cell stays an empty string).
* **Deterministic serialisation.**  ``content`` is ``" | "``-joined cells; a body
  row additionally embeds the header row above it, separated by a newline, so the
  unit is self-contained.  This mirrors the existing chunker convention in
  ``documents/chunking.py`` (``_serialize_row`` / ``_serialize_rows`` and the
  ``table_rows`` strategy that repeats the header in every sub-chunk) rather than
  inventing a second table serialisation.
* **No invented header.**  The first row is treated as the header exactly when the
  table has more than one row — the same rule the chunker already applies
  (``header = rows[0] if len(rows) > 1 else None``).  A single-row table gets no
  header and no header repetition.
* **No fabricated rows.**  A row whose cells are all blank carries no evidence and
  is skipped.  Original 0-based row indices are preserved, so a skipped row leaves
  a visible gap instead of silently renumbering the remaining evidence.
* **Bounded, measured size.**  ``token_count`` is measured with the project's own
  tokenizer (never estimated by hand); for the teacher-demo table a header-repeated
  body row measures ~36-48 tokens versus ~230 for the aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from documents.parser import ELEMENT_TYPE_TABLE, ParsedDocument, ParsedElement

#: Cell separator inside a serialised row.  Matches ``documents/chunking.py``.
CELL_SEPARATOR = " | "

#: Separator between the repeated header row and the row itself.
ROW_SEPARATOR = "\n"


@dataclass(frozen=True)
class TableRowRecord:
    """One persistable row-evidence record.

    ``row_index`` is the extractor's 0-based row index (including the header
    row).  ``cells`` is the verbatim cell tuple.  ``content`` is the deterministic
    serialisation described in the module docstring.  ``token_count`` is measured
    with the counter passed to :func:`table_row_records`.
    """

    row_index: int
    cells: tuple[str, ...]
    content: str
    token_count: int
    is_header: bool = False
    header_repeated: bool = False


def _default_counter() -> Callable[[str], int]:
    """The project's token counter (imported lazily to keep import cost down)."""
    from tokenization import count_tokens

    return count_tokens


def serialize_row(cells: Sequence[str]) -> str:
    """Serialise one row's cells deterministically (``"a | b | c"``)."""
    return CELL_SEPARATOR.join(cells)


def _is_blank_row(cells: Sequence[str]) -> bool:
    return not any(str(cell).strip() for cell in cells)


def table_row_records(
    element: ParsedElement,
    *,
    count_tokens: Callable[[str], int] | None = None,
) -> list[TableRowRecord]:
    """Project a parsed ``table`` element's cell grid into row records.

    Returns ``[]`` for anything that is not a ``table`` element, for a table with
    no cell grid, and for a grid whose rows are all blank — "no evidence" is always
    an empty list, never a synthesised row.  Ordering is source order, and the
    result is deterministic for identical input.
    """
    if element.element_type != ELEMENT_TYPE_TABLE:
        return []
    grid = element.table_data
    if not grid:
        return []

    counter = count_tokens or _default_counter()
    rows = [[str(cell) for cell in row] for row in grid]
    # Header only when there is more than one row, matching the chunker rule.
    header = rows[0] if len(rows) > 1 else None
    header_text = serialize_row(header) if header is not None else None

    records: list[TableRowRecord] = []
    for row_index, cells in enumerate(rows):
        if _is_blank_row(cells):
            continue

        if header_text is not None and row_index == 0:
            content = header_text
            is_header = True
            header_repeated = False
        elif header_text is not None:
            content = f"{header_text}{ROW_SEPARATOR}{serialize_row(cells)}"
            is_header = False
            header_repeated = True
        else:
            # Single-row table: no header exists, so nothing is repeated.
            content = serialize_row(cells)
            is_header = False
            header_repeated = False

        records.append(
            TableRowRecord(
                row_index=row_index,
                cells=tuple(cells),
                content=content,
                token_count=int(counter(content)),
                is_header=is_header,
                header_repeated=header_repeated,
            )
        )
    return records


def table_rows_by_source_id(parsed: ParsedDocument) -> dict[str, list[TableRowRecord]]:
    """Row records per table element, keyed by the parser's ``source_id``.

    Only ``table`` elements appear, and only when they have usable rows, so the
    caller can persist rows by resolving ``source_id`` to the aggregate element it
    just inserted.  Elements with no rows are omitted rather than mapped to ``[]``.
    """
    by_source: dict[str, list[TableRowRecord]] = {}
    for element in parsed.elements:
        if element.element_type != ELEMENT_TYPE_TABLE:
            continue
        records = table_row_records(element)
        if records:
            by_source[element.source_id] = records
    return by_source


def total_row_records(parsed: ParsedDocument) -> int:
    """Total row records a document would persist (used by tests and callers)."""
    return sum(len(rows) for rows in table_rows_by_source_id(parsed).values())


def rows_for_document(elements: Iterable[ParsedElement]) -> list[TableRowRecord]:
    """Flatten row records for a sequence of elements, in element order."""
    records: list[TableRowRecord] = []
    for element in elements:
        records.extend(table_row_records(element))
    return records


__all__ = [
    "CELL_SEPARATOR",
    "ROW_SEPARATOR",
    "TableRowRecord",
    "rows_for_document",
    "serialize_row",
    "table_row_records",
    "table_rows_by_source_id",
    "total_row_records",
]

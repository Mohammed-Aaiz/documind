"""Shared deterministic PyMuPDF layout builders for the test layer.

Owned by the test layer.  Not production code.

These helpers draw *real* PDF pages: real text at explicit coordinates and
real ruled tables that ``page.find_tables()`` detects.  Every coordinate is
explicit and deterministic, so a test can assert genuine read order and
table-to-heading attribution without inventing layout outside PyMuPDF.
"""

from __future__ import annotations

import fitz


def add_text(page, x: float, y: float, text: str, *, size: float = 11) -> None:
    """Insert one line of text at an explicit baseline position."""
    page.insert_text((x, y), text, fontsize=size, fontname="helv")


def draw_ruled_table(
    page,
    x0: float,
    y0: float,
    rows: list[list[str]],
    *,
    cell_width: float = 120.0,
    cell_height: float = 24.0,
    fontsize: float = 9.0,
) -> tuple[float, float, float, float]:
    """Draw a closed ruled grid with cell text; returns its ``(x0, y0, x1, y1)``.

    The grid is what makes ``page.find_tables()`` detect the region as a real
    table (the "lines" strategy), and the cell text is placed inside the
    ruling so the extractor's overlap check suppresses duplicate text blocks.
    """
    n_rows = len(rows)
    n_cols = max((len(row) for row in rows), default=0)
    if n_rows == 0 or n_cols == 0:
        raise ValueError("draw_ruled_table needs at least one row and one column")

    x1 = x0 + n_cols * cell_width
    y1 = y0 + n_rows * cell_height

    for row_index in range(n_rows + 1):
        page.draw_line(
            (x0, y0 + row_index * cell_height),
            (x1, y0 + row_index * cell_height),
            width=0.7,
        )
    for col_index in range(n_cols + 1):
        page.draw_line(
            (x0 + col_index * cell_width, y0),
            (x0 + col_index * cell_width, y1),
            width=0.7,
        )

    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            page.insert_text(
                (x0 + col_index * cell_width + 5, y0 + row_index * cell_height + 16),
                str(value),
                fontsize=fontsize,
                fontname="helv",
            )

    return (x0, y0, x1, y1)


def new_pdf():
    """Open an empty PDF document (caller closes it via ``tobytes`` + ``close``)."""
    return fitz.open()


def new_page(doc, *, width: float = 595, height: float = 842):
    """A4 page in PDF user-space points (origin top-left for our coordinates)."""
    return doc.new_page(width=width, height=height)

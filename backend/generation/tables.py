"""Deterministic table grounding for cell and row questions.

The measured failure this targets: on the frozen P3 benchmark the generative
engine answered **0 of 40** table questions correctly — it returned the table
header instead of the data row, a value from the wrong column (``Revenue
exceeds $150M`` for "what is the employees for 2010?"), or all three values of a
row when one was asked for.  A 250M-parameter seq2seq model is the wrong tool
for a lookup that the evidence already states structurally.

So when the retrieved evidence contains a simple pipe table, the cell/row is
resolved here — deterministically, from the table itself — instead of being
guessed by the model.  The answer is therefore evidence text verbatim, which is
both the correctness property and the grounding property: it cannot be invented.

Rules (all conservative; every unresolved case returns ``None`` and the caller
falls back to generation):

* a table is a header line plus at least one equal-width data row, each with at
  least three pipe-separated cells;
* a data row is identified by all of its first-cell terms appearing in the
  question, and the match must be unique;
* the asked column is the header cell sharing the most question terms, and the
  maximum must be unique — a tie is ambiguous and abstains;
* a *row* answer (the whole row, pipe-joined) is only produced when no column
  resolves but the question asks for "values"/"information"/... about that row;
* nothing is inferred from cell 0 being a label: in the benchmark's tables cell
  0 is also a real column (``Variable``, ``Division``, ``Year``, ``Method``,
  ``Tier``), and questions such as "the division for Enterprise Solutions" have
  that cell as the gold answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from generation.types import EvidenceBlock
from generation.verification import _QUESTION_WORDS

#: Minimum pipe-separated cells for a line to be considered tabular.  Two-column
#: text ("Key: value") is not a table and must not be read as one.
MIN_TABLE_CELLS = 3

#: Cell values participate in the answer but are never matched as labels.
_SEPARATOR_RE = re.compile(r"\s*\|\s*")
_LINE_SPLIT_RE = re.compile(r"\r?\n")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.%/-]*")

#: Question wording that asks for a whole row rather than one cell.
_ROW_CUES = frozenset(
    """values information recorded provided listed details detail data all""".split()
)

#: A table lookup asks for an attribute or an amount.  A question that names a
#: table term but asks *where/when/why* is not a lookup: "Where is the Premium
#: tier described?" must not be answered "Premium" merely because the header
#: happens to contain the word "tier".
_LOOKUP_CUE_RE = re.compile(
    r"\b(?:what|which|how (?:much|many)|name|list|give)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Table:
    """A simple pipe table recovered from one evidence block."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @property
    def width(self) -> int:
        return len(self.header)


@dataclass(frozen=True)
class TableAnswer:
    """A deterministic answer taken from a table cell or row.

    ``text`` is copied from the evidence — the resolver never composes new
    wording.  ``citation`` is the 1-based evidence block index the table came
    from, so the answer carries the same provenance as a generated one.
    """

    text: str
    citation: int
    kind: str  # "cell" | "row"
    row_label: str
    column: str | None = None


def parse_tables(text: str) -> list[Table]:
    """Recover pipe tables from ``text``; never raises, never guesses.

    Lines are used directly rather than the sentence splitter: extracted tables
    are line-structured, and the sentence splitter deliberately joins a newline
    that is followed by a lower-case word or a digit, which is exactly what a
    table row looks like.
    """
    tables: list[Table] = []
    header: list[str] | None = None
    rows: list[list[str]] = []

    def flush() -> None:
        nonlocal header, rows
        if header is not None and rows:
            tables.append(
                Table(header=tuple(header), rows=tuple(tuple(row) for row in rows))
            )
        header, rows = None, []

    for line in _LINE_SPLIT_RE.split(text or ""):
        stripped = line.strip()
        if "|" not in stripped:
            flush()
            continue
        cells = [cell.strip() for cell in _SEPARATOR_RE.split(stripped.strip("|"))]
        if len(cells) < MIN_TABLE_CELLS:
            flush()
            continue
        if header is None:
            header = cells
            rows = []
            continue
        if len(cells) != len(header):
            flush()
            if len(cells) >= MIN_TABLE_CELLS:
                header = cells
                rows = []
            continue
        rows.append(cells)

    flush()
    return tables


def _tokens(text: str) -> list[str]:
    """All lower-case tokens of ``text``, stopwords included.

    Stopwords are **not** removed here: a row or column really can be named
    ``Other``, ``All`` or ``Total``, and dropping those tokens made those rows
    unmatchable.
    """
    return _TOKEN_RE.findall((text or "").lower())


def subject_terms(text: str) -> list[str]:
    """Tokens of ``text`` that can name a row, column, heading or list item.

    Public because ``generation.lists`` matches list headings and items with the
    same rule; two tokenizers would drift.
    """
    return [token for token in _tokens(text) if token not in _QUESTION_WORDS]


def _resolve_row(question: str, table: Table) -> int | None:
    """Index of the single row whose label terms all occur in the question."""
    question_set = set(subject_terms(question))
    if not question_set:
        return None
    matches = [
        index
        for index, row in enumerate(table.rows)
        if row and subject_terms(row[0]) and set(subject_terms(row[0])) <= question_set
    ]
    if len(matches) != 1:
        # A longer label that contains a shorter one would match twice; that is
        # genuinely ambiguous and must not be guessed.
        return None
    return matches[0]


def _resolve_column(question: str, table: Table) -> int | None:
    """Index of the single header cell sharing the most terms with the question."""
    question_set = set(subject_terms(question))
    scored: list[tuple[int, int]] = []
    for index, cell in enumerate(table.header):
        overlap = len(question_set & set(subject_terms(cell)))
        if overlap:
            scored.append((overlap, index))
    if not scored:
        return None
    best = max(score for score, _ in scored)
    winners = [index for score, index in scored if score == best]
    if len(winners) != 1:
        return None
    return winners[0]


def _asks_for_row(question: str) -> bool:
    return bool(set(_tokens(question)) & _ROW_CUES)


def resolve_table_answer(
    question: str, blocks: Sequence[EvidenceBlock]
) -> TableAnswer | None:
    """Resolve a table cell or row answer, or ``None`` when not resolvable.

    ``None`` is the common case: prose evidence, an unrecognised table, an
    ambiguous row/column, or a question that is not a table lookup at all.  The
    caller must then use the normal generation path.
    """
    if not question or not blocks or not _LOOKUP_CUE_RE.search(question):
        return None

    for block in blocks:
        for table in parse_tables(block.content):
            row_index = _resolve_row(question, table)
            if row_index is None:
                continue
            row = table.rows[row_index]
            column_index = _resolve_column(question, table)

            if column_index is not None and column_index < len(row):
                cell = row[column_index].strip()
                if cell:
                    return TableAnswer(
                        text=cell,
                        citation=block.index,
                        kind="cell",
                        row_label=row[0].strip(),
                        column=table.header[column_index].strip(),
                    )
                continue

            if _asks_for_row(question):
                joined = " | ".join(cell.strip() for cell in row if cell.strip())
                if joined:
                    return TableAnswer(
                        text=joined,
                        citation=block.index,
                        kind="row",
                        row_label=row[0].strip(),
                    )
    return None


__all__ = [
    "Table",
    "TableAnswer",
    "parse_tables",
    "resolve_table_answer",
    "subject_terms",
]

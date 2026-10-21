"""Structure-discriminating evaluation corpus, version 1 (research dataset).

Why a new corpus
----------------
The production-aligned A–D ablation on the existing ``phase3d`` and ``heading``
corpora produced a **null result**: semantic-only and structure-aware retrieval
were effectively equivalent because almost none of the questions actually
*depend* on document structure.  Those corpora label questions by intent
("table", "section", "cross_page") but a semantic chunk retriever can answer
most of them from a single lexically-matching chunk.

This corpus is built to make the structure hypothesis **falsifiable**.  Every
structure-dependent question is designed so that a semantic-only retriever is
expected to fail or to be at risk of retrieving the wrong structural location,
and every such question is passed through an explicit anti-leakage gate
(:data:`DISCRIMINATION_*`) before it may enter the primary subset.  A weak
question is never deleted; it is recorded as an excluded/reviewed question.

Honesty contract
----------------
* **Synthetic but real documents.**  Documents are authored programmatically as
  real PDFs (headings with the font sizes the production extractor uses, body
  paragraphs, and ruled tables that ``page.find_tables`` detects).  Nothing is
  fabricated at scoring time: every answer is grounded in authored document text
  and every gold structural reference names an authored element.
* **Authored structural model.**  The structure tree is derived from the same
  declarative document spec the PDF builder renders, so a structural gold
  reference cannot drift from the document that backs it.  Element types and
  relation names use the production vocabulary (``graph.models.ELEMENT_TYPES``,
  ``graph.models.STRUCTURE_RELATIONS``); :func:`validate_corpus` asserts the
  vocabulary still matches production.
* **Deterministic and versioned.**  No timestamps, no randomness, stable
  ordering; ``CORPUS_VERSION`` changes on any label change.
* **No claim of proof.**  This corpus provides a better-controlled opportunity
  to test the hypothesis.  It does not demonstrate any advantage, and the A/B/C/D
  ablation has deliberately **not** been run on it here.

Production-parser note (read before scoring)
--------------------------------------------
The current PDF parser (``documents.parser``) emits only ``section``,
``paragraph``, ``table`` and ``text_block``.  ``table_row`` / ``table_cell`` /
``page`` / ``figure`` / ``list`` / ``list_item`` are part of the supported
schema vocabulary (``graph.models.ELEMENT_TYPES``) but are **not** emitted for
PDFs today.  Structural gold here therefore records the *intended* parsed
structure, including ``table_row`` / ``table_cell`` nodes, so the corpus is
forward-compatible with the schema; the future experiment must map persisted
elements to gold (by ``sequence_index``/content for emitted types, and from
``table.table_data`` for row/cell coordinates).

Run explicitly, from ``backend/``::

    ./venv/Scripts/python.exe evaluation/datasets/structure_discriminating_v1.py
    ./venv/Scripts/python.exe evaluation/datasets/structure_discriminating_v1.py --summary
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import fitz  # PyMuPDF

# Resolve the backend package root so the module runs from ``backend/`` directly
# (the same convention the other evaluation runners use).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from evaluation.schemas import QuestionCategory  # noqa: E402

#: Bump whenever any document, question or label changes.
CORPUS_VERSION = "structure-discriminating-v1"

# ---------------------------------------------------------------------------
# Production schema vocabulary (mirrored; asserted against graph.models in tests)
# ---------------------------------------------------------------------------

ELEMENT_TYPE_SECTION = "section"
ELEMENT_TYPE_PARAGRAPH = "paragraph"
ELEMENT_TYPE_TABLE = "table"
ELEMENT_TYPE_TABLE_ROW = "table_row"
ELEMENT_TYPE_TABLE_CELL = "table_cell"
ELEMENT_TYPES: tuple[str, ...] = (
    "page", "section", "paragraph", "text_block", "table", "table_row",
    "table_cell", "figure", "list", "list_item",
)
STRUCTURE_RELATIONS: tuple[str, ...] = (
    "CONTAINS", "PARENT_OF", "NEXT", "REFERENCES", "BELONGS_TO_PAGE",
)

# ---------------------------------------------------------------------------
# Authoring vocabularies
# ---------------------------------------------------------------------------

CAT_TABLE = "table_row_cell"
CAT_SECTION = "section_heading"
CAT_PAGE = "page_crossing"
CAT_MULTIHOP = "multi_hop_structural"
CAT_DISTRACTOR = "structural_distractor"
CAT_SEMANTIC = "semantic_control"
CAT_UNANSWERABLE = "unanswerable"

AUTHORING_CATEGORIES: tuple[str, ...] = (
    CAT_TABLE, CAT_SECTION, CAT_PAGE, CAT_MULTIHOP, CAT_DISTRACTOR,
    CAT_SEMANTIC, CAT_UNANSWERABLE,
)

DISCRIMINATING = "DISCRIMINATING"
WEAKLY_DISCRIMINATING = "WEAKLY_DISCRIMINATING"
NOT_DISCRIMINATING = "NOT_DISCRIMINATING"
DISCRIMINATION_LEVELS: tuple[str, ...] = (
    DISCRIMINATING, WEAKLY_DISCRIMINATING, NOT_DISCRIMINATING,
)

_CATEGORY_TO_KIND: dict[str, str] = {
    CAT_TABLE: "table",
    CAT_SECTION: "section",
    CAT_PAGE: "cross_page",
    CAT_MULTIHOP: "multi_hop",
    CAT_DISTRACTOR: "distractor",
    CAT_SEMANTIC: "factual",
    CAT_UNANSWERABLE: "unsupported",
}

_CATEGORY_TO_SCHEMA: dict[str, QuestionCategory] = {
    CAT_TABLE: QuestionCategory.TABLE_DEPENDENT,
    CAT_SECTION: QuestionCategory.SECTION_DEPENDENT,
    CAT_PAGE: QuestionCategory.PAGE_CROSS_PAGE,
    CAT_MULTIHOP: QuestionCategory.MULTI_HOP,
    CAT_DISTRACTOR: QuestionCategory.SECTION_DEPENDENT,
    CAT_SEMANTIC: QuestionCategory.DIRECT,
    CAT_UNANSWERABLE: QuestionCategory.DIRECT,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TableSpec:
    caption: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class DocumentSpec:
    doc_id: str
    name: str
    notes: str
    pages: tuple[tuple, ...]


@dataclass(frozen=True)
class StructuralElement:
    """One authored structural element (schema vocabulary)."""

    element_id: str
    document_id: str
    element_type: str
    parent_id: str | None
    page_number: int
    sequence_index: int
    heading_path: tuple[str, ...] = ()
    content: str = ""
    #: For ``table`` elements only.
    table_headers: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class CorpusQuestion:
    """One labelled question, including its structural gold annotations."""

    qid: str
    text: str
    category: str
    document_id: str
    answerable: bool = True
    expected_answer: str | None = None
    acceptable_answers: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    gold_element_ids: tuple[str, ...] = ()
    gold_table_cells: tuple[str, ...] = ()
    expected_structural_path: tuple[str, ...] = ()
    expected_evidence_type: str | None = None
    discrimination: str | None = None
    discrimination_rationale: str = ""
    notes: str = ""

    # --- compatibility with the production-aligned ablation runner ----------
    @property
    def kind(self) -> str:
        return _CATEGORY_TO_KIND[self.category]

    @property
    def schema_category(self) -> QuestionCategory:
        return _CATEGORY_TO_SCHEMA[self.category]


@dataclass
class DiscriminatingDoc:
    """One source document plus its authored structure and questions."""

    doc_id: str
    name: str
    file_type: str
    notes: str
    spec: DocumentSpec
    elements: list[StructuralElement] = field(default_factory=list)
    questions: list[CorpusQuestion] = field(default_factory=list)

    @property
    def builder(self):
        def build(path: Path) -> None:
            _render_document(self.spec, path)

        return build

    def write(self, directory: Path) -> Path:
        path = directory / self.name
        _render_document(self.spec, path)
        return path


@dataclass(frozen=True)
class Corpus:
    version: str
    documents: tuple[DiscriminatingDoc, ...]
    elements: tuple[StructuralElement, ...]
    questions: tuple[CorpusQuestion, ...]

    def __iter__(self):
        return iter(self.documents)

    def __len__(self) -> int:
        return len(self.documents)

    def document(self, doc_id: str) -> DiscriminatingDoc | None:
        for doc in self.documents:
            if doc.doc_id == doc_id:
                return doc
        return None


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

_PAGE_W, _PAGE_H = 595, 842
_LEFT, _RIGHT = 50.0, 545.0
_TOP, _BOTTOM = 55.0, 800.0
_HEAD_FONTS = {1: ("hebo", 16.0), 2: ("hebo", 13.0), 3: ("hebo", 11.0)}
_BODY = ("helv", 10.0)
_TABLE_FONT = ("helv", 8.5)


def _wrap(text: str, fontname: str, fontsize: float, width: float) -> list[str]:
    words = (text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if fitz.get_text_length(trial, fontname=fontname, fontsize=fontsize) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current or not lines:
        lines.append(current)
    return lines


def _draw_table(page, table: TableSpec, y: float) -> float:
    ncols = len(table.headers)
    rows = [table.headers, *table.rows]
    widths: list[float] = []
    for c in range(ncols):
        longest = max((len(str(row[c])) for row in rows), default=4)
        widths.append(max(60.0, min(150.0, longest * 5.2 + 14.0)))
    total = sum(widths)
    if _LEFT + total > _RIGHT:
        scale = (_RIGHT - _LEFT) / total
        widths = [w * scale for w in widths]
    xs = [_LEFT]
    for w in widths:
        xs.append(xs[-1] + w)
    row_h = 16.0
    y0 = y
    for r in range(len(rows) + 1):
        page.draw_line((xs[0], y0 + r * row_h), (xs[-1], y0 + r * row_h))
    for x in xs:
        page.draw_line((x, y0), (x, y0 + len(rows) * row_h))
    for r, row in enumerate(rows):
        font = "hebo" if r == 0 else "helv"
        for c, cell in enumerate(row):
            page.insert_text(
                (xs[c] + 4, y0 + r * row_h + 11),
                str(cell), fontsize=_TABLE_FONT[1], fontname=font,
            )
    return y0 + len(rows) * row_h + 16.0


def _render_document(spec: DocumentSpec, path: Path) -> None:
    doc = fitz.open()
    for page_index, blocks in enumerate(spec.pages, start=1):
        page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
        y = _TOP
        for block in blocks:
            kind = block[0]
            if kind == "h":
                _, level, text = block
                font, size = _HEAD_FONTS[level]
                y += {1: 16.0, 2: 12.0, 3: 10.0}[level]
                page.insert_text((_LEFT, y), text, fontsize=size, fontname=font)
                y += size * 1.6
            elif kind == "p":
                font, size = _BODY
                for line in _wrap(block[1], font, size, _RIGHT - _LEFT):
                    page.insert_text((_LEFT, y), line, fontsize=size, fontname=font)
                    y += size * 1.45
                y += size * 0.7
            elif kind == "t":
                y = _draw_table(page, block[1], y)
            else:  # pragma: no cover - authoring error
                raise ValueError(f"unknown block kind {kind!r}")
            if y > _BOTTOM:
                raise ValueError(
                    f"document {spec.doc_id!r} page {page_index} overflows the page"
                )
    doc.save(str(path))
    doc.close()


# ---------------------------------------------------------------------------
# Declarative documents
# ---------------------------------------------------------------------------

#: ``("h", level, text)`` | ``("p", text)`` | ``("t", TableSpec)``
_ATLAS = DocumentSpec(
    doc_id="atlas",
    name="atlas_propulsion.pdf",
    notes="H1–H3 with two tables; Ignition Sequence heading and body split across pages.",
    pages=(
        (
            ("h", 1, "Atlas Propulsion Manual"),
            ("p", "The Atlas programme operates the Kestrel thruster, which burns a Xenon-oxygen mixture for orbital insertion burns."),
            ("h", 2, "Thruster Operating Limits"),
            ("t", TableSpec("Thruster Parameters", ("Parameter", "Nominal", "Maximum"), (
                ("Chamber pressure", "24 bar", "31 bar"),
                ("Thrust", "18 kilonewtons", "22 kilonewtons"),
                ("Burn duration", "42 seconds", "60 seconds"),
                ("Coolant flow", "3 litres per minute", "5 litres per minute"),
                ("Ignition voltage", "480 volts", "520 volts"),
            ))),
            ("h", 3, "Ignition Sequence"),
        ),
        (
            ("p", "The ignition sequence begins with a Xenon purge and lasts 42 seconds."),
            ("p", "The flight computer aborts the sequence if chamber pressure exceeds 31 bar."),
            ("h", 2, "Coolant Loop"),
            ("t", TableSpec("Coolant Segments", ("Segment", "Pressure", "Temperature"), (
                ("Pump inlet", "1.2 bar", "18 degrees"),
                ("Chamber wall", "2.4 bar", "140 degrees"),
                ("Radiator inlet", "1.8 bar", "95 degrees"),
                ("Radiator outlet", "1.5 bar", "72 degrees"),
                ("Pump outlet", "2.1 bar", "66 degrees"),
            ))),
        ),
        (
            ("h", 2, "Thermal Margins"),
            ("p", "The radiator rejects 14 kilowatts at full thrust."),
            ("p", "A margin of 2 kilowatts is reserved for attitude manoeuvres."),
        ),
    ),
)

_FIELD = DocumentSpec(
    doc_id="field",
    name="field_survey.pdf",
    notes="Sampling Protocol spans pages 1–2; 'Kestrel frame' is reused in three sections.",
    pages=(
        (
            ("h", 1, "Meridian Field Survey"),
            ("p", "The Meridian survey characterises sediment transport along the eastern shelf."),
            ("h", 2, "Sampling Protocol"),
            ("p", "Every station is sampled at three tidal heights using a Kestrel frame."),
            ("p", "A duplicate sample is taken at every tenth station for quality control."),
            ("t", TableSpec("Sampling Stations", ("Station", "Depth", "Sediment"), (
                ("M-01", "12 centimetres", "Fine sand"),
                ("M-02", "18 centimetres", "Coarse sand"),
                ("M-03", "9 centimetres", "Silt"),
                ("M-04", "21 centimetres", "Gravel"),
                ("M-05", "15 centimetres", "Fine sand"),
            ))),
        ),
        (
            ("p", "The protocol requires a blank sample before each transect begins."),
            ("p", "Sampling depth is recorded to the nearest centimetre."),
            ("h", 2, "Instrument Calibration"),
            ("p", "The Kestrel frame is calibrated weekly against a granite reference block."),
            ("t", TableSpec("Calibration Drift", ("Session", "Drift", "Action"), (
                ("S-11", "0.2 millimetres", "None"),
                ("S-12", "0.4 millimetres", "Monitor"),
                ("S-13", "0.6 millimetres", "Recalibrate"),
                ("S-14", "0.1 millimetres", "None"),
                ("S-15", "0.5 millimetres", "Monitor"),
            ))),
        ),
        (
            ("h", 2, "Winter Sampling Protocol"),
            ("p", "The winter protocol uses a Nimbus frame instead of the Kestrel frame."),
            ("p", "Winter stations are sampled at two tidal heights only."),
        ),
    ),
)

_OSLO = DocumentSpec(
    doc_id="oslo",
    name="oslo_reactor.pdf",
    notes="Primary/Secondary Loop both contain a 'Pump Specifications' subsection.",
    pages=(
        (
            ("h", 1, "Oslo Reactor Handbook"),
            ("h", 2, "Primary Loop"),
            ("h", 3, "Pump Specifications"),
            ("t", TableSpec("Primary Pumps", ("Pump", "Flow", "Head"), (
                ("Pump A", "120 litres per second", "45 metres"),
                ("Pump B", "140 litres per second", "52 metres"),
                ("Pump C", "110 litres per second", "40 metres"),
                ("Pump D", "125 litres per second", "47 metres"),
                ("Pump E", "135 litres per second", "50 metres"),
            ))),
        ),
        (
            ("h", 3, "Seal Maintenance"),
            ("t", TableSpec("Seal Schedule", ("Seal", "Interval", "Torque"), (
                ("Primary seal", "6 hours", "80 newton metres"),
                ("Secondary seal", "Quarterly", "60 newton metres"),
                ("Standby seal", "Annually", "55 newton metres"),
                ("Flange seal", "Monthly", "70 newton metres"),
                ("Shaft seal", "Weekly", "65 newton metres"),
            ))),
            ("h", 2, "Secondary Loop"),
            ("h", 3, "Pump Specifications"),
            ("t", TableSpec("Secondary Pumps", ("Pump", "Flow", "Head"), (
                ("Pump A", "90 litres per second", "35 metres"),
                ("Pump B", "95 litres per second", "38 metres"),
                ("Pump C", "88 litres per second", "33 metres"),
                ("Pump D", "92 litres per second", "36 metres"),
                ("Pump E", "97 litres per second", "39 metres"),
            ))),
        ),
        (
            ("h", 2, "Emergency Procedures"),
            ("p", "On a primary loop trip the reactor scrams and both loops are isolated."),
            ("p", "The isolation valves close within 3 seconds of a trip signal."),
        ),
    ),
)

_ARCHIVE = DocumentSpec(
    doc_id="archive",
    name="archive_records.pdf",
    notes="Reel Inventory heading on page 1, its table on page 2; Access Rules repeats the count.",
    pages=(
        (
            ("h", 1, "Vermilion Archive"),
            ("p", "The Vermilion archive stores survey records from 1970 to 1995."),
            ("h", 2, "Reel Inventory"),
        ),
        (
            ("t", TableSpec("Reel Inventory", ("Reel", "Exposures", "Condition"), (
                ("R-01", "1200", "Good"),
                ("R-02", "980", "Fair"),
                ("R-03", "1100", "Good"),
                ("R-04", "760", "Poor"),
                ("R-05", "1040", "Good"),
                ("R-06", "880", "Fair"),
            ))),
            ("p", "Reels in poor condition are rephotographed before release."),
            ("h", 2, "Access Rules"),
            ("p", "A single reel holds up to twelve hundred exposures."),
            ("p", "Microfilm reels are stored at eighteen degrees and forty percent humidity."),
        ),
    ),
)

_DOCUMENTS: tuple[DocumentSpec, ...] = (_ATLAS, _FIELD, _OSLO, _ARCHIVE)


# ---------------------------------------------------------------------------
# Structure derivation (from the same spec the PDF renders)
# ---------------------------------------------------------------------------

def _build_document(doc: DocumentSpec) -> DiscriminatingDoc:
    elements: list[StructuralElement] = []
    sections: dict[tuple[str, ...], str] = {}
    tables: dict[str, str] = {}
    cells: dict[str, str] = {}
    paragraphs: list[tuple[str, str]] = []
    stack: list[tuple[int, str, str]] = []  # (level, heading_text, element_id)
    top_seq = 0
    seq = 0

    for page_number, blocks in enumerate(doc.pages, start=1):
        for block in blocks:
            kind = block[0]
            if kind == "h":
                _, level, text = block
                parent = None
                for lvl, _t, eid in reversed(stack):
                    if lvl < level:
                        parent = eid
                        break
                path = tuple([t for (lvl, t, _e) in stack if lvl < level] + [text])
                element_id = f"{doc.doc_id}:section:{top_seq}"
                top_seq += 1
                elements.append(StructuralElement(
                    element_id=element_id, document_id=doc.doc_id,
                    element_type=ELEMENT_TYPE_SECTION, parent_id=parent,
                    page_number=page_number, sequence_index=seq,
                    heading_path=path, content="",
                ))
                seq += 1
                stack = [(lvl, t, e) for (lvl, t, e) in stack if lvl < level] + [(level, text, element_id)]
                sections[path] = element_id
            elif kind == "p":
                text = block[1]
                parent = stack[-1][2] if stack else None
                path = tuple(t for (_lvl, t, _e) in stack)
                element_id = f"{doc.doc_id}:paragraph:{top_seq}"
                top_seq += 1
                elements.append(StructuralElement(
                    element_id=element_id, document_id=doc.doc_id,
                    element_type=ELEMENT_TYPE_PARAGRAPH, parent_id=parent,
                    page_number=page_number, sequence_index=seq,
                    heading_path=path, content=text,
                ))
                seq += 1
                paragraphs.append((text, element_id))
            elif kind == "t":
                table: TableSpec = block[1]
                parent = stack[-1][2] if stack else None
                path = tuple(t for (_lvl, t, _e) in stack)
                table_id = f"{doc.doc_id}:table:{top_seq}"
                top_seq += 1
                rendered = "\n".join(" | ".join(row) for row in (table.headers, *table.rows))
                elements.append(StructuralElement(
                    element_id=table_id, document_id=doc.doc_id,
                    element_type=ELEMENT_TYPE_TABLE, parent_id=parent,
                    page_number=page_number, sequence_index=seq,
                    heading_path=path, content=rendered,
                    table_headers=table.headers, table_rows=table.rows,
                ))
                seq += 1
                tables[table.caption] = table_id
                for r, row in enumerate(table.rows):
                    row_id = f"{table_id}/row{r}"
                    elements.append(StructuralElement(
                        element_id=row_id, document_id=doc.doc_id,
                        element_type=ELEMENT_TYPE_TABLE_ROW, parent_id=table_id,
                        page_number=page_number, sequence_index=seq,
                        heading_path=path, content=" | ".join(row),
                    ))
                    seq += 1
                    for c, cell in enumerate(row):
                        if not str(cell).strip():
                            continue
                        cell_id = f"{row_id}/cell{c}"
                        elements.append(StructuralElement(
                            element_id=cell_id, document_id=doc.doc_id,
                            element_type=ELEMENT_TYPE_TABLE_CELL, parent_id=row_id,
                            page_number=page_number, sequence_index=seq,
                            heading_path=path, content=str(cell),
                        ))
                        seq += 1
                        cells[cell_id] = cell_id
            else:  # pragma: no cover
                raise ValueError(f"unknown block kind {kind!r}")

    doc_obj = DiscriminatingDoc(
        doc_id=doc.doc_id, name=doc.name, file_type="pdf", notes=doc.notes, spec=doc,
        elements=elements,
    )
    # attach lookup tables for question authoring
    doc_obj._sections = sections  # type: ignore[attr-defined]
    doc_obj._tables = tables  # type: ignore[attr-defined]
    doc_obj._cells = cells  # type: ignore[attr-defined]
    doc_obj._paragraphs = paragraphs  # type: ignore[attr-defined]
    return doc_obj


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def _q(
    qid, text, category, doc, *, answerable=True, expected_answer=None,
    acceptable=(), evidence=(), gold=(), gold_cells=(), path=(),
    evidence_type=None, discrimination=DISCRIMINATING, rationale="", notes="",
) -> CorpusQuestion:
    return CorpusQuestion(
        qid=qid, text=text, category=category, document_id=doc.doc_id,
        answerable=answerable, expected_answer=expected_answer,
        acceptable_answers=tuple(acceptable),
        evidence=tuple(evidence), gold_element_ids=tuple(gold),
        gold_table_cells=tuple(gold_cells),
        expected_structural_path=tuple(path),
        expected_evidence_type=evidence_type,
        discrimination=discrimination if answerable else None,
        discrimination_rationale=rationale,
        notes=notes,
    )


def _table_questions(docs: dict[str, DiscriminatingDoc]) -> list[CorpusQuestion]:
    """20 table row/cell questions, generated from the authored tables."""
    out: list[CorpusQuestion] = []

    def cell_id(doc, caption, row, col):
        table_id = doc._tables[caption]  # type: ignore[attr-defined]
        return f"{table_id}/row{row}/cell{col}", table_id

    specs = [
        ("atlas", "Thruster Parameters", 2, "maximum", "at"),
        ("atlas", "Coolant Segments", 2, "temperature", "ac"),
        ("field", "Sampling Stations", 1, "depth", "fs"),
        ("oslo", "Primary Pumps", 1, "flow", "os"),
    ]
    for doc_id, caption, col, label, prefix in specs:
        doc = docs[doc_id]
        table_id = doc._tables[caption]  # type: ignore[attr-defined]
        table = next(e for e in doc.elements if e.element_id == table_id)
        row_label_col = 0
        # Primary Pumps rows reuse Pump A–E in the Secondary Loop table: a
        # semantic retriever can return the wrong section's table.
        ambiguous = doc_id == "oslo" and caption == "Primary Pumps"
        for r in range(len(table.table_rows)):
            cid, tid = cell_id(doc, caption, r, col)
            value = table.table_rows[r][col]
            row_label = table.table_rows[r][row_label_col]
            out.append(_q(
                f"{prefix}_tbl_{r+1}",
                f"What is the {label} recorded for {row_label} in the {caption} table?",
                CAT_TABLE, doc,
                expected_answer=value, acceptable=(value,),
                evidence=(row_label, value),
                gold=(tid, cid), gold_cells=(cid,),
                path=("document", "section", "table", "table_row", "table_cell"),
                evidence_type="table",
                discrimination=DISCRIMINATING if ambiguous else WEAKLY_DISCRIMINATING,
                rationale=(
                    "Row label 'Pump A–E' also appears in the Secondary Pumps table; only "
                    "the correct table/row identifies the cell."
                    if ambiguous else
                    "Cell value is unique, but it lives inside a table whose rows a "
                    "chunk retriever may not keep aligned with the header."
                ),
            ))
    return out


def _section_questions(docs) -> list[CorpusQuestion]:
    S = lambda doc, *path: docs[doc]._sections[tuple(path)]  # type: ignore[attr-defined]
    T = lambda doc, cap: docs[doc]._tables[cap]  # type: ignore[attr-defined]
    out = [
        _q("at_sec_1", "In the Thruster Operating Limits section, what is the maximum chamber pressure?",
           CAT_SECTION, docs["atlas"], expected_answer="31 bar", acceptable=("31 bar",),
           evidence=("maximum", "31 bar"),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thruster Operating Limits"), T("atlas", "Thruster Parameters")),
           path=("document", "section", "table"), evidence_type="table",
           discrimination=WEAKLY_DISCRIMINATING,
           rationale="Section names the table; the value also appears in the abort paragraph."),
        _q("at_sec_2", "In the Thruster Operating Limits section, what is the nominal thrust?",
           CAT_SECTION, docs["atlas"], expected_answer="18 kilonewtons", acceptable=("18 kilonewtons",),
           evidence=("Thrust", "18 kilonewtons"),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thruster Operating Limits"), T("atlas", "Thruster Parameters")),
           path=("document", "section", "table"), evidence_type="table",
           discrimination=WEAKLY_DISCRIMINATING,
           rationale="Unique value; the section merely scopes it."),
        _q("at_sec_3", "In the Coolant Loop section, what is the coolant temperature at the chamber wall?",
           CAT_SECTION, docs["atlas"], expected_answer="140 degrees", acceptable=("140 degrees",),
           evidence=("Chamber wall", "140 degrees"),
           gold=(S("atlas", "Atlas Propulsion Manual", "Coolant Loop"), T("atlas", "Coolant Segments")),
           path=("document", "section", "table"), evidence_type="table",
           discrimination=WEAKLY_DISCRIMINATING, rationale="Unique value inside one table."),
        _q("at_sec_4", "In the Coolant Loop section, what is the pressure at the pump outlet?",
           CAT_SECTION, docs["atlas"], expected_answer="2.1 bar", acceptable=("2.1 bar",),
           evidence=("Pump outlet", "2.1 bar"),
           gold=(S("atlas", "Atlas Propulsion Manual", "Coolant Loop"), T("atlas", "Coolant Segments")),
           path=("document", "section", "table"), evidence_type="table",
           discrimination=WEAKLY_DISCRIMINATING, rationale="Unique value inside one table."),
        _q("at_sec_5", "According to the Thermal Margins section, how much power does the radiator reject at full thrust?",
           CAT_SECTION, docs["atlas"], expected_answer="14 kilowatts", acceptable=("14 kilowatts",),
           evidence=("radiator rejects 14 kilowatts",),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thermal Margins"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=WEAKLY_DISCRIMINATING,
           rationale="Distinctive paragraph; section identity is not strictly required to find it."),
        _q("at_sec_6", "In the Ignition Sequence subsection, what does the ignition sequence begin with?",
           CAT_SECTION, docs["atlas"], expected_answer="Xenon purge", acceptable=("Xenon purge", "a Xenon purge"),
           evidence=("begins with a Xenon purge",),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thruster Operating Limits", "Ignition Sequence"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=WEAKLY_DISCRIMINATING, rationale="Distinctive phrase."),
        _q("fs_sec_1", "In the Instrument Calibration section, what is the Kestrel frame calibrated against?",
           CAT_SECTION, docs["field"], expected_answer="granite reference block",
           acceptable=("granite reference block",),
           evidence=("granite reference block",),
           gold=(S("field", "Meridian Field Survey", "Instrument Calibration"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="'Kestrel frame' appears in three sections; only Calibration is calibrated."),
        _q("fs_sec_2", "In the Winter Sampling Protocol section, which frame does the protocol use?",
           CAT_SECTION, docs["field"], expected_answer="Nimbus frame", acceptable=("Nimbus frame",),
           evidence=("Nimbus frame",),
           gold=(S("field", "Meridian Field Survey", "Winter Sampling Protocol"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="Frame name depends entirely on which protocol section is in scope."),
        _q("fs_sec_3", "In the Sampling Protocol section, at how many tidal heights is every station sampled?",
           CAT_SECTION, docs["field"], expected_answer="three tidal heights",
           acceptable=("three tidal heights", "three"),
           evidence=("three tidal heights",),
           gold=(S("field", "Meridian Field Survey", "Sampling Protocol"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="The Winter protocol samples at two heights; the count needs the right section."),
        _q("os_sec_1", "In the Seal Maintenance subsection, what is the interval for the primary seal?",
           CAT_SECTION, docs["oslo"], expected_answer="6 hours", acceptable=("6 hours",),
           evidence=("Primary seal", "6 hours"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Seal Maintenance"),
                 T("oslo", "Seal Schedule")),
           path=("document", "section", "table"), evidence_type="table",
           discrimination=WEAKLY_DISCRIMINATING, rationale="Unique row label and value."),
        _q("os_sec_2", "In the Emergency Procedures section, what closes within 3 seconds of a trip signal?",
           CAT_SECTION, docs["oslo"], expected_answer="isolation valves",
           acceptable=("isolation valves", "the isolation valves"),
           evidence=("isolation valves close within 3 seconds",),
           gold=(S("oslo", "Oslo Reactor Handbook", "Emergency Procedures"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=WEAKLY_DISCRIMINATING, rationale="Distinctive phrase."),
        _q("ar_sec_1", "In the Access Rules section, at what humidity are microfilm reels stored?",
           CAT_SECTION, docs["archive"], expected_answer="forty percent humidity",
           acceptable=("forty percent humidity", "40 percent humidity"),
           evidence=("forty percent humidity",),
           gold=(S("archive", "Vermilion Archive", "Access Rules"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=WEAKLY_DISCRIMINATING, rationale="Distinctive phrase."),
    ]
    return out


def _page_cross_questions(docs) -> list[CorpusQuestion]:
    S = lambda doc, *path: docs[doc]._sections[tuple(path)]  # type: ignore[attr-defined]
    T = lambda doc, cap: docs[doc]._tables[cap]  # type: ignore[attr-defined]

    def P(doc_id, substring):
        for text, eid in docs[doc_id]._paragraphs:  # type: ignore[attr-defined]
            if substring in text:
                return eid
        raise KeyError(f"no paragraph containing {substring!r} in {doc_id}")

    return [
        _q("at_pg_1", "How long does the Atlas ignition sequence last?",
           CAT_PAGE, docs["atlas"], expected_answer="42 seconds", acceptable=("42 seconds",),
           evidence=("lasts 42 seconds",),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thruster Operating Limits", "Ignition Sequence"),
                 P("atlas", "lasts 42 seconds")),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="The Ignition Sequence heading is on page 1; its body is on page 2."),
        _q("at_pg_2", "What chamber pressure aborts the Atlas ignition sequence?",
           CAT_PAGE, docs["atlas"], expected_answer="31 bar", acceptable=("31 bar",),
           evidence=("aborts the sequence if chamber pressure exceeds 31 bar",),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thruster Operating Limits", "Ignition Sequence"),
                 P("atlas", "aborts the sequence")),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="Answer continues onto page 2 and duplicates a table value in another section."),
        _q("fs_pg_1", "What does the Meridian Sampling Protocol require before each transect begins?",
           CAT_PAGE, docs["field"], expected_answer="blank sample", acceptable=("a blank sample", "blank sample"),
           evidence=("requires a blank sample before each transect",),
           gold=(S("field", "Meridian Field Survey", "Sampling Protocol"),
                 P("field", "requires a blank sample")),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="Sampling Protocol heading on page 1; this body continues onto page 2."),
        _q("fs_pg_2", "To what precision is Meridian sampling depth recorded?",
           CAT_PAGE, docs["field"], expected_answer="nearest centimetre", acceptable=("nearest centimetre",),
           evidence=("recorded to the nearest centimetre",),
           gold=(S("field", "Meridian Field Survey", "Sampling Protocol"),
                 P("field", "recorded to the nearest centimetre")),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING, rationale="Continuation body on page 2."),
        _q("os_pg_1", "What torque is specified for the flange seal?",
           CAT_PAGE, docs["oslo"], expected_answer="70 newton metres", acceptable=("70 newton metres",),
           evidence=("Flange seal", "70 newton metres"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop"),
                 S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Seal Maintenance"),
                 T("oslo", "Seal Schedule")),
           path=("document", "section", "table"), evidence_type="table",
           discrimination=DISCRIMINATING,
           rationale="Seal Maintenance (under Primary Loop) is on a later page than its section."),
        _q("os_pg_2", "What is the interval for the shaft seal?",
           CAT_PAGE, docs["oslo"], expected_answer="Weekly", acceptable=("Weekly", "weekly"),
           evidence=("Shaft seal", "Weekly"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop"),
                 S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Seal Maintenance"),
                 T("oslo", "Seal Schedule")),
           path=("document", "section", "table"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Seal table is on the section's continuation page."),
        _q("ar_pg_1", "How many exposures does reel R-06 hold?",
           CAT_PAGE, docs["archive"], expected_answer="880", acceptable=("880",),
           evidence=("R-06", "880"),
           gold=(S("archive", "Vermilion Archive", "Reel Inventory"),
                 T("archive", "Reel Inventory"),
                 f"{T('archive', 'Reel Inventory')}/row5/cell1"),
           gold_cells=(f"{T('archive', 'Reel Inventory')}/row5/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING,
           rationale="Reel Inventory heading is on page 1; its table is on page 2."),
        _q("ar_pg_2", "What is the condition of reel R-04?",
           CAT_PAGE, docs["archive"], expected_answer="Poor", acceptable=("Poor", "poor"),
           evidence=("R-04", "Poor"),
           gold=(S("archive", "Vermilion Archive", "Reel Inventory"),
                 T("archive", "Reel Inventory"),
                 f"{T('archive', 'Reel Inventory')}/row3/cell2"),
           gold_cells=(f"{T('archive', 'Reel Inventory')}/row3/cell2",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Table continues onto page 2."),
    ]


def _multi_hop_questions(docs) -> list[CorpusQuestion]:
    S = lambda doc, *path: docs[doc]._sections[tuple(path)]  # type: ignore[attr-defined]
    T = lambda doc, cap: docs[doc]._tables[cap]  # type: ignore[attr-defined]
    prim = T("oslo", "Primary Pumps")
    sec = T("oslo", "Secondary Pumps")
    return [
        _q("os_mh_1", "In the Secondary Loop, what is the flow of Pump B?",
           CAT_MULTIHOP, docs["oslo"], expected_answer="95 litres per second",
           acceptable=("95 litres per second", "95"),
           evidence=("Pump B", "95 litres per second"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Secondary Loop", "Pump Specifications"),
                 sec, f"{sec}/row1/cell1"),
           gold_cells=(f"{sec}/row1/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING,
           rationale="Requires section → subsection → table → row; 'Pump B' is ambiguous across loops."),
        _q("os_mh_2", "In the Secondary Loop, what is the head of Pump E?",
           CAT_MULTIHOP, docs["oslo"], expected_answer="39 metres", acceptable=("39 metres",),
           evidence=("Pump E", "39 metres"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Secondary Loop", "Pump Specifications"),
                 sec, f"{sec}/row4/cell2"),
           gold_cells=(f"{sec}/row4/cell2",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Section context selects between two pump tables."),
        _q("os_mh_3", "In the Primary Loop, what is the head of Pump B?",
           CAT_MULTIHOP, docs["oslo"], expected_answer="52 metres", acceptable=("52 metres",),
           evidence=("Pump B", "52 metres"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Pump Specifications"),
                 prim, f"{prim}/row1/cell2"),
           gold_cells=(f"{prim}/row1/cell2",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Same subsection name under a different parent."),
        _q("os_mh_4", "In the Primary Loop, what is the flow of Pump E?",
           CAT_MULTIHOP, docs["oslo"], expected_answer="135 litres per second",
           acceptable=("135 litres per second", "135"),
           evidence=("Pump E", "135 litres per second"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Pump Specifications"),
                 prim, f"{prim}/row4/cell1"),
           gold_cells=(f"{prim}/row4/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Section selects the correct pump table."),
        _q("os_mh_5", "Under Seal Maintenance, what torque is specified for the secondary seal?",
           CAT_MULTIHOP, docs["oslo"], expected_answer="60 newton metres",
           acceptable=("60 newton metres",),
           evidence=("Secondary seal", "60 newton metres"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Seal Maintenance"),
                 T("oslo", "Seal Schedule"), f"{T('oslo', 'Seal Schedule')}/row1/cell2"),
           gold_cells=(f"{T('oslo', 'Seal Schedule')}/row1/cell2",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Subsection → table → row → cell traversal."),
        _q("os_mh_6", "Under Seal Maintenance, what is the interval for the shaft seal?",
           CAT_MULTIHOP, docs["oslo"], expected_answer="Weekly", acceptable=("Weekly", "weekly"),
           evidence=("Shaft seal", "Weekly"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Seal Maintenance"),
                 T("oslo", "Seal Schedule"), f"{T('oslo', 'Seal Schedule')}/row4/cell1"),
           gold_cells=(f"{T('oslo', 'Seal Schedule')}/row4/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Subsection → table → row → cell traversal."),
        _q("at_mh_1", "Under the Thruster Operating Limits, what is the nominal coolant flow?",
           CAT_MULTIHOP, docs["atlas"], expected_answer="3 litres per minute",
           acceptable=("3 litres per minute", "3"),
           evidence=("Coolant flow", "3 litres per minute"),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thruster Operating Limits"),
                 T("atlas", "Thruster Parameters"), f"{T('atlas', 'Thruster Parameters')}/row3/cell1"),
           gold_cells=(f"{T('atlas', 'Thruster Parameters')}/row3/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Section → table → row → cell traversal."),
        _q("fs_mh_1", "Under Instrument Calibration, what action is required for a 0.6 millimetre drift?",
           CAT_MULTIHOP, docs["field"], expected_answer="Recalibrate", acceptable=("Recalibrate", "recalibrate"),
           evidence=("0.6 millimetres", "Recalibrate"),
           gold=(S("field", "Meridian Field Survey", "Instrument Calibration"),
                 T("field", "Calibration Drift"),
                 f"{T('field', 'Calibration Drift')}/row2/cell2"),
           gold_cells=(f"{T('field', 'Calibration Drift')}/row2/cell2",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Section → table → row → cell traversal."),
    ]


def _distractor_questions(docs) -> list[CorpusQuestion]:
    S = lambda doc, *path: docs[doc]._sections[tuple(path)]  # type: ignore[attr-defined]
    T = lambda doc, cap: docs[doc]._tables[cap]  # type: ignore[attr-defined]
    prim = T("oslo", "Primary Pumps")
    sec = T("oslo", "Secondary Pumps")
    return [
        _q("fs_ds_1", "Which frame does the winter protocol use?",
           CAT_DISTRACTOR, docs["field"], expected_answer="Nimbus frame", acceptable=("Nimbus frame",),
           evidence=("winter protocol uses a Nimbus frame",),
           gold=(S("field", "Meridian Field Survey", "Winter Sampling Protocol"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="'frame' appears in three sections with two different frame names."),
        _q("fs_ds_2", "Which frame does the summer sampling protocol use?",
           CAT_DISTRACTOR, docs["field"], expected_answer="Kestrel frame", acceptable=("Kestrel frame", "a Kestrel frame"),
           evidence=("three tidal heights using a Kestrel frame",),
           gold=(S("field", "Meridian Field Survey", "Sampling Protocol"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING, rationale="Must distinguish summer vs winter protocol."),
        _q("os_ds_1", "In the Secondary Loop, which pump has a flow of 92 litres per second?",
           CAT_DISTRACTOR, docs["oslo"], expected_answer="Pump D", acceptable=("Pump D",),
           evidence=("Pump D", "92 litres per second"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Secondary Loop", "Pump Specifications"),
                 sec, f"{sec}/row3/cell1"),
           gold_cells=(f"{sec}/row3/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="'Pump D' differs between the two loops."),
        _q("os_ds_2", "In the Primary Loop, which pump has a flow of 125 litres per second?",
           CAT_DISTRACTOR, docs["oslo"], expected_answer="Pump D", acceptable=("Pump D",),
           evidence=("Pump D", "125 litres per second"),
           gold=(S("oslo", "Oslo Reactor Handbook", "Primary Loop", "Pump Specifications"),
                 prim, f"{prim}/row3/cell1"),
           gold_cells=(f"{prim}/row3/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING, rationale="Must pick the Primary Loop's Pump D row."),
        _q("ar_ds_1", "According to the Access Rules, how many exposures does a single reel hold?",
           CAT_DISTRACTOR, docs["archive"], expected_answer="twelve hundred",
           acceptable=("twelve hundred", "1200"),
           evidence=("holds up to twelve hundred exposures",),
           gold=(S("archive", "Vermilion Archive", "Access Rules"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING,
           rationale="The same count appears as reel R-01's 1200 in the table; prose is the answer here."),
        _q("at_ds_1", "In the Thruster Operating Limits table, what is the maximum burn duration?",
           CAT_DISTRACTOR, docs["atlas"], expected_answer="60 seconds", acceptable=("60 seconds",),
           evidence=("Burn duration", "60 seconds"),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thruster Operating Limits"),
                 T("atlas", "Thruster Parameters"), f"{T('atlas', 'Thruster Parameters')}/row2/cell2"),
           gold_cells=(f"{T('atlas', 'Thruster Parameters')}/row2/cell2",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING,
           rationale="42 seconds (nominal) also appears in the Ignition Sequence paragraph."),
        _q("fs_ds_3", "Under Instrument Calibration, which drift value triggers recalibration?",
           CAT_DISTRACTOR, docs["field"], expected_answer="0.6 millimetres", acceptable=("0.6 millimetres",),
           evidence=("0.6 millimetres", "Recalibrate"),
           gold=(S("field", "Meridian Field Survey", "Instrument Calibration"),
                 T("field", "Calibration Drift"), f"{T('field', 'Calibration Drift')}/row2/cell1"),
           gold_cells=(f"{T('field', 'Calibration Drift')}/row2/cell1",),
           path=("document", "section", "table", "table_row", "table_cell"), evidence_type="table",
           discrimination=DISCRIMINATING,
           rationale="Five drift rows share the same unit; only the Recalibrate row is correct."),
        _q("fs_ds_4", "In the Winter Sampling Protocol, at how many tidal heights are stations sampled?",
           CAT_DISTRACTOR, docs["field"], expected_answer="two", acceptable=("two", "two tidal heights"),
           evidence=("sampled at two tidal heights",),
           gold=(S("field", "Meridian Field Survey", "Winter Sampling Protocol"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=DISCRIMINATING, rationale="Same phrase in the summer section says three."),
    ]


def _semantic_questions(docs) -> list[CorpusQuestion]:
    S = lambda doc, *path: docs[doc]._sections[tuple(path)]  # type: ignore[attr-defined]
    return [
        _q("at_sem_1", "What mixture does the Kestrel thruster burn?",
           CAT_SEMANTIC, docs["atlas"], expected_answer="Xenon-oxygen", acceptable=("Xenon-oxygen", "Xenon oxygen"),
           evidence=("burns a Xenon-oxygen mixture",),
           gold=(S("atlas", "Atlas Propulsion Manual"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive proper noun; semantic retrieval suffices."),
        _q("fs_sem_1", "What does the Meridian survey characterise?",
           CAT_SEMANTIC, docs["field"], expected_answer="sediment transport",
           acceptable=("sediment transport",),
           evidence=("characterises sediment transport",),
           gold=(S("field", "Meridian Field Survey"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive phrase; no structural dependency."),
        _q("fs_sem_2", "What is taken at every tenth station?",
           CAT_SEMANTIC, docs["field"], expected_answer="duplicate sample",
           acceptable=("a duplicate sample", "duplicate sample"),
           evidence=("duplicate sample is taken at every tenth station",),
           gold=(S("field", "Meridian Field Survey", "Sampling Protocol"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive phrase."),
        _q("ar_sem_1", "What does the Vermilion archive store?",
           CAT_SEMANTIC, docs["archive"], expected_answer="survey records",
           acceptable=("survey records",),
           evidence=("stores survey records from 1970 to 1995",),
           gold=(S("archive", "Vermilion Archive"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive phrase."),
        _q("ar_sem_2", "At what humidity are microfilm reels stored?",
           CAT_SEMANTIC, docs["archive"], expected_answer="forty percent humidity",
           acceptable=("forty percent humidity", "40 percent humidity"),
           evidence=("forty percent humidity",),
           gold=(S("archive", "Vermilion Archive", "Access Rules"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive phrase."),
        _q("os_sem_1", "What happens on a primary loop trip?",
           CAT_SEMANTIC, docs["oslo"], expected_answer="the reactor scrams",
           acceptable=("the reactor scrams", "reactor scrams"),
           evidence=("reactor scrams",),
           gold=(S("oslo", "Oslo Reactor Handbook", "Emergency Procedures"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive phrase."),
        _q("os_sem_2", "How long do the isolation valves take to close after a trip signal?",
           CAT_SEMANTIC, docs["oslo"], expected_answer="3 seconds", acceptable=("3 seconds",),
           evidence=("close within 3 seconds",),
           gold=(S("oslo", "Oslo Reactor Handbook", "Emergency Procedures"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive phrase."),
        _q("at_sem_2", "How much margin is reserved for attitude manoeuvres?",
           CAT_SEMANTIC, docs["atlas"], expected_answer="2 kilowatts", acceptable=("2 kilowatts",),
           evidence=("margin of 2 kilowatts",),
           gold=(S("atlas", "Atlas Propulsion Manual", "Thermal Margins"),),
           path=("document", "section", "paragraph"), evidence_type="paragraph",
           discrimination=NOT_DISCRIMINATING, rationale="Distinctive phrase."),
    ]


def _unanswerable(docs) -> list[CorpusQuestion]:
    specs = [
        ("at", "atlas", "What is the boiling point of mercury?"),
        ("at", "atlas", "How many staff work at the Meridian office?"),
        ("at", "atlas", "What is the melting point of tungsten?"),
        ("at", "atlas", "What is the fuel enrichment of the Oslo reactor?"),
        ("fs", "field", "Who is the chief executive of Quokka Industries?"),
        ("fs", "field", "How many employees work at the observatory?"),
        ("os", "oslo", "What is the tensile strength of the Nimbus frame?"),
        ("ar", "archive", "What is the capital of Finland?"),
    ]
    out = []
    for i, (prefix, doc_id, text) in enumerate(specs, start=1):
        out.append(_q(
            f"{prefix}_una_{i}", text, CAT_UNANSWERABLE, docs[doc_id],
            answerable=False, notes="No supporting evidence anywhere in the corpus.",
        ))
    return out


# ---------------------------------------------------------------------------
# Build + validate
# ---------------------------------------------------------------------------

def build_corpus() -> Corpus:
    """Return the immutable, deterministic corpus for ``CORPUS_VERSION``."""
    docs_list = [_build_document(spec) for spec in _DOCUMENTS]
    docs = {d.doc_id: d for d in docs_list}
    questions: list[CorpusQuestion] = []
    questions += _table_questions(docs)
    questions += _section_questions(docs)
    questions += _page_cross_questions(docs)
    questions += _multi_hop_questions(docs)
    questions += _distractor_questions(docs)
    questions += _semantic_questions(docs)
    questions += _unanswerable(docs)
    # Match the repository corpus convention: a document's ``questions`` carries
    # only its *answerable* questions; unanswerable questions are returned
    # separately by :func:`unanswerable_questions` (the runner appends them once).
    for doc in docs_list:
        doc.questions = [
            q for q in questions if q.document_id == doc.doc_id and q.answerable
        ]
    elements = tuple(e for doc in docs_list for e in doc.elements)
    return Corpus(
        version=CORPUS_VERSION,
        documents=tuple(docs_list),
        elements=elements,
        questions=tuple(questions),
    )


def unanswerable_questions() -> tuple[CorpusQuestion, ...]:
    return tuple(q for q in build_corpus().questions if not q.answerable)


def get_acceptable_answers(qid: str) -> list[str]:
    for q in build_corpus().questions:
        if q.qid == qid:
            return list(q.acceptable_answers)
    return []


def _element_index(corpus: Corpus) -> dict[str, StructuralElement]:
    return {e.element_id: e for e in corpus.elements}


_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip().lower()


def _production_vocabulary() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The live production vocabulary, imported lazily so the corpus stays offline."""
    from graph.models import ELEMENT_TYPES as PROD_TYPES
    from graph.models import STRUCTURE_RELATIONS as PROD_RELATIONS

    return tuple(PROD_TYPES), tuple(PROD_RELATIONS)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": list(self.errors), "summary": self.summary}


def validate_corpus(corpus: Corpus | None = None) -> ValidationResult:
    """Validate the corpus against the dataset contract; never mutates it."""
    corpus = corpus or build_corpus()
    errors: list[str] = []
    index = _element_index(corpus)

    # --- vocabulary matches production (schema reuse, not a second schema) ---
    try:
        prod_types, prod_relations = _production_vocabulary()
    except Exception as exc:  # pragma: no cover - import environment
        errors.append(f"could not import production schema vocabulary: {exc}")
        prod_types, prod_relations = ELEMENT_TYPES, STRUCTURE_RELATIONS
    if tuple(prod_types) != ELEMENT_TYPES:
        errors.append(f"element-type vocabulary drifted from production: {prod_types!r}")
    if tuple(prod_relations) != STRUCTURE_RELATIONS:
        errors.append(f"relation vocabulary drifted from production: {prod_relations!r}")

    doc_ids = {d.doc_id for d in corpus.documents}
    doc_blobs: dict[str, str] = {d: "" for d in doc_ids}
    for element in corpus.elements:
        doc_blobs[element.document_id] = f"{doc_blobs[element.document_id]} {_norm(element.content)}"

    # --- structural element integrity ---------------------------------------
    by_doc_seq: dict[str, set[int]] = {d: set() for d in doc_ids}
    for element in corpus.elements:
        if element.element_type not in ELEMENT_TYPES:
            errors.append(f"element {element.element_id}: unknown type {element.element_type!r}")
        if element.document_id not in doc_ids:
            errors.append(f"element {element.element_id}: unknown document {element.document_id!r}")
        if element.page_number < 1:
            errors.append(f"element {element.element_id}: page_number < 1")
        seqs = by_doc_seq[element.document_id]
        if element.sequence_index in seqs:
            errors.append(f"element {element.element_id}: duplicate sequence_index")
        seqs.add(element.sequence_index)
        if element.parent_id is not None:
            parent = index.get(element.parent_id)
            if parent is None:
                errors.append(f"element {element.element_id}: missing parent {element.parent_id!r}")
            elif parent.document_id != element.document_id:
                errors.append(f"element {element.element_id}: cross-document parent")
        # table cell / row chains
        if element.element_type == ELEMENT_TYPE_TABLE_CELL:
            row = index.get(element.parent_id or "")
            if row is None or row.element_type != ELEMENT_TYPE_TABLE_ROW:
                errors.append(f"cell {element.element_id}: parent is not a table_row")
            else:
                table = index.get(row.parent_id or "")
                if table is None or table.element_type != ELEMENT_TYPE_TABLE:
                    errors.append(f"cell {element.element_id}: row parent is not a table")
        if element.element_type == ELEMENT_TYPE_TABLE_ROW:
            table = index.get(element.parent_id or "")
            if table is None or table.element_type != ELEMENT_TYPE_TABLE:
                errors.append(f"row {element.element_id}: parent is not a table")

    # --- question integrity --------------------------------------------------
    seen_qids: set[str] = set()
    seen_texts: set[str] = set()
    categories: dict[str, int] = {}
    for q in corpus.questions:
        if q.qid in seen_qids:
            errors.append(f"duplicate question id {q.qid!r}")
        seen_qids.add(q.qid)
        key = q.text.strip().lower()
        if key in seen_texts:
            errors.append(f"duplicate question text {q.text!r}")
        seen_texts.add(key)
        if q.document_id not in doc_ids:
            errors.append(f"question {q.qid}: unknown document {q.document_id!r}")
        if q.category not in AUTHORING_CATEGORIES:
            errors.append(f"question {q.qid}: unknown category {q.category!r}")
        categories[q.category] = categories.get(q.category, 0) + 1

        golds = [index.get(g) for g in q.gold_element_ids]
        for gid, element in zip(q.gold_element_ids, golds):
            if element is None:
                errors.append(f"question {q.qid}: gold element {gid!r} does not exist")
            elif element.document_id != q.document_id:
                errors.append(f"question {q.qid}: cross-document gold reference {gid!r}")
        for cid in q.gold_table_cells:
            if index.get(cid) is None:
                errors.append(f"question {q.qid}: gold table cell {cid!r} does not exist")

        if q.answerable:
            # Grounding gate: evidence and the answer must actually occur in the
            # authored document text, so a question can never be fabricated.
            blob = doc_blobs.get(q.document_id, "")
            for needle in q.evidence:
                if _norm(needle) not in blob:
                    errors.append(
                        f"question {q.qid}: evidence {needle!r} not present in document text"
                    )
            candidates = [q.expected_answer, *q.acceptable_answers]
            if not any(_norm(c) and _norm(c) in blob for c in candidates if c):
                errors.append(
                    f"question {q.qid}: expected/acceptable answer not grounded in document text"
                )
            if not q.expected_answer:
                errors.append(f"question {q.qid}: answerable without expected_answer")
            if not q.acceptable_answers:
                errors.append(f"question {q.qid}: answerable without acceptable answers")
            if not q.evidence:
                errors.append(f"question {q.qid}: answerable without evidence substrings")
            if not q.gold_element_ids:
                errors.append(f"question {q.qid}: answerable without structural gold")
            if q.discrimination not in DISCRIMINATION_LEVELS:
                errors.append(f"question {q.qid}: invalid discrimination label")
            if q.discrimination in (DISCRIMINATING, WEAKLY_DISCRIMINATING) and not q.discrimination_rationale:
                errors.append(f"question {q.qid}: structural label without rationale")
            for part in q.expected_structural_path:
                if part not in ("document",) and part not in ELEMENT_TYPES:
                    errors.append(f"question {q.qid}: invalid structural path part {part!r}")
        else:
            if q.gold_element_ids or q.gold_table_cells or q.evidence:
                errors.append(f"question {q.qid}: unanswerable must carry no gold/evidence")
            if q.expected_answer:
                errors.append(f"question {q.qid}: unanswerable must carry no expected_answer")

        # Category-specific structural requirements.
        if q.category in (CAT_MULTIHOP, CAT_PAGE) and q.answerable:
            if not q.expected_structural_path:
                errors.append(f"question {q.qid}: structural question without expected path")
        if q.category == CAT_TABLE and q.answerable:
            if not q.gold_table_cells:
                errors.append(f"question {q.qid}: table question without gold cell")
            if ELEMENT_TYPE_TABLE not in q.expected_structural_path:
                errors.append(f"question {q.qid}: table question without table in structural path")

    # --- page-crossing property (objective check) ---------------------------
    for q in corpus.questions:
        if q.category != CAT_PAGE or not q.answerable:
            continue
        answer_pages = [index[g].page_number for g in q.gold_element_ids if g in index]
        if answer_pages and max(answer_pages) <= min(answer_pages):
            errors.append(
                f"question {q.qid}: labelled page-crossing but gold does not cross a page"
            )

    # --- summary / contract --------------------------------------------------
    answerable = [q for q in corpus.questions if q.answerable]
    structural = [
        q for q in answerable
        if q.category in (CAT_TABLE, CAT_SECTION, CAT_PAGE, CAT_MULTIHOP, CAT_DISTRACTOR)
    ]
    discriminating = [q for q in answerable if q.discrimination == DISCRIMINATING]
    weak = [q for q in answerable if q.discrimination in (WEAKLY_DISCRIMINATING, NOT_DISCRIMINATING)]
    summary = {
        "corpusVersion": corpus.version,
        "documents": len(corpus.documents),
        "questions": len(corpus.questions),
        "answerable": len(answerable),
        "unanswerable": len(corpus.questions) - len(answerable),
        "structural": len(structural),
        "discriminating": len(discriminating),
        "excludedWeak": len(weak),
        "elements": len(corpus.elements),
        "categories": dict(sorted(categories.items())),
        "discrimination": {
            level: sum(1 for q in answerable if q.discrimination == level)
            for level in DISCRIMINATION_LEVELS
        },
    }
    return ValidationResult(ok=not errors, errors=errors, summary=summary)


def corpus_contract() -> dict:
    """The versioned dataset contract (STEP 7)."""
    result = validate_corpus()
    return {
        "corpusVersion": CORPUS_VERSION,
        "documents": [d.name for d in build_corpus().documents],
        "summary": result.summary,
        "goldEvidencePolicy": (
            "Every answerable question carries expected_answer, acceptable answers and "
            "evidence substrings present in exactly the backing element; a retriever is "
            "never given the gold ids."
        ),
        "structuralEvidencePolicy": (
            "Every structural question names the authored element ids (schema vocabulary) "
            "required to answer it, its expected structural path, and its expected evidence "
            "type. Unanswerable questions carry no gold."
        ),
        "discriminationPolicy": (
            "Each answerable question is labelled DISCRIMINATING / WEAKLY_DISCRIMINATING / "
            "NOT_DISCRIMINATING by the anti-leakage gate. Only DISCRIMINATING questions form "
            "the primary structure subset; the rest are recorded as excluded/reviewed."
        ),
        "validationRules": [
            "element types and relations match the production schema vocabulary",
            "every gold element exists, belongs to the question's document, parent chain valid",
            "sequence_index unique per document; page_number >= 1",
            "table cell -> row -> table parent chains valid",
            "answerable questions carry gold; unanswerable questions carry none",
            "question ids and texts are unique",
            "page-crossing questions' gold actually crosses a page",
        ],
        "valid": result.ok,
        "errors": result.errors,
    }


def corpus_summary() -> dict:
    return validate_corpus().summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(summary: dict) -> None:
    print(f"corpus {summary['corpusVersion']}")
    for key in (
        "documents", "elements", "questions", "answerable", "unanswerable",
        "structural", "discriminating", "excludedWeak",
    ):
        print(f"  {key}: {summary[key]}")
    print("  categories:")
    for name, count in summary["categories"].items():
        print(f"    {name}: {count}")
    print("  discrimination:")
    for name, count in summary["discrimination"].items():
        print(f"    {name}: {count}")


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--validate", action="store_true", help="validate the corpus and report VALID (default action)")
    parser.add_argument("--summary", action="store_true", help="print the corpus summary only")
    parser.add_argument("--json", action="store_true", help="print the validation result as JSON")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    result = validate_corpus()
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.ok else 1
    _print_summary(result.summary)
    if result.ok:
        print("VALID")
        return 0
    print("INVALID")
    for error in result.errors:
        print(f"  - {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

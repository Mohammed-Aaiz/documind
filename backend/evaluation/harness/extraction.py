"""Phase 3F AC18 — Extraction evaluation.

Evaluates the document extraction pipeline against deterministic gold truth
for the existing Phase 3F corpus.  Gold data is established ONLY where the
corpus builder makes the expected structure objectively known.

No heuristic PDF heading inference is scored as authoritative.
No fuzzy semantic similarity is used as the primary correctness criterion.

This module NEVER imports production routes.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from documents.processing import extract_text, ExtractedElement


# ---------------------------------------------------------------------------
# Gold data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GoldElement:
    """Expected element in a document's gold extraction."""
    element_type: str  # heading, paragraph, table, list, text
    content_substring: str | None = None  # key substring that must appear
    heading_level: int | None = None  # only for DOCX/TXT (authoritative)
    heading_path: tuple[str, ...] | None = None  # only for DOCX/TXT
    table_rows: int | None = None  # expected row count for tables
    table_cols: int | None = None  # expected col count for tables
    table_header: tuple[str, ...] | None = None  # expected header cells
    list_item_count: int | None = None  # expected list item count
    list_items: tuple[str, ...] | None = None  # expected list item texts
    page: int | None = None  # expected page (PDF only)


@dataclass(frozen=True)
class GoldDocument:
    """Complete gold extraction truth for one corpus document."""
    name: str
    evaluable: bool  # False if gold truth cannot be established deterministically
    reason: str = ""  # why not evaluable (if applicable)
    elements: tuple[GoldElement, ...] = ()
    expected_heading_count: int = 0
    expected_paragraph_count: int = 0
    expected_table_count: int = 0
    expected_list_count: int = 0
    expected_total_count: int = 0
    score_heading_levels: bool = True  # False for PDFs (heuristic)
    score_heading_paths: bool = True  # False for PDFs (heuristic)
    score_content: bool = True  # False if content ordering is uncertain


# ---------------------------------------------------------------------------
# Gold extraction data — established deterministically from corpus builders
# ---------------------------------------------------------------------------

GOLD_DOCUMENTS: dict[str, GoldDocument] = {
    # =====================================================================
    # DOCX documents — authoritative heading/table/list detection
    # =====================================================================

    "short_sections.docx": GoldDocument(
        name="short_sections.docx",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=7,
        expected_paragraph_count=6,
        expected_table_count=0,
        expected_list_count=0,
        expected_total_count=13,
        elements=(
            GoldElement("heading", content_substring="Reference Manual",
                        heading_level=1, heading_path=("Reference Manual",)),
            GoldElement("heading", content_substring="Alpha",
                        heading_level=2, heading_path=("Reference Manual", "Alpha")),
            GoldElement("paragraph", content_substring="Zephyr valve"),
            GoldElement("heading", content_substring="Beta",
                        heading_level=2, heading_path=("Reference Manual", "Beta")),
            GoldElement("paragraph", content_substring="Nimbus sensor"),
            GoldElement("heading", content_substring="Gamma",
                        heading_level=2, heading_path=("Reference Manual", "Gamma")),
            GoldElement("paragraph", content_substring="Helios lamp"),
            GoldElement("heading", content_substring="Delta",
                        heading_level=2, heading_path=("Reference Manual", "Delta")),
            GoldElement("paragraph", content_substring="Quokka bracket"),
            GoldElement("heading", content_substring="Epsilon",
                        heading_level=2, heading_path=("Reference Manual", "Epsilon")),
            GoldElement("paragraph", content_substring="Vermilion coating"),
            GoldElement("heading", content_substring="Zeta",
                        heading_level=2, heading_path=("Reference Manual", "Zeta")),
            GoldElement("paragraph", content_substring="Solstice bearing"),
        ),
    ),

    "heading_heavy.docx": GoldDocument(
        name="heading_heavy.docx",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=7,
        expected_paragraph_count=4,
        expected_table_count=0,
        expected_list_count=0,
        expected_total_count=11,
        elements=(
            GoldElement("heading", content_substring="Handbook",
                        heading_level=1, heading_path=("Handbook",)),
            GoldElement("heading", content_substring="Installation",
                        heading_level=2, heading_path=("Handbook", "Installation")),
            GoldElement("heading", content_substring="Preparation",
                        heading_level=3, heading_path=("Handbook", "Installation", "Preparation")),
            GoldElement("heading", content_substring="Tools",
                        heading_level=4, heading_path=("Handbook", "Installation", "Preparation", "Tools")),
            GoldElement("paragraph", content_substring="Tundra torque wrench"),
            GoldElement("heading", content_substring="Wiring",
                        heading_level=4, heading_path=("Handbook", "Installation", "Preparation", "Wiring")),
            GoldElement("paragraph", content_substring="Kestrel cable"),
            GoldElement("heading", content_substring="Commissioning",
                        heading_level=2, heading_path=("Handbook", "Commissioning")),
            GoldElement("paragraph", content_substring="Commission the unit"),
            GoldElement("heading", content_substring="Maintenance",
                        heading_level=1, heading_path=("Maintenance",)),
            GoldElement("paragraph", content_substring="Zephyr filter"),
        ),
    ),

    "tables_small.docx": GoldDocument(
        name="tables_small.docx",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=1,
        expected_paragraph_count=0,
        expected_table_count=1,
        expected_list_count=0,
        expected_total_count=2,
        elements=(
            GoldElement("heading", content_substring="Results",
                        heading_level=1, heading_path=("Results",)),
            GoldElement("table", content_substring="PCA",
                        table_rows=3, table_cols=2,
                        table_header=("Method", "Result")),
        ),
    ),

    "tables_large.docx": GoldDocument(
        name="tables_large.docx",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=1,
        expected_paragraph_count=1,
        expected_table_count=1,
        expected_list_count=0,
        expected_total_count=3,
        elements=(
            GoldElement("heading", content_substring="Results",
                        heading_level=1, heading_path=("Results",)),
            GoldElement("table", content_substring="Method 30",
                        table_rows=31, table_cols=3,
                        table_header=("Method", "Accuracy", "Runtime")),
            GoldElement("paragraph", content_substring="recommended configuration"),
        ),
    ),

    "lists.docx": GoldDocument(
        name="lists.docx",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=2,
        expected_paragraph_count=0,
        expected_table_count=0,
        expected_list_count=2,
        expected_total_count=4,
        elements=(
            GoldElement("heading", content_substring="Procedure",
                        heading_level=1, heading_path=("Procedure",)),
            GoldElement("list", content_substring="Nimbus supply",
                        list_item_count=4,
                        list_items=(
                            "Isolate the Nimbus supply",
                            "Drain the Vermilion loop",
                            "Remove the Helios filter",
                            "Torque the Quokka bolts",
                        )),
            GoldElement("heading", content_substring="Checks",
                        heading_level=2, heading_path=("Procedure", "Checks")),
            GoldElement("list", content_substring="Zephyr reading",
                        list_item_count=2,
                        list_items=(
                            "Confirm the Zephyr reading",
                            "Log the Solstice temperature",
                        )),
        ),
    ),

    "mixed.docx": GoldDocument(
        name="mixed.docx",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=3,
        expected_paragraph_count=3,
        expected_table_count=1,
        expected_list_count=1,
        expected_total_count=8,
        elements=(
            GoldElement("heading", content_substring="Observatory Report",
                        heading_level=1, heading_path=("Observatory Report",)),
            GoldElement("paragraph", content_substring="Tundra survey"),
            GoldElement("heading", content_substring="Instrumentation",
                        heading_level=2, heading_path=("Observatory Report", "Instrumentation")),
            GoldElement("paragraph", content_substring="Nimbus array"),
            GoldElement("table", content_substring="Spring",
                        table_rows=3, table_cols=2,
                        table_header=("Season", "Pressure")),
            GoldElement("heading", content_substring="Findings",
                        heading_level=2, heading_path=("Observatory Report", "Findings")),
            GoldElement("paragraph", content_substring="lowest recorded pressure"),
            GoldElement("list", content_substring="Helios sensor",
                        list_item_count=2,
                        list_items=(
                            "The Helios sensor drifted by 2 millibars",
                            "The Zephyr probe remained stable",
                        )),
        ),
    ),

    # =====================================================================
    # TXT documents — deterministic Markdown/paragraph detection
    # =====================================================================

    "long_paragraph.txt": GoldDocument(
        name="long_paragraph.txt",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=0,
        expected_paragraph_count=2,
        expected_table_count=0,
        expected_list_count=0,
        expected_total_count=2,
        elements=(
            GoldElement("paragraph", content_substring="Meridian programme"),
            GoldElement("paragraph", content_substring="Meridian programme"),
        ),
    ),

    "dense_prose.txt": GoldDocument(
        name="dense_prose.txt",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=0,
        expected_paragraph_count=8,
        expected_table_count=0,
        expected_list_count=0,
        expected_total_count=8,
        elements=(
            GoldElement("paragraph", content_substring="Mariner survey"),
            GoldElement("paragraph", content_substring="stratified random"),
            GoldElement("paragraph", content_substring="laser diffraction"),
            GoldElement("paragraph", content_substring="41200 measurements"),
            GoldElement("paragraph", content_substring="1.4 kilograms"),
            GoldElement("paragraph", content_substring="14 millimetres"),
            GoldElement("paragraph", content_substring="sediment cores"),
            GoldElement("paragraph", content_substring="management recommendations"),
        ),
    ),

    "unpunctuated.txt": GoldDocument(
        name="unpunctuated.txt",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=0,
        expected_paragraph_count=1,
        expected_table_count=0,
        expected_list_count=0,
        expected_total_count=1,
        elements=(
            GoldElement("paragraph", content_substring="AlphaBetaGammaDelta"),
        ),
    ),

    "markdown_sections.txt": GoldDocument(
        name="markdown_sections.txt",
        evaluable=True,
        score_heading_levels=True,
        score_heading_paths=True,
        score_content=True,
        expected_heading_count=4,
        expected_paragraph_count=4,
        expected_table_count=0,
        expected_list_count=0,
        expected_total_count=8,
        elements=(
            GoldElement("heading", content_substring="Overview",
                        heading_level=1, heading_path=("Overview",)),
            GoldElement("paragraph", content_substring="Tundra station opened"),
            GoldElement("heading", content_substring="Power",
                        heading_level=2, heading_path=("Overview", "Power")),
            GoldElement("paragraph", content_substring="Helios generator"),
            GoldElement("heading", content_substring="Water",
                        heading_level=2, heading_path=("Overview", "Water")),
            GoldElement("paragraph", content_substring="Vermilion aquifer"),
            GoldElement("heading", content_substring="Decommissioning",
                        heading_level=1, heading_path=("Decommissioning",)),
            GoldElement("paragraph", content_substring="station closed"),
        ),
    ),

    # =====================================================================
    # PDF documents — heuristic heading detection, partial gold truth
    # =====================================================================

    "multipage_section.pdf": GoldDocument(
        name="multipage_section.pdf",
        evaluable=True,
        # Heading detection is heuristic for PDFs — do not score levels/paths
        score_heading_levels=False,
        score_heading_paths=False,
        score_content=True,
        expected_heading_count=1,
        expected_paragraph_count=7,
        expected_table_count=0,
        expected_list_count=0,
        expected_total_count=8,
        elements=(
            # "Orbital Mechanics" — size=16, bold → detected as heading
            GoldElement("heading", content_substring="Orbital Mechanics", page=1),
            GoldElement("paragraph", content_substring="Kestrel programme began", page=1),
            GoldElement("paragraph", content_substring="Nimbus booster", page=1),
            GoldElement("paragraph", content_substring="second phase", page=2),
            GoldElement("paragraph", content_substring="Falcon array replaced", page=2),
            GoldElement("paragraph", content_substring="Three flights", page=2),
            GoldElement("paragraph", content_substring="concluded in 1984", page=3),
            GoldElement("paragraph", content_substring="Falcon array was retired", page=3),
        ),
    ),

    "academic_two_column.pdf": GoldDocument(
        name="academic_two_column.pdf",
        evaluable=False,
        reason=(
            "Two-column PDF layout makes block ordering non-deterministic "
            "across PyMuPDF versions.  Element counts may be evaluated but "
            "element ordering and heading-path accuracy cannot be established "
            "objectively."
        ),
        score_heading_levels=False,
        score_heading_paths=False,
        score_content=False,
    ),
}


# ---------------------------------------------------------------------------
# Evaluation result types
# ---------------------------------------------------------------------------

@dataclass
class ElementPreservationResult:
    """Result of evaluating element type preservation for one document."""
    document: str
    evaluable: bool
    reason: str = ""
    expected_total: int = 0
    extracted_total: int = 0
    # Per-type counts
    expected_headings: int = 0
    extracted_headings: int = 0
    matched_headings: int = 0
    expected_paragraphs: int = 0
    extracted_paragraphs: int = 0
    matched_paragraphs: int = 0
    expected_tables: int = 0
    extracted_tables: int = 0
    matched_tables: int = 0
    expected_lists: int = 0
    extracted_lists: int = 0
    matched_lists: int = 0
    # Aggregate
    missing_count: int = 0
    unexpected_count: int = 0
    preservation_rate: float = 0.0


@dataclass
class HeadingPreservationResult:
    """Result of heading preservation evaluation."""
    document: str
    evaluable: bool
    reason: str = ""
    expected_count: int = 0
    extracted_count: int = 0
    detection_rate: float = 0.0
    level_accuracy: float = 0.0  # only when score_heading_levels=True
    path_accuracy: float = 0.0  # only when score_heading_paths=True
    level_evaluated: bool = False
    path_evaluated: bool = False


@dataclass
class TableExtractionResult:
    """Result of table extraction evaluation."""
    document: str
    evaluable: bool
    reason: str = ""
    expected_count: int = 0
    extracted_count: int = 0
    detection_rate: float = 0.0
    row_preservation: float = 0.0
    col_preservation: float = 0.0
    header_preservation: float = 0.0


@dataclass
class ListPreservationResult:
    """Result of list preservation evaluation."""
    document: str
    evaluable: bool
    reason: str = ""
    expected_count: int = 0
    extracted_count: int = 0
    detection_rate: float = 0.0
    item_preservation: float = 0.0
    ordering_preservation: float = 0.0


@dataclass
class ContentLossResult:
    """Result of content loss evaluation."""
    document: str
    evaluable: bool
    reason: str = ""
    missing_content: list[str] = field(default_factory=list)
    unexpected_content: list[str] = field(default_factory=list)
    preservation_rate: float = 0.0
    elements_checked: int = 0
    elements_matched: int = 0


@dataclass
class ExtractionEvaluationReport:
    """Complete extraction evaluation for one document."""
    document: str
    evaluable: bool
    reason: str = ""
    element_preservation: ElementPreservationResult | None = None
    heading_preservation: HeadingPreservationResult | None = None
    table_extraction: TableExtractionResult | None = None
    list_preservation: ListPreservationResult | None = None
    content_loss: ContentLossResult | None = None


# ---------------------------------------------------------------------------
# Evaluation functions
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Normalise text for comparison."""
    import re
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def evaluate_extraction_for_document(
    doc_name: str,
    file_type: str,
    builder,
) -> ExtractionEvaluationReport:
    """Run extraction on a corpus document and evaluate against gold truth.

    Args:
        doc_name: Document filename
        file_type: Format (docx, txt, pdf)
        builder: Callable[[Path], None] that builds the document

    Returns:
        ExtractionEvaluationReport with all applicable metrics
    """
    gold = GOLD_DOCUMENTS.get(doc_name)
    if gold is None:
        return ExtractionEvaluationReport(
            document=doc_name, evaluable=False,
            reason="No gold data defined for this document",
        )

    if not gold.evaluable:
        return ExtractionEvaluationReport(
            document=doc_name, evaluable=False, reason=gold.reason,
        )

    # Build and extract
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        path = directory / doc_name
        builder(path)
        elements = extract_text(path, file_type)

    # Run all evaluations
    ep = _evaluate_element_preservation(doc_name, gold, elements)
    hp = _evaluate_heading_preservation(doc_name, gold, elements)
    te = _evaluate_table_extraction(doc_name, gold, elements)
    lp = _evaluate_list_preservation(doc_name, gold, elements)
    cl = _evaluate_content_loss(doc_name, gold, elements)

    return ExtractionEvaluationReport(
        document=doc_name,
        evaluable=True,
        element_preservation=ep,
        heading_preservation=hp,
        table_extraction=te,
        list_preservation=lp,
        content_loss=cl,
    )


def _evaluate_element_preservation(
    doc_name: str,
    gold: GoldDocument,
    elements: list[ExtractedElement],
) -> ElementPreservationResult:
    """Evaluate element type preservation counts."""
    extracted = [e.element_type for e in elements]

    # Count by type
    expected_headings = gold.expected_heading_count
    expected_paragraphs = gold.expected_paragraph_count
    expected_tables = gold.expected_table_count
    expected_lists = gold.expected_list_count
    expected_total = gold.expected_total_count

    extracted_headings = sum(1 for t in extracted if t == "heading")
    extracted_paragraphs = sum(1 for t in extracted if t == "paragraph")
    extracted_tables = sum(1 for t in extracted if t == "table")
    extracted_lists = sum(1 for t in extracted if t == "list")
    extracted_total = len(elements)

    # Matched = min(expected, extracted) per type (conservative)
    matched_headings = min(expected_headings, extracted_headings)
    matched_paragraphs = min(expected_paragraphs, extracted_paragraphs)
    matched_tables = min(expected_tables, extracted_tables)
    matched_lists = min(expected_lists, extracted_lists)

    total_matched = matched_headings + matched_paragraphs + matched_tables + matched_lists
    total_expected = expected_headings + expected_paragraphs + expected_tables + expected_lists
    total_extracted = extracted_headings + extracted_paragraphs + extracted_tables + extracted_lists

    missing = max(0, total_expected - total_extracted)
    unexpected = max(0, total_extracted - total_expected)

    preservation = total_matched / total_expected if total_expected > 0 else 0.0

    return ElementPreservationResult(
        document=doc_name, evaluable=True,
        expected_total=expected_total, extracted_total=extracted_total,
        expected_headings=expected_headings, extracted_headings=extracted_headings,
        matched_headings=matched_headings,
        expected_paragraphs=expected_paragraphs, extracted_paragraphs=extracted_paragraphs,
        matched_paragraphs=matched_paragraphs,
        expected_tables=expected_tables, extracted_tables=extracted_tables,
        matched_tables=matched_tables,
        expected_lists=expected_lists, extracted_lists=extracted_lists,
        matched_lists=matched_lists,
        missing_count=missing, unexpected_count=unexpected,
        preservation_rate=preservation,
    )


def _evaluate_heading_preservation(
    doc_name: str,
    gold: GoldDocument,
    elements: list[ExtractedElement],
) -> HeadingPreservationResult:
    """Evaluate heading detection rate, level accuracy, and path accuracy."""
    gold_headings = [e for e in gold.elements if e.element_type == "heading"]
    extracted_headings = [e for e in elements if e.element_type == "heading"]

    expected_count = len(gold_headings)
    extracted_count = len(extracted_headings)
    detection_rate = extracted_count / expected_count if expected_count > 0 else 0.0

    # Level accuracy: compare heading levels (only for DOCX/TXT)
    level_accuracy = 0.0
    level_evaluated = gold.score_heading_levels and expected_count > 0
    if level_evaluated and expected_count > 0:
        matched_levels = 0
        for i, gold_h in enumerate(gold_headings):
            if i < len(extracted_headings):
                if extracted_headings[i].heading_level == gold_h.heading_level:
                    matched_levels += 1
        level_accuracy = matched_levels / expected_count

    # Path accuracy: compare heading paths (only for DOCX/TXT)
    path_accuracy = 0.0
    path_evaluated = gold.score_heading_paths and expected_count > 0
    if path_evaluated and expected_count > 0:
        matched_paths = 0
        for i, gold_h in enumerate(gold_headings):
            if i < len(extracted_headings) and gold_h.heading_path:
                extracted_path = tuple(extracted_headings[i].heading_path)
                if extracted_path == gold_h.heading_path:
                    matched_paths += 1
        path_accuracy = matched_paths / expected_count

    return HeadingPreservationResult(
        document=doc_name, evaluable=True,
        expected_count=expected_count, extracted_count=extracted_count,
        detection_rate=detection_rate,
        level_accuracy=level_accuracy,
        path_accuracy=path_accuracy,
        level_evaluated=level_evaluated,
        path_evaluated=path_evaluated,
    )


def _evaluate_table_extraction(
    doc_name: str,
    gold: GoldDocument,
    elements: list[ExtractedElement],
) -> TableExtractionResult:
    """Evaluate table detection, row/column preservation, header preservation."""
    gold_tables = [e for e in gold.elements if e.element_type == "table"]
    extracted_tables = [e for e in elements if e.element_type == "table"]

    expected_count = len(gold_tables)
    extracted_count = len(extracted_tables)
    detection_rate = extracted_count / expected_count if expected_count > 0 else 0.0

    if expected_count == 0:
        return TableExtractionResult(
            document=doc_name, evaluable=True,
            expected_count=0, extracted_count=extracted_count,
            detection_rate=1.0 if extracted_count == 0 else 0.0,
        )

    # Row/col/header preservation (compare matched tables by index)
    row_scores = []
    col_scores = []
    header_scores = []
    for i, gold_t in enumerate(gold_tables):
        if i < len(extracted_tables):
            ext_t = extracted_tables[i]
            # Row count
            if gold_t.table_rows is not None and ext_t.table_data:
                actual_rows = len(ext_t.table_data)
                row_scores.append(min(1.0, actual_rows / gold_t.table_rows))
            elif gold_t.table_rows is not None:
                row_scores.append(0.0)

            # Col count
            if gold_t.table_cols is not None and ext_t.table_data and ext_t.table_data[0]:
                actual_cols = len(ext_t.table_data[0])
                col_scores.append(min(1.0, actual_cols / gold_t.table_cols))
            elif gold_t.table_cols is not None:
                col_scores.append(0.0)

            # Header preservation
            if gold_t.table_header is not None and ext_t.table_data:
                actual_header = tuple(_norm(c) for c in ext_t.table_data[0])
                expected_header = tuple(_norm(c) for c in gold_t.table_header)
                header_scores.append(1.0 if actual_header == expected_header else 0.0)
            elif gold_t.table_header is not None:
                header_scores.append(0.0)

    return TableExtractionResult(
        document=doc_name, evaluable=True,
        expected_count=expected_count, extracted_count=extracted_count,
        detection_rate=detection_rate,
        row_preservation=sum(row_scores) / len(row_scores) if row_scores else 0.0,
        col_preservation=sum(col_scores) / len(col_scores) if col_scores else 0.0,
        header_preservation=sum(header_scores) / len(header_scores) if header_scores else 0.0,
    )


def _evaluate_list_preservation(
    doc_name: str,
    gold: GoldDocument,
    elements: list[ExtractedElement],
) -> ListPreservationResult:
    """Evaluate list detection, item preservation, ordering preservation."""
    gold_lists = [e for e in gold.elements if e.element_type == "list"]
    extracted_lists = [e for e in elements if e.element_type == "list"]

    expected_count = len(gold_lists)
    extracted_count = len(extracted_lists)
    detection_rate = extracted_count / expected_count if expected_count > 0 else 0.0

    if expected_count == 0:
        return ListPreservationResult(
            document=doc_name, evaluable=True,
            expected_count=0, extracted_count=extracted_count,
            detection_rate=1.0 if extracted_count == 0 else 0.0,
        )

    item_scores = []
    ordering_scores = []
    for i, gold_l in enumerate(gold_lists):
        if i < len(extracted_lists):
            ext_l = extracted_lists[i]
            # Item count preservation
            if gold_l.list_item_count is not None and ext_l.list_items:
                actual_count = len(ext_l.list_items)
                item_scores.append(min(1.0, actual_count / gold_l.list_item_count))
            elif gold_l.list_item_count is not None:
                item_scores.append(0.0)

            # Ordering preservation
            if gold_l.list_items is not None and ext_l.list_items:
                expected_items = [_norm(item) for item in gold_l.list_items]
                actual_items = [_norm(item) for item in ext_l.list_items]
                # Check if all expected items appear in order
                if len(actual_items) >= len(expected_items):
                    matches = 0
                    ai = 0
                    for ei, expected in enumerate(expected_items):
                        while ai < len(actual_items):
                            if expected in actual_items[ai]:
                                matches += 1
                                ai += 1
                                break
                            ai += 1
                    ordering_scores.append(matches / len(expected_items))
                else:
                    ordering_scores.append(0.0)
            elif gold_l.list_items is not None:
                ordering_scores.append(0.0)

    return ListPreservationResult(
        document=doc_name, evaluable=True,
        expected_count=expected_count, extracted_count=extracted_count,
        detection_rate=detection_rate,
        item_preservation=sum(item_scores) / len(item_scores) if item_scores else 0.0,
        ordering_preservation=sum(ordering_scores) / len(ordering_scores) if ordering_scores else 0.0,
    )


def _evaluate_content_loss(
    doc_name: str,
    gold: GoldDocument,
    elements: list[ExtractedElement],
) -> ContentLossResult:
    """Evaluate content preservation using deterministic substring matching."""
    if not gold.score_content:
        return ContentLossResult(
            document=doc_name, evaluable=False,
            reason="Content ordering is not deterministic for this document",
        )

    gold_elements_with_content = [
        e for e in gold.elements
        if e.content_substring is not None
    ]

    if not gold_elements_with_content:
        return ContentLossResult(
            document=doc_name, evaluable=True,
            preservation_rate=1.0,
        )

    missing = []
    matched = 0
    all_extracted_content = " ".join(_norm(e.content) for e in elements)

    for gold_e in gold_elements_with_content:
        expected_text = _norm(gold_e.content_substring)
        if expected_text in all_extracted_content:
            matched += 1
        else:
            missing.append(gold_e.content_substring)

    total = len(gold_elements_with_content)
    preservation_rate = matched / total if total > 0 else 1.0

    return ContentLossResult(
        document=doc_name, evaluable=True,
        missing_content=missing,
        preservation_rate=preservation_rate,
        elements_checked=total,
        elements_matched=matched,
    )


# ---------------------------------------------------------------------------
# Aggregate extraction evaluation
# ---------------------------------------------------------------------------

@dataclass
class ExtractionAggregation:
    """Aggregated extraction evaluation across all documents."""
    total_documents: int = 0
    evaluable_documents: int = 0
    not_evaluable_documents: int = 0
    not_evaluable_list: list[dict] = field(default_factory=list)
    # Aggregate element preservation
    overall_preservation_rate: float = 0.0
    # Aggregate heading preservation
    heading_detection_rate: float = 0.0
    heading_level_accuracy: float = 0.0
    heading_path_accuracy: float = 0.0
    # Aggregate table extraction
    table_detection_rate: float = 0.0
    table_row_preservation: float = 0.0
    table_col_preservation: float = 0.0
    table_header_preservation: float = 0.0
    # Aggregate list preservation
    list_detection_rate: float = 0.0
    list_item_preservation: float = 0.0
    list_ordering_preservation: float = 0.0
    # Aggregate content loss
    overall_content_preservation: float = 0.0
    total_missing_content: int = 0
    # Per-document results
    per_document: dict[str, dict] = field(default_factory=dict)


def aggregate_extraction_results(
    reports: list[ExtractionEvaluationReport],
) -> ExtractionAggregation:
    """Aggregate extraction evaluation results across all documents."""
    agg = ExtractionAggregation()
    agg.total_documents = len(reports)

    evaluable = [r for r in reports if r.evaluable]
    not_evaluable = [r for r in reports if not r.evaluable]
    agg.evaluable_documents = len(evaluable)
    agg.not_evaluable_documents = len(not_evaluable)
    agg.not_evaluable_list = [
        {"document": r.document, "reason": r.reason} for r in not_evaluable
    ]

    if not evaluable:
        return agg

    # Element preservation
    ep_rates = [r.element_preservation.preservation_rate
                for r in evaluable if r.element_preservation]
    agg.overall_preservation_rate = sum(ep_rates) / len(ep_rates) if ep_rates else 0.0

    # Heading preservation (only average across documents with expected headings)
    hp_det = [r.heading_preservation.detection_rate
              for r in evaluable if r.heading_preservation
              and r.heading_preservation.expected_count > 0]
    hp_lev = [r.heading_preservation.level_accuracy
              for r in evaluable if r.heading_preservation and r.heading_preservation.level_evaluated
              and r.heading_preservation.expected_count > 0]
    hp_path = [r.heading_preservation.path_accuracy
               for r in evaluable if r.heading_preservation and r.heading_preservation.path_evaluated
               and r.heading_preservation.expected_count > 0]
    agg.heading_detection_rate = sum(hp_det) / len(hp_det) if hp_det else 0.0
    agg.heading_level_accuracy = sum(hp_lev) / len(hp_lev) if hp_lev else 0.0
    agg.heading_path_accuracy = sum(hp_path) / len(hp_path) if hp_path else 0.0

    # Table extraction (only average across documents with expected tables)
    te_det = [r.table_extraction.detection_rate
              for r in evaluable if r.table_extraction
              and r.table_extraction.expected_count > 0]
    te_row = [r.table_extraction.row_preservation
              for r in evaluable if r.table_extraction and r.table_extraction.expected_count > 0]
    te_col = [r.table_extraction.col_preservation
              for r in evaluable if r.table_extraction and r.table_extraction.expected_count > 0]
    te_hdr = [r.table_extraction.header_preservation
              for r in evaluable if r.table_extraction and r.table_extraction.expected_count > 0]
    agg.table_detection_rate = sum(te_det) / len(te_det) if te_det else 0.0
    agg.table_row_preservation = sum(te_row) / len(te_row) if te_row else 0.0
    agg.table_col_preservation = sum(te_col) / len(te_col) if te_col else 0.0
    agg.table_header_preservation = sum(te_hdr) / len(te_hdr) if te_hdr else 0.0

    # List preservation (only average across documents with expected lists)
    lp_det = [r.list_preservation.detection_rate
              for r in evaluable if r.list_preservation
              and r.list_preservation.expected_count > 0]
    lp_item = [r.list_preservation.item_preservation
               for r in evaluable if r.list_preservation and r.list_preservation.expected_count > 0]
    lp_ord = [r.list_preservation.ordering_preservation
               for r in evaluable if r.list_preservation and r.list_preservation.expected_count > 0]
    agg.list_detection_rate = sum(lp_det) / len(lp_det) if lp_det else 0.0
    agg.list_item_preservation = sum(lp_item) / len(lp_item) if lp_item else 0.0
    agg.list_ordering_preservation = sum(lp_ord) / len(lp_ord) if lp_ord else 0.0

    # Content loss
    cl_rates = [r.content_loss.preservation_rate
                for r in evaluable if r.content_loss and r.content_loss.evaluable]
    cl_missing = [len(r.content_loss.missing_content)
                  for r in evaluable if r.content_loss]
    agg.overall_content_preservation = sum(cl_rates) / len(cl_rates) if cl_rates else 0.0
    agg.total_missing_content = sum(cl_missing)

    # Per-document
    for r in reports:
        doc_data: dict[str, Any] = {"evaluable": r.evaluable}
        if not r.evaluable:
            doc_data["reason"] = r.reason
        else:
            if r.element_preservation:
                ep = r.element_preservation
                doc_data["element_preservation"] = {
                    "expected": ep.expected_total,
                    "extracted": ep.extracted_total,
                    "preservation_rate": round(ep.preservation_rate, 4),
                    "by_type": {
                        "heading": {"expected": ep.expected_headings, "extracted": ep.extracted_headings},
                        "paragraph": {"expected": ep.expected_paragraphs, "extracted": ep.extracted_paragraphs},
                        "table": {"expected": ep.expected_tables, "extracted": ep.extracted_tables},
                        "list": {"expected": ep.expected_lists, "extracted": ep.extracted_lists},
                    },
                }
            if r.heading_preservation:
                hp = r.heading_preservation
                doc_data["heading_preservation"] = {
                    "expected": hp.expected_count,
                    "extracted": hp.extracted_count,
                    "detection_rate": round(hp.detection_rate, 4),
                }
                if hp.level_evaluated:
                    doc_data["heading_preservation"]["level_accuracy"] = round(hp.level_accuracy, 4)
                if hp.path_evaluated:
                    doc_data["heading_preservation"]["path_accuracy"] = round(hp.path_accuracy, 4)
            if r.table_extraction:
                te = r.table_extraction
                doc_data["table_extraction"] = {
                    "expected": te.expected_count,
                    "extracted": te.extracted_count,
                    "detection_rate": round(te.detection_rate, 4),
                }
                if te.expected_count > 0:
                    doc_data["table_extraction"]["row_preservation"] = round(te.row_preservation, 4)
                    doc_data["table_extraction"]["col_preservation"] = round(te.col_preservation, 4)
                    doc_data["table_extraction"]["header_preservation"] = round(te.header_preservation, 4)
            if r.list_preservation:
                lp = r.list_preservation
                doc_data["list_preservation"] = {
                    "expected": lp.expected_count,
                    "extracted": lp.extracted_count,
                    "detection_rate": round(lp.detection_rate, 4),
                }
                if lp.expected_count > 0:
                    doc_data["list_preservation"]["item_preservation"] = round(lp.item_preservation, 4)
                    doc_data["list_preservation"]["ordering_preservation"] = round(lp.ordering_preservation, 4)
            if r.content_loss:
                cl = r.content_loss
                doc_data["content_loss"] = {
                    "evaluable": cl.evaluable,
                    "preservation_rate": round(cl.preservation_rate, 4),
                    "elements_checked": cl.elements_checked,
                    "elements_matched": cl.elements_matched,
                }
                if cl.missing_content:
                    doc_data["content_loss"]["missing_content"] = cl.missing_content
        agg.per_document[r.document] = doc_data

    return agg

"""Phase 3F — Corpus contract.

Extends the existing Phase 3D corpus with:
  - Document metadata (synthetic/real, category, format)
  - Extended gold labels (acceptable_answers, difficulty, kind)
  - Reproducibility versioning

The existing 12-document / 42-question corpus is preserved as v1.
This module wraps the existing corpus builders without modifying them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Import existing corpus (do NOT modify it)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tests.phase3d_corpus import (
    build_corpus as _build_corpus,
    unanswerable_questions as _unanswerable,
    CorpusDoc as _CorpusDoc,
    Question as _Question,
)


# ---------------------------------------------------------------------------
# Extended metadata
# ---------------------------------------------------------------------------

CORPUS_VERSION = "phase3f-v1"
EVALUATION_VERSION = "3f-v1"


@dataclass(frozen=True)
class DocumentMeta:
    """Extended metadata for an evaluation document."""
    name: str
    format: str  # pdf, docx, txt
    synthetic: bool
    category: str  # short_sections, heading_heavy, tables, lists, mixed, etc.
    source: str  # "programmatic" for synthetic, URL/citation for real
    notes: str = ""


# Document metadata for the existing corpus
DOCUMENT_META: dict[str, DocumentMeta] = {
    "short_sections.docx": DocumentMeta(
        name="short_sections.docx", format="docx", synthetic=True,
        category="short_sections", source="programmatic",
        notes="Six short H2 sections",
    ),
    "heading_heavy.docx": DocumentMeta(
        name="heading_heavy.docx", format="docx", synthetic=True,
        category="heading_heavy", source="programmatic",
        notes="H1-H4 nesting",
    ),
    "tables_small.docx": DocumentMeta(
        name="tables_small.docx", format="docx", synthetic=True,
        category="tables", source="programmatic",
        notes="Small table, must stay atomic",
    ),
    "tables_large.docx": DocumentMeta(
        name="tables_large.docx", format="docx", synthetic=True,
        category="tables", source="programmatic",
        notes="31-row table with header repetition",
    ),
    "lists.docx": DocumentMeta(
        name="lists.docx", format="docx", synthetic=True,
        category="lists", source="programmatic",
        notes="Bulleted then numbered list",
    ),
    "mixed.docx": DocumentMeta(
        name="mixed.docx", format="docx", synthetic=True,
        category="mixed", source="programmatic",
        notes="Prose + heading + table + list",
    ),
    "long_paragraph.txt": DocumentMeta(
        name="long_paragraph.txt", format="txt", synthetic=True,
        category="long_paragraph", source="programmatic",
        notes="Two very long paragraphs",
    ),
    "dense_prose.txt": DocumentMeta(
        name="dense_prose.txt", format="txt", synthetic=True,
        category="dense_prose", source="programmatic",
        notes="Prose-heavy report, context window stress",
    ),
    "unpunctuated.txt": DocumentMeta(
        name="unpunctuated.txt", format="txt", synthetic=True,
        category="unpunctuated", source="programmatic",
        notes="Unpunctuated text, hard-cut path",
    ),
    "markdown_sections.txt": DocumentMeta(
        name="markdown_sections.txt", format="txt", synthetic=True,
        category="markdown", source="programmatic",
        notes="Markdown headings in TXT",
    ),
    "multipage_section.pdf": DocumentMeta(
        name="multipage_section.pdf", format="pdf", synthetic=True,
        category="multipage", source="programmatic",
        notes="One section spanning three pages",
    ),
    "academic_two_column.pdf": DocumentMeta(
        name="academic_two_column.pdf", format="pdf", synthetic=True,
        category="academic", source="programmatic",
        notes="Two-column academic PDF",
    ),
}


# Extended difficulty ratings (applied to existing questions)
QUESTION_DIFFICULTY: dict[str, str] = {
    # Factual — direct single-chunk answer
    "ss_1": "easy", "ss_2": "easy", "ss_3": "easy",
    "hh_3": "easy", "md_1": "easy", "mp_1": "easy", "mp_2": "easy",
    # Section-specific — requires correct section retrieval
    "ss_4": "medium", "hh_1": "medium", "hh_2": "medium",
    "mx_2": "medium", "md_2": "medium", "md_3": "medium",
    # Table — requires table chunk with header
    "ts_1": "medium", "ts_2": "medium", "tl_1": "hard",
    "tl_2": "medium", "tl_3": "hard", "mx_1": "medium",
    "mx_3": "hard",
    # List — requires list item integrity
    "li_1": "medium", "li_2": "hard", "li_3": "hard", "mx_4": "easy",
    # Long context — context window pressure
    "lp_1": "hard", "lp_2": "hard", "lp_3": "medium",
    # Dense prose — context window overflow
    "dp_1": "medium", "dp_2": "hard", "dp_3": "medium",
    "dp_4": "medium", "dp_5": "medium", "dp_6": "hard",
    # Multi-page/multi-chunk
    "mp_3": "medium", "mp_4": "hard",
    # Academic
    "ac_1": "medium", "ac_2": "hard", "ac_3": "easy",
    # Unpunctuated
    "up_1": "hard",
    # Unsupported
    "un_1": "easy", "un_2": "easy", "un_3": "easy",
}


# Acceptable answer variants (paraphrase tolerance)
ACCEPTABLE_ANSWERS: dict[str, list[str]] = {
    "ss_1": ["22 degrees", "22 deg", "22°"],
    "ss_2": ["14 watts", "14"],
    "ss_3": ["3 kilograms", "3 kg", "3 kilos"],
    "ss_4": ["vermilion", "the vermilion coating cures", "6 hours"],
    "hh_1": ["tundra torque wrench", "a tundra torque wrench"],
    "hh_2": ["behind the panel"],
    "hh_3": ["every 500 hours", "500 hours"],
    "ts_1": ["92 percent", "92%"],
    "ts_2": ["85 percent", "85%"],
    "tl_1": ["90 percent", "90%"],
    "tl_2": ["method 30", "Method 30"],
    "tl_3": ["84 milliseconds", "84 ms"],
    "li_1": ["remove the helios filter"],
    "li_2": ["nimbus supply", "isolate the nimbus supply"],
    "li_3": ["zephyr reading", "confirm the zephyr reading"],
    "mx_1": ["998 millibars", "998 mb"],
    "mx_2": ["quokka reference cell", "a quokka reference cell"],
    "mx_3": ["spring"],
    "mx_4": ["2 millibars", "by 2 millibars"],
    "lp_1": ["1.4 metres per year", "1.4 m/year", "1.4 metres/year"],
    "lp_2": ["1988"],
    "lp_3": ["twenty beaches", "20 beaches"],
    "dp_1": ["laser diffraction"],
    "dp_2": ["1.4 kilograms per metre per day", "1.4 kg/m/day"],
    "dp_3": ["14 millimetres", "14 mm"],
    "dp_4": ["1850"],
    "dp_5": ["northern", "northern transect"],
    "dp_6": ["design", "the design", "statistical panel"],
    "up_1": ["alphabetagammadelta"],
    "md_1": ["2005"],
    "md_2": ["helios generator", "helios"],
    "md_3": ["2019"],
    "mp_1": ["1971"],
    "mp_2": ["1984"],
    "mp_3": ["falcon array", "the falcon array"],
    "mp_4": ["1984"],
    "ac_1": ["quokka estimator", "quokka"],
    "ac_2": ["tundra basis"],
    "ac_3": ["11 percent", "11%"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_corpus():
    """Return the Phase 3D corpus (documents + labelled questions)."""
    return _build_corpus()


def get_unanswerable():
    """Return unanswerable questions."""
    return _unanswerable()


def get_all_questions():
    """Return all questions (answerable + unanswerable)."""
    corpus = get_corpus()
    unsupported = get_unanswerable()
    return [q for doc in corpus for q in doc.questions] + unsupported


def get_document_meta(name: str) -> DocumentMeta | None:
    """Get extended metadata for a document."""
    return DOCUMENT_META.get(name)


def get_difficulty(qid: str) -> str:
    """Get difficulty rating for a question."""
    return QUESTION_DIFFICULTY.get(qid, "unknown")


def get_acceptable_answers(qid: str) -> list[str]:
    """Get acceptable answer variants for a question."""
    return ACCEPTABLE_ANSWERS.get(qid, [])


def corpus_summary() -> dict:
    """Summarize the corpus for reproducibility metadata."""
    corpus = get_corpus()
    unsupported = get_unanswerable()
    all_q = get_all_questions()
    answerable = [q for q in all_q if q.answerable]

    # Count by kind
    kind_counts: dict[str, int] = {}
    for q in all_q:
        kind_counts[q.kind] = kind_counts.get(q.kind, 0) + 1

    # Count by format
    format_counts: dict[str, int] = {}
    for doc in corpus:
        fmt = DOCUMENT_META.get(doc.name, DocumentMeta(doc.name, "unknown", True, "unknown", "unknown")).format
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    # Count by difficulty
    diff_counts: dict[str, int] = {}
    for q in answerable:
        d = get_difficulty(q.qid)
        diff_counts[d] = diff_counts.get(d, 0) + 1

    return {
        "corpus_version": CORPUS_VERSION,
        "documents": len(corpus),
        "questions_total": len(all_q),
        "questions_answerable": len(answerable),
        "questions_unsupported": len(unsupported),
        "all_synthetic": all(DOCUMENT_META.get(d.name, DocumentMeta(d.name, "", True, "", "")).synthetic for d in corpus),
        "by_kind": kind_counts,
        "by_format": format_counts,
        "by_difficulty": diff_counts,
    }

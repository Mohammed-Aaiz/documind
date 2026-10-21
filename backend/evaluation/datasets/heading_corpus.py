"""Heading-rich evaluation corpus — real PDF headings, page-spanning sections.

Why this corpus exists
----------------------
The Phase 3D corpus names a ``multipage_section.pdf``, but its heading appears
only on the first page, so the structure chunker gives that section's later
pages no ``heading_path`` and the document graph can build no ``SAME_SECTION``
edge across the page boundary.  A dual-path (vector + structural) ablation run
on it therefore measures the vector path and very little else.

This corpus is built to make the structural path *possible* and then to
measure, honestly, whether it helps:

* **Real headings.**  Headings are written into the PDF with the font
  properties the extractor actually uses — H1 at 16 pt bold, H2 at 13 pt bold,
  H3 at 11 pt bold, body at 10 pt regular.  Nothing here depends on a
  ``docx`` style name; the headings must survive the same font-size heuristic
  ``documents.processing._classify_pdf_heading`` applies to real-world PDFs.
* **Page-spanning sections.**  A section heading is placed on one page and its
  body continues onto the next page with no new heading.  ``extract_pdf``
  carries ``heading_path`` across the page break, so the body on both pages
  shares one section.  That yields two or more chunks with an identical
  ``heading_path`` — the precondition for ``SAME_SECTION`` edges
  (``graph.service.plan_edges``).
* **Labels that a strategy cannot have seen.**  As in the Phase 3D corpus,
  ``evidence`` values are short, distinctive substrings present in exactly the
  chunk that supports the answer.  The ablation runner derives gold chunk ids
  from those substrings *after* ingestion, so the gold set is independent of
  every retrieval strategy being scored.
* **Section-naming questions.**  Most answerable questions name a distinctive
  term from their section heading, so the structural seeder
  (``graph.service.find_section_seed_matches``) has something real to match —
  the vector path and the structural path are both given a fair chance.

Kinds
-----
``kind="section"`` questions sit under a section heading; the runner maps them
to ``QuestionCategory.SECTION_DEPENDENT``.  ``kind="cross_page"`` questions
have their supporting text in a section *body that continues onto a later
page* than the heading; the runner maps them to
``QuestionCategory.PAGE_CROSS_PAGE``.  That split is what makes a "did the
structural path add cross-page evidence?" reading possible.

Instants of truth live in this module only; nothing here imports the chunker
or the retrieval pipeline.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

# Reuse the Phase 3D corpus types so the ablation runner's duck-typed interface
# (``name`` / ``file_type`` / ``builder`` / ``questions``) is unchanged.
from evaluation.datasets.phase3d_corpus import CorpusDoc, Question


# ---------------------------------------------------------------------------
# PDF layout
# ---------------------------------------------------------------------------
#
# The thresholds must match documents.processing:
#   H1  >= 14.0 pt
#   H2  >= 12.0 pt
#   H3  >= 10.5 pt and bold
# Body text is 10.0 pt regular, comfortably below every heading threshold.
#
# ``(size, bold, y-advance)``.  The advance leaves a generous gap after each
# block so two blocks never merge into one extracted block — if a heading were
# absorbed into a body block, the body would inherit the heading's font size
# and vanish from the paragraph stream.
_LAYOUT: dict[str, tuple[float, bool, float]] = {
    "h1": (16.0, True, 36.0),
    "h2": (13.0, True, 30.0),
    "h3": (11.0, True, 28.0),
    "p": (10.0, False, 20.0),
}

# Extra space *before* a heading.  PyMuPDF merges two text lines into one block
# when they sit closer than the larger font's line height, which would fold a
# heading into the paragraph above it and misclassify the whole block.  A large
# heading therefore needs more room above it than a small one.
_GAP_BEFORE: dict[str, float] = {"h1": 22.0, "h2": 18.0, "h3": 16.0, "p": 0.0}

_PAGE_W = 595
_PAGE_H = 842
_LEFT = 50.0
_TOP = 60.0


def _pdf_text(page, x: float, y: float, text: str, size: float, bold: bool) -> None:
    font = fitz.Font("hebo" if bold else "helv")
    writer = fitz.TextWriter(page.rect)
    writer.append((x, y), text, font=font, fontsize=size)
    writer.write_text(page)


def _render(path: Path, pages: list[list[tuple[str, str]]]) -> None:
    """Write ``pages`` (a list of block lists) as a single PDF.

    Each block is ``(kind, text)`` with ``kind`` in ``{"h1", "h2", "h3", "p"}``.
    """
    doc = fitz.open()
    for blocks in pages:
        page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
        y = _TOP
        for index, (kind, text) in enumerate(blocks):
            if index:
                y += _GAP_BEFORE[kind]
            size, bold, advance = _LAYOUT[kind]
            _pdf_text(page, _LEFT, y, text, size=size, bold=bold)
            y += advance
    doc.save(str(path))
    doc.close()


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_orbital_handbook(path: Path) -> None:
    """Kestrel Propulsion spans pages 1–2; Nimbus Avionics spans pages 2–3."""
    _render(path, [
        [
            ("h1", "Kestrel Propulsion"),
            ("p", "The Kestrel programme uses a Xenon-oxygen plasma thruster for its main burn."),
            ("p", "Thrust is vectored by two gimbal actuators on the thrust ring."),
            ("p", "The ignition sequence lasts 42 seconds and is watched by the flight computer."),
            ("p", "Chamber pressure is held at 24 bar throughout the burn."),
            ("p", "Coolant is routed through the chamber wall before every ignition."),
        ],
        [
            ("p", "The second burn trims the orbit and lasts a further 18 seconds."),
            ("p", "A Xenon-oxygen thruster can be restarted nine times between services."),
            ("p", "Residual propellant is vented through the Vernier nozzle after each burn."),
            ("h2", "Nimbus Avionics"),
            ("p", "The Nimbus avionics bus runs at 40 megahertz with triple redundancy."),
            ("p", "Flight software is uploaded over the Nimbus protocol from the ground station."),
        ],
        [
            ("p", "The Nimbus bus isolates a failed lane within 200 milliseconds."),
            ("p", "Telemetry is downlinked at 2 kilobits per second during eclipse."),
            ("h1", "Falcon Thermal Control"),
            ("p", "The Falcon thermal loop circulates ammonia through the radiator panels."),
            ("p", "The loop setpoint is 18 degrees and is adjusted before each manoeuvre."),
        ],
    ])


def _build_field_guide(path: Path) -> None:
    """Sampling Protocol spans pages 1–2; Instrument Calibration pages 2–3."""
    _render(path, [
        [
            ("h1", "Meridian Field Survey"),
            ("p", "The Meridian survey covers the eastern shelf and began in 2011."),
            ("h2", "Sampling Protocol"),
            ("p", "Every station is sampled at three tidal heights using a Kestrel frame."),
            ("p", "Samples are bagged, labelled and stored at four degrees."),
            ("p", "A duplicate sample is taken at every tenth station for quality control."),
        ],
        [
            ("p", "The protocol requires a blank sample before each transect begins."),
            ("p", "Blank samples are analysed separately to bound contamination."),
            ("p", "Sampling depth is recorded to the nearest centimetre on a marked line."),
            ("h2", "Instrument Calibration"),
            ("p", "The Kestrel frame is calibrated weekly against a granite reference block."),
        ],
        [
            ("p", "Calibration drift is logged in the survey register after every session."),
            ("p", "A drift greater than 0.5 millimetres triggers a full recalibration."),
            ("h3", "Drift Correction"),
            ("p", "Drift correction applies a linear offset to readings from the affected session."),
            ("p", "Corrected readings carry a Solstice marker in the archive."),
        ],
    ])


def _build_platform_spec(path: Path) -> None:
    """A single H1 section whose body spans all three pages (one heading path)."""
    _render(path, [
        [
            ("h1", "Quokka Processing Pipeline"),
            ("p", "The Quokka pipeline ingests documents and emits token-budgeted chunks."),
            ("p", "Stage one normalises whitespace and strips byte order marks."),
            ("p", "Stage two segments text on sentence boundaries."),
            ("p", "Stage three assigns heading context to every chunk."),
        ],
        [
            ("p", "Stage four measures each chunk with the embedding tokenizer."),
            ("p", "Any chunk above 256 tokens is split before persistence."),
            ("p", "The pipeline never drops a sentence during a split."),
            ("p", "Chunk identifiers are generated in document order."),
        ],
        [
            ("p", "Stage five writes the chunk graph edges for the document."),
            ("p", "The graph records next, previous, same page and same section relations."),
            ("p", "Stage six embeds every chunk with the Quokka encoder."),
            ("p", "The encoder produces 384 dimensional vectors."),
        ],
    ])


def _build_archive_notes(path: Path) -> None:
    """Solstice Records spans pages 1–2; two other H1 sections sit beside it."""
    _render(path, [
        [
            ("h1", "Vermilion Archive"),
            ("p", "The Vermilion archive stores survey records from 1970 to 1995."),
            ("p", "Records are catalogued by region and by survey season."),
            ("h1", "Solstice Records"),
            ("p", "Solstice records cover the northern transect and are held on microfilm."),
        ],
        [
            ("p", "Microfilm reels are stored at eighteen degrees and forty percent humidity."),
            ("p", "A single reel holds up to twelve hundred exposures."),
            ("h1", "Tundra Inventory"),
            ("p", "The Tundra inventory lists every instrument held by the observatory."),
            ("p", "Inventory checks are performed each quarter."),
        ],
    ])


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

def build_corpus() -> list[CorpusDoc]:
    """Return the heading-rich corpus (documents + labelled questions)."""
    return [
        CorpusDoc(
            name="orbital_handbook.pdf",
            file_type="pdf",
            builder=_build_orbital_handbook,
            notes="H1-H2 PDF; Kestrel Propulsion spans pages 1-2, Nimbus Avionics 2-3.",
            questions=[
                Question("oh_1", "What mixture does the Kestrel thruster burn?",
                         expected_answer="Xenon-oxygen", evidence=("Xenon-oxygen",),
                         kind="section"),
                Question("oh_2", "How long does the Kestrel Propulsion ignition sequence last?",
                         expected_answer="42 seconds", evidence=("42 seconds",),
                         kind="section"),
                Question("oh_3", "How many times can the thruster be restarted between services?",
                         expected_answer="nine times", evidence=("nine times",),
                         kind="cross_page"),
                Question("oh_4", "What does the Nimbus avionics bus run at?",
                         expected_answer="40 megahertz", evidence=("40 megahertz",),
                         kind="section"),
                Question("oh_5", "How quickly does the Nimbus bus isolate a failed lane?",
                         expected_answer="200 milliseconds", evidence=("200 milliseconds",),
                         kind="cross_page"),
                Question("oh_6", "What does the Falcon thermal loop circulate?",
                         expected_answer="ammonia", evidence=("ammonia",),
                         kind="section"),
            ],
        ),
        CorpusDoc(
            name="field_guide.pdf",
            file_type="pdf",
            builder=_build_field_guide,
            notes="Nested H1-H2-H3 PDF; Sampling Protocol spans pages 1-2.",
            questions=[
                Question("fg_1", "What frame is used to sample every station?",
                         expected_answer="Kestrel frame",
                         evidence=("three tidal heights",), kind="section"),
                Question("fg_2", "How often is a duplicate sample taken?",
                         expected_answer="every tenth station",
                         evidence=("every tenth station",), kind="section"),
                Question("fg_3", "What does the Sampling Protocol require before each transect?",
                         expected_answer="a blank sample", evidence=("blank sample",),
                         kind="cross_page"),
                Question("fg_4", "What is the Kestrel frame calibrated against?",
                         expected_answer="granite reference block",
                         evidence=("granite reference block",), kind="section"),
                Question("fg_5", "What size of drift triggers a full recalibration?",
                         expected_answer="0.5 millimetres", evidence=("0.5 millimetres",),
                         kind="cross_page"),
                Question("fg_6", "What marker do corrected readings carry in the archive?",
                         expected_answer="Solstice marker", evidence=("Solstice marker",),
                         kind="section"),
            ],
        ),
        CorpusDoc(
            name="platform_spec.pdf",
            file_type="pdf",
            builder=_build_platform_spec,
            notes="One H1 section spanning three pages; one heading path across 3 chunks.",
            questions=[
                Question("ps_1", "What does the Quokka pipeline emit?",
                         expected_answer="token-budgeted chunks",
                         evidence=("token-budgeted chunks",), kind="section"),
                Question("ps_2", "What is the maximum chunk size before splitting?",
                         expected_answer="256 tokens", evidence=("256 tokens",),
                         kind="cross_page"),
                Question("ps_3", "How many dimensions does the Quokka encoder produce?",
                         expected_answer="384 dimensional vectors",
                         evidence=("384 dimensional",), kind="cross_page"),
                Question("ps_4", "Which stage of the Quokka Processing Pipeline assigns heading context?",
                         expected_answer="Stage three", evidence=("Stage three",),
                         kind="section"),
            ],
        ),
        CorpusDoc(
            name="archive_notes.pdf",
            file_type="pdf",
            builder=_build_archive_notes,
            notes="Three H1 sections in one PDF; Solstice Records spans pages 1-2.",
            questions=[
                Question("an_1", "What period does the Vermilion archive cover?",
                         expected_answer="1970 to 1995", evidence=("1970 to 1995",),
                         kind="section"),
                Question("an_2", "Where are Solstice records held?",
                         expected_answer="microfilm", evidence=("held on microfilm",),
                         kind="section"),
                Question("an_3", "How many exposures does a single reel hold?",
                         expected_answer="twelve hundred", evidence=("twelve hundred",),
                         kind="cross_page"),
                Question("an_4", "How often are Tundra inventory checks performed?",
                         expected_answer="each quarter", evidence=("each quarter",),
                         kind="section"),
            ],
        ),
    ]


def unanswerable_questions() -> list[Question]:
    """Questions with no supporting evidence anywhere in this corpus."""
    return [
        Question("hun_1", "What is the boiling point of mercury?", answerable=False,
                 kind="unsupported"),
        Question("hun_2", "How many staff work at the Meridian office?",
                 answerable=False, kind="unsupported"),
        Question("hun_3", "What is the melting point of tungsten?", answerable=False,
                 kind="unsupported"),
    ]


# ---------------------------------------------------------------------------
# Paraphrase tolerance (mirrors evaluation.harness.corpus.ACCEPTABLE_ANSWERS)
# ---------------------------------------------------------------------------

ACCEPTABLE_ANSWERS: dict[str, list[str]] = {
    "oh_1": ["Xenon-oxygen", "xenon oxygen", "Xenon oxygen"],
    "oh_2": ["42 seconds", "42"],
    "oh_3": ["nine times", "9 times", "nine"],
    "oh_4": ["40 megahertz", "40 MHz", "40"],
    "oh_5": ["200 milliseconds", "200 ms"],
    "oh_6": ["ammonia"],
    "fg_1": ["Kestrel frame", "a Kestrel frame"],
    "fg_2": ["every tenth station", "each tenth station"],
    "fg_3": ["a blank sample", "blank sample"],
    "fg_4": ["granite reference block"],
    "fg_5": ["0.5 millimetres", "0.5 millimeters", "0.5 mm"],
    "fg_6": ["Solstice marker"],
    "ps_1": ["token-budgeted chunks", "token budgeted chunks"],
    "ps_2": ["256 tokens", "256"],
    "ps_3": ["384 dimensional vectors", "384 dimensions", "384"],
    "ps_4": ["Stage three", "stage 3", "Stage 3"],
    "an_1": ["1970 to 1995", "1970-1995"],
    "an_2": ["microfilm"],
    "an_3": ["twelve hundred", "1200"],
    "an_4": ["each quarter", "every quarter", "quarterly"],
}


def get_acceptable_answers(qid: str) -> list[str]:
    """Acceptable answer variants for a question id (empty when unknown)."""
    return ACCEPTABLE_ANSWERS.get(qid, [])


def corpus_summary() -> dict:
    """Small reproducibility summary: documents, questions and label coverage."""
    corpus = build_corpus()
    unsupported = unanswerable_questions()
    answerable = [q for doc in corpus for q in doc.questions]
    return {
        "corpus_version": "heading-v1",
        "documents": len(corpus),
        "questions_answerable": len(answerable),
        "questions_unsupported": len(unsupported),
        "all_pdf": all(doc.file_type == "pdf" for doc in corpus),
        "with_expected_answer": sum(1 for q in answerable if q.expected_answer),
        "with_evidence": sum(1 for q in answerable if q.evidence),
    }

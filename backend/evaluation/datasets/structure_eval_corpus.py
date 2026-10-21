"""Synthetic, versioned, structure-labelled corpus for the offline harness.

Research dataset.  Never imported by production modules and never collected by
pytest (``pytest.ini`` sets ``testpaths = tests``).

Honesty contract
----------------
This is an explicitly **synthetic** fixture.  It exists to exercise the offline,
deterministic, element-level evaluation harness
(:mod:`evaluation.structure_eval`) without PostgreSQL, pgvector, embeddings or a
local model — it is *not* a substitute for the real corpora
(:mod:`evaluation.datasets.phase3d_corpus`,
:mod:`evaluation.datasets.heading_corpus`) and it makes no claim about the
production pipeline.  Results measured on this fixture describe the harness and
the reference lexical baselines, and are labelled as such.

Every ground-truth label is authored here by hand (element ids, chunk ids, gold
answers, expected pages/sections/evidence types).  Nothing is derived from a
model, and nothing is filled in by the harness.

Each labelled section also carries **in-section distractors** — paragraphs that
share the section's vocabulary but do not answer the question.  They make the
retrieval task non-trivial (the top-K list cannot simply be the whole document)
and let the four variants produce genuinely different rankings.  A question with
no genuine evidence is marked ``answerable=False`` and carries **no** gold — the
harness must then report the affected metric as unavailable rather than ``0.0``.

``CORPUS_VERSION`` changes whenever any label changes, so a report can be tied
to the exact dataset revision it measured.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.schemas import QuestionCategory

#: Bump on any change to elements, chunks, questions or labels.
CORPUS_VERSION = "structure-eval-v2"

#: Default document ids, so tests and reports never hard-code strings.
DOC_MANUAL = "halcyon-manual"
DOC_APPENDIX = "halcyon-appendix"


@dataclass(frozen=True)
class EvalElement:
    """One structural element (the granularity the structure path retrieves)."""

    element_id: str
    document_id: str
    element_type: str
    """Matches :data:`graph.models.ELEMENT_TYPES` (``section``, ``paragraph``,
    ``table``, ...).  Kept as a plain string so this fixture has no import-time
    dependency on the production model layer."""

    sequence_index: int
    page_number: int
    heading_path: tuple[str, ...]
    content: str
    parent_element_id: str | None = None

    @property
    def section(self) -> str | None:
        return self.heading_path[-1] if self.heading_path else None


@dataclass(frozen=True)
class EvalChunk:
    """A chunk-level (semantic) unit backed by exactly one element.

    The one-to-one backing maps both retrieval granularities onto the same
    canonical evidence id, so chunk retrieval and element retrieval are scored
    against the *same* gold and remain comparable.
    """

    chunk_id: str
    document_id: str
    element_id: str
    content: str
    page_number: int


@dataclass(frozen=True)
class StructureQuestion:
    """One labelled question.

    ``gold_element_ids`` is the canonical ground truth (an element and its
    backing chunk share an id).  The remaining labels are used only for the
    grounding metrics, and each is optional — an absent label means "not
    measured", never "0".
    """

    question_id: str
    question: str
    category: QuestionCategory
    document_id: str | None
    gold_element_ids: tuple[str, ...] = ()
    gold_chunk_ids: tuple[str, ...] = ()
    gold_answers: tuple[str, ...] = ()
    expected_pages: tuple[int, ...] = ()
    expected_sections: tuple[str, ...] = ()
    expected_evidence_types: tuple[str, ...] = ()
    answerable: bool = True


@dataclass(frozen=True)
class EvalCorpus:
    """An immutable, ordered bundle of elements, chunks and questions."""

    version: str
    elements: tuple[EvalElement, ...]
    chunks: tuple[EvalChunk, ...]
    questions: tuple[StructureQuestion, ...]

    def element_by_id(self, element_id: str) -> EvalElement | None:
        for element in self.elements:
            if element.element_id == element_id:
                return element
        return None

    def chunk_by_id(self, chunk_id: str) -> EvalChunk | None:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def element_for_chunk(self, chunk_id: str) -> str | None:
        chunk = self.chunk_by_id(chunk_id)
        return chunk.element_id if chunk else None

    def elements_for_document(self, document_id: str) -> tuple[EvalElement, ...]:
        return tuple(e for e in self.elements if e.document_id == document_id)

    def chunks_for_document(self, document_id: str) -> tuple[EvalChunk, ...]:
        return tuple(c for c in self.chunks if c.document_id == document_id)


# ---------------------------------------------------------------------------
# Authored fixture
# ---------------------------------------------------------------------------

# doc = document id, sec = owning section element id, heading = heading path.
# ``None`` content marks a section heading element (structure only, no chunk).
_DOC1 = DOC_MANUAL
_DOC2 = DOC_APPENDIX

_ELEMENTS: tuple[EvalElement, ...] = (
    # ---- Document 1: the manual -------------------------------------------
    EvalElement("e-intro", _DOC1, "section", 0, 1, ("Introduction",), ""),
    EvalElement(
        "e-intro-body", _DOC1, "paragraph", 1, 1, ("Introduction",),
        "The Halcyon reactor removes heat using liquid sodium.", "e-intro",
    ),
    EvalElement(
        "e-intro-note", _DOC1, "paragraph", 2, 1, ("Introduction",),
        "The Halcyon reactor was commissioned in April 2019.", "e-intro",
    ),
    EvalElement("e-limits", _DOC1, "section", 3, 1, ("Operating Limits",), ""),
    EvalElement(
        "e-limits-body", _DOC1, "paragraph", 4, 1, ("Operating Limits",),
        "The maximum sustained output of the Halcyon reactor is 142.6 megawatts.",
        "e-limits",
    ),
    EvalElement(
        "e-limits-standby", _DOC1, "paragraph", 5, 1, ("Operating Limits",),
        "The standby output of the reactor is 40 megawatts.", "e-limits",
    ),
    EvalElement(
        "e-limits-trip", _DOC1, "paragraph", 6, 2, ("Operating Limits",),
        "The reactor trips automatically above 160 megawatts.", "e-limits",
    ),
    EvalElement("e-tables", _DOC1, "section", 7, 2, ("Tables",), ""),
    EvalElement(
        "e-pressure-table", _DOC1, "table", 8, 2, ("Tables", "Pressure Readings"),
        "Component Pressure Valve A 12 bar Valve B 9 bar", "e-tables",
    ),
    EvalElement("e-maint", _DOC1, "section", 9, 2, ("Maintenance",), ""),
    EvalElement(
        "e-maint-primary", _DOC1, "paragraph", 10, 3, ("Maintenance",),
        "The primary seal must be replaced every six hours of continuous operation.",
        "e-maint",
    ),
    EvalElement(
        "e-maint-secondary", _DOC1, "paragraph", 11, 3, ("Maintenance",),
        "The secondary seal must be inspected quarterly.", "e-maint",
    ),
    EvalElement(
        "e-maint-filter", _DOC1, "paragraph", 12, 3, ("Maintenance",),
        "The intake filter is replaced annually.", "e-maint",
    ),
    EvalElement(
        "e-maint-log", _DOC1, "paragraph", 13, 3, ("Maintenance",),
        "Every maintenance action is recorded in the service log.", "e-maint",
    ),
    # ---- Document 2: the appendix -----------------------------------------
    EvalElement("e-app-a", _DOC2, "section", 0, 1, ("Appendix A",), ""),
    EvalElement(
        "e-app-a-body", _DOC2, "paragraph", 1, 1, ("Appendix A",),
        "Valve A is manufactured by Quokka Industries.", "e-app-a",
    ),
    EvalElement(
        "e-app-a-note", _DOC2, "paragraph", 2, 1, ("Appendix A",),
        "Quokka Industries supplies several reactor components.", "e-app-a",
    ),
    EvalElement("e-app-b", _DOC2, "section", 3, 1, ("Appendix B",), ""),
    EvalElement(
        "e-app-b-body", _DOC2, "paragraph", 4, 1, ("Appendix B",),
        "The control firmware version is 7.2.", "e-app-b",
    ),
    EvalElement(
        "e-app-b-note", _DOC2, "paragraph", 5, 1, ("Appendix B",),
        "Firmware updates ship twice a year.", "e-app-b",
    ),
)

#: A chunk backs every element that carries answerable text (sections do not).
_CHUNK_BACKED = (
    "e-intro-body", "e-intro-note", "e-limits-body", "e-limits-standby",
    "e-limits-trip", "e-pressure-table", "e-maint-primary", "e-maint-secondary",
    "e-maint-filter", "e-maint-log", "e-app-a-body", "e-app-a-note",
    "e-app-b-body", "e-app-b-note",
)

_CHUNKS: tuple[EvalChunk, ...] = tuple(
    EvalChunk(
        chunk_id="c-" + element_id.split("-", 1)[1],
        document_id=next(e for e in _ELEMENTS if e.element_id == element_id).document_id,
        element_id=element_id,
        content=next(e for e in _ELEMENTS if e.element_id == element_id).content,
        page_number=next(e for e in _ELEMENTS if e.element_id == element_id).page_number,
    )
    for element_id in _CHUNK_BACKED
)

_QUESTIONS: tuple[StructureQuestion, ...] = (
    StructureQuestion(
        question_id="q-direct",
        question="What does the Halcyon reactor use to remove heat?",
        category=QuestionCategory.DIRECT,
        document_id=DOC_MANUAL,
        gold_element_ids=("e-intro-body",),
        gold_chunk_ids=("c-intro-body",),
        gold_answers=("liquid sodium",),
        expected_pages=(1,),
        expected_sections=("Introduction",),
        expected_evidence_types=("paragraph",),
    ),
    StructureQuestion(
        question_id="q-section",
        question="What is the maximum sustained output of the Halcyon reactor?",
        category=QuestionCategory.SECTION_DEPENDENT,
        document_id=DOC_MANUAL,
        gold_element_ids=("e-limits-body",),
        gold_chunk_ids=("c-limits-body",),
        gold_answers=("142.6 megawatts", "142.6"),
        expected_pages=(1,),
        expected_sections=("Operating Limits",),
        expected_evidence_types=("paragraph",),
    ),
    StructureQuestion(
        question_id="q-table",
        question="What pressure does Valve B operate at?",
        category=QuestionCategory.TABLE_DEPENDENT,
        document_id=DOC_MANUAL,
        gold_element_ids=("e-pressure-table",),
        gold_chunk_ids=("c-pressure-table",),
        gold_answers=("9 bar", "9"),
        expected_pages=(2,),
        expected_sections=("Tables",),
        expected_evidence_types=("table",),
    ),
    StructureQuestion(
        question_id="q-crosspage",
        question="How often must the primary seal be replaced?",
        category=QuestionCategory.PAGE_CROSS_PAGE,
        document_id=DOC_MANUAL,
        gold_element_ids=("e-maint-primary",),
        gold_chunk_ids=("c-maint-primary",),
        gold_answers=("every six hours", "six hours"),
        # The Maintenance heading sits on page 2 while the labelled paragraph
        # continues onto page 3 — the cross-page case.
        expected_pages=(2, 3),
        expected_sections=("Maintenance",),
        expected_evidence_types=("paragraph",),
    ),
    StructureQuestion(
        question_id="q-multihop",
        question="What two maintenance actions are required for the seals?",
        category=QuestionCategory.MULTI_HOP,
        document_id=DOC_MANUAL,
        gold_element_ids=("e-maint-primary", "e-maint-secondary"),
        gold_chunk_ids=("c-maint-primary", "c-maint-secondary"),
        gold_answers=("replace every six hours and inspect quarterly",),
        expected_pages=(2, 3),
        expected_sections=("Maintenance",),
        expected_evidence_types=("paragraph",),
    ),
    StructureQuestion(
        question_id="q-crossdoc",
        question="Which company manufactures Valve A, listed in the pressure table?",
        category=QuestionCategory.CROSS_DOCUMENT,
        document_id=None,  # evidence legitimately spans two documents
        gold_element_ids=("e-pressure-table", "e-app-a-body"),
        gold_chunk_ids=("c-pressure-table", "c-app-a-body"),
        gold_answers=("Quokka Industries", "Quokka"),
        expected_pages=(2, 1),
        expected_sections=("Tables", "Appendix A"),
        expected_evidence_types=("table", "paragraph"),
    ),
    StructureQuestion(
        question_id="q-firmware",
        question="What version of the control firmware is installed?",
        category=QuestionCategory.DIRECT,
        document_id=DOC_APPENDIX,
        gold_element_ids=("e-app-b-body",),
        gold_chunk_ids=("c-app-b-body",),
        gold_answers=("7.2", "version 7.2"),
        expected_pages=(1,),
        expected_sections=("Appendix B",),
        expected_evidence_types=("paragraph",),
    ),
    StructureQuestion(
        question_id="q-unanswerable-fuel",
        question="What is the Halcyon reactor's fuel enrichment percentage?",
        category=QuestionCategory.DIRECT,
        document_id=DOC_MANUAL,
        answerable=False,
    ),
    StructureQuestion(
        question_id="q-unanswerable-ceo",
        question="Who is the chief executive of Quokka Industries?",
        category=QuestionCategory.DIRECT,
        document_id=DOC_APPENDIX,
        answerable=False,
    ),
)


def build_corpus() -> EvalCorpus:
    """Return a fresh :class:`EvalCorpus` for the current ``CORPUS_VERSION``."""
    return EvalCorpus(
        version=CORPUS_VERSION,
        elements=_ELEMENTS,
        chunks=_CHUNKS,
        questions=_QUESTIONS,
    )


def corpus_summary() -> dict[str, object]:
    """Deterministic, path-free summary used by tests and reports."""
    corpus = build_corpus()
    categories: dict[str, int] = {}
    for question in corpus.questions:
        categories[question.category.value] = categories.get(question.category.value, 0) + 1
    return {
        "version": corpus.version,
        "documentCount": len({e.document_id for e in corpus.elements}),
        "elementCount": len(corpus.elements),
        "chunkCount": len(corpus.chunks),
        "questionCount": len(corpus.questions),
        "answerableCount": sum(1 for q in corpus.questions if q.answerable),
        "unanswerableCount": sum(1 for q in corpus.questions if not q.answerable),
        "categories": dict(sorted(categories.items())),
    }


__all__ = [
    "CORPUS_VERSION",
    "DOC_MANUAL",
    "DOC_APPENDIX",
    "EvalElement",
    "EvalChunk",
    "StructureQuestion",
    "EvalCorpus",
    "build_corpus",
    "corpus_summary",
]

"""Contract tests for the heading-rich evaluation corpus.

``evaluation.datasets.heading_corpus`` only has value if three things are true,
and none of them can be assumed:

1. the PDFs really contain **font-detectable headings** — the whole point is to
   exercise the extractor's font-size heuristic rather than a DOCX style name;
2. those headings really produce **sections that span pages**, so the structure
   chunker emits more than one chunk under an identical ``heading_path`` and the
   graph can build ``SAME_SECTION`` edges;
3. every labelled question's ``evidence`` really occurs in an ingested chunk, so
   the ablation runner's evidence-derived gold chunk ids are never empty.

The chunker is driven with a deterministic stand-in counter and a fixed cap, so
these tests depend on the real extractor but not on the embedding model.
"""

from __future__ import annotations

import math
import re
import tempfile
from collections import defaultdict
from pathlib import Path

import pytest

from documents.chunking import CHUNKER_VERSION_STRUCTURE, chunk_elements
from documents.processing import extract_text

from evaluation.datasets.heading_corpus import (
    build_corpus,
    corpus_summary,
    get_acceptable_answers,
    unanswerable_questions,
)

_MAX_TOKENS = 256


def _chars4(text: str) -> int:
    """Deterministic 4-characters-per-token counter (no model load)."""
    return max(1, math.ceil(len(text) / 4))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


@pytest.fixture(scope="module")
def corpus():
    """Extract every corpus document once and chunk it with the structure chunker."""
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for doc in build_corpus():
            path = doc.write(directory)
            elements = extract_text(path, doc.file_type)
            chunks = chunk_elements(
                elements,
                version=CHUNKER_VERSION_STRUCTURE,
                count_tokens=_chars4,
                max_tokens=_MAX_TOKENS,
            )
            out[doc.name] = {"doc": doc, "elements": elements, "chunks": chunks}
    return out


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


class TestCorpusShape:
    def test_every_document_is_a_pdf(self, corpus):
        for name, data in corpus.items():
            assert data["doc"].file_type == "pdf", name

    def test_every_document_produces_chunks(self, corpus):
        for name, data in corpus.items():
            assert data["chunks"], f"{name} produced no chunks"

    def test_summary_counts_are_consistent(self):
        summary = corpus_summary()
        answerable = [q for doc in build_corpus() for q in doc.questions]
        assert summary["documents"] == len(build_corpus())
        assert summary["questions_answerable"] == len(answerable)
        assert summary["questions_unsupported"] == len(unanswerable_questions())
        assert summary["all_pdf"] is True
        assert summary["with_expected_answer"] == len(answerable)
        assert summary["with_evidence"] == len(answerable)


# ---------------------------------------------------------------------------
# Real, font-detectable headings
# ---------------------------------------------------------------------------


EXPECTED_HEADINGS: dict[str, set[tuple[str, int]]] = {
    "orbital_handbook.pdf": {
        ("Kestrel Propulsion", 1),
        ("Nimbus Avionics", 2),
        ("Falcon Thermal Control", 1),
    },
    "field_guide.pdf": {
        ("Meridian Field Survey", 1),
        ("Sampling Protocol", 2),
        ("Instrument Calibration", 2),
        ("Drift Correction", 3),
    },
    "platform_spec.pdf": {("Quokka Processing Pipeline", 1)},
    "archive_notes.pdf": {
        ("Vermilion Archive", 1),
        ("Solstice Records", 1),
        ("Tundra Inventory", 1),
    },
}


class TestRealHeadings:
    @pytest.mark.parametrize("name", sorted(EXPECTED_HEADINGS))
    def test_expected_headings_are_detected(self, corpus, name):
        detected = {
            (e.content, e.heading_level)
            for e in corpus[name]["elements"]
            if e.element_type == "heading"
        }
        missing = EXPECTED_HEADINGS[name] - detected
        assert not missing, f"{name}: headings not detected: {missing}"

    def test_no_heading_block_absorbed_a_body_line(self, corpus):
        """A heading must be exactly the heading text, never heading + prose.

        If a heading merges with the paragraph above it, the block inherits the
        heading font and the paragraph silently disappears; this pins that.
        """
        known = {text for pairs in EXPECTED_HEADINGS.values() for text, _ in pairs}
        for name, data in corpus.items():
            for element in data["elements"]:
                if element.element_type == "heading":
                    assert element.content in known, (
                        f"{name}: unexpected heading block {element.content!r}"
                    )

    def test_heading_levels_cover_h1_h2_h3(self, corpus):
        levels = {
            e.heading_level
            for data in corpus.values()
            for e in data["elements"]
            if e.element_type == "heading"
        }
        assert levels == {1, 2, 3}


# ---------------------------------------------------------------------------
# Sections that span pages
# ---------------------------------------------------------------------------


EXPECTED_SPANNING: dict[str, dict[tuple[str, ...], set[int]]] = {
    "orbital_handbook.pdf": {
        ("Kestrel Propulsion",): {1, 2},
        ("Kestrel Propulsion", "Nimbus Avionics"): {2, 3},
    },
    "field_guide.pdf": {
        ("Meridian Field Survey", "Sampling Protocol"): {1, 2},
        ("Meridian Field Survey", "Instrument Calibration"): {2, 3},
    },
    "platform_spec.pdf": {("Quokka Processing Pipeline",): {1, 2, 3}},
    "archive_notes.pdf": {("Solstice Records",): {1, 2}},
}


def _paths_by_page(chunks) -> dict[tuple[str, ...], set[int]]:
    by_page: dict[tuple[str, ...], set[int]] = defaultdict(set)
    for chunk in chunks:
        if chunk.meta.heading_path and chunk.meta.page is not None:
            by_page[tuple(chunk.meta.heading_path)].add(chunk.meta.page)
    return dict(by_page)


class TestPageSpanningSections:
    @pytest.mark.parametrize("name", sorted(EXPECTED_SPANNING))
    def test_documented_sections_span_the_documented_pages(self, corpus, name):
        paths = _paths_by_page(corpus[name]["chunks"])
        for path, expected_pages in EXPECTED_SPANNING[name].items():
            assert path in paths, f"{name}: section {path!r} produced no chunks"
            assert paths[path] == expected_pages, (
                f"{name}: {path!r} spans {sorted(paths[path])}, expected "
                f"{sorted(expected_pages)}"
            )

    def test_every_document_has_a_cross_page_section(self, corpus):
        for name, data in corpus.items():
            spanning = {
                path: pages
                for path, pages in _paths_by_page(data["chunks"]).items()
                if len(pages) > 1
            }
            assert spanning, f"{name}: no section spans more than one page"


# ---------------------------------------------------------------------------
# Labels resolve to real chunks
# ---------------------------------------------------------------------------


class TestLabels:
    def test_evidence_is_findable_in_an_ingested_chunk(self, corpus):
        for name, data in corpus.items():
            for question in data["doc"].questions:
                hits = [
                    chunk
                    for chunk in data["chunks"]
                    if any(_norm(e) in _norm(chunk.content) for e in question.evidence)
                ]
                assert hits, f"{name}: {question.qid} has no chunk matching its evidence"

    def test_answerable_questions_carry_an_expected_answer(self, corpus):
        for name, data in corpus.items():
            for question in data["doc"].questions:
                assert question.answerable is True, question.qid
                assert question.expected_answer, f"{name}: {question.qid}"
                assert question.evidence, f"{name}: {question.qid}"

    def test_cross_page_questions_resolve_to_a_later_page_than_their_heading(
        self, corpus
    ):
        """A ``cross_page`` label must actually mean the body outlived the page.

        The supporting chunk sits in a section whose heading is on an earlier
        page; otherwise the label would be a claim the corpus does not support.
        """
        checked = 0
        for name, data in corpus.items():
            heading_pages = {
                element.content: element.page
                for element in data["elements"]
                if element.element_type == "heading"
            }
            for question in data["doc"].questions:
                if question.kind != "cross_page":
                    continue
                gold = [
                    chunk
                    for chunk in data["chunks"]
                    if any(
                        _norm(e) in _norm(chunk.content) for e in question.evidence
                    )
                ]
                assert gold, f"{name}: {question.qid} has no gold chunk"
                for chunk in gold:
                    section = chunk.meta.section
                    assert section in heading_pages, (
                        f"{name}: {question.qid} section {section!r} has no heading"
                    )
                    assert chunk.meta.page > heading_pages[section], (
                        f"{name}: {question.qid} gold page {chunk.meta.page} is not "
                        f"after its heading (page {heading_pages[section]})"
                    )
                    checked += 1
        assert checked, "no cross_page question was exercised"

    def test_unsupported_questions_have_no_support_anywhere(self, corpus):
        unsupported_ids = {q.qid for q in unanswerable_questions()}
        assert unsupported_ids, "the corpus must carry unsupported questions"
        for q in unanswerable_questions():
            assert q.answerable is False
            assert q.expected_answer is None
            assert not q.evidence
        answerable_ids = {
            q.qid for data in corpus.values() for q in data["doc"].questions
        }
        assert unsupported_ids.isdisjoint(answerable_ids)

    def test_paraphrase_variants_include_the_expected_answer(self):
        for doc in build_corpus():
            for question in doc.questions:
                variants = get_acceptable_answers(question.qid)
                assert variants, f"{question.qid} has no acceptable answer variants"
                assert question.expected_answer in variants, question.qid

"""Offline, deterministic, structure-aware evaluation harness (Feature #15).

What this measures
------------------
Four retrieval variants over a **structure-labelled** corpus, separating three
questions that are easy to conflate:

* **retrieval quality** — did the variant surface the labelled evidence?
  (Recall@K, Precision@K, MRR, nDCG@K against hand-authored gold element ids)
* **answer quality** — did the extracted answer match the labelled answers?
  (exact match, token-set F1, accuracy over the answerable population)
* **grounding** — was the answer drawn from the correct *structured* source,
  and on the expected page / under the expected section / in the expected
  evidence type? (page grounding, section grounding, evidence-type coverage,
  answer-source grounding)

Variants
--------
============  ==========================================================
``A``         ``semantic_only``      lexical scoring of **chunk** text
``B``         ``dual_path_chunk``    chunk scoring + chunk-graph expansion
``C``         ``structure_aware``    element scoring (content + heading path)
``D``         ``fused_dual_path``    chunks + elements fused through
                                     :func:`graph.evidence.fuse_evidence`
============  ==========================================================

Every variant returns real :class:`graph.evidence.EvidenceItem` objects, so the
fused variant runs the **production fusion contract** rather than a copy of it.

Honesty contract
----------------
* Fully **offline**: no PostgreSQL, pgvector, embeddings, model weights, network
  or external LLM judge.  The only import from production code is the
  deterministic, database-independent fusion module ``graph.evidence``.
* **Deterministic**: pure functions of the corpus and the question; every
  ordering has a total tie-break; reports carry no wall-clock time unless the
  caller explicitly asks for one.
* **No invented numbers**: a metric whose population is empty is reported as
  ``null`` (unavailable) with a reason, never as ``0.0``.
* The lexical scorers here are an honest *offline reference baseline*, not a
  stand-in for the production dual-path pipeline.  Production/pgvector
  evaluation stays in ``evaluation/experiments/run_dual_path_ablation.py``.

Research code.  Never imported by production modules and never collected by
pytest (``pytest.ini`` sets ``testpaths = tests``); run it explicitly:

    cd backend
    ./venv/Scripts/python.exe evaluation/structure_eval.py
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from evaluation import qa_metrics, retrieval_metrics  # noqa: E402
from evaluation.artifacts import ArtifactExistsError, write_evidence  # noqa: E402
from evaluation.datasets import structure_eval_corpus as corpus_module
from evaluation.datasets.structure_eval_corpus import EvalChunk, EvalCorpus, EvalElement, StructureQuestion
from graph.evidence import EvidenceItem, fuse_evidence

HARNESS_VERSION = "structure-eval-harness-v1"

#: Default retrieval depth.  Metrics are reported at this ``K``.
DEFAULT_TOP_K = 5

REPORTS_DIR = Path(__file__).resolve().parent / "reports"

#: Structural weight in the element scorer.  Content dominates; the heading
#: path contributes so that a section's own heading can surface its body.
_CONTENT_WEIGHT = 0.7
_HEADING_WEIGHT = 0.3

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

#: Minimal stoplist for the offline lexical baseline.  Production term
#: extraction lives in ``graph.service`` (``STOP_WORDS`` / ``terms_from_question``);
#: this copy keeps the harness free of the production import graph and is
#: deliberately small and stable.
_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "does", "do", "for",
        "from", "how", "in", "is", "it", "its", "of", "on", "or", "the", "to",
        "two", "was", "what", "when", "where", "which", "who", "why", "with",
    }
)


class StructureCorpusError(ValueError):
    """Raised when a corpus violates the harness contract.

    The message names the offending id so a malformed fixture fails loudly
    instead of silently producing misleading metrics.  It never carries a
    filesystem path.
    """


class StructureVariant(str, Enum):
    """The four variants Feature #15 compares."""

    A_SEMANTIC_ONLY = "A_semantic_only"
    B_DUAL_PATH_CHUNK = "B_dual_path_chunk"
    C_STRUCTURE_AWARE = "C_structure_aware"
    D_FUSED_DUAL_PATH = "D_fused_dual_path"


ALL_VARIANTS: tuple[StructureVariant, ...] = (
    StructureVariant.A_SEMANTIC_ONLY,
    StructureVariant.B_DUAL_PATH_CHUNK,
    StructureVariant.C_STRUCTURE_AWARE,
    StructureVariant.D_FUSED_DUAL_PATH,
)

#: Canonical evidence id is the backing *element* id: an element and its chunk
#: share one identity, so all four variants are scored against the same gold.
Retriever = Callable[[StructureQuestion], list[EvidenceItem]]


# ---------------------------------------------------------------------------
# Deterministic lexical primitives
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (punctuation is a separator)."""
    return _TOKEN_RE.findall((text or "").lower())


def query_terms(text: str) -> list[str]:
    """Content tokens of a question: stopwords dropped, order preserved, unique."""
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokenize(text):
        if token in _STOP_WORDS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def overlap_score(terms: Sequence[str], text: str) -> float:
    """Fraction of ``terms`` present in ``text`` as tokens; ``0.0`` for no terms."""
    if not terms:
        return 0.0
    present = set(tokenize(text))
    return sum(1 for term in terms if term in present) / len(terms)


def _sentences(text: str) -> list[str]:
    """Split into non-empty sentences; falls back to the whole text."""
    parts = [part.strip() for part in _SENTENCE_RE.split(text or "") if part.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


# ---------------------------------------------------------------------------
# Evidence construction
# ---------------------------------------------------------------------------

def _chunk_evidence(corpus: EvalCorpus, chunk: EvalChunk, score: float) -> EvidenceItem:
    element = corpus.element_by_id(chunk.element_id)
    return EvidenceItem(
        evidence_id=f"{chunk.document_id}:{chunk.chunk_id}",
        document_id=chunk.document_id,
        source_type="semantic",
        content=chunk.content,
        chunk_id=chunk.chunk_id,
        page_number=chunk.page_number,
        element_type=element.element_type if element else None,
        heading_path=element.heading_path if element else None,
        score=score,
        score_source="lexical_overlap",
    )


def _element_evidence(element: EvalElement) -> EvidenceItem:
    """Structural evidence never carries a similarity score.

    The lexical rank that selected the element is an ordering device, not a
    similarity; the production :func:`graph.evidence.evidence_from_structure_element`
    contract leaves ``score``/``score_source`` empty, and so does this.
    """
    return EvidenceItem(
        evidence_id=f"{element.document_id}:{element.element_id}",
        document_id=element.document_id,
        source_type="structure",
        content=element.content,
        structure_element_id=element.element_id,
        page_number=element.page_number,
        sequence_index=element.sequence_index,
        element_type=element.element_type,
        heading_path=element.heading_path or None,
        section=element.section,
        score=None,
        score_source=None,
    )


def _scope_chunks(corpus: EvalCorpus, question: StructureQuestion) -> tuple[EvalChunk, ...]:
    if question.document_id:
        return corpus.chunks_for_document(question.document_id)
    return corpus.chunks


def _scope_elements(corpus: EvalCorpus, question: StructureQuestion) -> tuple[EvalElement, ...]:
    if question.document_id:
        return corpus.elements_for_document(question.document_id)
    return corpus.elements


def _rank_chunks(corpus: EvalCorpus, terms: Sequence[str], chunks: Sequence[EvalChunk]) -> list[tuple[float, EvalChunk]]:
    """Rank chunks by overlap, tie-broken by (sequence_index, chunk_id)."""
    def sort_key(pair: tuple[float, EvalChunk]) -> tuple[float, int, str]:
        score, chunk = pair
        element = corpus.element_by_id(chunk.element_id)
        seq = element.sequence_index if element else 0
        return (-score, seq, chunk.chunk_id)

    scored = [(overlap_score(terms, chunk.content), chunk) for chunk in chunks]
    return sorted(scored, key=sort_key)


def _rank_elements(corpus: EvalCorpus, terms: Sequence[str], elements: Sequence[EvalElement]) -> list[tuple[float, EvalElement]]:
    """Rank elements by content + heading-path overlap, tie-broken by sequence index."""
    def structure_score(element: EvalElement) -> float:
        content = overlap_score(terms, element.content)
        heading = overlap_score(terms, " ".join(element.heading_path))
        return _CONTENT_WEIGHT * content + _HEADING_WEIGHT * heading

    def sort_key(pair: tuple[float, EvalElement]) -> tuple[float, int, str]:
        score, element = pair
        return (-score, element.sequence_index, element.element_id)

    scored = [(structure_score(element), element) for element in elements]
    return sorted(scored, key=sort_key)


# ---------------------------------------------------------------------------
# The four retrievers (real, deterministic, injected into the harness)
# ---------------------------------------------------------------------------

def retrieve_semantic_only(corpus: EvalCorpus, question: StructureQuestion, *, top_k: int) -> list[EvidenceItem]:
    """A: rank **chunks** by lexical overlap and return the top-K."""
    terms = query_terms(question.question)
    ranked = _rank_chunks(corpus, terms, _scope_chunks(corpus, question))
    return [_chunk_evidence(corpus, chunk, score) for score, chunk in ranked[:top_k]]


def retrieve_dual_path_chunk(corpus: EvalCorpus, question: StructureQuestion, *, top_k: int) -> list[EvidenceItem]:
    """B: semantic chunk ranking + chunk-graph expansion (same-section siblings).

    The second path is the document's own structure — the sibling chunks under
    the same heading — never a re-scoring of the same text.  The two paths are
    **interleaved** rather than concatenated: a saturated semantic list would
    otherwise always fill ``top_k`` and starve the structural path entirely,
    making variant B indistinguishable from variant A.
    """
    terms = query_terms(question.question)
    scoped = _scope_chunks(corpus, question)
    ranked = _rank_chunks(corpus, terms, scoped)
    semantic = [
        _chunk_evidence(corpus, chunk, score) for score, chunk in ranked if score > 0.0
    ][:top_k]

    chosen_ids = {item.chunk_id for item in semantic}
    sections: set[tuple[str, tuple[str, ...]]] = set()
    for item in semantic:
        element = corpus.element_by_id(corpus.element_for_chunk(item.chunk_id) or "")
        if element:
            sections.add((item.document_id, element.heading_path))

    expansions: list[tuple[int, str, EvalChunk]] = []
    for chunk in scoped:
        if chunk.chunk_id in chosen_ids:
            continue
        element = corpus.element_by_id(chunk.element_id)
        if element and (chunk.document_id, element.heading_path) in sections:
            expansions.append((element.sequence_index, chunk.chunk_id, chunk))
    expansions.sort(key=lambda t: (t[0], t[1]))
    expanded = [
        _chunk_evidence(corpus, chunk, overlap_score(terms, chunk.content))
        for _, _, chunk in expansions
    ]

    seen: set[tuple[str, str, str]] = set()
    out: list[EvidenceItem] = []
    for semantic_item, expansion_item in itertools.zip_longest(semantic, expanded):
        for item in (semantic_item, expansion_item):
            if item is None or item.identity() in seen:
                continue
            seen.add(item.identity())
            out.append(item)
            if len(out) >= top_k:
                return out
    return out


def retrieve_structure_aware(corpus: EvalCorpus, question: StructureQuestion, *, top_k: int) -> list[EvidenceItem]:
    """C: rank **elements** by content + heading path, with section parents added."""
    terms = query_terms(question.question)
    ranked = _rank_elements(corpus, terms, _scope_elements(corpus, question))
    scored = [(score, element) for score, element in ranked if score > 0.0][:top_k]

    out: list[EvidenceItem] = [_element_evidence(element) for _, element in scored]
    seen = {item.identity() for item in out}

    # Structural context: the section that owns each matched body element.
    for _, element in scored:
        if not element.parent_element_id:
            continue
        parent = corpus.element_by_id(element.parent_element_id)
        if parent is None:
            continue
        item = _element_evidence(parent)
        if item.identity() in seen:
            continue
        seen.add(item.identity())
        out.append(item)
        if len(out) >= top_k:
            break
    return out[:top_k]


def retrieve_fused_dual_path(corpus: EvalCorpus, question: StructureQuestion, *, top_k: int) -> list[EvidenceItem]:
    """D: fuse the semantic (chunk) and structural (element) streams.

    Uses the production :func:`graph.evidence.fuse_evidence` contract — real
    ordering, real deduplication, real provenance.
    """
    terms = query_terms(question.question)
    chunk_ranked = _rank_chunks(corpus, terms, _scope_chunks(corpus, question))
    element_ranked = _rank_elements(corpus, terms, _scope_elements(corpus, question))

    semantic = [_chunk_evidence(corpus, chunk, score) for score, chunk in chunk_ranked if score > 0.0][:top_k]
    structural = [_element_evidence(element) for score, element in element_ranked if score > 0.0][:top_k]

    fused = fuse_evidence(
        semantic_evidence=semantic,
        structural_evidence=structural,
        max_semantic=top_k,
        max_structural=top_k,
        max_fused=top_k,
        allow_multi_document=True,  # cross-document questions are labelled
    )
    return list(fused.items)


def retrieve(corpus: EvalCorpus, variant: StructureVariant, question: StructureQuestion, *, top_k: int) -> list[EvidenceItem]:
    """Dispatch to the variant's retriever at the requested depth."""
    if variant is StructureVariant.A_SEMANTIC_ONLY:
        return retrieve_semantic_only(corpus, question, top_k=top_k)
    if variant is StructureVariant.B_DUAL_PATH_CHUNK:
        return retrieve_dual_path_chunk(corpus, question, top_k=top_k)
    if variant is StructureVariant.C_STRUCTURE_AWARE:
        return retrieve_structure_aware(corpus, question, top_k=top_k)
    return retrieve_fused_dual_path(corpus, question, top_k=top_k)


# ---------------------------------------------------------------------------
# Extractive answer step (no model, no external judge)
# ---------------------------------------------------------------------------

def _novel_span(sentence: str, terms: Sequence[str]) -> str | None:
    """Longest run of consecutive "novel" content tokens in ``sentence``.

    A token is novel when it is neither a stopword nor one of the question's own
    terms.  The run is returned as the original substring, so the answer stays a
    verbatim span (never a paraphrase).  This is a generic extractive heuristic:
    it never consults the labelled answer.
    """
    term_set = set(terms)
    matches = list(_TOKEN_RE.finditer(sentence.lower()))
    runs: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    for match in matches:
        if match.group(0) in _STOP_WORDS or match.group(0) in term_set:
            if current:
                runs.append(current)
                current = []
        else:
            current.append(match)
    if current:
        runs.append(current)
    if not runs:
        return None
    best = max(runs, key=lambda run: (len(run), -run[0].start()))
    return sentence[best[0].start():best[-1].end()].strip()


def extractive_answer(question: StructureQuestion, evidence: Sequence[EvidenceItem]) -> dict[str, Any]:
    """Deterministically extract an answer span from the retrieved evidence.

    The best-overlap sentence is selected first; within it the longest run of
    novel content tokens becomes the answer, falling back to the whole sentence
    when every token is a stopword or question term.  The answer is always a
    verbatim span of one evidence item, so ``factual_grounded`` is true by
    construction for any non-empty answer.  That is stated rather than hidden —
    the metric validates wiring, it does not flatter the variants.  The span
    heuristic never consults the labelled answer.
    """
    terms = query_terms(question.question)
    best: tuple[float, str, str] | None = None  # (score, sentence, evidence_id)

    for item in evidence:
        for sentence in _sentences(item.content or ""):
            score = overlap_score(terms, sentence)
            if score > 0.0 and (best is None or score > best[0]):
                best = (score, sentence, item.evidence_id)

    supplied = [item.evidence_id for item in evidence]
    if best is None:
        return {
            "answer": "",
            "confidence": 0.0,
            "insufficient_context": True,
            "factual_grounded": False,
            "supplied_evidence_ids": supplied,
            "source_evidence_id": None,
        }

    score, sentence, evidence_id = best
    answer = _novel_span(sentence, terms) or sentence.strip()
    haystack = qa_metrics.normalize_text(
        " ".join((item.content or "") for item in evidence)
    )
    grounded = qa_metrics.normalize_text(answer) in haystack
    return {
        "answer": answer,
        "confidence": score,
        "insufficient_context": not answer,
        "factual_grounded": grounded,
        "supplied_evidence_ids": supplied,
        "source_evidence_id": evidence_id,
    }


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

_RETRIEVAL_KEYS = ("recall@{k}", "precision@{k}", "mrr", "ndcg@{k}")
_ANSWER_KEYS = ("exact_match", "token_f1", "answer_accuracy")
_GROUNDING_KEYS = (
    "page_grounding",
    "section_grounding",
    "evidence_type_coverage",
    "answer_source_grounded",
    "answer_corpus_grounded",
    "unsupported_answer_rate",
    "semantic_source_count",
    "structural_source_count",
)

#: Reasons recorded when a metric's population is empty.  ``{k}`` is filled in
#: with the run's actual ``top_k`` so a non-default depth is never mislabelled.
_UNAVAILABLE_REASONS_TEMPLATE: dict[str, str] = {
    "recall@{k}": "no question in this run carried labelled gold evidence",
    "precision@{k}": "no question in this run carried labelled gold evidence",
    "mrr": "no question in this run carried labelled gold evidence",
    "ndcg@{k}": "no question in this run carried labelled gold evidence",
    "exact_match": "no answerable question with a labelled answer was measured",
    "token_f1": "no answerable question with a labelled answer was measured",
    "answer_accuracy": "no answerable question with a labelled answer was measured",
    "page_grounding": "no question in this run carried an expected page",
    "section_grounding": "no question in this run carried an expected section",
    "evidence_type_coverage": "no question in this run carried an expected evidence type",
    "answer_source_grounded": "no answer was produced from a question carrying gold evidence",
    "answer_corpus_grounded": "no question was answered",
    "unsupported_answer_rate": "no unanswerable question was measured",
    "semantic_source_count": "no semantic evidence was retrieved",
    "structural_source_count": "no structural evidence was retrieved",
}


def validate_corpus(corpus: EvalCorpus) -> None:
    """Fail fast on a malformed corpus — before any metric is produced.

    Checks id uniqueness, that every chunk backs a real element, that every
    labelled gold id exists, and that answerable/unanswerable questions carry
    (or omit) gold consistently.  Raises :class:`StructureCorpusError`.
    """
    element_ids: set[str] = set()
    for element in corpus.elements:
        if element.element_id in element_ids:
            raise StructureCorpusError(f"duplicate element id {element.element_id!r}")
        element_ids.add(element.element_id)
        if element.page_number < 1:
            raise StructureCorpusError(
                f"element {element.element_id!r} has page_number < 1"
            )
    for element in corpus.elements:
        if element.parent_element_id and element.parent_element_id not in element_ids:
            raise StructureCorpusError(
                f"element {element.element_id!r} references missing parent "
                f"{element.parent_element_id!r}"
            )

    chunk_ids: set[str] = set()
    for chunk in corpus.chunks:
        if chunk.chunk_id in chunk_ids:
            raise StructureCorpusError(f"duplicate chunk id {chunk.chunk_id!r}")
        chunk_ids.add(chunk.chunk_id)
        if chunk.element_id not in element_ids:
            raise StructureCorpusError(
                f"chunk {chunk.chunk_id!r} backs unknown element {chunk.element_id!r}"
            )

    question_ids: set[str] = set()
    for question in corpus.questions:
        if question.question_id in question_ids:
            raise StructureCorpusError(f"duplicate question id {question.question_id!r}")
        question_ids.add(question.question_id)
        for element_id in question.gold_element_ids:
            if element_id not in element_ids:
                raise StructureCorpusError(
                    f"question {question.question_id!r} labels unknown element {element_id!r}"
                )
        for chunk_id in question.gold_chunk_ids:
            if chunk_id not in chunk_ids:
                raise StructureCorpusError(
                    f"question {question.question_id!r} labels unknown chunk {chunk_id!r}"
                )
        if question.answerable and not question.gold_element_ids:
            raise StructureCorpusError(
                f"answerable question {question.question_id!r} carries no gold evidence"
            )
        if not question.answerable and question.gold_element_ids:
            raise StructureCorpusError(
                f"unanswerable question {question.question_id!r} must carry no gold evidence"
            )


def _canonical_ids(corpus: EvalCorpus, items: Sequence[EvidenceItem]) -> list[str]:
    """Map evidence to canonical element ids, preserving order and de-duplicating."""
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        element_id = (
            corpus.element_for_chunk(item.chunk_id)
            if item.chunk_id
            else item.structure_element_id
        )
        if element_id and element_id not in seen:
            seen.add(element_id)
            out.append(element_id)
    return out


def measure_question(
    corpus: EvalCorpus,
    variant: StructureVariant,
    question: StructureQuestion,
    *,
    top_k: int,
) -> dict[str, Any]:
    """Measure one question for one variant.  Missing populations yield ``None``."""
    evidence = retrieve(corpus, variant, question, top_k=top_k)
    outcome = extractive_answer(question, evidence)

    retrieved_ids = _canonical_ids(corpus, evidence)
    gold = list(question.gold_element_ids)
    predicted = outcome["answer"]

    metrics: dict[str, float | None] = {}

    # --- retrieval quality (population: questions with labelled gold) -------
    if gold:
        metrics[f"recall@{top_k}"] = retrieval_metrics.recall_at_k(retrieved_ids, gold, top_k)
        metrics[f"precision@{top_k}"] = retrieval_metrics.precision_at_k(retrieved_ids, gold, top_k)
        metrics["mrr"] = retrieval_metrics.reciprocal_rank(retrieved_ids, gold)
        metrics[f"ndcg@{top_k}"] = retrieval_metrics.ndcg_at_k(retrieved_ids, gold, top_k)
    else:
        metrics[f"recall@{top_k}"] = None
        metrics[f"precision@{top_k}"] = None
        metrics["mrr"] = None
        metrics[f"ndcg@{top_k}"] = None

    # --- answer quality (population: answerable questions with gold answers) -
    has_answer_gold = question.answerable and bool(question.gold_answers)
    if has_answer_gold:
        metrics["exact_match"] = 1.0 if qa_metrics.exact_match_any(predicted, question.gold_answers) else 0.0
        metrics["token_f1"] = qa_metrics.token_f1_any(predicted, question.gold_answers)
        metrics["answer_accuracy"] = (
            1.0 if qa_metrics.token_f1_any(predicted, question.gold_answers) >= 0.5 else 0.0
        )
    else:
        metrics["exact_match"] = None
        metrics["token_f1"] = None
        metrics["answer_accuracy"] = None

    # --- grounding ----------------------------------------------------------
    retrieved_elements = [corpus.element_by_id(eid) for eid in retrieved_ids]

    if question.expected_pages:
        pages = {e.page_number for e in retrieved_elements if e is not None}
        metrics["page_grounding"] = 1.0 if pages & set(question.expected_pages) else 0.0
    else:
        metrics["page_grounding"] = None

    if question.expected_sections:
        sections = {e.section for e in retrieved_elements if e is not None and e.section}
        metrics["section_grounding"] = (
            1.0 if sections & set(question.expected_sections) else 0.0
        )
    else:
        metrics["section_grounding"] = None

    if question.expected_evidence_types:
        types = {e.element_type for e in retrieved_elements if e is not None}
        covered = len(types & set(question.expected_evidence_types))
        metrics["evidence_type_coverage"] = covered / len(set(question.expected_evidence_types))
    else:
        metrics["evidence_type_coverage"] = None

    source_id = outcome["source_evidence_id"]
    source_element = None
    if source_id:
        for item in evidence:
            if item.evidence_id == source_id:
                source_element = (
                    corpus.element_for_chunk(item.chunk_id)
                    if item.chunk_id
                    else item.structure_element_id
                )
                break
    if source_element and gold:
        metrics["answer_source_grounded"] = 1.0 if source_element in set(gold) else 0.0
    else:
        metrics["answer_source_grounded"] = None

    answered = bool(qa_metrics.normalize_text(predicted))
    if answered:
        metrics["answer_corpus_grounded"] = 1.0 if outcome["factual_grounded"] else 0.0
    else:
        metrics["answer_corpus_grounded"] = None

    if not question.answerable:
        metrics["unsupported_answer_rate"] = (
            1.0 if answered and not outcome["insufficient_context"] else 0.0
        )
    else:
        metrics["unsupported_answer_rate"] = None

    semantic_count = sum(1 for item in evidence if item.source_type == "semantic")
    structural_count = sum(1 for item in evidence if item.source_type == "structure")
    metrics["semantic_source_count"] = float(semantic_count) if evidence else None
    metrics["structural_source_count"] = float(structural_count) if evidence else None

    return {
        "question_id": question.question_id,
        "category": question.category.value,
        "answerable": question.answerable,
        "metrics": metrics,
        "detail": {
            "retrieved_element_ids": retrieved_ids,
            "gold_element_ids": gold,
            "predicted": predicted,
            "gold_answers": list(question.gold_answers),
            "confidence": outcome["confidence"],
            "insufficient_context": outcome["insufficient_context"],
            "source_evidence_id": source_id,
        },
    }


def _aggregate(
    rows: Sequence[dict[str, Any]],
    keys: Sequence[str],
    *,
    top_k: int,
) -> tuple[dict[str, float | None], dict[str, str]]:
    """Mean each metric over the rows where it was measured.

    A metric that was ``None`` for every row is reported as ``null`` with a
    reason — never coerced to ``0.0``.
    """
    metrics: dict[str, float | None] = {}
    unavailable: dict[str, str] = {}
    for key in keys:
        values = [row["metrics"].get(key) for row in rows]
        measured = [v for v in values if v is not None]
        if measured:
            metrics[key] = sum(measured) / len(measured)
        else:
            metrics[key] = None
            template = _UNAVAILABLE_REASONS_TEMPLATE.get(key, "population empty")
            unavailable[key] = template.format(k=top_k)
    return metrics, unavailable


def _by_category(
    rows: Sequence[dict[str, Any]],
    keys: Sequence[str],
    *,
    top_k: int,
) -> dict[str, dict[str, float | None]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row)
    return {name: _aggregate(items, keys, top_k=top_k)[0] for name, items in sorted(grouped.items())}


def _metric_keys(top_k: int) -> tuple[str, ...]:
    retrieval = tuple(key.format(k=top_k) for key in _RETRIEVAL_KEYS)
    return retrieval + _ANSWER_KEYS + _GROUNDING_KEYS


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class VariantRun:
    """One variant's measured results."""

    variant: str
    question_count: int
    metrics: dict[str, float | None]
    by_category: dict[str, dict[str, float | None]]
    unavailable: dict[str, str]
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "question_count": self.question_count,
            "metrics": self.metrics,
            "by_category": self.by_category,
            "unavailable": self.unavailable,
            "results": [
                {
                    "question_id": r["question_id"],
                    "category": r["category"],
                    "answerable": r["answerable"],
                    "metrics": r["metrics"],
                    "detail": r["detail"],
                }
                for r in self.results
            ],
        }


@dataclass
class StructureEvaluationReport:
    """Aggregate report for all requested variants."""

    corpus_version: str
    harness_version: str
    top_k: int
    metric_keys: tuple[str, ...] = ()
    runs: list[VariantRun] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Deterministic, path-free, timestamp-free machine-readable payload."""
        return {
            "corpus_version": self.corpus_version,
            "harness_version": self.harness_version,
            "top_k": self.top_k,
            "metric_keys": list(self.metric_keys),
            "offline": True,
            "requires_database": False,
            "requires_model": False,
            "runs": [run.to_dict() for run in self.runs],
        }


def evaluate(
    corpus: EvalCorpus,
    *,
    variants: Sequence[StructureVariant] = ALL_VARIANTS,
    top_k: int = DEFAULT_TOP_K,
) -> StructureEvaluationReport:
    """Measure every variant over ``corpus`` deterministically."""
    validate_corpus(corpus)
    keys = _metric_keys(top_k)

    report = StructureEvaluationReport(
        corpus_version=corpus.version,
        harness_version=HARNESS_VERSION,
        top_k=top_k,
        metric_keys=keys,
    )

    for variant in variants:
        rows = [
            measure_question(corpus, variant, question, top_k=top_k)
            for question in corpus.questions
        ]
        metrics, unavailable = _aggregate(rows, keys, top_k=top_k)
        report.runs.append(
            VariantRun(
                variant=variant.value,
                question_count=len(rows),
                metrics=metrics,
                by_category=_by_category(rows, keys, top_k=top_k),
                unavailable=unavailable,
                results=rows,
            )
        )
    return report


def write_report(
    report: StructureEvaluationReport,
    name: str,
    *,
    include_timestamp: bool = False,
    replace: bool = False,
) -> Path:
    """Write the report as deterministic JSON (and a markdown summary).

    ``include_timestamp`` is off by default so two runs over the same corpus
    produce byte-identical files (reproducibility check).

    Both destinations are checked BEFORE either is written, so a refused
    republication cannot leave half a report behind.  ``replace=True`` is the
    explicit, visible opt-in for a deliberate re-publication — the
    byte-reproducibility comparison rewrites the same name on purpose — and it is
    never inferred.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    if include_timestamp:
        from datetime import datetime, timezone

        payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    json_path = REPORTS_DIR / f"{name}.json"
    md_path = REPORTS_DIR / f"{name}.md"

    if not replace:
        collisions = [path for path in (json_path, md_path) if path.exists()]
        if collisions:
            raise ArtifactExistsError(
                "refusing to replace existing evaluation evidence: "
                + ", ".join(str(path) for path in collisions)
                + ". Evaluation artifacts are append-only — write to a new name, "
                "or pass replace=True for a deliberate re-publication."
            )

    lines = [
        f"# Structure evaluation report — {report.corpus_version}",
        "",
        f"- Harness: {report.harness_version}",
        f"- Top-K: {report.top_k}",
        "- Offline: yes (no PostgreSQL / pgvector / model)",
        "",
    ]
    for run in report.runs:
        lines += [f"## {run.variant}", "", f"- Questions: {run.question_count}", "", "| metric | value |", "|---|---|"]
        for key in report.metric_keys:
            value = run.metrics.get(key)
            rendered = "n/a" if value is None else f"{value:.4f}"
            lines.append(f"| {key} | {rendered} |")
        lines.append("")
        if run.unavailable:
            lines += ["Unavailable metrics (empty population):", ""]
            for key, reason in sorted(run.unavailable.items()):
                lines.append(f"- **{key}**: {reason}")
            lines.append("")

    write_evidence(
        json_path, json.dumps(payload, indent=2, sort_keys=True), replace=replace
    )
    write_evidence(md_path, "\n".join(lines), replace=replace)
    return json_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(report: StructureEvaluationReport) -> None:
    print(f"corpus={report.corpus_version} harness={report.harness_version} top_k={report.top_k}")
    header = "metric".ljust(28) + "".join(run.variant.ljust(22) for run in report.runs)
    print(header)
    for key in report.metric_keys:
        row = key.ljust(28)
        for run in report.runs:
            value = run.metrics.get(key)
            row += ("n/a" if value is None else f"{value:.4f}").ljust(22)
        print(row)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline structure-aware evaluation (Feature #15).")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--output", default="structure_eval")
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Include generated_at in the written JSON (off by default for reproducibility).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Replace an existing report of the same name (default: refuse, "
            "evaluation artifacts are append-only)."
        ),
    )
    args = parser.parse_args(argv)

    corpus = corpus_module.build_corpus()
    report = evaluate(corpus, top_k=args.top_k)
    _print_summary(report)
    try:
        path = write_report(
            report, args.output, include_timestamp=args.timestamp, replace=args.replace
        )
    except ArtifactExistsError as error:
        print(f"\n{error}")
        print("Nothing was written. Re-run with --replace to republish deliberately.")
        return 2
    print(f"\nwrote {path.name} to evaluation/reports/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

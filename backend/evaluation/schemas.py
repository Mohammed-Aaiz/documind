"""Shared data structures for the DocuMind evaluation framework.

Research code.  Never imported by production modules and never collected by
pytest (``pytest.ini`` sets ``testpaths = tests``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


class QuestionCategory(str, Enum):
    """Question categories the framework can report on.

    ``MULTIMODAL`` is declared but must not be used until real image/figure/
    table evidence is represented in the corpus — a category with no genuine
    evidence behind it would be a fabricated evaluation.
    """

    DIRECT = "direct_textual"
    SECTION_DEPENDENT = "section_dependent"
    PAGE_CROSS_PAGE = "page_cross_page"
    TABLE_DEPENDENT = "table_dependent"
    MULTI_HOP = "multi_hop"
    CROSS_DOCUMENT = "cross_document"
    MULTIMODAL = "multimodal"


class Baseline(str, Enum):
    """The four retrieval configurations the framework compares."""

    B1_VECTOR_ONLY = "B1_vector_only"
    B2_VECTOR_RERANK = "B2_vector_reranking"
    B3_STRUCTURE_ONLY = "B3_structure_only"
    B4_DUAL_PATH = "B4_dual_path"


class Ablation(str, Enum):
    """Ablation matrix: which components each variant enables."""

    A = "A"  # vector only
    B = "B"  # structure only
    C = "C"  # vector + structure
    D = "D"  # vector + structure + evidence gate


ABLATION_MATRIX: dict[Ablation, dict[str, bool]] = {
    Ablation.A: {"vector": True, "structure": False, "evidence_gate": False},
    Ablation.B: {"vector": False, "structure": True, "evidence_gate": False},
    Ablation.C: {"vector": True, "structure": True, "evidence_gate": False},
    Ablation.D: {"vector": True, "structure": True, "evidence_gate": True},
}


@dataclass(frozen=True)
class EvalQuestion:
    """One labelled evaluation question."""

    question_id: str
    question: str
    category: QuestionCategory
    document_id: str | None = None
    gold_answers: tuple[str, ...] = ()
    gold_chunk_ids: tuple[str, ...] = ()
    answerable: bool = True


@dataclass(frozen=True)
class RetrievalOutcome:
    """What a retrieval configuration returned for one question."""

    chunk_ids: tuple[str, ...]
    scores: tuple[float, ...] = ()
    retrieval_paths: tuple[str, ...] = ()
    structural_hops: tuple[int | None, ...] = ()


@dataclass(frozen=True)
class AnswerOutcome:
    """What the QA stage produced for one question."""

    answer: str
    confidence: float
    insufficient_context: bool
    factual_grounded: bool
    supplied_chunk_ids: tuple[str, ...] = ()


@dataclass
class QuestionResult:
    """Per-question measurement.  Every field is measured, never assumed."""

    question_id: str
    category: QuestionCategory
    answerable: bool
    retrieval: dict[str, float] = field(default_factory=dict)
    qa: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, float] = field(default_factory=dict)
    latency_ms: dict[str, float] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunReport:
    """Aggregate report for one (baseline/ablation) run.

    ``not_measured`` records anything the framework refused to invent, so an
    incomplete run is visibly incomplete rather than silently optimistic.

    ``metrics`` values are ``None`` when a metric's population was empty (for
    example ``unsupported_answer`` with no unanswerable questions); the reason
    is recorded in ``not_measured``.  A value is never silently coerced to
    ``0.0``.
    """

    baseline: str
    ablation: str | None = None
    question_count: int = 0
    metrics: dict[str, float | None] = field(default_factory=dict)
    by_category: dict[str, dict[str, float | None]] = field(default_factory=dict)
    latency_ms: dict[str, float] = field(default_factory=dict)
    results: list[QuestionResult] = field(default_factory=list)
    not_measured: dict[str, str] = field(default_factory=dict)

    def to_dict(self, *, include_detail: bool = False) -> dict[str, Any]:
        """Machine-readable report.

        ``include_detail`` adds the per-question diagnostics the runner
        recorded (:class:`QuestionResult.detail`: expected and predicted
        answers, retrieved/supplied evidence with ranks, outcome and failure
        attribution).  It is **off by default**, so the report format every
        existing consumer reads is unchanged; runs written to a caller-supplied
        output directory opt in.
        """
        results: list[dict[str, Any]] = []
        for r in self.results:
            entry: dict[str, Any] = {
                "question_id": r.question_id,
                "category": r.category.value,
                "answerable": r.answerable,
                "retrieval": r.retrieval,
                "qa": r.qa,
                "evidence": r.evidence,
                "latency_ms": r.latency_ms,
            }
            if include_detail:
                entry["detail"] = r.detail
            results.append(entry)

        return {
            "baseline": self.baseline,
            "ablation": self.ablation,
            "question_count": self.question_count,
            "metrics": self.metrics,
            "by_category": self.by_category,
            "latency_ms": self.latency_ms,
            "not_measured": self.not_measured,
            "includes_per_question_detail": include_detail,
            "results": results,
        }


def mean(values: Sequence[float]) -> float:
    """Mean of ``values``; ``0.0`` for an empty sequence (nothing measured)."""
    seq = [float(v) for v in values]
    if not seq:
        return 0.0
    return sum(seq) / len(seq)

"""Evaluation runner for the structure-aware dual-path retrieval framework.

Design contract
---------------
The runner **measures what it is given and refuses to invent the rest**:

* it never simulates a component.  B2 (vector + reranking) is reported as
  ``not_measured`` unless a real reranker exists — re-scoring with the same
  embedding model would not be a reranker;
* it never fills the ablation table with expected values.  A cell exists only
  after the corresponding run has executed;
* every aggregate is a mean over per-question measurements that are kept in the
  report, so any number can be traced back to the questions that produced it.

Wiring the pipeline is the caller's job: ``retrieve`` and ``answer`` are
injected, which keeps this module independent of the production pipeline while
still measuring it faithfully.
"""

from __future__ import annotations

import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Sequence

from evaluation import qa_metrics, retrieval_metrics
from evaluation.artifacts import ArtifactExistsError, RunOutput, write_evidence
from evaluation.schemas import (
    ABLATION_MATRIX,
    Ablation,
    Baseline,
    EvalQuestion,
    QuestionResult,
    RunReport,
    mean,
)

TOP_K = 5
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

#: Failure attributions produced by :func:`classify_question_outcome`.
#: ``NONE`` means the question was answered correctly.  The remaining values
#: follow the Phase 0 attribution rule: an answer that is wrong while its gold
#: evidence *was* supplied is an answer-stage failure; an answer that is wrong
#: because the gold evidence was never retrieved is a retrieval miss.
FAILURE_NONE = "none"
FAILURE_ANSWER_STAGE = "answer_stage"
FAILURE_RETRIEVAL_MISS = "retrieval_miss"
FAILURE_UNLABELLED = "unlabelled_evidence"
FAILURE_ABSTAINED = "abstained_on_answerable"
FAILURE_UNSUPPORTED = "unsupported_answer"

#: Where a real reranker would live.  Nothing in the project provides one.
RERANKER_MODULE = "embeddings.reranker"

#: Metrics whose denominator is a *population subset*, not the full question
#: set.  ``unsupported_answer`` is only defined over the **unanswerable**
#: questions: averaging its per-question 0/1 indicator over every question would
#: report the fraction of all questions that failed, not the unsupported-answer
#: rate.  This mirrors :func:`evaluation.qa_metrics.unsupported_answer_rate`.
UNANSWERABLE_ONLY_METRICS = frozenset({"unsupported_answer"})

#: Reason recorded when a subset metric's population is empty.  Such a metric is
#: reported as ``None`` (unavailable), never silently as ``0.0``.
_EMPTY_POPULATION_REASONS = {
    "unsupported_answer": "no unanswerable question was measured",
}

#: Retrieval returns an ordered list of chunk ids; answer returns
#: ``{"answer", "confidence", "insufficient_context", "factual_grounded",
#: "supplied_chunk_ids", "retrieval_paths", "structural_hops"}``.
RetrievalFn = Callable[[EvalQuestion], Awaitable[Sequence[str]]]
AnswerFn = Callable[[EvalQuestion, Sequence[str]], Awaitable[dict]]


def reranker_available() -> tuple[bool, str]:
    """Whether a genuine reranker exists in this project.

    Returns ``(available, reason_if_not)``.  B2 is only measurable when this is
    ``True``; otherwise the baseline is recorded as not measured.
    """
    if importlib.util.find_spec(RERANKER_MODULE) is None:
        return False, (
            f"no reranker module at {RERANKER_MODULE}. The project ships no "
            "cross-encoder or reranking model, so results are reported as NOT "
            "MEASURED rather than approximated by re-scoring with the same "
            "bi-encoder."
        )
    return True, ""


def classify_question_outcome(
    *,
    answerable: bool,
    predicted: str,
    expected: Sequence[str],
    insufficient_context: bool,
    has_gold_evidence: bool,
    gold_evidence_supplied: bool,
) -> tuple[str, str]:
    """Return ``(outcome, failure_category)`` for one measured question.

    Pure bookkeeping over values the pipeline already produced — it changes no
    behaviour and infers nothing beyond what was measured.  A question with no
    gold evidence at all is reported as ``unlabelled_evidence`` instead of
    being assigned a cause it cannot support.

    ``unsupported_answer`` mirrors
    :func:`evaluation.qa_metrics.unsupported_answer_rate` exactly (an
    unanswerable question that produced non-empty text and was not flagged
    insufficient), so the per-question label and the aggregate metric can never
    disagree.
    """
    answered = bool((predicted or "").strip())

    if not answerable:
        if answered and not insufficient_context:
            return "unsupported_answer", FAILURE_UNSUPPORTED
        return "correct_abstention", FAILURE_NONE

    if not answered:
        return "abstained", FAILURE_ABSTAINED

    if qa_metrics.exact_match_any(predicted, expected):
        return "correct", FAILURE_NONE

    if gold_evidence_supplied:
        return "incorrect", FAILURE_ANSWER_STAGE
    if has_gold_evidence:
        return "incorrect", FAILURE_RETRIEVAL_MISS
    return "incorrect", FAILURE_UNLABELLED


def _ranks(ids: Sequence[str]) -> dict[str, int]:
    """``{chunk_id: 1-based rank}`` for an ordered, possibly duplicated list."""
    return {chunk_id: rank for rank, chunk_id in enumerate(dict.fromkeys(ids), start=1)}


async def measure_question(
    question: EvalQuestion,
    retrieve: RetrievalFn,
    answer: AnswerFn,
    *,
    top_k: int = TOP_K,
) -> QuestionResult:
    """Measure one question.  All values come from the injected pipeline."""
    start = time.perf_counter()
    chunk_ids = list(await retrieve(question))
    retrieval_ms = (time.perf_counter() - start) * 1000.0

    start = time.perf_counter()
    outcome = await answer(question, chunk_ids)
    answer_ms = (time.perf_counter() - start) * 1000.0

    gold = tuple(question.gold_chunk_ids)
    expected = question.gold_answers or ("",)
    predicted = outcome.get("answer", "") or ""
    supplied = tuple(outcome.get("supplied_chunk_ids", chunk_ids))
    paths = tuple(outcome.get("retrieval_paths", ()))

    retrieval_scores = {
        f"recall@{top_k}": retrieval_metrics.recall_at_k(chunk_ids, gold, top_k),
        f"precision@{top_k}": retrieval_metrics.precision_at_k(chunk_ids, gold, top_k),
        "mrr": retrieval_metrics.reciprocal_rank(chunk_ids, gold),
        f"ndcg@{top_k}": retrieval_metrics.ndcg_at_k(chunk_ids, gold, top_k),
    }

    qa_scores = {
        "exact_match": 1.0 if qa_metrics.exact_match_any(predicted, expected) else 0.0,
        "token_f1": qa_metrics.token_f1_any(predicted, expected),
    }

    evidence_scores = {
        "evidence_coverage": qa_metrics.evidence_coverage(supplied, chunk_ids),
        "path_agreement": qa_metrics.path_agreement(paths),
        "factual_grounded": 1.0 if outcome.get("factual_grounded") else 0.0,
        "unsupported_answer": (
            1.0
            if (
                not question.answerable
                and qa_metrics.normalize_text(predicted)
                and not outcome.get("insufficient_context", False)
            )
            else 0.0
        ),
    }

    insufficient_context = bool(outcome.get("insufficient_context", True))
    gold_supplied = any(chunk_id in gold for chunk_id in supplied)
    evaluation_outcome, failure_category = classify_question_outcome(
        answerable=question.answerable,
        predicted=predicted,
        expected=expected,
        insufficient_context=insufficient_context,
        has_gold_evidence=bool(gold),
        gold_evidence_supplied=gold_supplied,
    )

    return QuestionResult(
        question_id=question.question_id,
        category=question.category,
        answerable=question.answerable,
        retrieval=retrieval_scores,
        qa=qa_scores,
        evidence=evidence_scores,
        latency_ms={"retrieval": retrieval_ms, "total": retrieval_ms + answer_ms},
        detail={
            "retrieved": chunk_ids,
            "supplied": list(supplied),
            "retrieval_paths": list(paths),
            "structural_hops": list(outcome.get("structural_hops", ())),
            "predicted": predicted,
            "expected": list(expected),
            "confidence": float(outcome.get("confidence", 0.0)),
            "insufficient_context": insufficient_context,
            # --- per-question diagnostics (never serialised unless asked for) --
            # Ranks are positions in the *measured* retrieval ranking and in the
            # evidence actually supplied to the answer stage; both come from the
            # injected pipeline, never from an assumption about it.
            "retrieved_ranks": _ranks(chunk_ids),
            "supplied_ranks": _ranks(supplied),
            "gold_retrieved": any(chunk_id in gold for chunk_id in chunk_ids),
            "gold_supplied": gold_supplied,
            "outcome": evaluation_outcome,
            "failure_category": failure_category,
        },
    )


def _aggregate(
    results: Sequence[QuestionResult],
) -> tuple[dict[str, float | None], dict[str, str]]:
    """Mean each metric over its own population.

    ``unsupported_answer`` is averaged over the **unanswerable** questions only
    (see :data:`UNANSWERABLE_ONLY_METRICS`); every other metric keeps its
    existing population.  A metric whose population is empty is reported as
    ``None`` with a reason, never as ``0.0``.
    """
    buckets: dict[str, list[float]] = {}
    present: set[str] = set()
    for result in results:
        for group in (result.retrieval, result.qa, result.evidence):
            for key, value in group.items():
                present.add(key)
                if key in UNANSWERABLE_ONLY_METRICS and result.answerable:
                    continue
                buckets.setdefault(key, []).append(value)

    metrics: dict[str, float | None] = {
        key: mean(values) for key, values in sorted(buckets.items())
    }
    unavailable: dict[str, str] = {}
    for key in sorted(UNANSWERABLE_ONLY_METRICS & present):
        if not buckets.get(key):
            metrics[key] = None
            unavailable[key] = _EMPTY_POPULATION_REASONS[key]
    return metrics, unavailable


def _by_category(
    results: Sequence[QuestionResult],
) -> dict[str, dict[str, float | None]]:
    grouped: dict[str, list[QuestionResult]] = {}
    for result in results:
        grouped.setdefault(result.category.value, []).append(result)
    return {
        name: _aggregate(items)[0] for name, items in sorted(grouped.items())
    }


async def run_baseline(
    baseline: Baseline,
    questions: Sequence[EvalQuestion],
    retrieve: RetrievalFn,
    answer: AnswerFn,
    *,
    ablation: Ablation | None = None,
    top_k: int = TOP_K,
) -> RunReport:
    """Run one labelled configuration over ``questions``.

    Refuses to run B2 without a real reranker, and records why, instead of
    producing a number that would not mean what its label claims.
    """
    report = RunReport(
        baseline=baseline.value,
        ablation=ablation.value if ablation else None,
        question_count=len(questions),
    )

    if baseline is Baseline.B2_VECTOR_RERANK:
        available, reason = reranker_available()
        if not available:
            report.not_measured[baseline.value] = reason
            return report

    results: list[QuestionResult] = []
    for question in questions:
        results.append(
            await measure_question(question, retrieve, answer, top_k=top_k)
        )

    report.results = results
    report.metrics, unavailable = _aggregate(results)
    report.not_measured.update(unavailable)
    report.by_category = _by_category(results)

    retrieval_latencies = [r.latency_ms.get("retrieval", 0.0) for r in results]
    total_latencies = [r.latency_ms.get("total", 0.0) for r in results]
    report.latency_ms = {
        "retrieval_mean": mean(retrieval_latencies),
        "total_mean": mean(total_latencies),
    }
    return report


async def run_ablation(
    build: Callable[[Ablation], tuple[RetrievalFn, AnswerFn]],
    questions: Sequence[EvalQuestion],
    *,
    variants: Sequence[Ablation] = (
        Ablation.A,
        Ablation.B,
        Ablation.C,
        Ablation.D,
    ),
    top_k: int = TOP_K,
) -> dict[str, RunReport]:
    """Run the ablation matrix.

    ``build`` maps each variant to the pipeline that actually implements the
    flag combination in :data:`ABLATION_MATRIX`.  A variant whose components
    cannot be provided must not be included in ``variants`` — the runner will
    not synthesise it.
    """
    reports: dict[str, RunReport] = {}
    for variant in variants:
        retrieve, answer = build(variant)
        reports[variant.value] = await run_baseline(
            Baseline.B4_DUAL_PATH, questions, retrieve, answer, ablation=variant, top_k=top_k
        )
    return reports


def write_report(
    report: RunReport,
    name: str,
    *,
    out_dir: RunOutput | Path | None = None,
    include_detail: bool = False,
    replace: bool = False,
) -> Path:
    """Persist a run report as JSON (machine-readable) plus a markdown summary.

    ``out_dir`` selects where the artifacts go:

    * ``None`` — the recorded research reports (:data:`REPORTS_DIR`), which is
      what existing callers rely on.  This path is **append-only**: it refuses
      to replace a same-named report and raises
      :class:`~evaluation.artifacts.ArtifactExistsError` instead;
    * a :class:`~evaluation.artifacts.RunOutput` — the caller's own directory,
      written through its append-only rules (a name collision raises);
    * a plain path — wrapped in a fresh ``RunOutput``.

    ``include_detail`` adds the per-question diagnostics to the JSON payload
    (see :meth:`evaluation.schemas.RunReport.to_dict`).

    ``replace`` is the explicit opt-in for a *deliberate* re-publication of an
    already recorded report.  It is never the default and never inferred from a
    collision, an environment variable or the presence of an output directory:
    the caller has to ask for the replacement at the call site.  A refusal
    happens before either file is written, so a collision cannot leave a
    report and a stale markdown side by side.
    """
    payload = report.to_dict(include_detail=include_detail)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    lines = [
        f"# Evaluation report — {report.baseline}",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Ablation variant: {report.ablation or 'n/a'}",
        f"- Questions: {report.question_count}",
        "",
    ]
    if report.not_measured:
        lines += ["## Not measured", ""]
        for key, reason in sorted(report.not_measured.items()):
            lines.append(f"- **{key}**: {reason}")
        lines.append("")

    if report.metrics:
        lines += ["## Metrics (measured)", "", "| metric | value |", "|---|---|"]
        for key, value in sorted(report.metrics.items()):
            rendered = "n/a" if value is None else f"{value:.4f}"
            lines.append(f"| {key} | {rendered} |")
        lines.append("")
    else:
        lines += ["## Metrics", "", "No metrics were produced by this run.", ""]

    lines += ["## Latency (ms)", ""]
    for key, value in sorted(report.latency_ms.items()):
        lines.append(f"- {key}: {value:.1f}")
    lines.append("")

    if out_dir is None:
        # Historical path: the recorded research reports, now append-only.  A
        # re-run no longer replaces a same-named report silently — the write
        # goes through evaluation.artifacts.write_evidence, which uses an
        # exclusive create.  A caller that deliberately wants to re-publish
        # passes replace=True; it is never inferred.
        json_path = REPORTS_DIR / f"{name}.json"
        md_path = REPORTS_DIR / f"{name}.md"
        if not replace:
            # Check the whole pair first: refusing only at the second write
            # would leave a fresh .json next to the previous run's .md.
            existing = [
                str(target) for target in (json_path, md_path) if target.exists()
            ]
            if existing:
                raise ArtifactExistsError(
                    "refusing to replace existing evaluation evidence: "
                    + ", ".join(existing)
                    + ". Recorded reports are append-only — write to a new name, "
                    "or pass replace=True for a deliberate re-publication."
                )
        json_path = write_evidence(
            json_path,
            json.dumps(payload, indent=2, sort_keys=True),
            replace=replace,
        )
        write_evidence(md_path, "\n".join(lines), replace=replace)
        return json_path

    output = out_dir if isinstance(out_dir, RunOutput) else RunOutput(out_dir)
    json_name, md_name = f"{name}.json", f"{name}.md"
    unreserved = [
        candidate
        for candidate in (json_name, md_name)
        if output.path(candidate) not in output.reserved
    ]
    if unreserved:
        output.reserve(*unreserved)

    output.write_json(json_name, payload, reserved=True)
    output.write_text(md_name, "\n".join(lines), reserved=True)
    return output.path(json_name)

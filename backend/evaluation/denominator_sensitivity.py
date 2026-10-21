"""Denominator sensitivity analysis (research-only, re-aggregation).

Purpose
-------
The production-aligned A–D runner (``experiments/run_dual_path_ablation.py`` via
:mod:`evaluation.runner`) aggregates every metric over **all** measured
questions.  The repository's earlier runners (``run_phase3d_evaluation.py``,
``run_phase3f_evaluation.py``, ``run_phase4b_evaluation.py``) instead aggregate
retrieval, answer and evidence metrics over the **answerable** population and
unsupported-answer behaviour over the **unanswerable** population.

This module answers a single, narrow question **without re-running any
experiment**: how much do the reported numbers move when the established
per-metric populations are applied?  It consumes the frozen per-question results
already written to ``evaluation/reports/ablation_*.json`` /
``ablation_heading_*.json`` and re-aggregates them.

It is a **sensitivity analysis**, not a replacement: the production-aligned
A/B/C/D reports are never modified, and no production module is imported — the
only repository import is the shared evaluation artifact writer
(:func:`evaluation.artifacts.write_evidence`).

Population definitions (from actual repository contracts, not intuition)
-----------------------------------------------------------------------
* **gold-bearing questions** — questions that carry gold retrieval evidence.
  In these corpora that is exactly the answerable set: ``run_dual_path_ablation.
  build_questions`` gives every unanswerable question ``gold_chunk_ids=()`` and
  every labelled question its evidence-derived chunk ids, and each
  ``*_config.json`` records ``withGoldChunks == answerable`` (39/39 phase3d,
  20/20 heading).  Retrieval metrics use this population.
* **answerable questions** — the answer-quality population.  ``qa_metrics.
  answer_accuracy`` documents the answerable population; the earlier runners use
  it for EM/token-F1 and ``evidence_coverage``.
* **unanswerable questions** — the unsupported-answer population.  Already
  implemented correctly by :func:`evaluation.qa_metrics.unsupported_answer_rate`
  and ``runner.UNANSWERABLE_ONLY_METRICS``.

Anything without a documented alternate population is reported as
``not_applicable`` with a reason rather than given an invented value.

Deterministic and path-free by default: two runs over the same reports produce
byte-identical output (add ``--timestamp`` to opt into a wall-clock field).

Append-only by default: an existing ``<name>.json`` / ``<name>.md`` is refused
rather than replaced, so a re-run cannot quietly discard a recorded analysis.
Pass ``--replace`` to republish the same name deliberately.

Run explicitly, from ``backend/``:

    ./venv/Scripts/python.exe evaluation/denominator_sensitivity.py
    ./venv/Scripts/python.exe evaluation/denominator_sensitivity.py --corpus heading
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

# This module is also run as a file (``python evaluation/denominator_sensitivity.py``),
# which puts only ``evaluation/`` on ``sys.path``.  The backend package root is
# added explicitly so the shared evaluation artifact writer is importable either
# way (the same bootstrap ``structure_eval.py`` uses).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from evaluation.artifacts import ArtifactExistsError, write_evidence  # noqa: E402

ANALYSIS_VERSION = "denominator-sensitivity-v1"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_OUTPUT = "denominator_sensitivity"

#: Corpus → report filename prefix (the production-aligned runner's convention).
CORPORA: dict[str, str] = {"phase3d": "ablation", "heading": "ablation_heading"}
VARIANTS: tuple[str, ...] = ("A", "B", "C", "D")

POPULATION_ALL = "all measured questions"
POPULATION_GOLD = "gold-bearing questions"
POPULATION_ANSWERABLE = "answerable questions"
POPULATION_UNANSWERABLE = "unanswerable questions"

#: (metric, group, population-predicate kind, population label, contract source)
RETRIEVAL_METRICS: tuple[str, ...] = ("recall@5", "precision@5", "mrr", "ndcg@5")
ANSWER_METRICS: tuple[str, ...] = ("exact_match", "token_f1")
EVIDENCE_METRICS: tuple[str, ...] = ("evidence_coverage",)

_RETRIEVAL_SOURCE = (
    "run_phase3d/3f/4b aggregate retrieval over the answerable population; in "
    "these corpora answerable == gold-bearing (run_dual_path_ablation gives every "
    "unanswerable question gold_chunk_ids=(), and *_config.json records "
    "withGoldChunks == answerable)."
)
_ANSWER_SOURCE = (
    "qa_metrics.answer_accuracy documents the answerable population; "
    "run_phase3d/3f/4b aggregate EM/token-F1 over the answerable population."
)
_EVIDENCE_SOURCE = (
    "run_phase3d/3f/4b aggregate evidence_coverage over the answerable population."
)

#: Metrics with no documented alternate population (or not recoverable from the
#: frozen reports).  Reported as ``not_applicable`` with a reason, never invented.
NOT_APPLICABLE: dict[str, str] = {
    "factual_grounded": (
        "An alternate population is documented (answered questions, per "
        "qa_metrics.factual_grounding_rate), but per-question answered-ness is not "
        "present in the frozen production-aligned reports (their to_dict omits "
        "detail.predicted/insufficient_context). Recomputing it would require "
        "re-running the experiment or changing the frozen report schema, so no "
        "sensitivity value is produced here."
    ),
    "path_agreement": (
        "No alternate population is documented; path_agreement is a per-question "
        "binary property of the retrieved source paths that is defined for every "
        "question regardless of answerability, so there is no population to switch."
    ),
}


def _gold_bearing(result: dict) -> bool:
    """A question that carries gold retrieval evidence (== answerable here)."""
    return bool(result.get("answerable", True))


def _answerable(result: dict) -> bool:
    return bool(result.get("answerable", True))


def _unanswerable(result: dict) -> bool:
    return not bool(result.get("answerable", True))


def _mean(values: Sequence[float]) -> float | None:
    """Mean, or ``None`` for an empty population (unavailable, never ``0.0``)."""
    seq = [float(v) for v in values]
    if not seq:
        return None
    return sum(seq) / len(seq)


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _record(
    corpus: str,
    variant: str,
    metric: str,
    group: str,
    results: Sequence[dict],
    current_metrics: dict,
    predicate: Callable[[dict], bool],
    population_label: str,
    source: str,
) -> dict[str, Any]:
    """Build one current-vs-sensitivity record for a metric."""
    current = current_metrics.get(metric)
    population = [r for r in results if predicate(r)]
    sensitivity = _mean([r.get(group, {}).get(metric) for r in population if metric in r.get(group, {})])
    delta = (
        None
        if current is None or sensitivity is None
        else float(sensitivity) - float(current)
    )
    return {
        "corpus": corpus,
        "variant": variant,
        "metric": metric,
        "status": "measured",
        "current": {
            "value": _round(current),
            "population": POPULATION_ALL,
            "n": len(results),
        },
        "sensitivity": {
            "value": _round(sensitivity),
            "population": population_label,
            "n": len(population),
        },
        "delta": _round(delta),
        "excluded_questions": len(results) - len(population),
        "population_source": source,
    }


def _unsupported_confirmation(
    corpus: str, variant: str, results: Sequence[dict], current_metrics: dict
) -> dict[str, Any]:
    """Confirm (not recompute) the corrected unanswerable-population metric."""
    unanswerable = [r for r in results if _unanswerable(r)]
    failures = sum(
        1 for r in unanswerable if r.get("evidence", {}).get("unsupported_answer") == 1.0
    )
    n = len(unanswerable)
    return {
        "corpus": corpus,
        "variant": variant,
        "metric": "unsupported_answer",
        "status": "confirmed",
        "reported_value": _round(current_metrics.get("unsupported_answer")),
        "failures": failures,
        "population": n,
        "human_readable": f"{failures}/{n}",
        "expected_denominator": n,
        "denominator_correct": n > 0 and (
            current_metrics.get("unsupported_answer") is None
            or abs(float(current_metrics["unsupported_answer"]) - failures / n) < 1e-9
        ),
    }


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def analyze_corpus(
    reports_dir: Path, corpus: str, prefix: str, variants: Sequence[str] = VARIANTS
) -> dict[str, Any]:
    """Re-aggregate one corpus' frozen per-question results by population."""
    variants_out: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    not_applicable: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []

    for variant in variants:
        report_path = reports_dir / f"{prefix}_{variant}.json"
        report = load_report(report_path)
        results = list(report.get("results", []))
        metrics = dict(report.get("metrics", {}))

        n_answerable = sum(1 for r in results if _answerable(r))
        counts = {
            "all": len(results),
            "gold_bearing": sum(1 for r in results if _gold_bearing(r)),
            "answerable": n_answerable,
            "unanswerable": len(results) - n_answerable,
        }

        variant_records: list[dict[str, Any]] = []
        for metric in RETRIEVAL_METRICS:
            variant_records.append(
                _record(corpus, variant, metric, "retrieval", results, metrics,
                        _gold_bearing, POPULATION_GOLD, _RETRIEVAL_SOURCE)
            )
        for metric in ANSWER_METRICS:
            variant_records.append(
                _record(corpus, variant, metric, "qa", results, metrics,
                        _answerable, POPULATION_ANSWERABLE, _ANSWER_SOURCE)
            )
        for metric in EVIDENCE_METRICS:
            variant_records.append(
                _record(corpus, variant, metric, "evidence", results, metrics,
                        _answerable, POPULATION_ANSWERABLE, _EVIDENCE_SOURCE)
            )
        for metric, reason in NOT_APPLICABLE.items():
            not_applicable.append({
                "corpus": corpus,
                "variant": variant,
                "metric": metric,
                "status": "not_applicable",
                "reason": reason,
            })

        records.extend(variant_records)
        unsupported.append(_unsupported_confirmation(corpus, variant, results, metrics))

        variants_out[variant] = {
            "questionCount": len(results),
            "populations": counts,
            "sourceReport": report_path.name,
            "metrics": {r["metric"]: r for r in variant_records},
        }

    return {
        "corpus": corpus,
        "variants": variants_out,
        "records": records,
        "notApplicable": not_applicable,
        "unsupportedAnswerConfirmation": unsupported,
    }


def analyze(
    reports_dir: Path = REPORTS_DIR, corpora: Sequence[str] | None = None
) -> dict[str, Any]:
    """Analyze all requested corpora from the frozen production-aligned reports."""
    names = tuple(corpora) if corpora else tuple(CORPORA)
    per_corpus = {
        name: analyze_corpus(reports_dir, name, CORPORA[name]) for name in names
    }
    records = [r for c in per_corpus.values() for r in c["records"]]
    not_applicable = [r for c in per_corpus.values() for r in c["notApplicable"]]
    unsupported = [
        r for c in per_corpus.values() for r in c["unsupportedAnswerConfirmation"]
    ]
    return {
        "analysis": "denominator-sensitivity",
        "analysisVersion": ANALYSIS_VERSION,
        "nature": "re-aggregation of frozen production-aligned per-question results; "
                  "no experiment was re-run and no report was modified",
        "sourceReports": sorted(
            f"{CORPORA[name]}_{v}.json" for name in names for v in VARIANTS
        ),
        "populationDefinitions": {
            POPULATION_ALL: "every measured question (existing runner _aggregate)",
            POPULATION_GOLD: "questions carrying gold retrieval evidence; == answerable here",
            POPULATION_ANSWERABLE: "questions the corpus marks answerable",
            POPULATION_UNANSWERABLE: "questions the corpus marks unanswerable",
        },
        "corpora": per_corpus,
        "records": records,
        "notApplicable": not_applicable,
        "unsupportedAnswerConfirmation": unsupported,
    }


def _f(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Denominator sensitivity analysis",
        "",
        f"- Analysis version: {payload['analysisVersion']}",
        "- Nature: re-aggregation of frozen production-aligned per-question results; "
        "no experiment was re-run and no production-aligned report was modified.",
        "",
        "## 1. Purpose",
        "",
        "The production-aligned A–D runner aggregates every metric over **all** "
        "measured questions. The repository's earlier runners aggregate retrieval, "
        "answer and evidence metrics over the **answerable** population. This "
        "analysis quantifies how much the reported numbers move under those "
        "established populations. It is a **sensitivity analysis**, not a "
        "replacement for the production-aligned evaluation.",
        "",
        "## 2. Population definitions",
        "",
        "| population | definition | source |",
        "|---|---|---|",
        "| all measured questions | every question in the run (current runner) | `runner._aggregate` |",
        "| gold-bearing questions | carry gold retrieval evidence; == answerable here | `run_phase3d/3f/4b`; corpus contract |",
        "| answerable questions | corpus marks the question answerable | `qa_metrics.answer_accuracy`; earlier runners |",
        "| unanswerable questions | corpus marks the question unanswerable | `qa_metrics.unsupported_answer_rate`; `runner.UNANSWERABLE_ONLY_METRICS` |",
        "",
    ]

    for index, (name, corpus) in enumerate(payload["corpora"].items(), start=3):
        lines += [f"## {index}. {name} table", ""]
        for variant, info in corpus["variants"].items():
            p = info["populations"]
            lines += [
                f"### Variant {variant}",
                "",
                f"- source: `{info['sourceReport']}`",
                f"- populations: all={p['all']}, gold-bearing={p['gold_bearing']}, "
                f"answerable={p['answerable']}, unanswerable={p['unanswerable']}",
                "",
                "| metric | current (all) | sensitivity | population | Δ | excluded |",
                "|---|---|---|---|---|---|",
            ]
            for metric, rec in info["metrics"].items():
                cur = rec["current"]
                sens = rec["sensitivity"]
                lines.append(
                    f"| {metric} | {_f(cur['value'])} | {_f(sens['value'])} "
                    f"| {sens['population']} ({sens['n']}) "
                    f"| {_f(rec['delta'])} | {rec['excluded_questions']} |"
                )
            lines.append("")

    lines += [
        f"## {3 + len(payload['corpora'])}. Unsupported-answer confirmation",
        "",
        "`unsupported_answer` is already population-correct (unanswerable denominator); "
        "this is a confirmation, not a new methodology.",
        "",
        "| corpus | variant | reported | human-readable | denominator correct |",
        "|---|---|---|---|---|",
    ]
    for rec in payload["unsupportedAnswerConfirmation"]:
        lines.append(
            f"| {rec['corpus']} | {rec['variant']} | {_f(rec['reported_value'])} "
            f"| {rec['human_readable']} | {rec['denominator_correct']} |"
        )
    lines.append("")

    lines += [
        "### Not applicable (no documented alternate population)",
        "",
        "| corpus | variant | metric | reason |",
        "|---|---|---|---|",
    ]
    for rec in payload["notApplicable"]:
        lines.append(
            f"| {rec['corpus']} | {rec['variant']} | {rec['metric']} | {rec['reason']} |"
        )
    lines.append("")

    n = 4 + len(payload["corpora"])
    lines += [
        f"## {n}. Interpretation",
        "",
        "Excluding the unanswerable questions raises the retrieval and answer "
        "metrics for both corpora; the magnitude is shown per variant above. The "
        "production-aligned (all-question) numbers remain the historical/current "
        "measurement; the contract-aligned values are a sensitivity view. No "
        "statistical significance or causal improvement is claimed.",
        "",
        f"## {n + 1}. Limitations",
        "",
        "- Re-aggregation only: it cannot correct the experiment design, only the "
        "denominator of the recorded per-question values.",
        "- Gold-bearing is equated with answerable for these corpora from the "
        "documented corpus contract; a corpus where answerable questions lack gold "
        "would need a different observable.",
        "- `factual_grounded` and `path_agreement` have no computable alternate "
        "population from the frozen reports (see the not-applicable table).",
        "",
        f"## {n + 2}. Recommendation",
        "",
        "Adopt the contract-aligned populations (retrieval/evidence → gold-bearing/"
        "answerable; answer → answerable; unsupported → unanswerable) as the "
        "default in a future evaluation revision, and report the all-question view "
        "only as an explicit sensitivity, so the historical and contract-aligned "
        "numbers are never confused.",
        "",
    ]
    return "\n".join(lines)


def write_report(
    payload: dict[str, Any],
    name: str = DEFAULT_OUTPUT,
    *,
    timestamp: bool = False,
    replace: bool = False,
) -> Path:
    """Write ``<name>.json`` + ``<name>.md``; deterministic unless ``timestamp``.

    Both destinations are checked BEFORE either is written, so a refused
    republication cannot leave half a report behind.  ``replace=True`` is the
    explicit, visible opt-in for a deliberate re-publication — this module's own
    determinism comparison writes the same name twice on purpose — and it is
    never inferred from the environment or from a previous write.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(payload)
    if timestamp:
        from datetime import datetime, timezone

        out["generated_at"] = datetime.now(timezone.utc).isoformat()

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

    write_evidence(
        json_path, json.dumps(out, indent=2, sort_keys=True), replace=replace
    )
    write_evidence(md_path, _render_markdown(out), replace=replace)
    return json_path


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--corpus",
        choices=[*CORPORA, "all"],
        default="all",
        help="corpus to analyze (default: all)",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="output basename")
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="include generated_at in the written JSON (off by default for reproducibility)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "replace an existing report of the same name (default: refuse, "
            "evaluation artifacts are append-only)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    corpora = None if args.corpus == "all" else [args.corpus]
    payload = analyze(REPORTS_DIR, corpora)

    for corpus in payload["corpora"].values():
        for variant, info in corpus["variants"].items():
            p = info["populations"]
            print(f"{corpus['corpus']:9s} {variant}  all={p['all']} "
                  f"gold={p['gold_bearing']} answerable={p['answerable']} "
                  f"unanswerable={p['unanswerable']}")

    try:
        path = write_report(
            payload, args.output, timestamp=args.timestamp, replace=args.replace
        )
    except ArtifactExistsError as error:
        print(f"\n{error}")
        print("Nothing was written. Re-run with --replace to republish deliberately.")
        return 2
    print(f"\nwrote evaluation/reports/{path.name} and {args.output}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

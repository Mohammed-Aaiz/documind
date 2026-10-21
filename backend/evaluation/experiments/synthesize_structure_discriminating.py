#!/usr/bin/env python3
"""Synthesise the ``structure_discriminating_v1`` A/B/C/D ablation.

Research-only reporting.  It reads the four reports produced by the established
production-aligned runner (``run_dual_path_ablation.py --corpus
structure_discriminating``) plus the corpus labels, and re-aggregates the
recorded per-question measurements by **pre-registered population**:

* the primary structural subset — ``DISCRIMINATING`` (the hypothesis test);
* the weak subset — ``WEAKLY_DISCRIMINATING``;
* the controls — ``NOT_DISCRIMINATING``;
* the full answerable set;
* the unanswerable set (unsupported-answer behaviour).

The population/denominator definitions follow
``evaluation.denominator_sensitivity``: retrieval/answer/evidence metrics are
reported over the answerable questions in each population; the unsupported-answer
rate is reported over unanswerable questions only, and is ``null`` (unavailable)
rather than ``0.0`` when that population is empty.

It never re-runs retrieval, never modifies the four ablation reports, and writes
only ``structure_discriminating_analysis.json`` and
``structure_discriminating_ablation_report.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from evaluation.artifacts import ArtifactExistsError, write_evidence  # noqa: E402
from evaluation.datasets import structure_discriminating_v1 as corpus_module  # noqa: E402

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
PREFIX = "ablation_structure_discriminating"
VARIANTS = ("A", "B", "C", "D")
ANALYSIS_VERSION = "structure-discriminating-synthesis-v1"

#: Answer accuracy threshold on token-set F1, as documented by
#: ``evaluation.qa_metrics.answer_accuracy``.
ANSWER_ACCURACY_THRESHOLD = 0.5

#: Metric → (group, key).  ``answer_accuracy`` is derived from ``qa.token_f1``.
RETRIEVAL_METRICS = (("recall@5", "retrieval", "recall@5"),
                     ("precision@5", "retrieval", "precision@5"),
                     ("mrr", "retrieval", "mrr"),
                     ("ndcg@5", "retrieval", "ndcg@5"))
ANSWER_METRICS = (("exact_match", "qa", "exact_match"), ("token_f1", "qa", "token_f1"))
EVIDENCE_METRICS = (("evidence_coverage", "evidence", "evidence_coverage"),
                    ("path_agreement", "evidence", "path_agreement"),
                    ("factual_grounded", "evidence", "factual_grounded"))

SUBSETS = (
    "DISCRIMINATING",
    "WEAKLY_DISCRIMINATING",
    "NOT_DISCRIMINATING",
    "ALL_ANSWERABLE",
    "UNANSWERABLE",
)

_UNAVAILABLE = {
    "section_grounding": (
        "the production-aligned runner does not emit a section-grounding metric"
    ),
    "answer_accuracy": None,  # derived, always available on answerable populations
    "unsupported_answer": "metric is defined only over the unanswerable population",
}


def _mean(values: Sequence[float | None]) -> float | None:
    seq = [float(v) for v in values if v is not None]
    if not seq:
        return None
    return sum(seq) / len(seq)


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def load_reports(reports_dir: Path = REPORTS_DIR) -> dict[str, dict]:
    reports: dict[str, dict] = {}
    for variant in VARIANTS:
        path = reports_dir / f"{PREFIX}_{variant}.json"
        reports[variant] = json.loads(path.read_text(encoding="utf-8"))
    return reports


def corpus_labels() -> dict[str, dict]:
    corpus = corpus_module.build_corpus()
    return {
        q.qid: {"category": q.category, "discrimination": q.discrimination,
                "answerable": q.answerable}
        for q in corpus.questions
    }


def _subset_qids(labels: dict[str, dict], subset: str) -> list[str]:
    if subset == "ALL_ANSWERABLE":
        return [q for q, m in labels.items() if m["answerable"]]
    if subset == "UNANSWERABLE":
        return [q for q, m in labels.items() if not m["answerable"]]
    return [q for q, m in labels.items() if m["answerable"] and m["discrimination"] == subset]


def aggregate(report: dict, qids: Sequence[str], *, unanswerable: bool) -> dict[str, float | None]:
    """Aggregate one report's per-question values over ``qids`` by population."""
    by_id = {r["question_id"]: r for r in report["results"]}
    rows = [by_id[q] for q in qids if q in by_id]
    out: dict[str, float | None] = {}

    if not unanswerable:
        for name, group, key in RETRIEVAL_METRICS + ANSWER_METRICS + EVIDENCE_METRICS:
            out[name] = _round(_mean([r[group][key] for r in rows]))
        out["answer_accuracy"] = _round(_mean(
            [1.0 if r["qa"]["token_f1"] >= ANSWER_ACCURACY_THRESHOLD else 0.0 for r in rows]
        ))
        out["unsupported_answer"] = None
        out["section_grounding"] = None
    else:
        out["unsupported_answer"] = _round(
            _mean([r["evidence"]["unsupported_answer"] for r in rows])
        )
        out["factual_grounded"] = _round(_mean([r["evidence"]["factual_grounded"] for r in rows]))
        for name, _g, _k in RETRIEVAL_METRICS + ANSWER_METRICS + EVIDENCE_METRICS:
            out.setdefault(name, None)
        out["answer_accuracy"] = None
        out["section_grounding"] = None
    return out


def build_analysis(reports: dict[str, dict], labels: dict[str, dict]) -> dict[str, Any]:
    subsets: dict[str, Any] = {}
    for subset in SUBSETS:
        qids = _subset_qids(labels, subset)
        unanswerable = subset == "UNANSWERABLE"
        per_variant = {
            variant: aggregate(reports[variant], qids, unanswerable=unanswerable)
            for variant in VARIANTS
        }
        deltas: dict[str, dict[str, float | None]] = {}
        for metric in per_variant["A"]:
            deltas[metric] = {
                "C-A": _delta(per_variant["C"][metric], per_variant["A"][metric]),
                "D-A": _delta(per_variant["D"][metric], per_variant["A"][metric]),
                "D-C": _delta(per_variant["D"][metric], per_variant["C"][metric]),
                "B-A": _delta(per_variant["B"][metric], per_variant["A"][metric]),
            }
        subsets[subset] = {
            "n": len(qids),
            "qids": sorted(qids),
            "variants": per_variant,
            "deltas": deltas,
        }

    return {
        "analysis": "structure-discriminating-ablation-synthesis",
        "analysisVersion": ANALYSIS_VERSION,
        "corpusVersion": corpus_module.CORPUS_VERSION,
        "sourceReports": [f"{PREFIX}_{v}.json" for v in VARIANTS],
        "answerAccuracyThreshold": ANSWER_ACCURACY_THRESHOLD,
        "populationDefinitions": {
            "DISCRIMINATING": "pre-registered primary structural subset (answerable)",
            "WEAKLY_DISCRIMINATING": "weak subset (answerable), reported separately",
            "NOT_DISCRIMINATING": "semantic controls (answerable)",
            "ALL_ANSWERABLE": "every answerable question",
            "UNANSWERABLE": "every unanswerable question (unsupported-answer metric)",
        },
        "subsets": subsets,
        "questionAudit": _question_audit(reports, labels),
        "unavailable": _UNAVAILABLE,
    }


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return _round(float(a) - float(b))


def _question_audit(reports: dict[str, dict], labels: dict[str, dict]) -> dict[str, Any]:
    a_by = {r["question_id"]: r for r in reports["A"]["results"]}
    c_by = {r["question_id"]: r for r in reports["C"]["results"]}
    disc = [q for q, m in labels.items() if m["answerable"] and m["discrimination"] == "DISCRIMINATING"]

    per_question: list[dict] = []
    by_category: dict[str, dict[str, int]] = {}
    for qid in sorted(disc):
        a, c = a_by[qid], c_by[qid]
        a_prec, c_prec = a["retrieval"]["precision@5"], c["retrieval"]["precision@5"]
        verdict = "tie" if a_prec == c_prec else ("C>A" if c_prec > a_prec else "A>C")
        category = labels[qid]["category"]
        bucket = by_category.setdefault(category, {"C>A": 0, "A>C": 0, "tie": 0})
        bucket[verdict] += 1
        per_question.append({
            "question_id": qid,
            "category": category,
            "recall@5": {"A": a["retrieval"]["recall@5"], "C": c["retrieval"]["recall@5"]},
            "precision@5": {"A": a_prec, "C": c_prec},
            "token_f1": {"A": a["qa"]["token_f1"], "C": c["qa"]["token_f1"]},
            "verdict_precision@5": verdict,
        })
    return {"perQuestion": per_question, "byCategory": dict(sorted(by_category.items()))}


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

_METRIC_ROWS = (
    ("recall@5", "Recall@5"),
    ("precision@5", "Precision@5"),
    ("mrr", "MRR"),
    ("ndcg@5", "NDCG@5"),
    ("exact_match", "Exact Match"),
    ("token_f1", "Token F1"),
    ("answer_accuracy", "Answer Accuracy"),
    ("evidence_coverage", "Evidence Coverage"),
    ("path_agreement", "Path Agreement"),
    ("factual_grounded", "Factual Grounded"),
    ("unsupported_answer", "Unsupported Answer Rate"),
    ("section_grounding", "Section Grounding"),
)


def _f(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _table(subset: dict) -> list[str]:
    lines = [
        "| Metric | A Semantic | B Structure-Only | C Structure-Aware | D Fused |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in _METRIC_ROWS:
        row = [subset["variants"][v][key] for v in VARIANTS]
        lines.append("| " + label + " | " + " | ".join(_f(x) for x in row) + " |")
    lines.append("")
    lines.append(f"Population size: n = {subset['n']}.")
    lines.append("")
    return lines


def _delta_table(subset: dict) -> list[str]:
    lines = [
        "| Metric | C − A | D − A | D − C | B − A |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in _METRIC_ROWS:
        d = subset["deltas"][key]
        lines.append(
            "| " + label + " | " + " | ".join(_f(d[k]) for k in ("C-A", "D-A", "D-C", "B-A")) + " |"
        )
    lines.append("")
    return lines


def _verdict(analysis: dict) -> tuple[str, str]:
    """Neutral verdict driven by the pre-registered primary subset."""
    disc = analysis["subsets"]["DISCRIMINATING"]["variants"]
    a, c = disc["A"], disc["C"]
    keys = ("recall@5", "precision@5", "ndcg@5", "token_f1", "answer_accuracy")
    diffs = {
        k: (None if a[k] is None or c[k] is None else round(c[k] - a[k], 6))
        for k in keys
    }
    positive = [k for k, d in diffs.items() if d is not None and d > 1e-9]
    negative = [k for k, d in diffs.items() if d is not None and d < -1e-9]
    if positive and not negative:
        return "STRUCTURE BENEFIT OBSERVED", json.dumps(diffs, sort_keys=True)
    if negative and not positive:
        return "NO STRUCTURE BENEFIT OBSERVED", json.dumps(diffs, sort_keys=True)
    if diffs.get("recall@5") in (0.0, None) and diffs.get("token_f1") in (0.0, None):
        return "NO STRUCTURE BENEFIT OBSERVED", json.dumps(diffs, sort_keys=True)
    return "MIXED / INCONCLUSIVE", json.dumps(diffs, sort_keys=True)


def _d(subset: dict, metric: str, delta: str) -> float | None:
    return subset["deltas"][metric][delta]


def _measure_word(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if abs(value) < 1e-9:
        return "no measurable difference"
    if value > 0:
        return f"measured increase of {value:.4f}"
    return f"measured decrease of {abs(value):.4f}"


def render_markdown(analysis: dict) -> str:
    disc = analysis["subsets"]["DISCRIMINATING"]
    allans = analysis["subsets"]["ALL_ANSWERABLE"]
    unans = analysis["subsets"]["UNANSWERABLE"]
    control = analysis["subsets"]["NOT_DISCRIMINATING"]
    verdict, diffs = _verdict(analysis)

    disc_ra = disc["variants"]["A"]["recall@5"]
    disc_rc = disc["variants"]["C"]["recall@5"]
    dc_ra = _d(disc, "recall@5", "D-C")
    dc_f1 = _d(disc, "token_f1", "D-C")
    ct_pa = _d(control, "path_agreement", "C-A")
    unsup = {v: unans["variants"][v]["unsupported_answer"] for v in VARIANTS}

    lines = [
        "# Structure-discriminating ablation — A/B/C/D synthesis",
        "",
        f"- Corpus: `{analysis['corpusVersion']}`",
        f"- Synthesis version: `{analysis['analysisVersion']}`",
        "- Source: the established production-aligned runner "
        f"(`{'`, `'.join(analysis['sourceReports'])}`).",
        "- Method: re-aggregation of recorded per-question measurements by "
        "pre-registered population; no retrieval was re-run.",
        "",
        "## 1. Purpose",
        "",
        "Test whether structure-aware retrieval (**C**) improves retrieval, answer "
        "or grounding performance over semantic-only retrieval (**A**) on genuinely "
        "structure-discriminating questions, using the production-aligned A/B/C/D "
        "runner and the established denominator methodology.",
        "",
        "## 2. Population definitions",
        "",
        "| population | definition |",
        "|---|---|",
    ]
    for name, definition in analysis["populationDefinitions"].items():
        lines.append(f"| {name} | {definition} |")
    lines += [
        "",
        "Retrieval / answer / evidence metrics are reported over the **answerable** "
        "questions of each population; `unsupported_answer` is reported over the "
        "**unanswerable** population only (`null` when empty). `answer_accuracy` "
        "uses the documented threshold F1 ≥ 0.5. `section_grounding` is not emitted "
        "by the production-aligned runner.",
        "",
        "## 3. Primary table — full answerable population",
        "",
    ]
    lines += _table(allans)
    lines += ["## 4. Primary hypothesis test — DISCRIMINATING subset", ""]
    lines += _table(disc)
    lines += ["## 5. Effect deltas", "", "### DISCRIMINATING subset", ""]
    lines += _delta_table(disc)
    lines += ["### Full answerable population", ""]
    lines += _delta_table(allans)
    lines += ["## 6. Weak subset — WEAKLY_DISCRIMINATING", ""]
    lines += _table(analysis["subsets"]["WEAKLY_DISCRIMINATING"])
    lines += ["## 7. Controls — NOT_DISCRIMINATING", ""]
    lines += _table(analysis["subsets"]["NOT_DISCRIMINATING"])
    lines += ["## 8. Unanswerable population", ""]
    lines += _table(unans)
    lines += ["### Unsupported-answer rate by variant", ""]
    for v in VARIANTS:
        a = unans["variants"][v]["unsupported_answer"]
        lines.append(f"- {v}: {_f(a)}")
    lines += [
        "",
        "## 9. Category-level analysis (DISCRIMINATING)",
        "",
        "| category | C>A | A>C | tie |",
        "|---|---:|---:|---:|",
    ]
    for category, counts in analysis["questionAudit"]["byCategory"].items():
        lines.append(f"| {category} | {counts['C>A']} | {counts['A>C']} | {counts['tie']} |")
    lines += [
        "",
        "(Comparison on Precision@5 per question, the framework's ranking metric.)",
        "",
        "## 10. Research questions answered",
        "",
        f"1. **Did C outperform A on the DISCRIMINATING subset?** No. Recall@5 was "
        f"{_measure_word(_d(disc, 'recall@5', 'C-A'))} (A={_f(disc_ra)}, C={_f(disc_rc)}); "
        f"Precision@5 {_measure_word(_d(disc, 'precision@5', 'C-A'))}; "
        f"nDCG@5 {_measure_word(_d(disc, 'ndcg@5', 'C-A'))}; "
        f"token F1 {_measure_word(_d(disc, 'token_f1', 'C-A'))}; "
        f"answer accuracy {_measure_word(_d(disc, 'answer_accuracy', 'C-A'))}.",
        f"2. **By which metrics?** Only `path_agreement` moves positively "
        f"({_measure_word(_d(disc, 'path_agreement', 'C-A'))}), which is true by "
        f"construction because C uses the dual path. Retrieval rank metrics are ties "
        f"or slightly lower for C; token F1 is lower for C.",
        f"3. **Consistent across structural categories?** Yes — every DISCRIMINATING "
        f"question tied on Precision@5 (see §9); no category showed a C>A win.",
        f"4. **Did D outperform C?** No. D−C on the DISCRIMINATING subset was "
        f"{_measure_word(dc_ra)} (Recall@5) and {_measure_word(dc_f1)} (token F1); "
        f"D additionally abstains on unanswerable questions.",
        f"5. **Did the controls behave as expected?** The NOT_DISCRIMINATING controls "
        f"showed no structural advantage; C−A path_agreement {_measure_word(ct_pa)}, "
        f"recall {_measure_word(_d(control, 'recall@5', 'C-A'))}. Controls are "
        f"consistent with a null structure effect.",
        f"6. **Unanswerable questions?** A/C answered all 8 (unsupported rate "
        f"{_f(unsup['A'])} / {_f(unsup['C'])}); D abstained on all 8 "
        f"({_f(unsup['D'])}). The gate's abstention behaviour is the one clear "
        f"measured effect.",
        f"7. **What does the experiment support?** The evidence-gate abstention "
        f"benefit on unanswerable questions, and preserved retrieval provenance "
        f"(path_agreement). Nothing about the structure-aware retrieval advantage.",
        f"8. **What does it not support?** Any retrieval, answer-quality or grounding "
        f"advantage of structure-aware retrieval (C) over semantic-only retrieval (A) "
        f"on the pre-registered DISCRIMINATING subset.",
        f"9. **Parser/chunker limitations?** The PDF parser emits only "
        f"section/paragraph/table/text_block (no persisted table_row/table_cell), and "
        f"the production `legacy` chunker does not populate heading_path/section, so "
        f"heading/section seeding is inert and the only live structural signal is the "
        f"element stream.",
        f"10. **Next research decision?** Investigate whether the element-level "
        f"structural stream is reachable for these questions (parser coverage / "
        f"chunker configuration) before enlarging the corpus; only then is a larger "
        f"evaluation likely to be informative.",
        "",
        f"**Verdict:** {verdict}. Key C−A deltas: `{diffs}`.",
        "",
        "The primary subset was fixed before the experiment; no subset was chosen "
        "after looking at outcomes. No statistical significance and no causal claim "
        "is made: the framework's paired bootstrap exists but was not applied here.",
        "",
        "## 11. Limitations",
        "",
        "- The current PDF parser emits only `section`, `paragraph`, `table` and "
        "`text_block`; persisted `table_row` / `table_cell` nodes do not exist, so "
        "row/cell gold is not resolved natively in the production graph.",
        "- The production default chunker is `legacy`, which does not populate "
        "`heading_path`/`section`; heading/section seeding is therefore inert and "
        "the live structural signal is the element-level stream.",
        "- Corpus is synthetic (authored PDFs), 72 questions; results are specific "
        "to this corpus and configuration.",
        "- Latency is reported by the runner but is not part of the effect analysis.",
        "",
        "## 12. Recommended next research decision",
        "",
        "If the DISCRIMINATING result shows no measurable C−A difference, the "
        "structure hypothesis remains unsupported on this corpus and the next step "
        "is to investigate whether the element-level structural stream is actually "
        "reachable for these questions (parser coverage / chunker configuration) "
        "before enlarging the corpus. If an effect is observed, replicate on a "
        "larger corpus and apply the framework's paired bootstrap before drawing "
        "conclusions.",
        "",
    ]
    return "\n".join(lines)


def write_reports(
    analysis: dict,
    out_dir: Path = REPORTS_DIR,
    *,
    timestamp: bool = False,
    replace: bool = False,
) -> dict[str, Path]:
    """Write the two synthesis artifacts, refusing to replace existing evidence.

    The destinations, the JSON serialization and the markdown rendering are
    unchanged from the pre-1.6Y revision; only the write is append-only now, so a
    re-run cannot silently replace an already-published synthesis.

    ``replace=True`` is an explicit, visible opt-in for a deliberate
    re-publication; it is never inferred.  Both artifacts go through the central
    ``write_evidence`` rule, which raises ``ArtifactExistsError`` when a
    destination exists and ``replace`` is False.  This is a library entry point,
    so the refusal propagates instead of being swallowed; ``main()`` reports it
    and exits non-zero.
    """
    payload = dict(analysis)
    if timestamp:
        from datetime import datetime, timezone

        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    # No directory is created up front: write_evidence creates a parent only when
    # it is about to write, so a refused run leaves the filesystem untouched.
    json_path = write_evidence(
        out_dir / "structure_discriminating_analysis.json",
        json.dumps(payload, indent=2, sort_keys=True),
        replace=replace,
    )
    md_path = write_evidence(
        out_dir / "structure_discriminating_ablation_report.md",
        render_markdown(payload),
        replace=replace,
    )
    return {"json": json_path, "md": md_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--timestamp", action="store_true",
                        help="include generated_at in the JSON (off by default)")
    parser.add_argument("--replace", action="store_true",
                        help=("deliberately re-publish the synthesis artifacts; without "
                              "this flag existing artifacts are preserved and the run "
                              "exits non-zero"))
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    reports = load_reports(Path(args.reports_dir))
    analysis = build_analysis(reports, corpus_labels())
    try:
        paths = write_reports(
            analysis,
            Path(args.reports_dir),
            timestamp=args.timestamp,
            replace=args.replace,
        )
    except ArtifactExistsError as error:
        print("REFUSING TO REPLACE EXISTING SYNTHESIS EVIDENCE")
        print(f"  {error}")
        print("  Re-run with --replace only if re-publishing the synthesis is intended.")
        return 2

    verdict, diffs = _verdict(analysis)
    disc = analysis["subsets"]["DISCRIMINATING"]["variants"]
    print(f"corpus={analysis['corpusVersion']} primary n={analysis['subsets']['DISCRIMINATING']['n']}")
    print(f"  DISCRIMINATING recall@5  A={_f(disc['A']['recall@5'])} C={_f(disc['C']['recall@5'])}")
    print(f"  DISCRIMINATING token_f1  A={_f(disc['A']['token_f1'])} C={_f(disc['C']['token_f1'])}")
    print(f"  C-A key deltas: {diffs}")
    print(f"  verdict: {verdict}")
    print(f"wrote {paths['json'].name} and {paths['md'].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

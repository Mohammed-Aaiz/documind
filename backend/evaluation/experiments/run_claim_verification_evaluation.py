"""Evaluate claim-level verifiers on the versioned claim dataset.

Compares the production lexical verifier (``generation.verification``) with the
relation-aware verifier (``generation.verification_relations``) on
``evaluation/datasets/claim_verification_v1.py``.

Fairness rules:

* Both verifiers see the same evidence blocks and claim strings.
* The baseline's two-way outcome is mapped honestly: SUPPORTED when it accepts,
  CONTRADICTED when it says the value belongs to a different entity, and
  ``UNSUPPORTED`` otherwise — it has no contradiction label, so contradiction
  recall is structurally zero rather than guessed.
* Thresholds: the relation verifier exposes no score threshold to tune. Its ratios
  were fixed before the held-out split was evaluated, and the single similarity
  constant (0.80) was chosen on the dev split and then frozen.
* ``dev`` and ``test`` are reported separately; the test split is held out.

Usage (from ``backend/``)::

    python -m evaluation.experiments.run_claim_verification_evaluation --split dev
    python -m evaluation.experiments.run_claim_verification_evaluation --split test
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

REPORT_ROOT = Path("evaluation/reports")
RUN_ID = "claim_verification_2026-10-17"


def _blocks(evidence: tuple[str, ...]):
    from generation.types import EvidenceBlock

    return [
        EvidenceBlock(index=index, content=text, document_name="claim-fixture")
        for index, text in enumerate(evidence, start=1)
    ]


def _baseline(example):
    """Run the production verifier and map its outcome to a 3-way label."""
    from generation.verification import check_claim

    check = check_claim(example.claim, _blocks(example.evidence))
    if check.supported:
        label = "SUPPORTED"
    elif "different entity" in check.reason:
        label = "CONTRADICTED"
    else:
        label = "UNSUPPORTED"
    citation_ok = True
    if example.stated_citations:
        citation_ok = bool(set(example.stated_citations) & set(check.citation_indices))
    return label, citation_ok, check.reason


def _relations(example):
    from generation.verification_relations import verify_claim

    verdict = verify_claim(example.claim, _blocks(example.evidence), example.stated_citations)
    return verdict.label, verdict.citation_ok, verdict.explanation


def _metrics(rows: list[dict], name: str) -> dict:
    def _count(predicate) -> int:
        return sum(1 for row in rows if predicate(row))

    tp = _count(lambda r: r["gold"] == "SUPPORTED" and r[f"{name}_label"] == "SUPPORTED")
    fp = _count(lambda r: r["gold"] != "SUPPORTED" and r[f"{name}_label"] == "SUPPORTED")
    fn = _count(lambda r: r["gold"] == "SUPPORTED" and r[f"{name}_label"] != "SUPPORTED")

    ctp = _count(lambda r: r["gold"] == "CONTRADICTED" and r[f"{name}_label"] == "CONTRADICTED")
    cfp = _count(lambda r: r["gold"] != "CONTRADICTED" and r[f"{name}_label"] == "CONTRADICTED")
    cfn = _count(lambda r: r["gold"] == "CONTRADICTED" and r[f"{name}_label"] != "CONTRADICTED")

    def _safe(numerator: int, denominator: int):
        return round(numerator / denominator, 4) if denominator else None

    precision = _safe(tp, tp + fp)
    recall = _safe(tp, tp + fn)
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if precision and recall
        else 0.0
    )
    cprecision = _safe(ctp, ctp + cfp)
    crecall = _safe(ctp, ctp + cfn)
    cf1 = (
        round(2 * cprecision * crecall / (cprecision + crecall), 4)
        if cprecision and crecall
        else 0.0
    )

    negatives = _count(lambda r: r["gold"] != "SUPPORTED")
    positives = _count(lambda r: r["gold"] == "SUPPORTED")
    insufficient = [r for r in rows if r["gold"] == "INSUFFICIENT_EVIDENCE"]
    citation_rows = [r for r in rows if not r["citation_correct"]]

    return {
        "examples": len(rows),
        "support_precision": precision,
        "support_recall": recall,
        "support_f1": f1,
        "support_true_positives": tp,
        "support_false_positives": fp,
        "support_false_negatives": fn,
        "contradiction_precision": cprecision,
        "contradiction_recall": crecall,
        "contradiction_f1": cf1,
        "false_accept_rate": _safe(fp, negatives),
        "false_reject_rate": _safe(fn, positives),
        "insufficient_gold": len(insufficient),
        "insufficient_correct": sum(
            1 for r in insufficient if r[f"{name}_label"] == "INSUFFICIENT_EVIDENCE"
        ),
        "wrong_citation_examples": len(citation_rows),
        "wrong_citations_detected": sum(1 for r in citation_rows if not r[f"{name}_citation_ok"]),
    }


def _by_category(rows: list[dict], name: str) -> dict:
    out: dict[str, dict] = {}
    for category in sorted({row["category"] for row in rows}):
        subset = [row for row in rows if row["category"] == category]
        out[category] = {
            "examples": len(subset),
            "correct": sum(1 for row in subset if row[f"{name}_label"] == row["gold"]),
        }
    return out


def _timed(func, example):
    started = time.perf_counter()
    outcome = func(example)
    return outcome, (time.perf_counter() - started) * 1000


def run(split: str) -> dict:
    from evaluation.datasets.claim_verification_v1 import EXAMPLES, by_split, statistics as dataset_statistics

    examples = by_split(split) if split in ("dev", "test") else EXAMPLES
    rows = []
    baseline_ms: list[float] = []
    relations_ms: list[float] = []

    # Load the shared embedder once, before timing, so per-claim latency is steady
    # state rather than a mixture of one 10 s model load and 1 ms comparisons.  The
    # one-off cost is reported separately: it is a cold-start cost, not per claim.
    from generation.verification_relations import semantic_similarity

    warmup_started = time.perf_counter()
    semantic_similarity("warm up phrase", "warm up phrase")
    warmup_ms = round((time.perf_counter() - warmup_started) * 1000, 4)

    for example in examples:
        (base_label, base_citation_ok, base_reason), base_ms = _timed(_baseline, example)
        (rel_label, rel_citation_ok, rel_reason), rel_ms = _timed(_relations, example)
        baseline_ms.append(base_ms)
        relations_ms.append(rel_ms)
        rows.append(
            {
                "example_id": example.example_id,
                "category": example.category,
                "split": example.split,
                "gold": example.label,
                "claim": example.claim,
                "hard": example.hard,
                "evidence_conflict": example.evidence_conflict,
                "citation_correct": example.citation_correct,
                "baseline_label": base_label,
                "baseline_citation_ok": base_citation_ok,
                "baseline_reason": base_reason,
                "relations_label": rel_label,
                "relations_citation_ok": rel_citation_ok,
                "relations_reason": rel_reason,
            }
        )

    summary = {
        "run_id": RUN_ID,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "dataset": "evaluation/datasets/claim_verification_v1.py",
        "dataset_statistics": dataset_statistics(),
        "baseline": _metrics(rows, "baseline"),
        "relations": _metrics(rows, "relations"),
        "baseline_by_category": _by_category(rows, "baseline"),
        "relations_by_category": _by_category(rows, "relations"),
        "latency_ms_per_claim": {
            "embedder_cold_start_ms": warmup_ms,
            "baseline_mean": round(statistics.mean(baseline_ms), 4),
            "relations_mean": round(statistics.mean(relations_ms), 4),
            "baseline_max": round(max(baseline_ms), 4),
            "relations_max": round(max(relations_ms), 4),
        },
        "mismatches": [
            {
                "example_id": row["example_id"],
                "category": row["category"],
                "gold": row["gold"],
                "baseline": row["baseline_label"],
                "relations": row["relations_label"],
                "claim": row["claim"],
            }
            for row in rows
            if row["relations_label"] != row["gold"] or row["baseline_label"] != row["gold"]
        ],
    }
    return {"summary": summary, "rows": rows}


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown(summary: dict) -> str:
    b, r = summary["baseline"], summary["relations"]
    stats = summary["dataset_statistics"]
    latency = summary["latency_ms_per_claim"]
    lines = [
        "# Claim verification evaluation — lexical baseline vs relation-aware verifier",
        "",
        f"- Run: `{summary['run_id']}` (`{summary['split']}` split)",
        f"- Started: {summary['started_at']}",
        f"- Dataset: `{summary['dataset']}` — {stats['total']} examples "
        f"({stats['dev']} dev / {stats['test']} test), synthetic",
        f"- Latency per claim (after a {latency['embedder_cold_start_ms']} ms one-off "
        f"embedder load): baseline {latency['baseline_mean']} ms, "
        f"relations {latency['relations_mean']} ms (max {latency['relations_max']} ms)",
        "",
        "## Claim-level metrics",
        "",
        "| Metric | Lexical baseline | Relation verifier |",
        "|---|---|---|",
        f"| Support precision | {_fmt(b['support_precision'])} | {_fmt(r['support_precision'])} |",
        f"| Support recall | {_fmt(b['support_recall'])} | {_fmt(r['support_recall'])} |",
        f"| Support F1 | {_fmt(b['support_f1'])} | {_fmt(r['support_f1'])} |",
        f"| Contradiction precision | {_fmt(b['contradiction_precision'])} | {_fmt(r['contradiction_precision'])} |",
        f"| Contradiction recall | {_fmt(b['contradiction_recall'])} | {_fmt(r['contradiction_recall'])} |",
        f"| Contradiction F1 | {_fmt(b['contradiction_f1'])} | {_fmt(r['contradiction_f1'])} |",
        f"| False-accept rate | {_fmt(b['false_accept_rate'])} | {_fmt(r['false_accept_rate'])} |",
        f"| False-reject rate | {_fmt(b['false_reject_rate'])} | {_fmt(r['false_reject_rate'])} |",
        f"| Insufficient-evidence correct (of {r['insufficient_gold']}) | "
        f"{b['insufficient_correct']} | {r['insufficient_correct']} |",
        f"| Wrong citations detected (of {r['wrong_citation_examples']}) | "
        f"{b['wrong_citations_detected']} | {r['wrong_citations_detected']} |",
        "",
        "## Per category (correct / examples)",
        "",
        "| Category | Baseline | Relation |",
        "|---|---|---|",
    ]
    for category, base in summary["baseline_by_category"].items():
        rel = summary["relations_by_category"][category]
        lines.append(
            f"| {category} | {base['correct']}/{base['examples']} | {rel['correct']}/{rel['examples']} |"
        )

    lines += ["", "## Mismatches (first 25)", ""]
    for row in summary["mismatches"][:25]:
        lines.append(
            f"- `{row['example_id']}` ({row['category']}) gold `{row['gold']}` · "
            f"baseline `{row['baseline']}` · relations `{row['relations']}` — {row['claim'][:110]}"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- The dataset is synthetic; these numbers are not real-world accuracy, and the",
        "  paraphrase cases share more vocabulary than real paraphrases typically do.",
        "- Contradiction recall for the baseline is structurally zero: it reports only",
        "  'supported' vs 'not supported', with one wrong-entity special case.",
        "- The relation verifier is deterministic apart from the paraphrase fallback:",
        "  similarity is only consulted when the head term and numbers/units already",
        "  agree, and then must clear 0.80. It adds",
        f"  {latency['relations_mean'] - latency['baseline_mean']:.3f} ms per claim on this",
        "  machine (the first call includes loading the shared embedder).",
        "",
    ]
    return "\n".join(lines)


def write_report(payload: dict, run_id: str = RUN_ID) -> Path:
    out_dir = REPORT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    (out_dir / f"summary_{summary['split']}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (out_dir / f"rows_{summary['split']}.jsonl").open("w", encoding="utf-8") as handle:
        for row in payload["rows"]:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / f"REPORT_{summary['split']}.md").write_text(
        render_markdown(summary), encoding="utf-8"
    )
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate claim-level verifiers.")
    parser.add_argument("--split", default="dev", choices=("dev", "test", "all"))
    parser.add_argument(
        "--run-id",
        default=RUN_ID,
        help="Report directory name; use a new value instead of overwriting a previous run.",
    )
    args = parser.parse_args()

    payload = run(args.split)
    # Stamp the directory actually written, so a report never claims to be a run it
    # is not (an earlier revision reused the default id inside a `--run-id` folder).
    payload["summary"]["run_id"] = args.run_id
    out_dir = write_report(payload, args.run_id)
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "baseline": payload["summary"]["baseline"],
                "relations": payload["summary"]["relations"],
                "latency_ms_per_claim": payload["summary"]["latency_ms_per_claim"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

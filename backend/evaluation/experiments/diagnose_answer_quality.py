"""Reproducible diagnostic for answer coverage and relevance (Mission 4).

Reads the frozen benchmark, the two recorded 10-mark runs and the v2 claim
annotations.  It performs **no model inference**: every number here is derived
from artifacts that already exist, so the diagnosis can be re-run exactly.

By default the buckets are computed from the recorded ``fmt10`` generation run,
so they are the pre-change population.  ``--generation-run`` re-reads a newer
run's ``results.jsonl`` (for example
``generation_benchmark_2026-10-18_m4_post_v2``) and classifies its answers with
the **current** ``answerability`` code.  The frozen pre-change capture is
``reports/answer_quality_diagnosis_2026-10-18_m4/analysis.json`` (HEAD
``6baaa2a``, 49 gate refusals).

What it reports:

* the answer buckets for the 140 answerable questions (answered with claims,
  answerability-gate abstention, withheld by the grounding policy);
* for each gate abstention, the gate's missing terms, its coverage and whether
  the gold answer occurs in the row's context;
* for each withheld answer, the claims the verifier rejected;
* the v2 non-claim population by category and verifier acceptance;
* every supported claim annotated as not answering its question;
* the current metric block from the latest claim evaluation.

Usage (from ``backend``)::

    python -m evaluation.experiments.diagnose_answer_quality \
        --run-id answer_quality_diagnosis_2026-10-18_m4
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from evaluation.datasets import answer_claims_v2
from evaluation.experiments.run_answer_claim_evaluation import (
    BENCHMARK_PATH,
    EXPECTED_SHA256,
    REPORT_ROOT,
    RUN_DIRS,
    _load_run,
    load_benchmark,
    sha256_of,
)
from generation.verification import answerability

DEFAULT_RUN_ID = "answer_quality_diagnosis_2026-10-18_m4"
CLAIM_RUN = "answer_claim_evaluation_2026-10-18_m4_baseline_v2"


def _gold_in_context(gold: str, context: str) -> bool:
    needle = " ".join(str(gold).lower().split())
    return bool(needle) and needle in " ".join(context.lower().split())


def _buckets(benchmark: dict[str, dict], rows: dict[str, dict]) -> dict:
    answerable = [
        rid for rid, row in benchmark.items() if row.get("question_kind") != "UNANSWERABLE"
    ]
    buckets: Counter[str] = Counter()
    gate_cases: list[dict] = []
    withheld_cases: list[dict] = []
    for rid in answerable:
        row = rows[rid]
        answer = str(row.get("generative_answer") or "").strip()
        warnings = row.get("generative_warnings") or []
        claims = int(row.get("generative_claims") or 0)
        if answer and claims:
            buckets["answered_with_claims"] += 1
        elif answer and not claims:
            buckets["answer_without_claims"] += 1
        elif not answer and any("does not cover" in warning for warning in warnings):
            buckets["gate_abstention"] += 1
            decision = answerability(benchmark[rid]["question"], benchmark[rid]["context"])
            gate_cases.append(
                {
                    "example_id": rid,
                    "question_kind": benchmark[rid]["question_kind"],
                    "question": benchmark[rid]["question"],
                    "gold": benchmark[rid]["answer"],
                    "gold_in_context": _gold_in_context(
                        benchmark[rid]["answer"], benchmark[rid]["context"]
                    ),
                    "gate_coverage": round(decision.coverage, 4),
                    "gate_missing": list(decision.missing),
                }
            )
        elif not answer and any("withheld" in warning.lower() for warning in warnings):
            buckets["withheld"] += 1
            withheld_cases.append(
                {
                    "example_id": rid,
                    "question_kind": benchmark[rid]["question_kind"],
                    "question": benchmark[rid]["question"],
                    "gold": benchmark[rid]["answer"],
                    "unsupported_claims": list(row.get("generative_unsupported") or []),
                }
            )
        elif not answer:
            buckets["empty_no_warning"] += 1
        else:
            buckets["other"] += 1
    return {
        "answerable": len(answerable),
        "buckets": dict(buckets),
        "gate_cases": gate_cases,
        "withheld_cases": withheld_cases,
    }


def _non_claims(claim_rows: list[dict]) -> dict:
    non_claims = [row for row in claim_rows if row["gold"] == answer_claims_v2.NOT_A_CLAIM]
    categories = Counter(row["category"] for row in non_claims)
    return {
        "count": len(non_claims),
        "denominator": len(claim_rows),
        "rate": round(len(non_claims) / len(claim_rows), 4),
        "categories": dict(categories),
        "lexical_accepted": sum(1 for row in non_claims if row["lexical_supported"]),
        "relations_accepted": sum(1 for row in non_claims if row["relations_supported"]),
        "records": [
            {
                "claim_id": row["claim_id"],
                "example_id": row["example_id"],
                "claim": row["claim"],
                "category": row["category"],
                "lexical_label": row["lexical_label"],
                "relations_label": row["relations_label"],
            }
            for row in non_claims
        ],
    }


def _off_target(claim_rows: list[dict]) -> dict:
    off_target = [
        row
        for row in claim_rows
        if row["gold"] == answer_claims_v2.SUPPORTED and row["answers_question"] is False
    ]
    return {
        "count": len(off_target),
        "records": [
            {
                "claim_id": row["claim_id"],
                "example_id": row["example_id"],
                "claim": row["claim"],
                "category": row["category"],
                "lexical_label": row["lexical_label"],
                "relations_label": row["relations_label"],
                "rationale": row["rationale"],
            }
            for row in off_target
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument(
        "--generation-run",
        default=None,
        help="Classify this generation run's answers instead of the recorded fmt10 run.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out_dir = REPORT_ROOT / args.run_id
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(f"Run directory already exists: {out_dir}")

    benchmark_rows = load_benchmark(BENCHMARK_PATH)
    benchmark = {str(row["example_id"]): row for row in benchmark_rows}
    runs = {mode: _load_run(run_id) for mode, run_id in RUN_DIRS.items()}
    if args.generation_run:
        runs["lexical"] = _load_run(args.generation_run)
    claim_rows = [
        json.loads(line)
        for line in (
            REPORT_ROOT / CLAIM_RUN / "claims.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    analysis = {
        "run_id": args.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": str(BENCHMARK_PATH),
        "benchmark_sha256": sha256_of(BENCHMARK_PATH),
        "benchmark_hash_matches_expected": sha256_of(BENCHMARK_PATH) == EXPECTED_SHA256,
        "claim_report": CLAIM_RUN,
        "dataset": {
            "version": answer_claims_v2.DATASET_VERSION,
            "path": f"evaluation/datasets/{answer_claims_v2.DATASET_PATH.name}",
            "sha256": hashlib.sha256(answer_claims_v2.DATASET_PATH.read_bytes()).hexdigest(),
            "statistics": answer_claims_v2.statistics(),
        },
        "recorded_runs": {mode: run_id for mode, run_id in RUN_DIRS.items()},
        "generation_run": args.generation_run or RUN_DIRS["lexical"],
        "answer_buckets": _buckets(benchmark, runs["lexical"]),
        "non_claims": _non_claims(claim_rows),
        "supported_off_target": _off_target(claim_rows),
        "metrics": json.loads(
            (REPORT_ROOT / CLAIM_RUN / "summary.json").read_text(encoding="utf-8")
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8"
    )
    buckets = analysis["answer_buckets"]["buckets"]
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "answerable": analysis["answer_buckets"]["answerable"],
                "buckets": buckets,
                "non_claims": analysis["non_claims"]["count"],
                "off_target": analysis["supported_off_target"]["count"],
                "benchmark_hash_ok": analysis["benchmark_hash_matches_expected"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

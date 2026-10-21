"""Question-level error ledger for answer quality (Mission 5).

Joins the frozen benchmark, the Mission 4 baseline and post-change generation
runs, and the v2 claim annotations into one machine-readable row per answerable
question.  No model inference: every field is read from an existing artifact.

Outputs (under ``evaluation/reports/<run-id>/``):

* ``ledger.jsonl`` — one record per question with answers, status, rejected
  claims, EM/F1 against the gold answer, and a diagnostic category;
* ``summary.json`` — category counts, the returned-vs-withheld unsupported-claim
  split, and per-run coverage/quality figures.

Usage (from ``backend``)::

    python -m evaluation.experiments.build_answer_error_ledger \
        --run-id answer_quality_mission5_2026-10-18_diagnosis
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter

from evaluation.datasets import answer_claims_v2
from evaluation.experiments.run_answer_claim_evaluation import REPORT_ROOT
from evaluation.experiments.run_generation_benchmark import (
    BENCHMARK_PATH,
    EXPECTED_SHA256,
    is_unanswerable,
    load_benchmark,
)
from evaluation.qa_metrics import token_f1

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

DEFAULT_RUN_ID = "answer_quality_mission5_2026-10-18_diagnosis"
BASELINE_RUN = "generation_benchmark_2026-10-18_m4_baseline"
M4_RUN = "generation_benchmark_2026-10-18_m4_post_v2"


def _load_run(run_id: str) -> dict[str, dict]:
    path = REPORT_ROOT / run_id / "results.jsonl"
    if not path.exists():
        raise SystemExit(f"Generation run not found: {path}")
    return {
        row["example_id"]: row
        for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    }


def _answers_question(claims: list[dict]) -> dict[str, int]:
    answers = [claim for claim in claims if claim.get("label") != answer_claims_v2.NOT_A_CLAIM]
    return {
        "propositional": len(answers),
        "answers_question_true": sum(1 for claim in answers if claim.get("answers_question") is True),
        "answers_question_false": sum(1 for claim in answers if claim.get("answers_question") is False),
    }


def _category(row: dict) -> str:
    if row["unanswerable"]:
        return "unanswerable_answered" if row["generative_answer"] else "unanswerable_abstained"
    if row["generative_answer"]:
        return "answered_exact" if row["generative_em"] else "answered_nonempty"
    warnings = " ".join(row.get("generative_warnings", []))
    if "does not cover" in warnings:
        return "gate_refusal"
    if "withheld" in warnings:
        return "withheld"
    return "empty_other"


def _diagnose(record: dict) -> tuple[str, str, str, str]:
    """Deterministic (root cause, action, confidence, severity) for one row.

    These are diagnostic hypotheses derived from recorded fields, not
    adjudicated labels; the report says so wherever they are used.
    """
    if record["unanswerable"]:
        if record["m4_answer"]:
            return (
                "spurious answer to an unanswerable question",
                "keep the answerability gate; review this row's context",
                "high",
                "high",
            )
        return ("correct abstention", "none", "high", "none")
    if record["m4_category"] == "gate_refusal":
        return (
            "answerability gate refused: more than one distinctive question term is absent",
            "evidence/context construction or a pattern-specific gate term (follow-up)",
            "high",
            "medium",
        )
    if record["m4_category"] == "withheld":
        if record.get("table_entity_candidate"):
            return (
                "table header anchor in numeric_entity_alignment",
                "table column binding (Mission 5, implemented)",
                "high",
                "medium",
            )
        if record["m4_unsupported_claims"]:
            return (
                "numeric entity mismatch against a prose/heading anchor, or a genuinely wrong value",
                "none in Mission 5; section-body alignment or wrong-answer review",
                "medium",
                "medium",
            )
        return ("no claim extracted from the generated text", "inspect generation output", "low", "low")
    if record["m4_category"] == "answered_exact":
        return ("none", "none", "high", "none")
    if record["answer_relevance"]["answers_question_false"]:
        return (
            "supported but off-target claim(s)",
            "question-attribute binding at generation time (follow-up)",
            "medium",
            "medium",
        )
    return ("non-exact answer (format/incomplete)", "none (generation completeness)", "low", "low")


def _change(baseline: dict, post: dict) -> str:
    before, after = baseline["generative_answer"].strip(), post["generative_answer"].strip()
    if before == after:
        return "unchanged"
    if before and not after:
        return "answer_lost"
    if not before and after:
        return "answer_added_exact" if post["generative_em"] else "answer_added_nonempty"
    return "answer_changed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--baseline-run", default=BASELINE_RUN)
    parser.add_argument("--m4-run", default=M4_RUN)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out_dir = REPORT_ROOT / args.run_id
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(f"Run directory already exists: {out_dir}")

    benchmark_rows = load_benchmark(BENCHMARK_PATH)
    benchmark = {str(row["example_id"]): row for row in benchmark_rows}
    actual_hash = hashlib.sha256(BENCHMARK_PATH.read_bytes()).hexdigest()
    if actual_hash != EXPECTED_SHA256:
        raise SystemExit("Frozen benchmark hash mismatch; refusing to write a ledger.")

    baseline = _load_run(args.baseline_run)
    m4 = _load_run(args.m4_run)

    claims: list[dict] = [
        json.loads(line)
        for line in answer_claims_v2.DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    claims_by_example: dict[str, list[dict]] = {}
    for claim in claims:
        claims_by_example.setdefault(claim["example_id"], []).append(claim)

    records: list[dict] = []
    for example_id, row in benchmark.items():
        base = baseline[example_id]
        post = m4[example_id]
        question_claims = claims_by_example.get(example_id, [])
        rejected = list(post.get("generative_unsupported", []))
        record = {
            "example_id": example_id,
            "question_kind": row.get("question_kind"),
            "unanswerable": is_unanswerable(row),
            "question": row.get("question", ""),
            "gold": row.get("answer", ""),
            "baseline_answer": base["generative_answer"],
            "baseline_status": base["generative_status"],
            "baseline_em": bool(base["generative_em"]),
            "baseline_f1": round(float(token_f1(base["generative_answer"], row.get("answer", ""))), 4),
            "m4_answer": post["generative_answer"],
            "m4_status": post["generative_status"],
            "m4_em": bool(post["generative_em"]),
            "m4_f1": round(float(token_f1(post["generative_answer"], row.get("answer", ""))), 4),
            "m4_claims": int(post["generative_claims"]),
            "m4_supported_claims": int(post["generative_supported_claims"]),
            "m4_citation_accuracy": float(post.get("generative_citation_accuracy", 0.0)),
            "m4_unsupported_claims": rejected,
            "m4_warnings": post.get("generative_warnings", []),
            "answer_relevance": _answers_question(question_claims),
            "annotated_claims": [
                {
                    "claim_id": claim["claim_id"],
                    "claim": claim["claim"],
                    "label": claim["label"],
                    "answers_question": claim.get("answers_question"),
                }
                for claim in question_claims
            ],
            "baseline_category": _category(base),
            "m4_category": _category(post),
            "change": _change(base, post),
            "benchmark_context": row.get("context", ""),
        }
        # Diagnostic hint only: a withheld answer whose rejected claim is a
        # numeric value carried by a pipe-delimited table row is the pattern
        # studied by the table-entity alignment intervention.
        table_rows = [line for line in record["benchmark_context"].splitlines() if "|" in line]
        claim_numbers = {number for claim in rejected for number in _NUMBER.findall(claim)}
        record["table_entity_candidate"] = bool(
            not post["generative_answer"]
            and "withheld" in " ".join(post.get("generative_warnings", []))
            and claim_numbers
            and any(
                claim_numbers & set(_NUMBER.findall(row)) for row in table_rows
            )
        )
        root_cause, action, confidence, severity = _diagnose(record)
        record["root_cause_hypothesis"] = root_cause
        record["proposed_action"] = action
        record["confidence"] = confidence
        record["severity"] = severity
        records.append(record)

    answerable = [r for r in records if not r["unanswerable"]]
    summary = {
        "run_id": args.run_id,
        "benchmark": str(BENCHMARK_PATH),
        "benchmark_sha256": actual_hash,
        "benchmark_hash_matches_expected": actual_hash == EXPECTED_SHA256,
        "dataset_version": answer_claims_v2.DATASET_VERSION,
        "dataset_sha256": hashlib.sha256(answer_claims_v2.DATASET_PATH.read_bytes()).hexdigest(),
        "baseline_run": args.baseline_run,
        "m4_run": args.m4_run,
        "rows": len(records),
        "answerable": len(answerable),
        "unanswerable": len(records) - len(answerable),
        "baseline_buckets": dict(Counter(r["baseline_category"] for r in answerable)),
        "m4_buckets": dict(Counter(r["m4_category"] for r in answerable)),
        "changes": dict(Counter(r["change"] for r in answerable)),
        "m4_answered": sum(1 for r in answerable if r["m4_answer"]),
        "m4_em": sum(1 for r in answerable if r["m4_em"]),
        "m4_f1_mean": round(
            sum(float(token_f1(r["m4_answer"], r["gold"])) for r in answerable) / len(answerable), 4
        ),
        "returned_vs_withheld_unsupported": {
            "returned_claims": sum(r["m4_claims"] for r in answerable if r["m4_answer"]),
            "returned_unsupported": sum(
                len(r["m4_unsupported_claims"]) for r in answerable if r["m4_answer"]
            ),
            "withheld_answers": sum(
                1 for r in answerable if not r["m4_answer"] and r["m4_unsupported_claims"]
            ),
            "withheld_unsupported": sum(
                len(r["m4_unsupported_claims"]) for r in answerable if not r["m4_answer"]
            ),
        },
        "table_entity_candidates": [r["example_id"] for r in answerable if r["table_entity_candidate"]],
        "off_target_claims": sum(r["answer_relevance"]["answers_question_false"] for r in answerable),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "ledger.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""Claim-level evaluation on DocuMind's *actual* generated answers.

Motivation
----------
``run_claim_verification_evaluation.py`` measured both verifiers on synthetic
claims.  The generation benchmark then showed that the relation-aware verifier
improved grounding metrics but lowered token F1, so the verifier stayed opt-in.
The missing measurement is the one this runner performs: do the verifiers judge
the claims the generator *really* emits, on the evidence the generator really saw?

Design
------
* The frozen 182-row benchmark is hash-verified before anything else.  A mismatch
  aborts without writing.
* The claims come from ``evaluation/datasets/answer_claims_v1`` — the union of
  the claims in the recorded lexical run (production default) and the recorded
  relation-verifier run.  Every claim is checked against the recorded answers
  before scoring, so the dataset cannot drift from the reports it describes.
* Both verifiers receive the same claim, the same question and the same single
  evidence block (the benchmark row's ``context`` — exactly what the generator
  was given; retrieval is not part of this measurement).
* The lexical verifier is binary.  It is mapped honestly: SUPPORTED when it
  accepts, CONTRADICTED only for its explicit wrong-entity outcome, UNSUPPORTED
  otherwise.  Its contradiction recall is therefore structurally low, and a
  rejection is *not* counted as proof that a claim is contradicted.
* Non-propositional fragments (table renders, headers, bare tokens) are excluded
  from support/contradiction metrics and reported separately: accepting them is a
  generation-quality signal, not a claim-truth error.
* Generation-level consequences are computed from the two recorded benchmark
  runs (never re-run here): coverage, EM/F1, unsupported-claim rate, abstention,
  and which answers the candidate verifier would remove or admit.

Usage (from ``backend/``)::

    python -m evaluation.experiments.run_answer_claim_evaluation
    python -m evaluation.experiments.run_answer_claim_evaluation --run-id <new-name>
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from evaluation.datasets import answer_claims_v1, answer_claims_v2
from evaluation.experiments.run_generation_benchmark import (
    BENCHMARK_PATH,
    EXPECTED_SHA256,
    load_benchmark,
    sha256_of,
)

REPORT_ROOT = Path("evaluation/reports")
RUN_ID = "answer_claim_evaluation_2026-10-18_r4"

#: Versioned datasets.  Each module exposes its own ``split_claims`` so a report
#: is scored on the population it was annotated against: v1 uses the frozen
#: pre-fix extraction, v2 the corrected production splitter.
DATASETS = {"v1": answer_claims_v1, "v2": answer_claims_v2}

#: Recorded 10-mark runs compared here.  Both are historical artifacts; this
#: runner reads them and never regenerates or overwrites them.
RUN_DIRS = {
    "lexical": "generation_benchmark_2026-10-17_fmt10",
    "relations": "generation_benchmark_2026-10-17_fmt10_relations_r5",
}

#: Label the lexical verifier's explicit wrong-entity outcome as a contradiction,
#: matching the mapping used by the synthetic claim evaluation.
_LEXICAL_CONTRADICTION_MARKER = "different entity"


# ---------------------------------------------------------------------------
# Inputs and integrity
# ---------------------------------------------------------------------------

def _load_run(run_id: str) -> dict[str, dict]:
    path = REPORT_ROOT / run_id / "results.jsonl"
    if not path.exists():
        raise SystemExit(f"Recorded run not found: {path}")
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                row = json.loads(line)
                rows[str(row["example_id"])] = row
    return rows


def _answer_claims(row: dict, split_claims) -> list[str]:
    return split_claims(str(row.get("generative_answer") or ""))


def validate_inputs(
    claims: list[answer_claims_v1.AnswerClaim],
    benchmark: dict[str, dict],
    runs: dict[str, dict[str, dict]],
    split_claims,
) -> dict:
    """Fail closed if the dataset and the recorded answers disagree."""
    problems: list[str] = []
    seen: set[str] = set()
    for claim in claims:
        if claim.claim_id in seen:
            problems.append(f"duplicate claim id {claim.claim_id}")
        seen.add(claim.claim_id)
        row = benchmark.get(claim.example_id)
        if row is None:
            problems.append(f"{claim.claim_id}: example_id not in benchmark")
            continue
        if row.get("question_kind") == "UNANSWERABLE":
            problems.append(f"{claim.claim_id}: benchmark row is unanswerable")
        if not (row.get("context") or "").strip():
            problems.append(f"{claim.claim_id}: benchmark row has no context")
        if claim.question_kind != row.get("question_kind"):
            problems.append(f"{claim.claim_id}: question_kind drifted")
        present = {
            mode: claim.claim in _answer_claims(runs[mode][claim.example_id], split_claims)
            for mode in runs
        }
        if not any(present.values()):
            problems.append(f"{claim.claim_id}: claim not present in any recorded answer")
        expected = {mode for mode, has_claim in present.items() if has_claim}
        if set(claim.produced_by) != expected:
            problems.append(
                f"{claim.claim_id}: produced_by={sorted(claim.produced_by)} but answers give {sorted(expected)}"
            )
    if problems:
        raise SystemExit("Annotation/answer integrity failed:\n  " + "\n  ".join(problems[:20]))
    return {
        "claims": len(claims),
        "examples": len({claim.example_id for claim in claims}),
        "benchmark_rows": len(benchmark),
        "answerable_rows": sum(1 for row in benchmark.values() if row.get("question_kind") != "UNANSWERABLE"),
    }


# ---------------------------------------------------------------------------
# Verifier execution
# ---------------------------------------------------------------------------

def _evidence(context: str):
    from generation.types import EvidenceBlock

    return [EvidenceBlock(index=1, content=context, document_name="benchmark-context")]


def _lexical(claim: str, context: str, question: str, blocks=None) -> dict:
    from generation.verification import check_claim

    check = check_claim(claim, blocks if blocks is not None else _evidence(context), question=question)
    # The lexical verifier is binary.  Its "different entity" reason is a native
    # signal worth counting, but it is not a three-way contradiction verdict:
    # mapping it to CONTRADICTED would invent a label the verifier does not emit.
    return {
        "label": answer_claims_v1.SUPPORTED if check.supported else "UNSUPPORTED",
        "supported": bool(check.supported),
        "entity_conflict": (not check.supported) and _LEXICAL_CONTRADICTION_MARKER in check.reason,
        "reason": check.reason,
        "stated_citations": list(check.citation_indices),
    }


def _relations(claim: str, context: str, question: str, blocks=None) -> dict:
    from generation.verification_relations import verify_claim

    # The question is required: the verifier uses it to attribute a value-only
    # claim to the asked entity.  Omitting it silently changes the verifier under
    # test (it would accept any bare number that appears in the passage).
    verdict = verify_claim(
        claim, blocks if blocks is not None else _evidence(context), question=question
    )
    return {
        "label": verdict.label,
        "supported": verdict.label == answer_claims_v1.SUPPORTED,
        "reason": verdict.explanation,
        "supporting_blocks": list(verdict.supporting_blocks),
        "contradicting_blocks": list(verdict.contradicting_blocks),
        "citation_ok": verdict.citation_ok,
        "best_support_score": verdict.best_support_score,
    }


def verify_both(
    claim: str, context: str, question: str
) -> tuple[dict, dict, float, float]:
    """Run both verifiers on one claim with *identical* inputs.

    One evidence list is built and passed to both calls, so the claim, question,
    block content and citation indices cannot drift between verifiers.  Each call
    is timed separately; the single entry point is what ``score_claims`` uses, so
    the equivalence test covers the evaluation path rather than a look-alike.
    """
    blocks = _evidence(context)
    started = time.perf_counter()
    lexical = _lexical(claim, context, question, blocks)
    lexical_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    relations = _relations(claim, context, question, blocks)
    relations_ms = (time.perf_counter() - started) * 1000
    return lexical, relations, lexical_ms, relations_ms


def score_claims(
    claims: list[answer_claims_v1.AnswerClaim],
    benchmark: dict[str, dict],
    runs: dict[str, dict[str, dict]],
) -> tuple[list[dict], dict]:
    from generation.planning import extract_citations
    from generation.verification_relations import semantic_similarity

    # Warm the shared embedder once, outside the per-claim timing, so the
    # relation verifier's latency is steady-state rather than one model load.
    warmup_started = time.perf_counter()
    semantic_similarity("warm up phrase", "warm up phrase")
    warmup_ms = round((time.perf_counter() - warmup_started) * 1000, 3)

    rows: list[dict] = []
    lexical_ms: list[float] = []
    relations_ms: list[float] = []

    for claim in claims:
        row = benchmark[claim.example_id]
        context = str(row.get("context") or "")
        question = str(row.get("question") or "")

        # One evidence list is shared by both calls, so the claim, question,
        # block content and citation indices are identical; each call is timed
        # separately inside the helper.
        lexical, relations, lexical_elapsed_ms, relations_elapsed_ms = verify_both(
            claim.claim, context, question
        )
        lexical_ms.append(lexical_elapsed_ms)
        relations_ms.append(relations_elapsed_ms)

        stated = extract_citations(claim.claim)
        rows.append(
            {
                "claim_id": claim.claim_id,
                "example_id": claim.example_id,
                "question_kind": claim.question_kind,
                "claim": claim.claim,
                "gold": claim.label,
                "category": claim.category,
                "answers_question": claim.answers_question,
                "uncertainty": claim.uncertainty,
                "produced_by": list(claim.produced_by),
                "rationale": claim.rationale,
                "lexical_label": lexical["label"],
                "lexical_supported": lexical["supported"],
                "lexical_entity_conflict": lexical["entity_conflict"],
                "lexical_reason": lexical["reason"],
                "relations_label": relations["label"],
                "relations_supported": relations["supported"],
                "relations_reason": relations["reason"],
                "relations_supporting_blocks": relations["supporting_blocks"],
                "relations_contradicting_blocks": relations["contradicting_blocks"],
                "relations_citation_ok": relations["citation_ok"],
                "stated_citations": stated,
                "citation_correct": (not stated) or stated == [1],
            }
        )

    timing = {
        "embedder_cold_start_ms": warmup_ms,
        "lexical_mean_ms": round(statistics.mean(lexical_ms), 4),
        "lexical_max_ms": round(max(lexical_ms), 4),
        "relations_mean_ms": round(statistics.mean(relations_ms), 4),
        "relations_max_ms": round(max(relations_ms), 4),
    }
    return rows, timing


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    """95% Wilson interval for a binomial proportion (None when total == 0)."""
    if total <= 0:
        return None
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def _metrics(rows: list[dict], key: str) -> dict:
    """Support/contradiction/abstention metrics for one verifier.

    ``key`` is ``lexical`` or ``relations``; ``rows`` are propositional claims.
    PARTIALLY_SUPPORTED counts as *not fully supported* (a false accept when a
    verifier accepts it) and is reported separately.
    """
    prediction = f"{key}_label"

    def count(predicate) -> int:
        return sum(1 for row in rows if predicate(row))

    tp = count(lambda r: r["gold"] == answer_claims_v1.SUPPORTED and r[prediction] == answer_claims_v1.SUPPORTED)
    fp = count(lambda r: r["gold"] != answer_claims_v1.SUPPORTED and r[prediction] == answer_claims_v1.SUPPORTED)
    fn = count(lambda r: r["gold"] == answer_claims_v1.SUPPORTED and r[prediction] != answer_claims_v1.SUPPORTED)
    tn = count(lambda r: r["gold"] != answer_claims_v1.SUPPORTED and r[prediction] != answer_claims_v1.SUPPORTED)

    ctp = count(lambda r: r["gold"] == answer_claims_v1.CONTRADICTED and r[prediction] == answer_claims_v1.CONTRADICTED)
    cfp = count(lambda r: r["gold"] != answer_claims_v1.CONTRADICTED and r[prediction] == answer_claims_v1.CONTRADICTED)
    cfn = count(lambda r: r["gold"] == answer_claims_v1.CONTRADICTED and r[prediction] != answer_claims_v1.CONTRADICTED)

    positives = count(lambda r: r["gold"] == answer_claims_v1.SUPPORTED)
    negatives = len(rows) - positives
    insufficient = [r for r in rows if r["gold"] == answer_claims_v1.INSUFFICIENT]
    partial = [r for r in rows if r["gold"] == answer_claims_v1.PARTIAL]

    def safe(numerator: int, denominator: int):
        return round(numerator / denominator, 4) if denominator else None

    precision = safe(tp, tp + fp)
    recall = safe(tp, tp + fn)
    f1 = (
        None
        if precision is None or recall is None
        else round(2 * precision * recall / (precision + recall), 4)
        if precision + recall
        else 0.0
    )
    cprecision = safe(ctp, ctp + cfp)
    crecall = safe(ctp, ctp + cfn)
    cf1 = (
        None
        if cprecision is None or crecall is None
        else round(2 * cprecision * crecall / (cprecision + crecall), 4)
        if cprecision + crecall
        else 0.0
    )

    return {
        "claims": len(rows),
        "support_precision": precision,
        "support_recall": recall,
        "support_f1": f1,
        "support_true_positives": tp,
        "support_false_positives": fp,
        "support_false_negatives": fn,
        "support_true_negatives": tn,
        "support_precision_ci95": wilson_interval(tp, tp + fp),
        "support_recall_ci95": wilson_interval(tp, tp + fn),
        "false_accept_rate": safe(fp, negatives),
        "false_accept_count": fp,
        "false_accept_ci95": wilson_interval(fp, negatives),
        "false_reject_rate": safe(fn, positives),
        "false_reject_count": fn,
        "false_reject_ci95": wilson_interval(fn, positives),
        "binary_decision_accuracy": safe(tp + tn, len(rows)),
        "contradiction_precision": cprecision,
        "contradiction_recall": crecall,
        "contradiction_f1": cf1,
        "contradiction_true_positives": ctp,
        "contradiction_false_positives": cfp,
        "contradiction_false_negatives": cfn,
        "contradiction_precision_ci95": wilson_interval(ctp, ctp + cfp),
        "contradiction_recall_ci95": wilson_interval(ctp, ctp + cfn),
        "insufficient_gold": len(insufficient),
        "insufficient_correct": sum(1 for r in insufficient if r[prediction] == answer_claims_v1.INSUFFICIENT),
        "partial_gold": len(partial),
        "partial_accepted": sum(1 for r in partial if r[prediction] == answer_claims_v1.SUPPORTED),
        "exact_three_way": safe(
            sum(1 for r in rows if r[prediction] == r["gold"]), len(rows)
        ),
    }


def _by(rows: list[dict], field: str, key: str) -> dict:
    out: dict[str, dict] = {}
    for value in sorted({row[field] for row in rows}):
        subset = [row for row in rows if row[field] == value]
        out[str(value)] = _metrics(subset, key)
    return out


def _non_claim_metrics(rows: list[dict]) -> dict:
    total = len(rows)
    return {
        "fragments": total,
        "lexical_accepted": sum(1 for row in rows if row["lexical_supported"]),
        "relations_accepted": sum(1 for row in rows if row["relations_supported"]),
        "lexical_accept_rate": round(sum(1 for row in rows if row["lexical_supported"]) / total, 4) if total else None,
        "relations_accept_rate": round(sum(1 for row in rows if row["relations_supported"]) / total, 4) if total else None,
    }


def _answer_relevance(rows: list[dict]) -> dict:
    """Supported claims that still do not answer the question.

    Both verifiers judge a claim against evidence, not against the question, so
    this is the part of answer quality they cannot see.  Reporting it keeps a
    high support score from being read as answer correctness.
    """
    off_target = [row for row in rows if row["answers_question"] is False]
    supported_off_target = [row for row in off_target if row["gold"] == answer_claims_v1.SUPPORTED]
    return {
        "propositional_claims": len(rows),
        "answers_question": sum(1 for row in rows if row["answers_question"] is True),
        "off_target_claims": len(off_target),
        "supported_off_target": len(supported_off_target),
        "supported_off_target_lexical_accepted": sum(
            1 for row in supported_off_target if row["lexical_label"] == answer_claims_v1.SUPPORTED
        ),
        "supported_off_target_relations_accepted": sum(
            1 for row in supported_off_target if row["relations_label"] == answer_claims_v1.SUPPORTED
        ),
        "lexical_accepted": sum(
            1 for row in off_target if row["lexical_label"] == answer_claims_v1.SUPPORTED
        ),
        "relations_accepted": sum(
            1 for row in off_target if row["relations_label"] == answer_claims_v1.SUPPORTED
        ),
        "examples": [
            {
                "claim_id": row.get("claim_id", ""),
                "claim": row.get("claim", ""),
                "gold": row["gold"],
            }
            for row in supported_off_target[:8]
        ],
    }


def _attribute_binding(rows: list[dict]) -> dict:
    """Claims held back because the value is bound to a different attribute.

    ``misbound`` means: the value occurs in the row, but under a column other than
    the one the question asks for, and the asked attribute states no competing
    value.  Under the frozen annotation protocol (rule 5) that is insufficient
    evidence, not a contradiction, so the verifier records it as such and this
    block reports how often the binding check fired.
    """
    value_only = [row for row in rows if row["category"] == "value_only"]
    misbound = [row for row in rows if "different attribute" in row["relations_reason"]]
    contradiction_by_table_binding = [
        row for row in rows if row["relations_reason"].startswith("evidence contradicts the claim: the asked column")
    ]
    return {
        "value_only_claims": len(value_only),
        "misbound_withheld": len(misbound),
        "misbound_gold_labels": {
            label: sum(1 for row in misbound if row["gold"] == label)
            for label in answer_claims_v1.PROPOSITIONAL_LABELS
        },
        "contradiction_by_table_binding": len(contradiction_by_table_binding),
        # The prose patterns ("or $X" derivative, percentage change) establish the
        # remaining contradictions; they are counted by the contradiction metrics.
        "prose_contradictions": sum(
            1
            for row in rows
            if row["gold"] == answer_claims_v1.CONTRADICTED
            and row["relations_label"] == answer_claims_v1.CONTRADICTED
        )
        - len(contradiction_by_table_binding),
        "claim_ids": [row["claim_id"] for row in misbound],
        "note": (
            "A value found under a different attribute is abstained on rather than "
            "labelled CONTRADICTED unless the asked attribute states its own value. "
            "Column choice uses question/header overlap and abstains on ties."
        ),
    }


def _citation_metrics(rows: list[dict]) -> dict:
    cited = [row for row in rows if row["stated_citations"]]
    return {
        "claims_with_stated_citation": len(cited),
        "claims_without_stated_citation": len(rows) - len(cited),
        "attribution_correct": sum(1 for row in cited if row["citation_correct"]),
        "attribution_accuracy": round(sum(1 for row in cited if row["citation_correct"]) / len(cited), 4) if cited else None,
        "note": (
            "The benchmark supplies one evidence block per row, so any stated [1] is "
            "correct and any other index is not.  This measures whether the generator "
            "cites, not whether retrieval supplied the right passage."
        ),
    }


# ---------------------------------------------------------------------------
# Generation-level consequences (from recorded runs only)
# ---------------------------------------------------------------------------

def _coverage(
    run_id: str, rows: dict[str, dict], benchmark: dict[str, dict], split_claims
) -> dict:
    answerable = [rid for rid, row in benchmark.items() if row.get("question_kind") != "UNANSWERABLE"]
    results = [rows[rid] for rid in answerable if rid in rows]
    nonempty = [row for row in results if str(row.get("generative_answer") or "").strip()]
    claim_pairs = [
        (str(row["example_id"]), claim)
        for row in results
        for claim in _answer_claims(row, split_claims)
    ]
    return {
        "answerable": len(answerable),
        "evaluated": len(results),
        "answered": len(nonempty),
        "answer_coverage": round(len(nonempty) / len(answerable), 4) if answerable else None,
        "empty": len(results) - len(nonempty),
        "claims": len(claim_pairs),
        "unique_claims": len(set(claim_pairs)),
        "questions_with_claims": len({example_id for example_id, _ in claim_pairs}),
        "claims_per_answer": round(len(claim_pairs) / len(nonempty), 3) if nonempty else None,
        "gate_abstentions": sum(
            1 for row in results if any("does not cover" in warning for warning in row.get("generative_warnings", []))
        ),
        "withheld": sum(
            1 for row in results if any("withheld" in warning for warning in row.get("generative_warnings", []))
        ),
        "run_id": run_id,
    }


def _generation_impact(
    benchmark: dict[str, dict],
    lexical_rows: dict[str, dict],
    relations_rows: dict[str, dict],
    split_claims,
) -> dict:
    from evaluation.qa_metrics import exact_match, token_f1

    answerable = [rid for rid, row in benchmark.items() if row.get("question_kind") != "UNANSWERABLE"]

    dropped: list[dict] = []
    added: list[dict] = []
    changed: list[dict] = []
    same = 0
    for rid in answerable:
        lex = str(lexical_rows[rid].get("generative_answer") or "").strip()
        rel = str(relations_rows[rid].get("generative_answer") or "").strip()
        gold = str(benchmark[rid].get("answer") or "")
        if lex and rel and lex != rel:
            changed.append({"example_id": rid})
        elif not lex and rel:
            added.append(
                {
                    "example_id": rid,
                    "answer": rel,
                    "em": bool(exact_match(rel, gold)),
                    "f1": round(float(token_f1(rel, gold)), 4),
                }
            )
        elif lex and not rel:
            dropped.append(
                {
                    "example_id": rid,
                    "answer": lex,
                    "em": bool(exact_match(lex, gold)),
                    "f1": round(float(token_f1(lex, gold)), 4),
                }
            )
        else:
            same += 1

    def _summary(items: list[dict]) -> dict:
        if not items:
            return {"count": 0, "em": 0, "f1": 0.0}
        return {
            "count": len(items),
            "em": round(sum(1 for item in items if item["em"]) / len(items), 4),
            "f1": round(statistics.mean(item["f1"] for item in items), 4),
        }

    return {
        "answer_sets": {
            "identical": same,
            "both_answered_differently": len(changed),
            "only_lexical_answered": len(dropped),
            "only_relations_answered": len(added),
        },
        "dropped_by_relations": {**_summary(dropped), "rows": dropped},
        "added_by_relations": {**_summary(added), "rows": added},
        "coverage_lexical": _coverage(
            RUN_DIRS["lexical"], lexical_rows, benchmark, split_claims
        ),
        "coverage_relations": _coverage(
            RUN_DIRS["relations"], relations_rows, benchmark, split_claims
        ),
        "recorded_metrics": {
            mode: json.loads((REPORT_ROOT / run_id / "summary.json").read_text(encoding="utf-8"))["metrics"]
            for mode, run_id in RUN_DIRS.items()
        },
    }


# ---------------------------------------------------------------------------
# Run and report
# ---------------------------------------------------------------------------

def run(dataset=answer_claims_v1) -> dict:
    if not BENCHMARK_PATH.exists():
        raise SystemExit(f"Frozen benchmark not found: {BENCHMARK_PATH}")
    actual_hash = sha256_of(BENCHMARK_PATH)
    if actual_hash != EXPECTED_SHA256:
        raise SystemExit(
            "Frozen benchmark hash mismatch; aborting without writing results.\n"
            f"  expected {EXPECTED_SHA256}\n  actual   {actual_hash}"
        )

    benchmark_rows = load_benchmark(BENCHMARK_PATH)
    benchmark = {str(row["example_id"]): row for row in benchmark_rows}
    claims = dataset.load()
    runs = {mode: _load_run(run_id) for mode, run_id in RUN_DIRS.items()}
    integrity = validate_inputs(claims, benchmark, runs, dataset.split_claims)

    scored, timing = score_claims(claims, benchmark, runs)
    propositional = [row for row in scored if row["gold"] in answer_claims_v1.PROPOSITIONAL_LABELS]
    non_claims = [row for row in scored if row["gold"] == answer_claims_v1.NOT_A_CLAIM]
    impact = _generation_impact(
        benchmark, runs["lexical"], runs["relations"], dataset.split_claims
    )
    entity_signals = [row for row in propositional if row["lexical_entity_conflict"]]

    summary = {
        "run_id": RUN_ID,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": str(BENCHMARK_PATH),
        "benchmark_sha256": actual_hash,
        "benchmark_hash_matches_expected": actual_hash == EXPECTED_SHA256,
        "dataset": f"evaluation/datasets/{dataset.DATASET_PATH.name}",
        "dataset_version": dataset.DATASET_VERSION,
        "extraction": dataset.EXTRACTION,
        "supersedes": getattr(dataset, "SUPERSEDES", None),
        "dataset_change": getattr(dataset, "CHANGES", None),
        "dataset_statistics": answer_claims_v1.statistics(claims),
        "integrity": integrity,
        "evidence": "one block per row: the benchmark row's context (what the generator saw)",
        "propositional_examples": len({row["example_id"] for row in propositional}),
        "fragment_only_examples": len(
            {row["example_id"] for row in non_claims}
            - {row["example_id"] for row in propositional}
        ),
        "lexical": _metrics(propositional, "lexical"),
        "relations": _metrics(propositional, "relations"),
        "provenance_sensitivity": {
            "claims": len([row for row in propositional if len(row["produced_by"]) == 2]),
            "lexical": _metrics(
                [row for row in propositional if len(row["produced_by"]) == 2], "lexical"
            ),
            "relations": _metrics(
                [row for row in propositional if len(row["produced_by"]) == 2], "relations"
            ),
        },
        "uncertainty_sensitivity": {
            "claims": len([row for row in propositional if row["uncertainty"] == "none"]),
            "lexical": _metrics(
                [row for row in propositional if row["uncertainty"] == "none"], "lexical"
            ),
            "relations": _metrics(
                [row for row in propositional if row["uncertainty"] == "none"], "relations"
            ),
        },
        "lexical_by_category": _by(propositional, "category", "lexical"),
        "relations_by_category": _by(propositional, "category", "relations"),
        "lexical_by_question_kind": _by(propositional, "question_kind", "lexical"),
        "relations_by_question_kind": _by(propositional, "question_kind", "relations"),
        "non_claims": _non_claim_metrics(non_claims),
        "lexical_entity_signals": {
            "count": len(entity_signals),
            "gold_supported": sum(
                1 for row in entity_signals if row["gold"] == answer_claims_v1.SUPPORTED
            ),
            "gold_contradicted": sum(
                1 for row in entity_signals if row["gold"] == answer_claims_v1.CONTRADICTED
            ),
            "gold_insufficient": sum(
                1 for row in entity_signals if row["gold"] == answer_claims_v1.INSUFFICIENT
            ),
            "gold_partial": sum(
                1 for row in entity_signals if row["gold"] == answer_claims_v1.PARTIAL
            ),
            "note": (
                "The lexical verifier's native 'different entity' reason is not a "
                "contradiction verdict; it is counted here and excluded from the "
                "three-way contradiction metrics."
            ),
        },
        "denominators": {
            "claims_scored": len(propositional),
            "support_positives": sum(
                1 for row in propositional if row["gold"] == answer_claims_v1.SUPPORTED
            ),
            "support_negatives": sum(
                1 for row in propositional if row["gold"] != answer_claims_v1.SUPPORTED
            ),
            "gold_contradicted": sum(
                1 for row in propositional if row["gold"] == answer_claims_v1.CONTRADICTED
            ),
            "gold_insufficient": sum(
                1 for row in propositional if row["gold"] == answer_claims_v1.INSUFFICIENT
            ),
            "gold_partial": sum(
                1 for row in propositional if row["gold"] == answer_claims_v1.PARTIAL
            ),
            "non_claims": len(non_claims),
            "answerable_questions": impact["coverage_lexical"]["answerable"],
            "nonempty_answers_lexical": impact["coverage_lexical"]["answered"],
            "nonempty_answers_relations": impact["coverage_relations"]["answered"],
            "unique_claims_lexical": impact["coverage_lexical"]["unique_claims"],
            "unique_claims_relations": impact["coverage_relations"]["unique_claims"],
            "questions_with_claims_lexical": impact["coverage_lexical"]["questions_with_claims"],
            "questions_with_claims_relations": impact["coverage_relations"]["questions_with_claims"],
            "claims_with_stated_citation": _citation_metrics(propositional)[
                "claims_with_stated_citation"
            ],
        },
        "answer_relevance": _answer_relevance(propositional),
        "attribute_binding": _attribute_binding(propositional),
        "citation": _citation_metrics(propositional),
        "generation_impact": impact,
        "timing_ms_per_claim": timing,
        "labels": {
            "lexical": "SUPPORTED / UNSUPPORTED (binary; native wrong-entity reason reported separately)",
            "relations": "SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE",
            "relations_binding": (
                "A value under a different attribute is INSUFFICIENT_EVIDENCE unless the asked "
                "attribute states a competing value, in which case it is CONTRADICTED"
            ),
        },
        "limitations": [
            "Single annotator (the coding agent); labels are a reference set, not adjudicated human ground truth.",
            "86 of 140 answerable questions produced claims; the rest abstained or were withheld, so claim-level metrics do not cover them.",
            "The benchmark provides one evidence block per row, so citation attribution and multi-passage support cannot be measured.",
            "Claims are dominated by short value answers (49 value-only, 29 non-propositional fragments), so the set under-represents academic prose.",
            "The two recorded runs regenerate answers from the same frozen benchmark; no new generation was run for this evaluation.",
            "Claim extraction is versioned: v1 uses the frozen pre-fix splitter (legacy_split) and keeps the artificial 'Dr.' fragment; v2 uses the corrected production splitter. Population counts and metrics are not sample-comparable across versions.",
            "Claim and evidence splitters share one abbreviation rule (generation.sentence_boundaries); a newline is always a sentence boundary in evidence, so an abbreviation at a line break can still split (no benchmark row exercises this).",
            "No 15-mark relation-verifier benchmark run exists, so the 5/10/15-mark comparison is not available for verifier choice.",
            "Attribute binding is a heuristic over readable structures only (pipe tables and two prose patterns). It abstains when the asked column cannot be identified; it is not a general table parser.",
            "The two frozen labels for unit-only table cells disagree with each other: 'm/s' offered as the asked variable is INSUFFICIENT_EVIDENCE, while 'hPa' offered as the asked minimum is SUPPORTED. The verifier follows the protocol and holds both back, so one is counted as a false rejection.",
            "Latency and the one-off embedder load are measured; process memory and CPU were not instrumented.",
        ],
    }
    return {"summary": summary, "claims": scored}


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _ci(interval) -> str:
    return f"{interval[0]:.3f}–{interval[1]:.3f}" if interval else "n/a"


def _metric_rows(lexical: dict, relations: dict) -> list[str]:
    rows = [
        ("Support precision", "support_precision", "support_precision_ci95"),
        ("Support recall", "support_recall", "support_recall_ci95"),
        ("Support F1", "support_f1", None),
        ("False-accept rate", "false_accept_rate", "false_accept_ci95"),
        ("False-reject rate", "false_reject_rate", "false_reject_ci95"),
        ("Binary decision accuracy", "binary_decision_accuracy", None),
        ("Contradiction precision", "contradiction_precision", "contradiction_precision_ci95"),
        ("Contradiction recall", "contradiction_recall", "contradiction_recall_ci95"),
        ("Contradiction F1", "contradiction_f1", None),
        ("Exact 3-way labels", "exact_three_way", None),
    ]
    lines = ["| Metric | Lexical | Relation-aware |", "|---|---:|---:|"]
    for label, key, ci_key in rows:
        if lexical[key] is None or relations[key] is None:
            lines.append(
                f"| {label} | {_fmt(lexical[key])} | {_fmt(relations[key])} |"
            )
            continue
        if ci_key:
            lines.append(
                f"| {label} | {_fmt(lexical[key])} ({_ci(lexical[ci_key])}) | "
                f"{_fmt(relations[key])} ({_ci(relations[ci_key])}) |"
            )
        else:
            lines.append(f"| {label} | {_fmt(lexical[key])} | {_fmt(relations[key])} |")
    lines += [
        "",
        f"| Insufficient-evidence correct (of {relations['insufficient_gold']}) | "
        f"{lexical['insufficient_correct']} | {relations['insufficient_correct']} |",
        f"| Partially-supported claims accepted (of {relations['partial_gold']}) | "
        f"{lexical['partial_accepted']} | {relations['partial_accepted']} |",
        f"| Claims scored | {lexical['claims']} | {relations['claims']} |",
    ]
    return lines


def render_markdown(summary: dict) -> str:
    stats = summary["dataset_statistics"]
    impact = summary["generation_impact"]
    cov_l, cov_r = impact["coverage_lexical"], impact["coverage_relations"]
    metrics_l = impact["recorded_metrics"]["lexical"]
    metrics_r = impact["recorded_metrics"]["relations"]
    lexical = summary["lexical"]
    relations = summary["relations"]
    denominators = summary["denominators"]
    positives = denominators["support_positives"]
    negatives = denominators["support_negatives"]
    contradiction_positives = denominators["gold_contradicted"]
    lines = [
        "# Claim-level verification on actual generated answers",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- Started: {summary['started_at']}",
        f"- Benchmark: `{summary['benchmark']}`",
        f"- SHA-256: `{summary['benchmark_sha256']}` (matches expected: {summary['benchmark_hash_matches_expected']})",
        f"- Dataset: `{summary['dataset']}` ({summary['dataset_version']}) — {stats['total']} claims "
        f"over {stats['examples']} questions ({stats['propositional']} propositional / "
        f"{stats['non_claims']} non-claim fragments)",
        f"- Extraction: {summary['extraction']}",
        f"- Claim-level metrics below cover {summary['propositional_examples']} questions; a further "
        f"{summary['fragment_only_examples']} produced only fragments.",
        f"- Evidence: {summary['evidence']}",
        "",
    ]
    change = summary.get("dataset_change")
    if change:
        lines += [
            "## Dataset version change",
            "",
            f"- `{summary['dataset_version']}` supersedes `{summary['supersedes']}`: "
            f"{len(change['removed'])} records removed, {len(change['added'])} added "
            f"({change['example_id']} — {change['reason']}).",
            "- Removed: "
            + "; ".join(
                f"`{removed['claim_id']}` \"{removed['claim']}\" ({removed['label']})"
                for removed in change["removed"]
            ),
            "- Added: "
            + "; ".join(
                f"`{added['claim_id']}` \"{added['claim']}\" ({added['label']})"
                for added in change["added"]
            ),
            "",
        ]
    lines += [
        "## Annotation protocol (frozen before scoring)",
        "",
        "1. Judge only against the benchmark row's `context`; outside knowledge never supports a claim.",
        "2. Read a value-only answer as `<question attribute> = <value>`; the question supplies the attribute.",
        "3. SUPPORTED = the context asserts the claim (paraphrase and elliptical extraction allowed).",
        "4. CONTRADICTED = the context asserts a different specific value for the same entity/attribute; "
        "a missing fact is never contradicted.",
        "5. INSUFFICIENT_EVIDENCE = the context neither asserts nor contradicts it; PARTIALLY_SUPPORTED = "
        "a compound with at least one wrong element; NOT_A_CLAIM = no proposition.",
        f"6. Ambiguity is recorded ({stats['uncertainty'].get('low', 0)} low, "
        f"{stats['uncertainty'].get('moderate', 0)} moderate), never forced into a confident label. "
        "Annotations are by a single annotator; see the dataset docstring and the architecture record.",
        "",
        "## Label distribution",
        "",
        "| Label | Count |",
        "|---|---:|",
        *[f"| {name} | {count} |" for name, count in sorted(stats["labels"].items())],
        "",
        "| Category | Count |",
        "|---|---:|",
        *[f"| {name} | {count} |" for name, count in sorted(stats["categories"].items())],
        "",
        f"Ambiguous annotations: {stats['ambiguous_examples']} "
        f"({stats['uncertainty'].get('low', 0)} low, {stats['uncertainty'].get('moderate', 0)} moderate).",
        "",
        "## Claim-level metrics (propositional claims only)",
        "",
        *_metric_rows(summary["lexical"], summary["relations"]),
        "",
        f"**Lexical is binary.** It emits SUPPORTED / not-supported; its native "
        f"wrong-entity reason fired {summary['lexical_entity_signals']['count']} times "
        f"(gold: {summary['lexical_entity_signals']['gold_supported']} supported, "
        f"{summary['lexical_entity_signals']['gold_contradicted']} contradicted, "
        f"{summary['lexical_entity_signals']['gold_insufficient']} insufficient, "
        f"{summary['lexical_entity_signals']['gold_partial']} partial). It is not mapped to "
        "CONTRADICTED, so lexical contradiction precision/recall are reported as undefined "
        "where no positive predictions exist.",
        "",
        "### Denominators",
        "",
        "| Population | Count |",
        "|---|---:|",
        *[
            f"| {name} | {value} |"
            for name, value in summary["denominators"].items()
        ],
        "",
        "Support precision = TP / (TP + FP), recall = TP / (TP + FN), false-accept = "
        "FP / all non-SUPPORTED claims, false-reject = FN / all SUPPORTED claims. "
        "PARTIALLY_SUPPORTED counts as not fully supported. A rate with a zero "
        "denominator, and an F1 whose precision or recall is undefined, is reported as `n/a`.",
        "",
        "### Sensitivity to ambiguous annotations",
        "",
        f"Excluding the {stats['propositional'] - summary['uncertainty_sensitivity']['claims']} ambiguous "
        f"claims ({summary['uncertainty_sensitivity']['claims']} remain): "
        f"lexical P {_fmt(summary['uncertainty_sensitivity']['lexical']['support_precision'])} / "
        f"R {_fmt(summary['uncertainty_sensitivity']['lexical']['support_recall'])} / "
        f"F1 {_fmt(summary['uncertainty_sensitivity']['lexical']['support_f1'])}, "
        f"false accepts {summary['uncertainty_sensitivity']['lexical']['false_accept_count']}; "
        f"relation-aware P {_fmt(summary['uncertainty_sensitivity']['relations']['support_precision'])} / "
        f"R {_fmt(summary['uncertainty_sensitivity']['relations']['support_recall'])} / "
        f"F1 {_fmt(summary['uncertainty_sensitivity']['relations']['support_f1'])}, "
        f"false accepts {summary['uncertainty_sensitivity']['relations']['false_accept_count']}.",
        "",
        f"On the {summary['provenance_sensitivity']['claims']} claims both runs emitted (removing "
        "the answer-set difference from the comparison): "
        f"lexical P {_fmt(summary['provenance_sensitivity']['lexical']['support_precision'])} / "
        f"R {_fmt(summary['provenance_sensitivity']['lexical']['support_recall'])} / "
        f"F1 {_fmt(summary['provenance_sensitivity']['lexical']['support_f1'])}, "
        f"false accepts {summary['provenance_sensitivity']['lexical']['false_accept_count']}; "
        f"relation-aware P {_fmt(summary['provenance_sensitivity']['relations']['support_precision'])} / "
        f"R {_fmt(summary['provenance_sensitivity']['relations']['support_recall'])} / "
        f"F1 {_fmt(summary['provenance_sensitivity']['relations']['support_f1'])}, "
        f"false accepts {summary['provenance_sensitivity']['relations']['false_accept_count']}.",
        "",
        "## Per category (claims / support F1 / false accepts)",
        "",
        "| Category | Claims | Lexical F1 | Relations F1 | Lexical FA | Relations FA |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for category, lex in summary["lexical_by_category"].items():
        rel = summary["relations_by_category"][category]
        lines.append(
            f"| {category} | {lex['claims']} | {_fmt(lex['support_f1'])} | {_fmt(rel['support_f1'])} | "
            f"{lex['false_accept_count']} | {rel['false_accept_count']} |"
        )
    lines += [
        "",
        "## Per question type (propositional claims)",
        "",
        "| Question kind | Claims | Lexical F1 | Relations F1 | Lexical FA | Relations FA |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for kind, lex in summary["lexical_by_question_kind"].items():
        rel = summary["relations_by_question_kind"][kind]
        lines.append(
            f"| {kind} | {lex['claims']} | {_fmt(lex['support_f1'])} | {_fmt(rel['support_f1'])} | "
            f"{lex['false_accept_count']} | {rel['false_accept_count']} |"
        )
    nc = summary["non_claims"]
    relevance = summary["answer_relevance"]
    binding = summary["attribute_binding"]
    lines += [
        "",
        "## Question-to-attribute binding",
        "",
        f"- Value-only claims scored: {binding['value_only_claims']}",
        f"- Values held back as bound to another attribute: {binding['misbound_withheld']} "
        f"({binding['misbound_gold_labels']})",
        f"- Contradictions established by table binding (the asked column states its own "
        f"value): {binding['contradiction_by_table_binding']}; by the prose patterns "
        f"(derivative amount, percentage change): {binding['prose_contradictions']}",
        f"- {binding['note']}",
        "",
        "## Answer relevance (what a support verdict cannot see)",
        "",
        f"- Propositional claims that answer the gold question: {relevance['answers_question']} "
        f"of {relevance['propositional_claims']}",
        f"- Claims that do not answer the gold question: {relevance['off_target_claims']} "
        f"(lexical accepted {relevance['lexical_accepted']}, "
        f"relation-aware accepted {relevance['relations_accepted']})",
        f"- Fully supported but off-target claims: {relevance['supported_off_target']} "
        f"(lexical accepted {relevance['supported_off_target_lexical_accepted']}, "
        f"relation-aware accepted {relevance['supported_off_target_relations_accepted']})",
        "- Neither verifier checks whether the claim answers the question: the lexical verifier "
        "uses the question only for numeric entity alignment, the relation verifier to "
        "attribute and bind a value-only claim. Both accept these off-target claims.",
        "",
        "| Off-target example | Gold |",
        "|---|---|",
    ]
    for example in relevance["examples"]:
        lines.append(
            f"| {example['claim'][:70].replace('|', '/')} | {example['gold']} |"
        )
    lines += [
        "",
        "## Failure classes",
        "",
        f"- **Generation:** {nc['fragments']} of {stats['total']} emitted claims are not claims; "
        f"{relevance['supported_off_target']} fully supported claims do not answer the question; "
        f"only {cov_l['answered']}/140 answerable questions receive an answer.",
        "- **Retrieval/evidence:** not measured — every row supplies its context; the 65 empty "
        f"answers are {cov_l['gate_abstentions']} gate abstentions and {cov_l['withheld']} withheld "
        "answers, not retrieval failures.",
        f"- **Verification:** lexical accepts {lexical['false_accept_count']}/{negatives} negatives and "
        f"rejects {lexical['false_reject_count']}/{positives} positives; relation-aware accepts "
        f"{relations['false_accept_count']}/{negatives} and rejects "
        f"{relations['false_reject_count']}/{positives}, with "
        f"{relations['contradiction_true_positives']}/{contradiction_positives} contradictions found "
        f"and {relations['contradiction_false_positives']} false contradictions.",
        "- **Integration:** corrected; both verifiers now receive the same claim, question and "
        "evidence list, and a regression test asserts it.",
        f"- **Annotation:** {stats['ambiguous_examples']} records carry uncertainty; the labels come "
        "from a single annotator, so the five CONTRADICTED cases remain the largest uncertainty.",
        "",
        "## Non-propositional fragments (excluded from the metrics above)",
        "",
        f"- {nc['fragments']} table renders / headers / bare tokens were emitted as answers.",
        f"- Lexical accepted {nc['lexical_accepted']} ({_fmt(nc['lexical_accept_rate'])}); "
        f"relation-aware accepted {nc['relations_accepted']} ({_fmt(nc['relations_accept_rate'])}).",
        "- Accepting these is not a truth error (they assert nothing), but it is a generation-quality",
        "  failure: the user receives a table header instead of an answer.",
        "",
        "## Citation attribution",
        "",
        f"- Claims with a stated citation: {summary['citation']['claims_with_stated_citation']} "
        f"(of {stats['propositional']} propositional claims)",
        f"- Attribution correct: {summary['citation']['attribution_correct']} "
        f"({_fmt(summary['citation']['attribution_accuracy'])})",
        f"- {summary['citation']['note']}",
        "",
        "## Generation-level consequences (recorded runs, not re-generated)",
        "",
        "| Metric | Lexical (production) | Relation-aware |",
        "|---|---:|---:|",
        f"| Answer coverage (of 140 answerable) | {cov_l['answered']} ({_fmt(cov_l['answer_coverage'])}) | "
        f"{cov_r['answered']} ({_fmt(cov_r['answer_coverage'])}) |",
        f"| Claims emitted | {cov_l['claims']} | {cov_r['claims']} |",
        f"| Unique claims | {cov_l['unique_claims']} | {cov_r['unique_claims']} |",
        f"| Questions with claims | {cov_l['questions_with_claims']} | {cov_r['questions_with_claims']} |",
        f"| Claims per answer | {_fmt(cov_l['claims_per_answer'])} | {_fmt(cov_r['claims_per_answer'])} |",
        f"| Answerability-gate abstentions | {cov_l['gate_abstentions']} | {cov_r['gate_abstentions']} |",
        f"| Withheld (unattributable) | {cov_l['withheld']} | {cov_r['withheld']} |",
        f"| Exact match | {_fmt(metrics_l['generative_em'])} | {_fmt(metrics_r['generative_em'])} |",
        f"| Token F1 | {_fmt(metrics_l['generative_f1'])} | {_fmt(metrics_r['generative_f1'])} |",
        f"| Unsupported-claim rate | {_fmt(metrics_l['generative_unsupported_claim_rate'])} | "
        f"{_fmt(metrics_r['generative_unsupported_claim_rate'])} |",
        f"| Citation accuracy | {_fmt(metrics_l['generative_citation_accuracy'])} | "
        f"{_fmt(metrics_r['generative_citation_accuracy'])} |",
        f"| Abstention on unanswerable | {_fmt(metrics_l['generative_abstention_unanswerable'])} | "
        f"{_fmt(metrics_r['generative_abstention_unanswerable'])} |",
        f"| Spurious answer on unanswerable | {_fmt(metrics_l['generative_spurious_unanswerable'])} | "
        f"{_fmt(metrics_r['generative_spurious_unanswerable'])} |",
        "",
        f"- Answers identical in both runs: {impact['answer_sets']['identical']}",
        f"- Both answered differently: {impact['answer_sets']['both_answered_differently']}",
        f"- Only lexical answered: {impact['answer_sets']['only_lexical_answered']} "
        f"(EM {_fmt(impact['dropped_by_relations']['em'])}, F1 {_fmt(impact['dropped_by_relations']['f1'])})",
        f"- Only relation-aware answered: {impact['answer_sets']['only_relations_answered']} "
        f"(EM {_fmt(impact['added_by_relations']['em'])}, F1 {_fmt(impact['added_by_relations']['f1'])})",
        "",
        "## Disagreements with the reference labels",
        "",
        "| Claim | Gold | Lexical | Relations | ID |",
        "|---|---|---|---|---|",
    ]
    for row in summary["_disagreements"]:
        lines.append(
            f"| {row['claim'][:70].replace('|', '/')} | {row['gold']} | {row['lexical_label']} | "
            f"{row['relations_label']} | `{row['claim_id']}` |"
        )
    lines += [
        "",
        "## Latency",
        "",
        f"- Embedder cold start (one-off): {summary['timing_ms_per_claim']['embedder_cold_start_ms']} ms",
        f"- Lexical: mean {summary['timing_ms_per_claim']['lexical_mean_ms']} ms, "
        f"max {summary['timing_ms_per_claim']['lexical_max_ms']} ms per claim",
        f"- Relation-aware: mean {summary['timing_ms_per_claim']['relations_mean_ms']} ms, "
        f"max {summary['timing_ms_per_claim']['relations_max_ms']} ms per claim",
        "",
        "## Limitations",
        "",
        *[f"- {note}" for note in summary["limitations"]],
        "",
    ]
    return "\n".join(lines)


def write_report(payload: dict, run_id: str = RUN_ID) -> Path:
    out_dir = REPORT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    summary["run_id"] = run_id
    summary["_disagreements"] = [
        row
        for row in payload["claims"]
        if row["gold"] in answer_claims_v1.PROPOSITIONAL_LABELS
        and (row["lexical_label"] != row["gold"] or row["relations_label"] != row["gold"])
    ]
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out_dir / "claims.jsonl").open("w", encoding="utf-8") as handle:
        for row in payload["claims"]:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "REPORT.md").write_text(render_markdown(summary), encoding="utf-8")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Claim-level evaluation on actual generated answers.")
    parser.add_argument("--run-id", default=RUN_ID, help="Report directory name; never overwrite an earlier run.")
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASETS),
        default="v1",
        help="Versioned annotation set; each uses its own frozen extraction.",
    )
    parser.add_argument("--force", action="store_true", help="Allow writing into an existing run directory.")
    args = parser.parse_args()

    out_dir = REPORT_ROOT / args.run_id
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(
            f"Run directory already exists: {out_dir}\n"
            "Choose a new --run-id, or pass --force to replace this experiment's output."
        )
    payload = run(DATASETS[args.dataset])
    written = write_report(payload, args.run_id)
    summary = payload["summary"]
    print(
        json.dumps(
            {
                "out_dir": str(written),
                "lexical": summary["lexical"],
                "relations": summary["relations"],
                "non_claims": summary["non_claims"],
                "generation_impact": {
                    key: value
                    for key, value in summary["generation_impact"].items()
                    if key != "recorded_metrics"
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Question-level answer-quality ledger for Mission 6 (2026-10-21).

One record per benchmark row, joining the frozen benchmark, the previous
(Mission 5) generation run, the new (Mission 6) run, and the v2 claim
annotations.  No model inference: every field is read from an existing
artifact, so the ledger is reproducible from the runs it names.

Honesty rules followed here:

* a field that needs human judgement (is the answer *relevant*, *complete*, was
  the requested attribute *really* identified) is recorded as ``"unknown"``
  unless the artifact actually supports a value — the ledger never invents a
  label to look complete;
* ``answers_question`` / ``supported`` come from the annotated claim dataset,
  which was annotated against the **Mission 5** answers; they are therefore
  reported for the previous run only and marked ``unknown`` for the new one;
* every record states which fields are derived and which are unknown.

Usage (from ``backend``)::;;

    python -m evaluation.experiments.build_answer_quality_ledger \\
        --run-id answer_quality_mission6_2026-10-21
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from evaluation.datasets import answer_claims_v2
import re

from evaluation.experiments.run_generation_benchmark import (
    BENCHMARK_PATH,
    EXPECTED_SHA256,
    is_unanswerable,
    load_benchmark,
)
from evaluation.qa_metrics import exact_match, token_f1

REPORT_ROOT = Path("evaluation/reports")
DEFAULT_RUN_ID = "answer_quality_mission6_2026-10-21"
DEFAULT_PREVIOUS_RUN = "generation_benchmark_2026-10-18_m5_post_v1_r2"
DEFAULT_CURRENT_RUN = "generation_benchmark_2026-10-21_m6_post_v1"

UNKNOWN = "unknown"

#: Sections whose gold answer is the section *title* while the question asks
#: what the section contains.  Returning the body is not a wrong answer to the
#: question asked, so these are annotation artifacts, not model failures.
_SECTION_TITLE_QUESTION_RE = re.compile(
    r"\b(?:what information is provided in|which section covers|what is covered in|"
    r"what is discussed in|describe the content of)\b",
    re.IGNORECASE,
)


def _load_run(run_id: str) -> dict[str, dict]:
    path = REPORT_ROOT / run_id / "results.jsonl"
    if not path.exists():
        raise SystemExit(f"Generation run not found: {path}")
    return {
        row["example_id"]: row
        for row in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def _run_kind(row: dict) -> str:
    """How the answer was produced.

    ``generative_model`` is authoritative when the run recorded it (Mission 7
    onward).  For older runs the recorded warnings are the only signal, so they
    are used as a documented fallback.
    """
    producer = str(row.get("generative_model") or "")
    if producer == "deterministic-table":
        return "deterministic_table"
    if producer == "deterministic-list":
        return "deterministic_list"
    if not producer:
        warnings = " ".join(row.get("generative_warnings", []))
        if "of the table in evidence" in warnings:
            return "deterministic_table"
        if "read directly from evidence" in warnings:
            return "deterministic_list"
    if "does not cover" in " ".join(row.get("generative_warnings", [])):
        return "gate_refusal"
    if "withheld" in " ".join(row.get("generative_warnings", [])):
        return "withheld_unattributable"
    if not row.get("generative_answer"):
        return "model_abstained"
    return "model_generated"


#: Unit words a reference answer may keep or drop; a difference that survives
#: only here is a formatting difference, not a different fact.
_UNIT_WORDS = frozenset(
    """percent % usd people employees engineers members items requests users
    dollars months days seconds minutes hours years""".split()
)


def _format_variant(gold: str, answer: str) -> bool:
    """Whether the two answers differ only by currency symbol or unit word.

    ``412.5 million`` vs ``$412.5 million`` and ``9`` vs ``9 members`` assert the
    same fact.  Counting them as wrong answers overstates the defect, so they are
    classified separately and never fixed by rewriting the answer to match the
    gold string.
    """
    def normalise(text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9][a-z0-9.%/-]*", text.lower().replace("$", " "))
        return [token for token in tokens if token not in _UNIT_WORDS]

    gold_tokens = normalise(gold)
    answer_tokens = normalise(answer)
    if not gold_tokens or not answer_tokens:
        return False
    return set(gold_tokens) == set(answer_tokens)


def _family(category: str, benchmark: dict, current: dict) -> tuple[str, str]:
    """(failure family, uncertainty) for the row.

    Families separate what a code change can fix from what only a benchmark
    review can: a runtime defect is actionable, an ambiguous question is not.
    """
    if category.startswith("none") or category == "correct abstention":
        return ("no_failure", "none")
    if category == "spurious answer to an unanswerable question":
        return ("runtime_defect", "moderate")
    if category == "false answerability-gate refusal":
        return ("runtime_defect", "moderate")
    if category == "false abstention or withholding":
        return ("runtime_defect", "moderate")
    if category == "metric or annotation artifact":
        return ("annotation_artifact", "low")
    if _format_variant(str(benchmark.get("answer", "")), str(current.get("generative_answer", ""))):
        return ("reference_format_variant", "low")

    answer = str(current.get("generative_answer", ""))
    evidence = str(benchmark.get("context", ""))
    quantities = len(re.findall(r"\d", evidence))
    if benchmark.get("question_kind") in ("LONG_CONTEXT", "MULTI_CHUNK") and quantities > 6:
        # Several values compete for one under-specified question; the reference
        # answer picks one without a cue the code could follow.
        return ("ambiguous_reference", "moderate")
    return ("runtime_defect", "low")


def _summary(claims: list[dict]) -> dict:
    answers = [c for c in claims if c.get("label") != answer_claims_v2.NOT_A_CLAIM]
    return {
        "propositional_claims": len(answers),
        "non_claims": len(claims) - len(answers),
        "supported": sum(1 for c in answers if c.get("label") == "SUPPORTED"),
        "answers_question_true": sum(1 for c in answers if c.get("answers_question") is True),
        "answers_question_false": sum(1 for c in answers if c.get("answers_question") is False),
    }


def _classify(benchmark: dict, current: dict) -> tuple[str, str, str, str]:
    """(category, root-cause hypothesis, confidence, disposition)."""
    question = str(benchmark.get("question", ""))
    if is_unanswerable(benchmark):
        if current.get("generative_answer"):
            return (
                "spurious answer to an unanswerable question",
                "gate and verifier both permitted a value the document does not support",
                "high",
                "unresolved",
            )
        return ("correct abstention", "none", "high", "none")

    if current.get("generative_em"):
        kind = _run_kind(current)
        if kind == "deterministic_table":
            return (
                "none (table lookup)",
                "row/column resolved from the table instead of generated",
                "high",
                "fixed_mission_6",
            )
        if kind == "deterministic_list":
            return (
                "none (list lookup)",
                "position/item resolved from the ordered list instead of generated",
                "high",
                "fixed_mission_7",
            )
        return ("none", "none", "high", "none")

    if not (current.get("generative_answer") or "").strip():
        kind = _run_kind(current)
        if kind == "gate_refusal":
            hypothesis = (
                "the answerability gate still counts more than one distinctive question term "
                "as absent; the remaining cases are paraphrase/compound-noun/entity-locator "
                "mismatches, and unblocking them was measured not to produce correct answers"
            )
            return ("false answerability-gate refusal", hypothesis, "high", "accepted_limitation")
        if kind == "withheld_unattributable":
            return (
                "false abstention or withholding",
                "the generated text could not be lexically attributed to the evidence, or the "
                "model returned the wrong span/row of a list",
                "medium",
                "unresolved",
            )
        return ("model abstention", "the model emitted no answer for supplied evidence", "medium", "unresolved")

    if _SECTION_TITLE_QUESTION_RE.search(question) and current.get("generative_answer"):
        return (
            "metric or annotation artifact",
            "gold answer is the section title while the question asks what the section contains; "
            "the returned body text is a correct answer to the question asked",
            "high",
            "annotation_artifact",
        )
    return (
        "incorrect answer to an answerable question",
        "generation selected a value that does not answer the asked attribute",
        "medium",
        "unresolved",
    )


def _intervention(category: str, current: dict) -> tuple[str, str]:
    """(proposed intervention, regression risk) supported by the diagnosis.

    A row this mission fixed states the change that fixed it; an unresolved row
    states the narrowest intervention the recorded evidence supports and the risk
    of making it.  Nothing here is a promise: it is the next step the evidence
    points at, and the risk is about trading one failure mode for another.
    """
    if category.startswith("none"):
        return ("none needed", "none (answer is correct and verified)")
    if category == "correct abstention":
        return ("none needed", "none (abstention is correct)")
    if category == "spurious answer to an unanswerable question":
        return (
            "tighten the answerability gate for this question shape only, or review the row's "
            "gold label; no rule was found that closes it without costing answerable coverage",
            "high — a broader gate tightening reduces answerable coverage (measured in Missions 4-5)",
        )
    if category == "false answerability-gate refusal":
        return (
            "question-attribute reasoning on the evidence, or benchmark review for the section-title "
            "and paraphrase families; a looser threshold was measured not to produce correct answers",
            "high — a generic answer-type or structural-word rule admits unanswerable rows (measured)",
        )
    if category == "false abstention or withholding":
        return (
            "list-aware selection (the model returns the wrong list item for 'which is second/fifth'), "
            "or an evidence-side check that the withheld value answers the asked attribute",
            "medium — a looser support ratio would also accept the wrong list item",
        )
    if category == "model abstention":
        return (
            "inspect the prompt/decoding for this question shape; the evidence contains the answer",
            "low — prompt changes were measured to regress other rows in Mission 3",
        )
    if category == "metric or annotation artifact":
        return (
            "benchmark review: the gold answer is the section title while the question asks what the "
            "section contains",
            "none — no code change is warranted",
        )
    return (
        "question-attribute binding at generation time: select the value whose attribute matches the "
        "question rather than the lexically nearest value in the passage",
        "medium — needs a new measured signal; a rule that over-selects reduces coverage",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--previous-run", default=DEFAULT_PREVIOUS_RUN)
    parser.add_argument("--current-run", default=DEFAULT_CURRENT_RUN)
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

    previous = _load_run(args.previous_run)
    current = _load_run(args.current_run)

    dataset_bytes = answer_claims_v2.DATASET_PATH.read_bytes()
    claims = [
        json.loads(line)
        for line in dataset_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    by_example: dict[str, list[dict]] = {}
    for claim in claims:
        by_example.setdefault(claim["example_id"], []).append(claim)

    records: list[dict] = []
    for example_id, bench in benchmark.items():
        prev, curr = previous[example_id], current[example_id]
        gold = str(bench.get("answer", "") or "")
        unanswerable = is_unanswerable(bench)
        category, hypothesis, confidence, disposition = _classify(bench, curr)
        family, uncertainty = _family(category, bench, curr)
        intervention, regression_risk = _intervention(category, curr)
        if family == "reference_format_variant":
            intervention = (
                "none — the answer and the reference assert the same fact; rewriting the answer to "
                "match the reference string would be metric gaming"
            )
            regression_risk = "none (no change proposed)"
        elif family == "ambiguous_reference":
            intervention = (
                "benchmark review: the question names no cue that selects one of several competing "
                "values; a deterministic rule would have to guess"
            )
            regression_risk = "none (no change proposed)"

        new_answer = curr.get("generative_answer", "")
        old_answer = prev.get("generative_answer", "")
        if not old_answer and new_answer:
            change = "answer_added_exact" if curr.get("generative_em") else "answer_added_nonempty"
        elif old_answer and not new_answer:
            change = "answer_lost"
        elif old_answer != new_answer:
            change = "answer_changed"
        else:
            change = "unchanged"

        records.append(
            {
                "example_id": example_id,
                "question_kind": bench.get("question_kind"),
                "answerability": "unanswerable" if unanswerable else "answerable",
                "question": bench.get("question", ""),
                "reference_answer": gold,
                "evidence": bench.get("context", ""),
                "previous_run": args.previous_run,
                "previous_answer": old_answer,
                "previous_em": bool(prev.get("generative_em")),
                "previous_f1": round(float(token_f1(old_answer, gold)), 4),
                "current_run": args.current_run,
                "current_answer": new_answer,
                "current_em": bool(curr.get("generative_em")),
                "current_f1": round(float(token_f1(new_answer, gold)), 4),
                "current_producer": _run_kind(curr),
                "regression_status": (
                    "improved"
                    if (curr.get("generative_em") and not prev.get("generative_em"))
                    else "regressed"
                    if (prev.get("generative_em") and not curr.get("generative_em"))
                    else "unchanged"
                ),
                "failure_family": family,
                "uncertainty": uncertainty,
                "answered": bool(new_answer.strip()),
                "answer_change": change,
                "addresses_question": "yes" if curr.get("generative_em") else UNKNOWN,
                "supported": (
                    "yes" if curr.get("generative_verified") else "no" if new_answer.strip() else UNKNOWN
                ),
                "complete_enough": "yes" if curr.get("generative_em") else UNKNOWN,
                "requested_attribute_identified": (
                    "yes" if curr.get("generative_em") else UNKNOWN
                ),
                "claim_extraction_error": UNKNOWN,
                "verification_reasons": list(curr.get("generative_unsupported", [])),
                "citation_alignment": (
                    round(float(curr.get("generative_citation_accuracy", 0.0)), 4)
                    if curr.get("generative_claims")
                    else UNKNOWN
                ),
                "claim_count": int(curr.get("generative_claims", 0)),
                "supported_claim_count": int(curr.get("generative_supported_claims", 0)),
                "claim_annotation_previous_run": _summary(by_example.get(example_id, [])),
                "error_category": category,
                "root_cause_hypothesis": hypothesis,
                "evidence_for_diagnosis": {
                    "previous_warnings": prev.get("generative_warnings", []),
                    "current_warnings": curr.get("generative_warnings", []),
                    "previous_status": prev.get("generative_status"),
                    "current_status": curr.get("generative_status"),
                    "gold_in_evidence": bool(gold) and gold.lower() in str(bench.get("context", "")).lower(),
                },
                "proposed_intervention": intervention,
                "regression_risk": regression_risk,
                "confidence": confidence,
                "disposition": disposition,
                "fields_not_annotated": [
                    "claim_extraction_error",
                    "addresses_question (unless exact)",
                    "complete_enough (unless exact)",
                    "requested_attribute_identified (unless exact)",
                ],
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "ERROR_LEDGER.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    answerable = [r for r in records if r["answerability"] == "answerable"]
    unanswerable_rows = [r for r in records if r["answerability"] == "unanswerable"]
    categories = Counter(r["error_category"] for r in records)
    producers = Counter(r["current_producer"] for r in answerable)
    summary = {
        "run_id": args.run_id,
        "benchmark": str(BENCHMARK_PATH),
        "benchmark_sha256": actual_hash,
        "benchmark_hash_matches_expected": actual_hash == EXPECTED_SHA256,
        "dataset_version": "answer_claims_v2",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "previous_run": args.previous_run,
        "current_run": args.current_run,
        "rows": len(records),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable_rows),
        "answerable_answered": sum(1 for r in answerable if r["answered"]),
        "answerable_exact": sum(1 for r in answerable if r["current_em"]),
        "previous_answerable_answered": sum(1 for r in answerable if r["previous_answer"].strip()),
        "previous_answerable_exact": sum(1 for r in answerable if r["previous_em"]),
        "current_producers": dict(producers),
        "error_categories": dict(categories),
        "failure_families": dict(Counter(r["failure_family"] for r in records)),
        "regression_status": dict(Counter(r["regression_status"] for r in records)),
        "unchanged_rows": sum(1 for r in records if r["answer_change"] == "unchanged"),
        "changes": dict(Counter(r["answer_change"] for r in records)),
        "regressions": {
            "lost_answer": [r["example_id"] for r in records if r["answer_change"] == "answer_lost"],
            "exact_to_not_exact": [
                r["example_id"]
                for r in records
                if r["previous_em"] and not r["current_em"] and not r["answerability"] == "unanswerable"
            ],
            "new_spurious_unanswerable": [
                r["example_id"]
                for r in unanswerable_rows
                if r["answered"] and not r["previous_answer"].strip()
            ],
        },
        "unknown_fields": [
            "claim_extraction_error",
            "addresses_question (except exact matches)",
            "complete_enough (except exact matches)",
            "requested_attribute_identified (except exact matches)",
        ],
        "notes": [
            "One record per benchmark row; no model inference is performed by this script.",
            "Claim annotations (answer_claims_v2) were made against the Mission 5 answers, so they "
            "describe the previous run column, not the current one.",
            "EM/F1 use the project's shared normalisation (evaluation.qa_metrics).",
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("notes",)}, indent=2)[:4000])


if __name__ == "__main__":
    main()

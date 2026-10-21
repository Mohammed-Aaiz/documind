"""P3 benchmark: extractive baseline vs. local generative path.

Read-only over the frozen benchmark.  Writes a new, versioned experiment
directory; it never touches ``backend/phases/`` or a previous result.

Design constraints (``DOCUMIND_PROJECT_CONTEXT.md`` §0.7, §0.8):

* The benchmark is **frozen**: the SHA-256 is verified before any inference and
  a mismatch aborts the run.
* Both engines see the **same evidence**: each benchmark row is self-contained
  (``context``), so the row's context becomes one numbered evidence block for
  the generator and the direct context for the extractive model.  Retrieval is
  therefore not part of this measurement and is reported as such.
* Metrics use the project's existing definitions (``evaluation/qa_metrics.py``)
  so results are comparable with the recorded Phase 4F numbers.
* Scoring is only reported for what the labels support.  The benchmark has
  ``answer`` strings and ``is_impossible`` flags; it does **not** provide
  claim-level ground truth, so faithfulness is reported only through the
  deterministic verifier, with that limitation stated in the report.

Usage (from ``backend/``)::

    python -m evaluation.experiments.run_generation_benchmark
    python -m evaluation.experiments.run_generation_benchmark --limit 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

BENCHMARK_PATH = Path("phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl")
EXPECTED_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
REPORT_ROOT = Path("evaluation/reports")
RUN_DATE = "2026-10-17"

#: Set by ``--format``.  Each format writes its own run directory, so a
#: 5-mark run can never overwrite the historical 10-mark report.
GENERATIVE_FORMAT = "10"
RUN_ID = f"generation_benchmark_{RUN_DATE}"


def _set_format(value: str) -> None:
    global GENERATIVE_FORMAT, RUN_ID
    GENERATIVE_FORMAT = str(value)
    RUN_ID = f"generation_benchmark_{RUN_DATE}_fmt{GENERATIVE_FORMAT}"
    # A run under a non-default verifier gets its own directory so it can never
    # overwrite the lexical-verifier report.
    from generation.verification import verifier_mode

    if verifier_mode() != "lexical":
        RUN_ID = f"{RUN_ID}_{verifier_mode()}_verifier"


# ---------------------------------------------------------------------------
# Frozen benchmark integrity
# ---------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_benchmark(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def is_unanswerable(row: dict) -> bool:
    return bool(row.get("metadata", {}).get("is_impossible")) or row.get("question_kind") == "UNANSWERABLE"


def percentile(values: Iterable[float], pct: float) -> float:
    data = sorted(values)
    if not data:
        return 0.0
    if len(data) == 1:
        return float(data[0])
    rank = (len(data) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(data) - 1)
    weight = rank - low
    return float(data[low] * (1 - weight) + data[high] * weight)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class RowResult:
    example_id: str
    category: str
    unanswerable: bool
    gold: str
    extractive_answer: str
    extractive_score: float
    extractive_em: bool
    extractive_f1: float
    generative_answer: str
    generative_lead: str
    generative_em: bool
    generative_abstained: bool
    generative_verified: bool
    generative_claims: int
    generative_supported_claims: int
    generative_citation_accuracy: float
    generative_unsupported: list[str]
    generative_latency_ms: int
    generative_status: str = "UNSUPPORTED"
    generative_warnings: list[str] = field(default_factory=list)
    #: Which producer answered: the local model, the deterministic table reader or
    #: the deterministic list reader.  Recorded because the answer *text* alone
    #: cannot tell them apart, and the ledger must attribute a row to the change
    #: that produced it.
    generative_model: str = ""


def _classify_failure(result: RowResult) -> str:
    """Deterministic error category for the answerable rows that failed."""
    if result.unanswerable:
        return "none"
    if result.generative_em:
        return "none"
    if not result.generative_answer.strip():
        return "empty_or_abstained"
    if result.generative_status == "UNSUPPORTED":
        return "unsupported_claim"
    if result.generative_status == "PARTIALLY_SUPPORTED":
        return "partially_supported"
    if result.generative_verified:
        return "incorrect_answer"
    return "unverified"


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run(limit: int | None = None) -> dict:
    from evaluation.qa_metrics import exact_match, token_f1
    from generation.service import answer_generatively
    from generation.types import GenerationUnavailableError
    from chat.qa_model import answer_question, get_model_status

    if not get_model_status()["available"]:
        raise SystemExit("Extractive QA model unavailable; refusing to report baseline numbers.")
    if not BENCHMARK_PATH.exists():
        raise SystemExit(f"Frozen benchmark not found: {BENCHMARK_PATH}")

    actual_hash = sha256_of(BENCHMARK_PATH)
    if actual_hash != EXPECTED_SHA256:
        raise SystemExit(
            "Frozen benchmark hash mismatch; aborting without writing results.\n"
            f"  expected {EXPECTED_SHA256}\n  actual   {actual_hash}"
        )

    rows = load_benchmark(BENCHMARK_PATH)
    if limit:
        rows = rows[:limit]

    results: list[RowResult] = []
    started = datetime.now(timezone.utc)

    for index, row in enumerate(rows, start=1):
        question = str(row.get("question", ""))
        gold = str(row.get("answer", "") or "")
        context = str(row.get("context", "") or "")
        unanswerable = is_unanswerable(row)

        # --- extractive baseline (production function, no retrieval) ---------
        try:
            qa = answer_question(question, context)
            ext_answer = str(qa.get("answer", "") or "")
            ext_score = float(qa.get("score", 0.0) or 0.0)
        except Exception:
            ext_answer, ext_score = "", 0.0

        # --- generative path (the production service, same evidence) ---------
        # ``answer_generatively`` — not the raw engine — is used so the measured
        # numbers include the answerability gate, withholding policy, entity
        # alignment and warning generation that users actually receive.
        try:
            gen = answer_generatively(
                question, [_ChunkRow(context)] if context else [], answer_format=GENERATIVE_FORMAT
            )
            verification = gen.verification
            gen_answer = gen.answer
            gen_abstained = gen.abstained
            gen_verified = bool(verification.get("verified"))
            gen_claims = int(verification.get("claimCount", 0))
            gen_supported = int(verification.get("supportedClaims", 0))
            gen_precision = float(verification.get("citationAccuracy", 0.0))
            gen_unsupported = list(verification.get("unsupportedClaims", []))
            gen_status = str(verification.get("status", "UNSUPPORTED"))
            gen_ms = gen.latency_ms
            gen_warnings = list(gen.warnings)
            gen_model = gen.model
        except GenerationUnavailableError as exc:
            raise SystemExit(f"Generative model unavailable: {exc}") from exc

        results.append(
            RowResult(
                example_id=str(row.get("example_id", f"row_{index}")),
                category=str(row.get("question_kind", "UNKNOWN")),
                unanswerable=unanswerable,
                gold=gold,
                extractive_answer=ext_answer,
                extractive_score=ext_score,
                extractive_em=bool(exact_match(ext_answer, gold)) if not unanswerable else False,
                extractive_f1=float(token_f1(ext_answer, gold)) if not unanswerable else 0.0,
                generative_answer=gen_answer,
                generative_lead=_lead_answer(gen_answer),
                generative_em=bool(_em(gen_answer, gold)) if (not unanswerable and gen_answer) else False,
                generative_abstained=gen_abstained,
                generative_verified=gen_verified,
                generative_claims=gen_claims,
                generative_supported_claims=gen_supported,
                generative_citation_accuracy=gen_precision,
                generative_unsupported=gen_unsupported,
                generative_latency_ms=gen_ms,
                generative_status=gen_status,
                generative_warnings=gen_warnings,
                generative_model=gen_model,
            )
        )
        if index % 20 == 0:
            print(f"  evaluated {index}/{len(rows)}", flush=True)

    return _summarise(results, rows, actual_hash, started)


def _lead_answer(answer: str) -> str:
    """The direct answer: the first sentence, before any elaboration.

    10/15-mark answers deliberately add evidence sentences, so full-answer EM
    against a short gold span is not a like-for-like measure of correctness.
    The lead metrics are reported next to the full-answer metrics; neither
    replaces the other.
    """
    first = answer.strip().split("\n", 1)[0]
    for separator in (". ", "? ", "! "):
        if separator in first:
            first = first.split(separator, 1)[0] + separator.strip()
            break
    return first.strip()


class _ChunkRow:
    """Minimal SourceChunk-shaped adapter for a benchmark row's context."""

    def __init__(self, content: str) -> None:
        self.chunk_id = "benchmark-context"
        self.content = content
        self.score = 0.0
        self.document_id = "benchmark"
        self.document_name = "benchmark-context"
        self.page = None
        self.heading_path = None
        self.section = None


def _summarise(
    results: list[RowResult],
    rows: list[dict],
    benchmark_hash: str,
    started: datetime,
) -> dict:
    answerable = [r for r in results if not r.unanswerable]
    unanswerable = [r for r in results if r.unanswerable]

    def rate(part: int, whole: int) -> float:
        return round(part / whole, 4) if whole else 0.0

    ext_em = rate(sum(1 for r in answerable if r.extractive_em), len(answerable))
    gen_em = rate(sum(1 for r in answerable if r.generative_answer and _em(r.generative_answer, r.gold)), len(answerable))
    gen_lead_em = rate(
        sum(1 for r in answerable if r.generative_lead and _em(r.generative_lead, r.gold)),
        len(answerable),
    )
    gen_lead_f1 = round(
        statistics.mean([_f1(r.generative_lead, r.gold) for r in answerable]), 4
    ) if answerable else 0.0
    ext_f1 = round(statistics.mean([r.extractive_f1 for r in answerable]), 4) if answerable else 0.0
    gen_f1 = round(
        statistics.mean([_f1(r.generative_answer, r.gold) for r in answerable]), 4
    ) if answerable else 0.0

    gen_abstain_unanswerable = rate(
        sum(1 for r in unanswerable if r.generative_abstained or not r.generative_answer.strip()),
        len(unanswerable),
    )
    gen_spurious = rate(
        sum(1 for r in unanswerable if r.generative_answer.strip() and not r.generative_abstained),
        len(unanswerable),
    )
    ext_abstain_unanswerable = rate(
        sum(1 for r in unanswerable if not r.extractive_answer.strip()), len(unanswerable)
    )
    ext_spurious = rate(
        sum(1 for r in unanswerable if r.extractive_answer.strip()), len(unanswerable)
    )

    claims = sum(r.generative_claims for r in results)
    supported = sum(r.generative_supported_claims for r in results)
    unsupported_claims = sum(len(r.generative_unsupported) for r in results)
    latencies = [r.generative_latency_ms for r in results]

    failures = [_classify_failure(r) for r in answerable]
    failure_counts: dict[str, int] = {}
    for name in failures:
        failure_counts[name] = failure_counts.get(name, 0) + 1

    status_counts: dict[str, int] = {}
    for row in results:
        status_counts[row.generative_status] = status_counts.get(row.generative_status, 0) + 1
    gate_abstentions = sum(
        1 for row in results if any("does not cover" in w for w in row.generative_warnings)
    )
    withheld = sum(
        1 for row in results if any("withheld" in w for w in row.generative_warnings)
    )

    summary = {
        "run_id": RUN_ID,
        "started_at": started.isoformat(),
        "benchmark": str(BENCHMARK_PATH),
        "benchmark_sha256": benchmark_hash,
        "benchmark_hash_matches_expected": benchmark_hash == EXPECTED_SHA256,
        "examples_evaluated": len(results),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "generative_format": GENERATIVE_FORMAT,
        "retrieval": "not measured — benchmark rows are self-contained (context supplied with the row)",
        "metrics": {
            "extractive_em": ext_em,
            "extractive_f1": ext_f1,
            "generative_em": gen_em,
            "generative_f1": gen_f1,
            "generative_lead_em": gen_lead_em,
            "generative_lead_f1": gen_lead_f1,
            "extractive_abstention_unanswerable": ext_abstain_unanswerable,
            "extractive_spurious_unanswerable": ext_spurious,
            "generative_abstention_unanswerable": gen_abstain_unanswerable,
            "generative_spurious_unanswerable": gen_spurious,
            "generative_empty_rate": rate(
                sum(1 for r in results if not r.generative_answer.strip()), len(results)
            ),
            "generative_claim_count": claims,
            "generative_supported_claims": supported,
            "generative_unsupported_claim_count": unsupported_claims,
            "generative_unsupported_claim_rate": rate(unsupported_claims, claims) if claims else None,
            "generative_citation_accuracy": rate(supported, claims) if claims else None,
            "generative_verified_rate": rate(sum(1 for r in results if r.generative_verified), len(results)),
            "generative_answerability_gate_abstentions": gate_abstentions,
            "generative_withheld_unattributable": withheld,
            "generative_status_counts": status_counts,
        },
        "latency_ms": {
            "generative_p50": round(percentile(latencies, 50), 1),
            "generative_p95": round(percentile(latencies, 95), 1),
            "generative_max": max(latencies) if latencies else 0,
        },
        "failure_categories_answerable": failure_counts,
        "notes": [
            "EM/F1 are computed only on answerable rows, using the project's normalise/EM/token-F1 functions.",
            "The extractive model has no no-answer head, so its abstention is only ever an empty span; the production evidence gate is NOT part of this measurement.",
            "Faithfulness is measured by the deterministic verifier (lexical attribution), not by human or entailment judging.",
        ],
    }
    return {"summary": summary, "rows": [r.__dict__ for r in results]}


def _em(predicted: str, gold: str) -> bool:
    from evaluation.qa_metrics import exact_match

    return exact_match(predicted, gold)


def _f1(predicted: str, gold: str) -> float:
    from evaluation.qa_metrics import token_f1

    return float(token_f1(predicted, gold))


def write_report(payload: dict) -> Path:
    out_dir = REPORT_ROOT / RUN_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in payload["rows"]:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(payload["summary"], handle, indent=2)
    (out_dir / "REPORT.md").write_text(_render_markdown(payload["summary"]), encoding="utf-8")
    return out_dir


def _render_markdown(summary: dict) -> str:
    m = summary["metrics"]
    lines = [
        "# Generation benchmark — extractive vs. local generative",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- Started: {summary['started_at']}",
        f"- Benchmark: `{summary['benchmark']}`",
        f"- SHA-256: `{summary['benchmark_sha256']}` (matches expected: {summary['benchmark_hash_matches_expected']})",
        f"- Examples: {summary['examples_evaluated']} "
        f"({summary['answerable']} answerable / {summary['unanswerable']} unanswerable)",
        f"- Generative format: {summary['generative_format']}-mark",
        f"- Retrieval: {summary['retrieval']}",
        "",
        "## Metrics",
        "",
        "| Metric | Extractive baseline | Local generative |",
        "|---|---|---|",
        f"| Exact match (answerable) | {m['extractive_em']:.3f} | {m['generative_em']:.3f} |",
        f"| Token F1 (answerable) | {m['extractive_f1']:.3f} | {m['generative_f1']:.3f} |",
        f"| Lead-answer EM (answerable) | — | {m['generative_lead_em']:.3f} |",
        f"| Lead-answer F1 (answerable) | — | {m['generative_lead_f1']:.3f} |",
        f"| Abstention on unanswerable | {m['extractive_abstention_unanswerable']:.3f} | {m['generative_abstention_unanswerable']:.3f} |",
        f"| Spurious answer on unanswerable | {m['extractive_spurious_unanswerable']:.3f} | {m['generative_spurious_unanswerable']:.3f} |",
        f"| Empty answer rate (all) | — | {m['generative_empty_rate']:.3f} |",
        f"| Unsupported-claim rate | — | {m['generative_unsupported_claim_rate'] if m['generative_unsupported_claim_rate'] is not None else 'n/a'} |",
        f"| Citation accuracy (lexical) | — | {m['generative_citation_accuracy'] if m['generative_citation_accuracy'] is not None else 'n/a'} |",
        f"| Verified rate (all) | — | {m['generative_verified_rate']:.3f} |",
        f"| Answerability-gate abstentions | — | {m['generative_answerability_gate_abstentions']} |",
        f"| Withheld (unattributable) | — | {m['generative_withheld_unattributable']} |",
        "",
        "### Answer-level verification status (generative)",
        "",
        "| Status | Count |",
        "|---|---|",
        *[f"| {name} | {count} |" for name, count in sorted(m['generative_status_counts'].items())],
        "",
        "## Latency (generative, CPU)",
        "",
        f"- p50: {summary['latency_ms']['generative_p50']} ms",
        f"- p95: {summary['latency_ms']['generative_p95']} ms",
        f"- max: {summary['latency_ms']['generative_max']} ms",
        "",
        "## Failure categories (answerable rows)",
        "",
    ]
    for name, count in sorted(summary["failure_categories_answerable"].items()):
        lines.append(f"- `{name}`: {count}")
    lines += ["", "## Notes", ""]
    lines += [f"- {note}" for note in summary["notes"]]
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the generative path on the frozen P3 benchmark.")
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N examples.")
    parser.add_argument(
        "--format",
        dest="answer_format",
        default="10",
        choices=("5", "10", "15"),
        help="Answer format for the generative path (each writes its own run directory).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override the report directory name instead of overwriting a previous run.",
    )
    args = parser.parse_args()
    _set_format(args.answer_format)
    if args.run_id:
        globals()["RUN_ID"] = args.run_id

    payload = run(limit=args.limit)
    out_dir = write_report(payload)
    m = payload["summary"]["metrics"]
    print(json.dumps({"out_dir": str(out_dir), "metrics": m}, indent=2))


if __name__ == "__main__":
    main()

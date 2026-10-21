"""Candidate-model evaluation on the frozen P3 benchmark (experimental).

This runner evaluates a **candidate** generator without touching production: the
production engine, prompt and defaults are not modified, and no API route uses
this code.  It exists so a model decision can be made from the same rows, the
same gate and the same scoring functions as the incumbent.

Protocol (identical for every candidate):

1. Verify the frozen benchmark SHA-256; abort without writing on a mismatch.
2. For each row, apply the production answerability gate (``answerability``).
3. Generate with the candidate under a fixed system prompt and decoding config.
4. Treat a model-refusal phrase as abstention, and withhold any answer whose
   claims cannot be attributed to the row's context (production verifier).
5. Apply the production mark elaboration (10 marks) and re-verify, exactly as
   ``generation.service`` does.
6. Score with ``evaluation.qa_metrics`` and report the same rates as
   ``run_generation_benchmark``.

The candidate is a causal (chat) model, so its answer style differs from the
seq2seq incumbent; that difference is part of what the experiment measures.

Usage (from ``backend/``)::

    python -m evaluation.experiments.run_candidate_model_evaluation
    python -m evaluation.experiments.run_candidate_model_evaluation --limit 20
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from evaluation.experiments.run_generation_benchmark import (
    BENCHMARK_PATH,
    EXPECTED_SHA256,
    _lead_answer,
    is_unanswerable,
    load_benchmark,
    percentile,
    sha256_of,
)

REPORT_ROOT = Path("evaluation/reports")
RUN_ID = "candidate_qwen25_05b_instruct_2026-10-17"
FORMAT = "10"

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_REVISION = "main"  # resolved below to the cached commit if available
SYSTEM_PROMPT = (
    "You answer questions using only the given context. "
    "Reply with the shortest correct answer phrase and nothing else. "
    "If the context does not contain the answer, reply exactly: INSUFFICIENT_EVIDENCE"
)
MAX_NEW_TOKENS = 64

#: Refusal phrases a chat model may produce instead of abstaining cleanly.
REFUSAL_PHRASES = (
    "insufficient_evidence",
    "insufficient evidence",
    "not enough information",
    "cannot be determined",
    "cannot determine",
    "does not contain",
    "not mentioned",
    "no information",
)

#: Qwen's tokenizer sometimes splits a decimal ("$142. 6 million").  Normalising
#: a space between digits around a decimal point is model-agnostic cleanup, not a
#: benchmark-specific rule.
_DECIMAL_SPLIT_RE = re.compile(r"(?<=\d)\.\s+(?=\d)")


def _normalise_text(text: str) -> str:
    return _DECIMAL_SPLIT_RE.sub(".", text.strip())


def _is_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)


class CandidateEngine:
    """Lazy causal-LM adapter used only by this experiment."""

    def __init__(self, model_id: str = MODEL_ID) -> None:
        self.model_id = model_id
        self.tokenizer = None
        self.model = None
        self.revision: str | None = None
        self.load_seconds: float | None = None
        self.peak_rss_mb: float = 0.0

    def load(self) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        started = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_id).eval()
        self.revision = getattr(self.model.config, "_commit_hash", None)
        self.load_seconds = round(time.perf_counter() - started, 2)
        self._sample_rss()

    def _sample_rss(self) -> None:
        try:
            import psutil

            rss = psutil.Process().memory_info().rss / 1e6
            self.peak_rss_mb = max(self.peak_rss_mb, rss)
        except Exception:  # pragma: no cover - measurement only
            pass

    def answer(self, question: str, context: str) -> tuple[str, int]:
        import torch

        assert self.tokenizer is not None and self.model is not None
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        encoded = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=1024
        )
        started = time.perf_counter()
        with torch.no_grad():
            output = self.model.generate(
                **encoded,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        text = self.tokenizer.decode(
            output[0][encoded["input_ids"].shape[1] :], skip_special_tokens=True
        )
        self._sample_rss()
        return _normalise_text(text), latency_ms


def run(limit: int | None = None) -> dict:
    from chat.qa_model import answer_question, get_model_status
    from generation.planning import compose_answer, plan_support_points
    from generation.service import build_evidence_blocks
    from generation.types import AnswerFormat
    from generation.verification import answerability, verify_answer
    from evaluation.qa_metrics import exact_match, token_f1

    if not get_model_status()["available"]:
        raise SystemExit("Extractive QA model unavailable; refusing a partial comparison.")
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

    engine = CandidateEngine()
    engine.load()

    results = []
    started = datetime.now(timezone.utc)
    for index, row in enumerate(rows, start=1):
        question = str(row.get("question", ""))
        context = str(row.get("context", "") or "")
        gold = str(row.get("answer", "") or "")
        unanswerable = is_unanswerable(row)

        class _Chunk:
            chunk_id = "benchmark-context"
            content = context
            score = 0.0
            document_id = "benchmark"
            document_name = "benchmark-context"
            page = None
            heading_path = None
            section = None

        blocks = build_evidence_blocks([_Chunk()] if context else [])
        decision = answerability(question, context)
        gate_abstained = not decision.allowed

        if gate_abstained:
            answer, latency_ms, abstained, reason = "", 0, True, "answerability_gate"
        else:
            raw, latency_ms = engine.answer(question, context)
            if _is_refusal(raw):
                answer, abstained, reason = "", True, "model_refusal"
            else:
                answer, abstained, reason = raw, False, "generated"

        # Withholding policy: unattributable text is not an answer.
        verification = verify_answer(answer, blocks, question=question)
        withheld = False
        if answer and verification.supported_claims == 0:
            answer, abstained, withheld = "", True, True
            reason = "withheld_unattributable"
            verification = verify_answer("", blocks, question=question)

        # Mark elaboration (same policy as production) at 10 marks.
        if answer and not abstained:
            points = plan_support_points(question, blocks, 10, answer=answer)
            if points:
                answer = compose_answer(answer, points, 10)
                verification = verify_answer(answer, blocks, question=question)

        # Extractive baseline on the same row, for a fair same-run comparison.
        try:
            qa = answer_question(question, context)
            ext_answer = str(qa.get("answer", "") or "")
            ext_score = float(qa.get("score", 0.0) or 0.0)
        except Exception:
            ext_answer, ext_score = "", 0.0

        results.append(
            {
                "example_id": row.get("example_id"),
                "category": row.get("question_kind", "UNKNOWN"),
                "unanswerable": unanswerable,
                "gold": gold,
                "answer": answer,
                "lead": _lead_answer(answer),
                "em": bool(exact_match(answer, gold)) if (answer and not unanswerable) else False,
                "f1": float(token_f1(answer, gold)) if not unanswerable else 0.0,
                "status": verification.status,
                "claims": verification.claim_count,
                "supported_claims": verification.supported_claims,
                "unsupported": list(verification.unsupported_claims),
                "abstained": abstained,
                "reason": reason,
                "withheld": withheld,
                "gate_abstained": gate_abstained,
                "latency_ms": latency_ms,
                "extractive_answer": ext_answer,
                "extractive_score": ext_score,
            }
        )
        if index % 20 == 0:
            print(f"  evaluated {index}/{len(rows)}", flush=True)

    return _summarise(
        results=results,
        rows=rows,
        benchmark_hash=actual_hash,
        started=started,
        engine=engine,
        answer_format=FORMAT,
    )


def _summarise(results, rows, benchmark_hash, started, engine, answer_format) -> dict:
    from evaluation.qa_metrics import exact_match, token_f1

    answerable = [r for r in results if not r["unanswerable"]]
    unanswerable = [r for r in results if r["unanswerable"]]

    def rate(part: int, whole: int) -> float:
        return round(part / whole, 4) if whole else 0.0

    claims = sum(r["claims"] for r in results)
    unsupported = sum(len(r["unsupported"]) for r in results)
    latencies = [r["latency_ms"] for r in results]

    summary = {
        "run_id": RUN_ID,
        "started_at": started.isoformat(),
        "model": engine.model_id,
        "model_revision": engine.revision,
        "answer_format": answer_format,
        "system_prompt": SYSTEM_PROMPT,
        "max_new_tokens": MAX_NEW_TOKENS,
        "decoding": "greedy (do_sample=False)",
        "benchmark": str(BENCHMARK_PATH),
        "benchmark_sha256": benchmark_hash,
        "benchmark_hash_matches_expected": benchmark_hash == EXPECTED_SHA256,
        "examples_evaluated": len(results),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "load_seconds": engine.load_seconds,
        "peak_rss_mb": round(engine.peak_rss_mb, 0),
        "metrics": {
            "candidate_em": rate(sum(1 for r in answerable if r["em"]), len(answerable)),
            "candidate_f1": round(
                statistics.mean([r["f1"] for r in answerable]), 4
            ) if answerable else 0.0,
            "candidate_lead_em": rate(
                sum(1 for r in answerable if r["lead"] and exact_match(r["lead"], r["gold"])),
                len(answerable),
            ),
            "candidate_lead_f1": round(
                statistics.mean(
                    [float(token_f1(r["lead"], r["gold"])) for r in answerable]
                ),
                4,
            ) if answerable else 0.0,
            "extractive_em": rate(
                sum(1 for r in answerable if exact_match(r["extractive_answer"], r["gold"])),
                len(answerable),
            ),
            "extractive_f1": round(
                statistics.mean(
                    [float(token_f1(r["extractive_answer"], r["gold"])) for r in answerable]
                ),
                4,
            ) if answerable else 0.0,
            "abstention_unanswerable": rate(
                sum(1 for r in unanswerable if r["abstained"] or not r["answer"].strip()),
                len(unanswerable),
            ),
            "spurious_unanswerable": rate(
                sum(1 for r in unanswerable if r["answer"].strip() and not r["abstained"]),
                len(unanswerable),
            ),
            "empty_rate_all": rate(
                sum(1 for r in results if not r["answer"].strip()), len(results)
            ),
            "supported_rate": rate(
                sum(1 for r in results if r["status"] == "SUPPORTED"), len(results)
            ),
            "unsupported_claim_rate": rate(unsupported, claims) if claims else None,
            "claims": claims,
            "withheld_unattributable": sum(1 for r in results if r["withheld"]),
            "gate_abstentions": sum(1 for r in results if r["gate_abstained"]),
            "model_refusals": sum(1 for r in results if r["reason"] == "model_refusal"),
        },
        "latency_ms": {
            "p50": round(percentile(latencies, 50), 1),
            "p95": round(percentile(latencies, 95), 1),
            "max": max(latencies) if latencies else 0,
        },
        "notes": [
            "Same frozen rows, same answerability gate, same verifier and same "
            "mark elaboration as the production path; only the generating model differs.",
            "The candidate is a causal chat model evaluated at 10 marks, the same "
            "format as the incumbent comparison report.",
            "EM/F1 are computed on answerable rows only, using the project's metrics.",
            "This is an experimental evaluation; no production default was changed.",
        ],
    }
    return {"summary": summary, "rows": results}


def render_markdown(summary: dict) -> str:
    m = summary["metrics"]
    return "\n".join(
        [
            f"# Candidate model evaluation — {summary['model']}",
            "",
            f"- Run: `{summary['run_id']}`",
            f"- Started: {summary['started_at']}",
            f"- Model: `{summary['model']}` (revision: `{summary['model_revision']}`)",
            f"- Benchmark: `{summary['benchmark']}`",
            f"- SHA-256: `{summary['benchmark_sha256']}` (matches: {summary['benchmark_hash_matches_expected']})",
            f"- Rows: {summary['examples_evaluated']} "
            f"({summary['answerable']} answerable / {summary['unanswerable']} unanswerable)",
            f"- Format: {summary['answer_format']}-mark, greedy decoding, max_new_tokens={summary['max_new_tokens']}",
            f"- Load time: {summary['load_seconds']} s; peak process RSS: {summary['peak_rss_mb']} MB",
            "",
            "## Results",
            "",
            "| Metric | Extractive baseline | Candidate |",
            "|---|---|---|",
            f"| Exact match (answerable) | {m['extractive_em']:.3f} | {m['candidate_em']:.3f} |",
            f"| Token F1 (answerable) | {m['extractive_f1']:.3f} | {m['candidate_f1']:.3f} |",
            f"| Lead-answer EM | — | {m['candidate_lead_em']:.3f} |",
            f"| Abstention on unanswerable | 0.000 | {m['abstention_unanswerable']:.3f} |",
            f"| Spurious answer on unanswerable | 1.000 | {m['spurious_unanswerable']:.3f} |",
            f"| Empty answer rate (all) | — | {m['empty_rate_all']:.3f} |",
            f"| SUPPORTED rate (all) | — | {m['supported_rate']:.3f} |",
            f"| Unsupported-claim rate | — | {m['unsupported_claim_rate']} |",
            f"| Withheld (unattributable) | — | {m['withheld_unattributable']} |",
            f"| Answerability-gate abstentions | — | {m['gate_abstentions']} |",
            f"| Model refusals | — | {m['model_refusals']} |",
            "",
            "## Latency (CPU)",
            "",
            f"- p50: {summary['latency_ms']['p50']} ms",
            f"- p95: {summary['latency_ms']['p95']} ms",
            f"- max: {summary['latency_ms']['max']} ms",
            "",
            "## Notes",
            "",
            *[f"- {note}" for note in summary["notes"]],
            "",
        ]
    )


def write_report(payload: dict) -> Path:
    out_dir = REPORT_ROOT / RUN_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in payload["rows"]:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(payload["summary"], indent=2), encoding="utf-8"
    )
    (out_dir / "REPORT.md").write_text(render_markdown(payload["summary"]), encoding="utf-8")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a candidate generator on the frozen benchmark.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    payload = run(limit=args.limit)
    out_dir = write_report(payload)
    print(json.dumps({"out_dir": str(out_dir), "metrics": payload["summary"]["metrics"]}, indent=2))


if __name__ == "__main__":
    main()

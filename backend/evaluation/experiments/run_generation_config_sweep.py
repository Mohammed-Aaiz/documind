"""Configuration sweep for the current generator (no model replacement).

Before any model download, this asks the cheaper question: does the approved
``google/flan-t5-base`` path improve under a different decoding configuration or
prompt shape?  Every variant is evaluated on the **same frozen P3 rows** with the
same scoring functions and the same answerability gate as production.

Design:

* The benchmark SHA-256 is verified first; a mismatch aborts without writing.
* ``answer_generatively`` is called for every row, so gate, withholding,
  verification and mark elaboration are identical across variants — only the
  swept parameter changes.
* Decoding variants patch ``generation.engine.DECODE_PARAMS`` (production default
  is restored after each variant).
* Prompt variants patch ``generation.engine.build_prompt``.
* Each variant writes its predictions into one report directory; no historical
  report is touched.

Usage (from ``backend/``)::

    python -m evaluation.experiments.run_generation_config_sweep
    python -m evaluation.experiments.run_generation_config_sweep --limit 40
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
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
RUN_ID = "generation_config_sweep_2026-10-17"
FORMAT = "5"


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    decode: dict | None = None
    prompt: str = "default"  # default | context_first | short_answer


VARIANTS: tuple[Variant, ...] = (
    Variant("v0_current", "beams=4, no_repeat_ngram=3 (production default)"),
    Variant("v1_greedy", "beams=1 (greedy)", decode={"num_beams": 1, "no_repeat_ngram_size": 3}),
    Variant(
        "v2_short_answer",
        "beams=4, prompt asks for a short answer phrase",
        prompt="short_answer",
    ),
    Variant(
        "v3_context_first",
        "beams=4, context placed before the question",
        prompt="context_first",
    ),
)


def _patched_build_prompt(original, mode: str):
    """Return a ``build_prompt`` replacement for the given prompt mode."""

    def build(question, plan, blocks):
        prompt = original(question, plan, blocks)
        if mode == "short_answer":
            # Replace only the final depth cue; the evidence block is untouched.
            head, _, _ = prompt.rpartition("\n")
            return head + "\nAnswer with a short phrase:"
        if mode == "context_first":
            text = prompt
            marker = "\nAnswer in one sentence:"
            if marker in text:
                body, _, cue = text.partition(marker)
                lines = body.splitlines()
                question_line = lines[0]
                rest = "\n".join(lines[1:])
                return rest.strip() + "\n\n" + question_line + "\n" + cue.strip()
        return prompt

    return build


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _evaluate_variant(rows: list[dict], variant: Variant) -> dict:
    from generation import engine
    from generation.planning import build_prompt as real_build_prompt
    from generation.service import answer_generatively
    from evaluation.qa_metrics import exact_match, token_f1

    saved_decode = dict(engine.DECODE_PARAMS)
    saved_prompt = engine.build_prompt
    try:
        if variant.decode is not None:
            engine.DECODE_PARAMS.clear()
            engine.DECODE_PARAMS.update(variant.decode)
        if variant.prompt != "default":
            engine.build_prompt = _patched_build_prompt(real_build_prompt, variant.prompt)

        results = []
        for row in rows:
            question = str(row.get("question", ""))
            context = str(row.get("context", "") or "")
            unanswerable = is_unanswerable(row)
            answer = answer_generatively(
                question, [_ChunkRow(context)] if context else [], answer_format=FORMAT
            )
            results.append({"row": row, "result": answer, "unanswerable": unanswerable})
    finally:
        engine.DECODE_PARAMS.clear()
        engine.DECODE_PARAMS.update(saved_decode)
        engine.build_prompt = saved_prompt

    answerable = [item for item in results if not item["unanswerable"]]
    unanswerable_rows = [item for item in results if item["unanswerable"]]

    def _answer(item) -> str:
        return item["result"].answer

    def _gold(item) -> str:
        return str(item["row"].get("answer", "") or "")

    em = sum(exact_match(_answer(i), _gold(i)) for i in answerable) / len(answerable)
    f1 = statistics.mean(token_f1(_answer(i), _gold(i)) for i in answerable)
    lead_em = sum(exact_match(_lead_answer(_answer(i)), _gold(i)) for i in answerable) / len(answerable)
    empty = sum(1 for i in answerable if not _answer(i).strip()) / len(answerable)
    abstain_unanswerable = sum(
        1 for i in unanswerable_rows if not _answer(i).strip() or i["result"].abstained
    ) / len(unanswerable_rows)
    spurious = sum(
        1 for i in unanswerable_rows if _answer(i).strip() and not i["result"].abstained
    ) / len(unanswerable_rows)
    claims = sum(int(i["result"].verification.get("claimCount", 0)) for i in results)
    unsupported = sum(len(i["result"].verification.get("unsupportedClaims", [])) for i in results)
    latencies = [i["result"].latency_ms for i in results]

    summary = {
        "variant": variant.name,
        "description": variant.description,
        "decode": variant.decode or "production default",
        "prompt_mode": variant.prompt,
        "examples": len(results),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable_rows),
        "em": round(em, 4),
        "f1": round(f1, 4),
        "lead_em": round(lead_em, 4),
        "empty_answer_rate_answerable": round(empty, 4),
        "abstention_unanswerable": round(abstain_unanswerable, 4),
        "spurious_unanswerable": round(spurious, 4),
        "unsupported_claim_rate": round(unsupported / claims, 4) if claims else None,
        "latency_p50_ms": round(percentile(latencies, 50), 1),
        "latency_p95_ms": round(percentile(latencies, 95), 1),
    }

    # Per-row predictions are kept so any two variants can be compared pairwise
    # (how many questions does each get right that the other misses?) instead of
    # reading a difference of two answers as an improvement.
    predictions = [
        {
            "example_id": item["row"].get("example_id"),
            "unanswerable": item["unanswerable"],
            "gold": _gold(item),
            "answer": _answer(item),
            "em": exact_match(_answer(item), _gold(item)),
            "f1": round(token_f1(_answer(item), _gold(item)), 4),
            "status": item["result"].verification.get("status"),
        }
        for item in results
    ]
    return summary, predictions


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


def run(limit: int | None = None) -> dict:
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

    started = datetime.now(timezone.utc)
    results = []
    predictions: dict[str, list[dict]] = {}
    for variant in VARIANTS:
        print(f"  running {variant.name} on {len(rows)} rows", flush=True)
        summary, rows_out = _evaluate_variant(rows, variant)
        results.append(summary)
        predictions[variant.name] = rows_out

    pairwise = _pairwise(predictions)

    return {
        "run_id": RUN_ID,
        "started_at": started.isoformat(),
        "benchmark": str(BENCHMARK_PATH),
        "benchmark_sha256": actual_hash,
        "benchmark_hash_matches_expected": actual_hash == EXPECTED_SHA256,
        "answer_format": FORMAT,
        "rows": len(rows),
        "model": "google/flan-t5-base",
        "variants": results,
        "pairwise_vs_current": pairwise,
        "predictions": predictions,
    }


def _pairwise(predictions: dict[str, list[dict]]) -> dict:
    """Answerable-question win/loss counts for every variant against v0."""
    base = {row["example_id"]: row for row in predictions.get("v0_current", [])}
    out: dict[str, dict] = {}
    for name, rows in predictions.items():
        if name == "v0_current":
            continue
        won = lost = 0
        for row in rows:
            if row["unanswerable"]:
                continue
            other = base.get(row["example_id"])
            if other is None:
                continue
            if row["em"] and not other["em"]:
                won += 1
            elif other["em"] and not row["em"]:
                lost += 1
        out[name] = {"correct_only_in_variant": won, "correct_only_in_v0": lost}
    return out


def render_markdown(payload: dict) -> str:
    lines = [
        "# Generation configuration sweep — flan-t5-base",
        "",
        f"- Run: `{payload['run_id']}`",
        f"- Started: {payload['started_at']}",
        f"- Benchmark: `{payload['benchmark']}`",
        f"- SHA-256: `{payload['benchmark_sha256']}` (matches: {payload['benchmark_hash_matches_expected']})",
        f"- Rows: {payload['rows']}, format: {payload['answer_format']}-mark",
        f"- Model: `{payload['model']}` (unchanged; no candidate download in this run)",
        "",
        "| Variant | EM | F1 | Lead EM | Empty (answerable) | Abstain (unanswerable) | Spurious | Unsupported | p50 | p95 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for v in payload["variants"]:
        lines.append(
            f"| `{v['variant']}` | {v['em']:.3f} | {v['f1']:.3f} | {v['lead_em']:.3f} | "
            f"{v['empty_answer_rate_answerable']:.3f} | {v['abstention_unanswerable']:.3f} | "
            f"{v['spurious_unanswerable']:.3f} | {v['unsupported_claim_rate']} | "
            f"{v['latency_p50_ms']:.0f} ms | {v['latency_p95_ms']:.0f} ms |"
        )
    pairwise = payload.get("pairwise_vs_current") or {}
    if pairwise:
        lines += [
            "",
            "## Pairwise against the production config (answerable rows)",
            "",
            "| Variant | Correct only in variant | Correct only in v0 |",
            "|---|---|---|",
        ]
        for name, counts in pairwise.items():
            lines.append(
                f"| `{name}` | {counts['correct_only_in_variant']} | {counts['correct_only_in_v0']} |"
            )
        lines += [
            "",
            "A one-or-two-answer difference on 140 answerable rows is inside noise; the "
            "pairwise columns are the honest way to read these totals.",
        ]

    lines += ["", "## Variant definitions", ""]
    lines += [f"- `{v['variant']}` — {v['description']}" for v in payload["variants"]]
    lines += [
        "",
        "Every variant uses the production `answer_generatively` path (answerability gate, "
        "withholding, verification, mark elaboration), so the only difference is the swept "
        "parameter. No benchmark row was edited and no candidate model was downloaded.",
        "",
    ]
    return "\n".join(lines)


def write_report(payload: dict) -> Path:
    out_dir = REPORT_ROOT / RUN_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps({k: v for k, v in payload.items() if k != "predictions"}, indent=2),
        encoding="utf-8",
    )
    for name, rows in payload.get("predictions", {}).items():
        with (out_dir / f"predictions_{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "REPORT.md").write_text(render_markdown(payload), encoding="utf-8")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep decoding/prompt configuration on the frozen benchmark.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    payload = run(limit=args.limit)
    out_dir = write_report(payload)
    print(json.dumps({"out_dir": str(out_dir), "variants": payload["variants"]}, indent=2))


if __name__ == "__main__":
    main()

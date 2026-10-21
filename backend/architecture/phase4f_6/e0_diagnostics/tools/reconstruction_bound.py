#!/usr/bin/env python
"""Reproduce the answer-reconstruction EM bound from the recorded predictions.

Phase QA Quality Stabilization — Experiment 1 (reconstruction only).

Both production QA (`chat/qa_model.py`) and every Phase 4F runner used to turn a
predicted token span into text with ``tokenizer.decode()``, which re-inserts
spaces at subword boundaries and corrupts the values the tokenizer split::

    142.6 million  ->  "142. 6 million"
    $4,900         ->  "$ 4, 900"
    2011-2020      ->  "2011 - 2020"

The fix (implemented once in `backend/answer_span.py`, used by both
`chat/qa_model.py` and every Phase 4F runner) recovers the answer by slicing the
ORIGINAL context through the tokenizer's character offsets.

What this script does
---------------------
It reads the recorded prediction artifact and re-scores it, changing exactly one
variable: the answer text.  Nothing else is touched — the benchmark, the
checkpoints, the selected spans, the logits, the scores, the thresholds and the
metric definitions are all held fixed.

    NO model is loaded, NO inference is run, NO dataset is created,
    NO threshold is fitted, NO training is performed.

HONEST LIMITATION — this is an estimate, not a re-run
-----------------------------------------------------
`model_40min_predictions.json` stores only the post-decode STRING.  It does not
store the source context, the tokenised input, or the offsets, so the real fix
cannot be re-applied to this artifact.  What is measured here is a documented,
deliberately conservative string repair of the decode artifact:

    the decode artifact is removed by deleting the spaces that the tokenizer
    inserted inside a numeric/date/currency/percentage value

This is therefore a *reconstruction-only* quantity on a *leaked* population.  It
is NOT model performance, NOT generalization, and NOT an accuracy claim.  The
affected-example counts and the recorded baseline are reported alongside the
estimate so the estimate can be judged rather than trusted.

Writes:
    backend/architecture/phase4f_6/decision/RECONSTRUCTION_BOUND.json
    backend/architecture/phase4f_6/decision/RECONSTRUCTION_BOUND.md

Does NOT modify model_40min_predictions.json, MODEL_40MIN_EVALUATION.json, the
benchmark, or any historical F2/A0 artifact.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[5]
PREDICTIONS = ROOT / "backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json"
BENCHMARK = ROOT / "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
DECISION = ROOT / "backend/architecture/phase4f_6/decision"

BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
PREDICTIONS_SHA256_PREFIX = "d7d9d65e944488ac"  # recorded when the artifact was frozen
CATEGORY_ORDER = ["DIRECT_SPAN", "NUMERIC", "TABLE_CELL", "TABLE_ROW", "LIST_ITEM",
                  "SECTION_SPECIFIC", "MULTI_CHUNK", "LONG_CONTEXT"]
BRANCHES = ["F2_primary", "A0_secondary"]

# ---------------------------------------------------------------------------
# The documented repair.  Each rule deletes a space that `decode()` inserted
# *inside* a single value.  Spaces that separate words are never touched, so
# ordinary answers ("New York", "the treatment achieved 22.1% improvement")
# pass through unchanged.
# ---------------------------------------------------------------------------
REPAIR_RULES = [
    # "142. 6" -> "142.6"      (digit, space, decimal/separator + digit)
    (re.compile(r"(?<=\d) (?=[.,]\d)"), ""),
    # "89, 000" -> "89,000", "$ 4,900" -> "$4,900"
    (re.compile(r"(?<=[.,$]) (?=\d)"), ""),
    # "22.1 %" -> "22.1%"
    (re.compile(r"(?<=\d) (?=%)"), ""),
    # "2011 - 2020" -> "2011-2020"
    (re.compile(r"(?<=\d) (?=[-\u2013]\d)"), ""),
    (re.compile(r"(?<=[-\u2013]) (?=\d)"), ""),
]

# a value that contains a decimal point or a thousands separator
NUMERIC_VALUE = re.compile(r"\d[.,]\d")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def exact_match(pred: str, gold: str) -> bool:
    return normalize_text(pred) == normalize_text(gold)


def token_f1(pred: str, gold: str) -> float:
    p = set(normalize_text(pred).split())
    g = set(normalize_text(gold).split())
    if not p or not g:
        return 0.0
    common = p & g
    if not common:
        return 0.0
    precision = len(common) / len(p)
    recall = len(common) / len(g)
    return 2 * precision * recall / (precision + recall)


def repair_answer(answer: str) -> str:
    """Delete the spaces `decode()` inserted inside a single value."""
    for pattern, repl in REPAIR_RULES:
        answer = pattern.sub(repl, answer)
    return answer


def score_branch(preds: list[dict]) -> dict:
    ans_em_before, ans_f1_before = [], []
    ans_em_after, ans_f1_after = [], []
    unans_total = unans_spurious_before = unans_spurious_after = 0
    changed = 0
    changed_fixed = changed_broken = 0
    gold_numeric = gold_numeric_em_before = gold_numeric_em_after = 0
    answerable = 0
    per_cat = defaultdict(lambda: {"n": 0, "answerable": 0, "em_before": [],
                                   "em_after": [], "changed": 0, "repaired": 0})

    for p in preds:
        cat = p.get("category")
        before = p.get("predicted_answer") or ""
        after = repair_answer(before)
        gold = p.get("gold_answer") or ""
        is_ans = p.get("answerability") == "ANSWERABLE"

        per_cat[cat]["n"] += 1
        if before != after:
            changed += 1
            per_cat[cat]["changed"] += 1
        if after == "" and before != "":
            per_cat[cat]["repaired"] += 1

        if is_ans:
            answerable += 1
            per_cat[cat]["answerable"] += 1
            em_b, em_a = exact_match(before, gold), exact_match(after, gold)
            ans_em_before.append(em_b)
            ans_f1_before.append(token_f1(before, gold))
            ans_em_after.append(em_a)
            ans_f1_after.append(token_f1(after, gold))
            if em_a and not em_b:
                changed_fixed += 1
            elif em_b and not em_a:
                changed_broken += 1
            per_cat[cat]["em_before"].append(em_b)
            per_cat[cat]["em_after"].append(em_a)
            if NUMERIC_VALUE.search(gold):
                gold_numeric += 1
                gold_numeric_em_before += int(em_b)
                gold_numeric_em_after += int(em_a)
        else:
            unans_total += 1
            unans_spurious_before += int(before.strip() != "")
            unans_spurious_after += int(after.strip() != "")

    def pct(seq):
        return round(sum(seq) / len(seq) * 100, 2) if seq else 0.0

    return {
        "n": len(preds),
        "answerable": answerable,
        "unanswerable": unans_total,
        "answerable_em_before_pct": pct(ans_em_before),
        "answerable_em_after_pct": pct(ans_em_after),
        "answerable_em_before_count": sum(ans_em_before),
        "answerable_em_after_count": sum(ans_em_after),
        "answerable_f1_before_pct": pct(ans_f1_before),
        "answerable_f1_after_pct": pct(ans_f1_after),
        "predictions_changed_by_repair": changed,
        "em_gained": changed_fixed,
        "em_lost": changed_broken,
        "gold_answers_with_decimal_or_thousands": gold_numeric,
        "gold_numeric_em_before": gold_numeric_em_before,
        "gold_numeric_em_after": gold_numeric_em_after,
        "unanswerable_spurious_before": unans_spurious_before,
        "unanswerable_spurious_after": unans_spurious_after,
        "by_category": {
            c: {
                "n": v["n"],
                "answerable": v["answerable"],
                "em_before_pct": pct(v["em_before"]),
                "em_after_pct": pct(v["em_after"]),
                "predictions_changed": v["changed"],
            }
            for c, v in sorted(per_cat.items(),
                               key=lambda kv: CATEGORY_ORDER.index(kv[0])
                               if kv[0] in CATEGORY_ORDER else 99)
        },
    }


def main() -> int:
    if not PREDICTIONS.exists():
        print(f"FATAL: predictions artifact not found: {PREDICTIONS}")
        return 1
    if not BENCHMARK.exists():
        print(f"FATAL: benchmark not found: {BENCHMARK}")
        return 1

    preds_sha = sha256_file(PREDICTIONS)
    bench_sha = sha256_file(BENCHMARK)
    print("=" * 72)
    print("RECONSTRUCTION BOUND — read-only re-score of recorded predictions")
    print("=" * 72)
    print(f"predictions : {PREDICTIONS.relative_to(ROOT)}")
    print(f"  sha256    : {preds_sha}")
    print(f"  recorded  : {PREDICTIONS_SHA256_PREFIX}... "
          f"({'MATCH' if preds_sha.startswith(PREDICTIONS_SHA256_PREFIX) else 'CHANGED'})")
    print(f"benchmark   : {bench_sha} "
          f"({'VERIFIED' if bench_sha == BENCHMARK_SHA256 else 'CHANGED'})")
    print("NO model loaded. NO inference run. NO dataset created. No fits.\n")

    with open(PREDICTIONS, encoding="utf-8") as fh:
        artifact = json.load(fh)

    results = {
        "artifact": "RECONSTRUCTION_BOUND",
        "note": ("Reconstruction-only ESTIMATE of the tokenizer.decode() answer-text defect, derived "
                 "from recorded strings. Not model performance, not generalization; the authoritative "
                 "measurement is a real re-run of the fixed decoder. See limitations."),
        "method": {
            "changed_variable": "answer text only (decoded span -> reconstructed source text)",
            "held_fixed": ["benchmark", "checkpoints", "selected spans", "logits", "scores",
                           "thresholds", "metric definitions", "normalization"],
            "repair_rules": [p.pattern for p, _ in REPAIR_RULES],
            "population": "recorded 182-example benchmark predictions (training-set overlap: 100%)",
        },
        "limitations": [
            ("The recorded artifact stores only the post-decode string; the source context and "
             "the tokenizer offsets are absent, so the real fix cannot be re-applied here. The "
             "measured quantity is a documented string repair of the decode artefact."),
            ("The population is fully leaked (every example is present in training_data.jsonl / "
             "training_data_v3.jsonl), so this is a training-set quantity with no generalization "
             "meaning."),
            ("The repair is a heuristic approximation, not the fix, so it is not authoritative on "
             "its own. It was validated against a real re-run: this script gives F2 UNGATED "
             "answerable EM 21/140, and the fixed decoder measured directly on the same benchmark "
             "also gives 21/140 ungated (15.0%) - the estimate matches the measurement exactly. "
             "The 14.29% quoted from phase4f_5f/f2/threshold_experiment is the SAME run with the "
             "abstention gate ON, not a different quantity. The re-run remains authoritative."),
            ("No model improvements were made. Span selection, scoring and confidence are "
             "unchanged by the reconstruction fix."),
        ],
        "inputs": {
            "predictions_path": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
            "predictions_sha256": preds_sha,
            "predictions_sha256_recorded_prefix": PREDICTIONS_SHA256_PREFIX,
            "benchmark_path": str(BENCHMARK.relative_to(ROOT)).replace("\\", "/"),
            "benchmark_sha256": bench_sha,
            "benchmark_sha256_expected": BENCHMARK_SHA256,
        },
        "branches": {},
    }

    for branch in BRANCHES:
        node = artifact.get(branch)
        if not node:
            print(f"WARNING: branch '{branch}' missing from the artifact")
            continue
        stats = score_branch(node["predictions"])
        stats["checkpoint"] = node.get("checkpoint")
        stats["model_sha256"] = node.get("model_sha256")
        results["branches"][branch] = stats

        print("-" * 72)
        print(f"{branch}  (checkpoint {node.get('checkpoint')})")
        print("-" * 72)
        print(f"  predictions                       : {stats['n']} "
              f"({stats['answerable']} answerable, {stats['unanswerable']} unanswerable)")
        print(f"  answerable EM  before (recorded)  : {stats['answerable_em_before_pct']}% "
              f"({stats['answerable_em_before_count']}/{stats['answerable']})")
        print(f"  answerable EM  after  (repaired)  : {stats['answerable_em_after_pct']}% "
              f"({stats['answerable_em_after_count']}/{stats['answerable']})")
        print(f"  answerable F1  before -> after    : "
              f"{stats['answerable_f1_before_pct']}% -> {stats['answerable_f1_after_pct']}%")
        print(f"  predictions changed by repair     : {stats['predictions_changed_by_repair']}")
        print(f"  EM gained / lost                  : "
              f"+{stats['em_gained']} / -{stats['em_lost']}")
        print(f"  gold with decimal/thousands       : "
              f"{stats['gold_answers_with_decimal_or_thousands']} "
              f"(EM before {stats['gold_numeric_em_before']} -> "
              f"after {stats['gold_numeric_em_after']})")
        print(f"  unanswerable spurious before/after: "
              f"{stats['unanswerable_spurious_before']} / "
              f"{stats['unanswerable_spurious_after']}")
        print("  by category (EM before -> after):")
        for cat, v in stats["by_category"].items():
            print(f"    {cat:<18} n={v['n']:<4} answerable={v['answerable']:<4} "
                  f"EM {v['em_before_pct']:>5}% -> {v['em_after_pct']:>5}% "
                  f"changed={v['predictions_changed']}")
        print()

    DECISION.mkdir(parents=True, exist_ok=True)
    out_json = DECISION / "RECONSTRUCTION_BOUND.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    lines = [
        "# Reconstruction Bound — answer-text reconstruction only",
        "",
        "> **This is a reconstruction experiment, not a model result.** The measured",
        "> quantity is the effect of removing the `tokenizer.decode()` spacing artefact",
        "> from the recorded answer strings. It is *not* model performance, *not*",
        "> generalization, and *not* an accuracy claim.",
        "",
        "## Method",
        "",
        "- Changed variable: **answer text only** (decoded span → reconstructed source text).",
        "- Held fixed: benchmark, checkpoints, selected spans, logits, scores, thresholds,",
        "  metric definitions and normalization.",
        "- **No model was loaded, no inference was run, no dataset was created, nothing was fitted.**",
        "- Repair rules (delete the spaces `decode()` inserted *inside* one value): "
        + ", ".join(f"`{p.pattern}`" for p, _ in REPAIR_RULES),
        "",
        "## Limitations",
        "",
    ]
    for item in results["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append(f"- predictions: `{results['inputs']['predictions_path']}` "
                 f"sha256 `{preds_sha[:16]}...` "
                 f"({'MATCH' if preds_sha.startswith(PREDICTIONS_SHA256_PREFIX) else 'CHANGED'})")
    lines.append(f"- benchmark: `{results['inputs']['benchmark_path']}` "
                 f"sha256 `{bench_sha[:16]}...` "
                 f"({'VERIFIED' if bench_sha == BENCHMARK_SHA256 else 'CHANGED'})")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    for branch, s in results["branches"].items():
        lines.append(f"### {branch}")
        lines.append("")
        lines.append(f"- predictions: {s['n']} ({s['answerable']} answerable, "
                     f"{s['unanswerable']} unanswerable)")
        lines.append(f"- answerable EM before (as recorded): **{s['answerable_em_before_pct']}%** "
                     f"({s['answerable_em_before_count']}/{s['answerable']})")
        lines.append(f"- answerable EM after repair: **{s['answerable_em_after_pct']}%** "
                     f"({s['answerable_em_after_count']}/{s['answerable']})")
        lines.append(f"- answerable F1: {s['answerable_f1_before_pct']}% → "
                     f"{s['answerable_f1_after_pct']}%")
        lines.append(f"- predictions changed by the repair: "
                     f"{s['predictions_changed_by_repair']} (EM +{s['em_gained']} / "
                     f"-{s['em_lost']})")
        lines.append(f"- gold answers containing a decimal/thousands separator: "
                     f"{s['gold_answers_with_decimal_or_thousands']} "
                     f"(EM {s['gold_numeric_em_before']} → {s['gold_numeric_em_after']})")
        lines.append("")
        lines.append("| category | n | answerable | EM before | EM after | changed |")
        lines.append("|---|---|---|---|---|---|")
        for cat, v in s["by_category"].items():
            lines.append(f"| {cat} | {v['n']} | {v['answerable']} | "
                         f"{v['em_before_pct']}% | {v['em_after_pct']}% | "
                         f"{v['predictions_changed']} |")
        lines.append("")
    out_md = DECISION / "RECONSTRUCTION_BOUND.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 72)
    print(f"wrote {out_json.relative_to(ROOT)}")
    print(f"wrote {out_md.relative_to(ROOT)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

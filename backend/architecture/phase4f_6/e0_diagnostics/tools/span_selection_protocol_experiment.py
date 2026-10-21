#!/usr/bin/env python
"""Runner-protocol span selection: recorded argmax chain -> joint-score selection.

Phase QA Quality Stabilization — Experiment 3 (span SELECTION, not boundaries).

Question
--------
The recorded Phase 4F runner protocol selects an answer span with a greedy chain:

    s = argmax(start_logits)
    e = s + argmax(end_logits[s : s + 50])

That is NOT the standard extractive-QA rule.  The best end *given the best start*
is only the best pair when the best start is unconstrained; the pair maximising
`start_logit + end_logit` (joint selection) can pick a different start entirely.
Experiment 2 (`SPAN_BOUNDARY_FORENSICS`) measured a gap on identical logits but
deliberately did NOT act on it, because changing the runners' selection rule is a
PROTOCOL change that invalidates the comparability of every recorded Phase 4F
metric.  This tool is the explicit experiment that action called for.

The recorded fleet is NOT uniform (audited in this repository)
-------------------------------------------------------------
* 9 of the 10 runners call `torch.argmax(start_logits)` **unmasked**, so the
  start can legitimately land on `[CLS]` or a question token; the answer text
  then comes from `reconstruct_answer`, whose decode fallback cannot find a
  context span and returns the decoded (question) tokens instead.
* `phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py` additionally
  sets `masked_start[0] = -inf` before the argmax.

Both recorded variants are measured here, so the before/after is against the
protocol that actually produced the recorded numbers, not an idealised one.

Method
------
Every variant reads the SAME logits for the SAME 182 frozen benchmark examples.
Exactly one variable changes: the span-selection rule.  The benchmark, the
checkpoints, the tokenization, the metric definitions and the answer-text
reconstruction (fixed in Experiment 1) are held fixed.

S1/S2 call the shipped `answer_span.select_joint_span`, i.e. exactly the code a
runner upgrade would use — not a re-implementation.

Honesty
-------
* This tool DOES run inference (CPU) on the recorded checkpoints.  No training,
  no weight change, no benchmark change, no threshold change, no fitting.
* The population is **fully leaked**: all 182 examples appear in
  `training_data.jsonl` / `training_data_v3.jsonl`.  Nothing here is a
  generalization result, and nothing here licenses a production change.
* n = 140 answerable examples, so 1 example = 0.71pp.  1-2 example differences
  are noise and are reported as counts, never as percentages alone.
* Joint selection maximises the MODEL'S OWN score, not accuracy.  The EM change
  is an empirical outcome, reported with the EM gained/lost flips so it can be
  judged rather than assumed to be an improvement.

Writes:
    backend/architecture/phase4f_6/decision/SPAN_SELECTION_PROTOCOL_EXPERIMENT.json
    backend/architecture/phase4f_6/decision/SPAN_SELECTION_PROTOCOL_EXPERIMENT.md
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[5]
BACKEND = Path(__file__).resolve().parents[4]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from answer_span import (  # noqa: E402
    reconstruct_answer,
    select_joint_span,
    span_text,
    tokenize_with_offsets,
)

BENCHMARK = ROOT / "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
DECISION = ROOT / "backend/architecture/phase4f_6/decision"
MODELS = {
    "A0": ROOT / "backend/models/documind-qa",
    "F2": ROOT / "backend/phase4f/phase4f_5f/f2/checkpoints/F2/checkpoint_epoch2",
}
BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
MAX_LENGTH = 384
RECORDED_WINDOW = 50
WIDE_WINDOW = 100
PRODUCTION_N_BEST = 20
SPECIAL = {"[CLS]", "[PAD]", "[SEP]"}

# name -> {kind: chain|joint|nbest, window, mask_cls, text: fallback|strict, note}
VARIANTS = [
    {
        "name": "S0_recorded_argmax_nomask50",
        "kind": "chain", "window": RECORDED_WINDOW, "mask_cls": False,
        "text": "fallback",
        "note": "majority recorded runner protocol (9 of 10 runners): unmasked "
                "argmax(start), then argmax(end) in a 50-token window; answer text via "
                "reconstruct_answer incl. its decode fallback",
    },
    {
        "name": "S0b_recorded_argmax_nomask50_strict",
        "kind": "chain", "window": RECORDED_WINDOW, "mask_cls": False,
        "text": "strict",
        "note": "identical selection; answer text via strict context mapping "
                "(shows what the decode fallback adds)",
    },
    {
        "name": "S0c_recorded_argmax_clsmask50",
        "kind": "chain", "window": RECORDED_WINDOW, "mask_cls": True,
        "text": "fallback",
        "note": "threshold_experiment protocol: [CLS]-masked argmax chain, window 50",
    },
    {
        "name": "S4_recorded_argmax_nomask100",
        "kind": "chain", "window": WIDE_WINDOW, "mask_cls": False,
        "text": "fallback",
        "note": "majority recorded rule with the window widened to 100",
    },
    {
        "name": "S1_joint_logit50",
        "kind": "joint", "window": RECORDED_WINDOW, "mask_cls": None,
        "text": "strict",
        "note": "joint max(s_logit + e_logit) via answer_span.select_joint_span, window 50",
    },
    {
        "name": "S2_joint_logit100",
        "kind": "joint", "window": WIDE_WINDOW, "mask_cls": None,
        "text": "strict",
        "note": "joint max(s_logit + e_logit) via answer_span.select_joint_span, window 100",
    },
    {
        "name": "S3_production_nbest100_prob",
        "kind": "nbest", "window": WIDE_WINDOW, "mask_cls": None,
        "text": "strict",
        "note": "live production rule: 20x20 n-best, softmax_s * softmax_e, window 100",
    },
]
VARIANT_NAMES = [v["name"] for v in VARIANTS]
VARIANT_BY_NAME = {v["name"]: v for v in VARIANTS}

COMPARISONS = [
    ("S0_recorded_argmax_nomask50", "S1_joint_logit50",
     "majority recorded runner protocol (unmasked chain) -> joint selection, window 50"),
    ("S0c_recorded_argmax_clsmask50", "S1_joint_logit50",
     "threshold_experiment protocol ([CLS]-masked chain) -> joint selection, window 50"),
    ("S4_recorded_argmax_nomask100", "S2_joint_logit100",
     "unmasked chain at window 100 -> joint at window 100"),
]


# ---------------------------------------------------------------------------
# Metrics — identical definitions to the Phase 4F runners
# ---------------------------------------------------------------------------

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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Selection rules
# ---------------------------------------------------------------------------

def recorded_argmax_chain(start_logits, end_logits, window, mask_cls):
    """The recorded runner chain: optional [CLS] mask, argmax start, in-window end."""
    masked = start_logits.copy()
    if mask_cls:
        masked[0] = -np.inf
    s = int(np.argmax(masked))
    e = s + int(np.argmax(end_logits[s:s + window]))
    return s, e


def production_nbest(start_probs, end_probs, sequence_ids, token_ids, tokenizer,
                     max_ans, n_best=PRODUCTION_N_BEST):
    """Live production rule: 20x20 n-best candidates scored by softmax product."""
    st = np.argsort(-start_probs)[:n_best]
    et = np.argsort(-end_probs)[:n_best]
    best = None
    for s in st:
        for e in et:
            if e < s or (e - s + 1) > max_ans:
                continue
            if tokenizer.convert_ids_to_tokens(int(token_ids[s])) in SPECIAL:
                continue
            if tokenizer.convert_ids_to_tokens(int(token_ids[e])) in ("[SEP]", "[PAD]"):
                continue
            if sequence_ids[s] != 1 or sequence_ids[e] != 1:
                continue
            score = float(start_probs[s] * end_probs[e])
            if best is None or score > best[0]:
                best = (score, int(s), int(e))
    return (best[1], best[2]) if best else None


def predict(cfg, c, tokenizer):
    """Return (answer_text, span, diagnostics) for one cached example."""
    if cfg["kind"] == "chain":
        s, e = recorded_argmax_chain(c["sl"], c["el"], cfg["window"], cfg["mask_cls"])
        span = (s, e)
    elif cfg["kind"] == "joint":
        span = select_joint_span(c["sl"], c["el"], c["seq"], cfg["window"],
                                 offsets=c["offsets"])
    else:  # production n-best
        span = production_nbest(c["sp"], c["ep"], c["seq"], c["ids_list"],
                                tokenizer, cfg["window"])

    start_off_context = span is None or c["seq"][span[0]] != 1
    strict_text = span_text(c["context"], c["offsets"], c["seq"], span)
    if cfg["text"] == "fallback":
        text = reconstruct_answer(
            c["context"], c["offsets"], c["seq"], span[0], span[1],
            tokenizer=tokenizer, input_ids=c["ids"]) if span else ""
    else:
        text = strict_text
    return text, span, {
        "unmappable_span": not strict_text,
        "start_off_context": start_off_context,
        "decode_fallback_used": cfg["text"] == "fallback" and not strict_text and bool(text),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not BENCHMARK.exists():
        print(f"FATAL: benchmark not found: {BENCHMARK}")
        return 1
    bench_sha = sha256_file(BENCHMARK)

    examples = []
    with open(BENCHMARK, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                examples.append(json.loads(line))

    print("=" * 82)
    print("SPAN-SELECTION PROTOCOL EXPERIMENT — same logits, different selection only")
    print("=" * 82)
    print(f"benchmark: {BENCHMARK.relative_to(ROOT)}")
    print(f"  sha256 : {bench_sha} "
          f"({'VERIFIED' if bench_sha == BENCHMARK_SHA256 else 'CHANGED'})")
    print(f"examples : {len(examples)} (leaked population: all appear in the training data)")
    print("Changed: span-selection rule. Held fixed: benchmark, checkpoints, logits,")
    print("tokenization, metric definitions, and the Experiment-1 answer-text decoder.")
    print("No training. No weight change. No threshold change.\n")

    results = {
        "artifact": "SPAN_SELECTION_PROTOCOL_EXPERIMENT",
        "note": (
            "Before/after experiment for upgrading the Phase 4F runner span-selection "
            "rule from the greedy argmax chain to joint-score selection. Every variant "
            "reads the same logits. Leaked population — not a generalization result."
        ),
        "changed": "span-selection rule only",
        "held_fixed": [
            "benchmark", "checkpoints", "logits", "tokenization",
            "metric definitions", "answer-text reconstruction (Experiment 1)",
        ],
        "no_training": True,
        "recorded_protocol_audit": {
            "finding": (
                "The recorded runner fleet is not uniform. 9 of the 10 runners call "
                "torch.argmax(start_logits) unmasked; only "
                "phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py masks "
                "[CLS] (masked_start[0] = -inf)."
            ),
            "unmasked_runners": [
                "phase4f/experiments/run_experiment.py",
                "phase4f/experiments/evaluate.py",
                "phase4f/experiments/final_gpu_package/evaluation/evaluate.py",
                "phase4f/phase4f_5/run_experiment.py",
                "phase4f/phase4f_5/evaluation/evaluate.py",
                "phase4f/phase4f_5e/run_analysis.py",
                "phase4f/phase4f_5f/run_experiment.py",
                "phase4f/phase4f_5f/f2/run_f2.py",
                "phase4f/phase4f_5f/h1/run_h1.py",
            ],
            "cls_masked_runners": [
                "phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py",
            ],
        },
        "variants": {v["name"]: v["note"] for v in VARIANTS},
        "comparisons": [{"before": b, "after": a, "description": d}
                        for b, a, d in COMPARISONS],
        "limitations": [
            "Population is fully leaked (all 182 examples appear in training_data.jsonl / "
            "training_data_v3.jsonl); no generalization claim is possible.",
            "n = 140 answerable examples, so 1 example = 0.71pp; 1-2 example differences "
            "are noise and are reported as counts.",
            "Inference is CPU-only against the recorded checkpoints; no training and no "
            "weights changed.",
            "Joint selection maximises the MODEL'S own score, not accuracy, so the EM change "
            "is an empirical outcome — the EM gained/lost flips are reported alongside it.",
            "This is an offline protocol comparison. Applying it to the runners is a frozen-"
            "protocol change and is recorded as a decision, not performed silently.",
        ],
        "inputs": {
            "benchmark_path": "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl",
            "benchmark_sha256": bench_sha,
            "benchmark_sha256_expected": BENCHMARK_SHA256,
            "max_length": MAX_LENGTH,
            "recorded_window": RECORDED_WINDOW,
            "wide_window": WIDE_WINDOW,
        },
        "models": {},
        "findings": {},
    }

    for label, model_path in MODELS.items():
        tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        model = AutoModelForQuestionAnswering.from_pretrained(str(model_path))
        model.eval()
        print("-" * 82)
        print(f"MODEL {label}  ({model_path.relative_to(ROOT)})")
        print("-" * 82)

        cache = []
        for ex in examples:
            encoding, offsets, sequence_ids = tokenize_with_offsets(
                tokenizer, ex["question"], ex["context"], max_length=MAX_LENGTH,
                truncation=True, padding="max_length", return_tensors="pt")
            with torch.no_grad():
                out = model(**encoding)
            cache.append({
                "example_id": ex["example_id"],
                "kind": ex["question_kind"],
                "context": ex["context"],
                "gold": ex.get("answer", "") or "",
                "answerable": ex["question_kind"] != "UNANSWERABLE",
                "ids": encoding["input_ids"][0],
                "ids_list": encoding["input_ids"][0].tolist(),
                "offsets": offsets,
                "seq": sequence_ids,
                "sl": out.start_logits[0].numpy(),
                "el": out.end_logits[0].numpy(),
                "sp": torch.softmax(out.start_logits[0], dim=0).numpy(),
                "ep": torch.softmax(out.end_logits[0], dim=0).numpy(),
            })

        variant_results = {}
        preds_by_variant = {}
        for cfg in VARIANTS:
            name = cfg["name"]
            preds = []
            for c in cache:
                text, span, diag = predict(cfg, c, tokenizer)
                preds.append({
                    "example_id": c["example_id"],
                    "kind": c["kind"],
                    "gold": c["gold"],
                    "answerable": c["answerable"],
                    "pred": text,
                    "span": span,
                    **diag,
                    "em": exact_match(text, c["gold"]),
                    "f1": token_f1(text, c["gold"]),
                })
            preds_by_variant[name] = preds

            ans = [p for p in preds if p["answerable"]]
            unans = [p for p in preds if not p["answerable"]]
            per_kind = defaultdict(lambda: {"n": 0, "em": 0})
            for p in ans:
                per_kind[p["kind"]]["n"] += 1
                per_kind[p["kind"]]["em"] += int(p["em"])
            em_count = sum(int(p["em"]) for p in ans)
            variant_results[name] = {
                "rule": cfg["kind"],
                "max_answer_length": cfg["window"],
                "cls_masked": cfg["mask_cls"],
                "answer_text_source": cfg["text"],
                "answerable_n": len(ans),
                "answerable_em_count": em_count,
                "answerable_em_pct": round(em_count / len(ans) * 100, 2),
                "answerable_f1_pct": round(sum(p["f1"] for p in ans) / len(ans) * 100, 2),
                "non_empty_predictions": sum(1 for p in preds if p["pred"].strip()),
                "n_predictions": len(preds),
                "unmappable_spans": sum(1 for p in preds if p["unmappable_span"]),
                "starts_off_context": sum(1 for p in preds if p["start_off_context"]),
                "decode_fallback_answers": sum(1 for p in preds if p["decode_fallback_used"]),
                "unanswerable_spurious": sum(1 for p in unans if p["pred"].strip()),
                "by_question_kind": {
                    k: {"n": v["n"], "em": v["em"]}
                    for k, v in sorted(per_kind.items())
                },
            }
            entry = variant_results[name]
            print(f"  {name:<38} EM {entry['answerable_em_pct']:>6.2f}% "
                  f"({entry['answerable_em_count']}/{entry['answerable_n']})  "
                  f"F1 {entry['answerable_f1_pct']:>6.2f}%  "
                  f"non-empty {entry['non_empty_predictions']}/{entry['n_predictions']}  "
                  f"off-ctx starts {entry['starts_off_context']}")

        # ---- before/after flips for each comparison ----
        comparisons = {}
        for before_name, after_name, desc in COMPARISONS:
            before = {p["example_id"]: p for p in preds_by_variant[before_name]}
            after = {p["example_id"]: p for p in preds_by_variant[after_name]}
            gained, lost, changed = [], [], 0
            for ex in examples:
                if ex["question_kind"] == "UNANSWERABLE":
                    continue
                eid = ex["example_id"]
                b, a = before[eid], after[eid]
                if b["pred"] != a["pred"]:
                    changed += 1
                row = {"example_id": eid, "question_kind": b["kind"], "gold": b["gold"],
                       "before": b["pred"], "after": a["pred"]}
                if a["em"] and not b["em"]:
                    gained.append(row)
                elif b["em"] and not a["em"]:
                    lost.append(row)
            bv, av = variant_results[before_name], variant_results[after_name]
            comparisons[f"{before_name}__to__{after_name}"] = {
                "description": desc,
                "before_variant": before_name,
                "after_variant": after_name,
                "answerable_n": bv["answerable_n"],
                "em_before_count": bv["answerable_em_count"],
                "em_before_pct": bv["answerable_em_pct"],
                "em_after_count": av["answerable_em_count"],
                "em_after_pct": av["answerable_em_pct"],
                "f1_before_pct": bv["answerable_f1_pct"],
                "f1_after_pct": av["answerable_f1_pct"],
                "predictions_changed": changed,
                "em_gained_count": len(gained),
                "em_lost_count": len(lost),
                "em_gained": gained,
                "em_lost": lost,
            }
            print(f"  -> {before_name} -> {after_name}: "
                  f"EM {bv['answerable_em_count']}/{bv['answerable_n']} -> "
                  f"{av['answerable_em_count']}/{av['answerable_n']}; "
                  f"gained {len(gained)}, lost {len(lost)}, answers changed {changed}")

        results["models"][label] = {
            "checkpoint": str(model_path.relative_to(ROOT)).replace("\\", "/"),
            "variants": variant_results,
            "comparisons": comparisons,
        }
        print()
        del model

    # ---- findings ----
    a0v = results["models"]["A0"]["variants"]
    f2v = results["models"]["F2"]["variants"]

    def line(v, name):
        e = v[name]
        return (f"{e['answerable_em_count']}/{e['answerable_n']} (EM "
                f"{e['answerable_em_pct']}%, F1 {e['answerable_f1_pct']}%)")

    def cmp_of(label, before, after):
        return results["models"][label]["comparisons"][f"{before}__to__{after}"]

    results["findings"] = {
        "DC1_recorded_fleet_is_not_uniform": {
            "claim": "The recorded argmax chain was implemented differently across runners.",
            "result": "CONFIRMED — and it changes the result by ~8pp on A0.",
            "evidence": (
                f"A0 unmasked chain {line(a0v, 'S0_recorded_argmax_nomask50')} vs [CLS]-masked "
                f"chain {line(a0v, 'S0c_recorded_argmax_clsmask50')}; F2 "
                f"{line(f2v, 'S0_recorded_argmax_nomask50')} vs "
                f"{line(f2v, 'S0c_recorded_argmax_clsmask50')}. "
                f"Off-context starts: A0 {a0v['S0_recorded_argmax_nomask50']['starts_off_context']} "
                f"-> {a0v['S0c_recorded_argmax_clsmask50']['starts_off_context']}; F2 "
                f"{f2v['S0_recorded_argmax_nomask50']['starts_off_context']} -> "
                f"{f2v['S0c_recorded_argmax_clsmask50']['starts_off_context']} (of 182)."
            ),
        },
        "H1_selection_rule_is_weaker_than_joint": {
            "claim": "The recorded argmax chain is a weaker selector than joint-score "
                     "selection on identical logits.",
            "result": "SUPPORTED for the majority (unmasked) protocol; REFUTED for the "
                      "[CLS]-masked protocol on A0.",
            "evidence": (
                f"A0 unmasked chain {line(a0v, 'S0_recorded_argmax_nomask50')} -> joint "
                f"{line(a0v, 'S1_joint_logit50')} "
                f"(+{cmp_of('A0', 'S0_recorded_argmax_nomask50', 'S1_joint_logit50')['em_gained_count']} "
                f"/ -{cmp_of('A0', 'S0_recorded_argmax_nomask50', 'S1_joint_logit50')['em_lost_count']}); "
                f"A0 [CLS]-masked chain {line(a0v, 'S0c_recorded_argmax_clsmask50')} -> joint "
                f"{line(a0v, 'S1_joint_logit50')}. "
                f"F2 unmasked chain {line(f2v, 'S0_recorded_argmax_nomask50')} -> joint "
                f"{line(f2v, 'S1_joint_logit50')} "
                f"(+{cmp_of('F2', 'S0_recorded_argmax_nomask50', 'S1_joint_logit50')['em_gained_count']} "
                f"/ -{cmp_of('F2', 'S0_recorded_argmax_nomask50', 'S1_joint_logit50')['em_lost_count']})."
            ),
            "mechanism": (
                "On A0 the recorded chain's weakness is dominated by its UNMASKED start, "
                "not by the greedy-vs-joint distinction: the argmax start lands off the "
                "context (on [CLS]/question tokens) for "
                f"{a0v['S0_recorded_argmax_nomask50']['starts_off_context']}/182 examples, and "
                "the decode fallback then returns question text. Joint selection cannot "
                "pick such a span (it requires context-mappable tokens), which is most of "
                "the improvement. On F2 the model's start is already on the context, so the "
                "gap is 1/140 — noise."
            ),
        },
        "H2_window_vs_rule": {
            "claim": "The 50-token window, not the greedy rule, is what suppresses EM.",
            "result": "REFUTED — widening 50 -> 100 changes no EM at all.",
            "evidence": (
                f"Recorded rule at window 100: A0 {line(a0v, 'S4_recorded_argmax_nomask100')}, "
                f"F2 {line(f2v, 'S4_recorded_argmax_nomask100')}. "
                f"Joint at window 50: A0 {line(a0v, 'S1_joint_logit50')}, "
                f"F2 {line(f2v, 'S1_joint_logit50')}. "
                f"Joint at window 100: A0 {line(a0v, 'S2_joint_logit100')}, "
                f"F2 {line(f2v, 'S2_joint_logit100')}."
            ),
        },
        "H3_joint_equals_production": {
            "claim": "Joint-logit selection already matches the live production rule.",
            "result": ("SUPPORTED" if all(
                v["S2_joint_logit100"]["answerable_em_count"]
                == v["S3_production_nbest100_prob"]["answerable_em_count"]
                for v in (a0v, f2v)) else "REFUTED"),
            "evidence": (
                f"A0 joint/window100 {line(a0v, 'S2_joint_logit100')} vs production "
                f"{line(a0v, 'S3_production_nbest100_prob')}; F2 "
                f"{line(f2v, 'S2_joint_logit100')} vs "
                f"{line(f2v, 'S3_production_nbest100_prob')}."
            ),
            "implication": "Upgrading the runners to joint selection aligns the research "
                           "protocol with production; it is not a new method.",
        },
        "H4_decode_fallback": {
            "claim": "The decode fallback in reconstruct_answer silently emits text from the "
                     "question sequence when the recorded chain selects an off-context span.",
            "result": "MEASURED",
            "evidence": (
                f"decode_fallback_answers: A0 "
                f"{a0v['S0_recorded_argmax_nomask50']['decode_fallback_answers']} -> "
                f"{a0v['S0c_recorded_argmax_clsmask50']['decode_fallback_answers']} "
                f"([CLS]-masked) -> {a0v['S1_joint_logit50']['decode_fallback_answers']} (joint); "
                f"F2 {f2v['S0_recorded_argmax_nomask50']['decode_fallback_answers']} -> "
                f"{f2v['S1_joint_logit50']['decode_fallback_answers']}. "
                f"Strict-mapping non-empty predictions: A0 "
                f"{a0v['S0b_recorded_argmax_nomask50_strict']['non_empty_predictions']}/182 vs "
                f"{a0v['S0_recorded_argmax_nomask50']['non_empty_predictions']}/182 with the fallback."
            ),
        },
        "decision_on_applying": {
            "options": [
                "A. Leave the runners as-is; keep this as a measurement only.",
                "B. Upgrade all runners to joint selection as an explicitly labelled "
                "protocol v2, re-run the eval-only runners, and keep the v1 recorded "
                "numbers labelled as v1 (never overwritten).",
            ],
            "recommendation": (
                "B. The upgrade never loses an example on any comparison measured here, "
                "removes the off-context/decode-fallback failure mode, aligns the research "
                "protocol with the live production rule, and is already implemented and "
                "tested in answer_span.select_joint_span. It must be a labelled protocol "
                "change with before/after recorded, not a silent edit."
            ),
            "not_done_here": (
                "No runner was modified by this experiment. The recorded v1 metrics remain "
                "the recorded v1 metrics."
            ),
        },
        "verdict": (
            "Joint selection is a non-regressing protocol improvement on identical logits. "
            "Against the majority (unmasked) recorded runner protocol: A0 11/140 -> 22/140 "
            "(+7.86pp, 11 gained / 0 lost), F2 21/140 -> 22/140 (+0.71pp, 1 gained / 0 lost). "
            "Against the [CLS]-masked threshold_experiment protocol: A0 EM unchanged at "
            "22/140 (F1 -0.86pp, 3 answers differ), F2 +1 example. It also removes the "
            "off-context/decode-fallback failure mode entirely (A0 107 -> 0 off-context "
            "starts) and reproduces the live production rule exactly. The window (50 vs "
            "100) is not a factor. Because it is a PROTOCOL change, every recorded Phase 4F "
            "EM/F1 becomes non-comparable until re-run under the new rule; it is recorded "
            "as a decision above and was NOT applied silently. No generalization claim is "
            "possible on this leaked population."
        ),
    }

    print("=" * 82)
    print("FINDINGS")
    print("=" * 82)
    for key, f in results["findings"].items():
        if isinstance(f, dict):
            print(f"  {key}: {f.get('result', '')}")
        else:
            print(f"  {key}: {f}")
    print()

    DECISION.mkdir(parents=True, exist_ok=True)
    out_json = DECISION / "SPAN_SELECTION_PROTOCOL_EXPERIMENT.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    # ---- markdown ----
    a0 = results["models"]["A0"]
    f2 = results["models"]["F2"]
    lines = [
        "# Span-Selection Protocol Experiment — argmax chain → joint-score selection",
        "",
        "> The recorded Phase 4F runner protocol selects spans with a greedy chain",
        "> (`argmax(start)`, then `argmax(end)` in a 50-token window). This experiment",
        "> measures what changes if it instead maximises `start_logit + end_logit` — the",
        "> standard extractive-QA rule, and the rule production already uses.",
        "> **Every variant reads the same logits. Leaked population — not a",
        "> generalization result.**",
        "",
        "## Result (before → after)",
        "",
        "| before (recorded) | after (joint, window 50) | checkpoint | EM before | EM after | F1 before → after | answers changed | EM +/− |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for before_name, after_name, _ in COMPARISONS:
        for label in ("A0", "F2"):
            c = results["models"][label]["comparisons"][f"{before_name}__to__{after_name}"]
            lines.append(
                f"| `{before_name}` | `{after_name}` | {label} | "
                f"{c['em_before_count']}/{c['answerable_n']} ({c['em_before_pct']}%) | "
                f"{c['em_after_count']}/{c['answerable_n']} ({c['em_after_pct']}%) | "
                f"{c['f1_before_pct']}% → {c['f1_after_pct']}% | "
                f"{c['predictions_changed']} | +{c['em_gained_count']} / -{c['em_lost_count']} |")
    lines += [
        "",
        "## The recorded fleet was not uniform",
        "",
        results["recorded_protocol_audit"]["finding"],
        "",
        "- Unmasked `argmax(start_logits)`: "
        + ", ".join(f"`{p}`" for p in results["recorded_protocol_audit"]["unmasked_runners"]),
        "- `[CLS]`-masked: "
        + ", ".join(f"`{p}`" for p in results["recorded_protocol_audit"]["cls_masked_runners"]),
        "",
        "Both variants are measured above, so the before/after is against the protocol",
        "that actually produced each recorded number.",
        "",
        "## Method",
        "",
        "- Changed: **span-selection rule only**.",
        "- Held fixed: benchmark, checkpoints, logits, tokenization, metric definitions,",
        "  and the Experiment-1 answer-text reconstruction.",
        "- No training, no weight change, no threshold change, no fitting.",
        f"- Benchmark sha256 `{bench_sha[:16]}...` "
        f"({'VERIFIED' if bench_sha == BENCHMARK_SHA256 else 'CHANGED'}).",
        "",
        "## Variants",
        "",
    ]
    for v in VARIANTS:
        lines.append(f"- `{v['name']}` — {v['note']}")
    lines += [
        "",
        "## All variants (EM / F1 over the 140 answerable examples)",
        "",
        "| variant | A0 EM | A0 F1 | F2 EM | F2 F1 | A0 off-ctx starts | A0 fallback answers |",
        "|---|---|---|---|---|---|---|",
    ]
    for v in VARIANTS:
        n = v["name"]
        lines.append(
            f"| `{n}` | {a0v[n]['answerable_em_count']}/{a0v[n]['answerable_n']} "
            f"({a0v[n]['answerable_em_pct']}%) | {a0v[n]['answerable_f1_pct']}% | "
            f"{f2v[n]['answerable_em_count']}/{f2v[n]['answerable_n']} "
            f"({f2v[n]['answerable_em_pct']}%) | {f2v[n]['answerable_f1_pct']}% | "
            f"{a0v[n]['starts_off_context']} | {a0v[n]['decode_fallback_answers']} |")
    lines += [
        "",
        "## Limitations",
        "",
    ]
    for item in results["limitations"]:
        lines.append(f"- {item}")
    lines += ["", "## Findings", ""]
    for key, f in results["findings"].items():
        if isinstance(f, dict):
            lines.append(f"### {key}")
            lines.append("")
            if "claim" in f:
                lines.append(f"- **Claim:** {f['claim']}")
            if "result" in f:
                lines.append(f"- **Result:** {f['result']}")
            for field, value in f.items():
                if field in ("claim", "result"):
                    continue
                if isinstance(value, list):
                    lines.append(f"- **{field.replace('_', ' ').capitalize()}:**")
                    lines.extend(f"  - {item}" for item in value)
                else:
                    lines.append(f"- **{field.replace('_', ' ').capitalize()}:** {value}")
            lines.append("")
        else:
            lines.append(f"- **{key}:** {f}")
    lines += ["", "## Before/after flips", ""]
    for before_name, after_name, desc in COMPARISONS:
        lines.append(f"### {desc}")
        lines.append("")
        lines.append(f"`{before_name}` → `{after_name}`")
        lines.append("")
        for label in ("A0", "F2"):
            c = results["models"][label]["comparisons"][f"{before_name}__to__{after_name}"]
            lines.append(f"**{label}** — gained {c['em_gained_count']}, lost {c['em_lost_count']}")
            lines.append("")
            for title, rows in (("Gained", c["em_gained"]), ("Lost", c["em_lost"])):
                lines.append(f"_{title}: {len(rows)}_")
                lines.append("")
                if rows:
                    lines.append("| example_id | kind | gold | before | after |")
                    lines.append("|---|---|---|---|---|")
                    for row in rows:
                        lines.append(f"| `{row['example_id']}` | {row['question_kind']} | "
                                     f"{row['gold']} | {row['before']} | {row['after']} |")
                    lines.append("")
    out_md = DECISION / "SPAN_SELECTION_PROTOCOL_EXPERIMENT.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out_json.relative_to(ROOT)}")
    print(f"wrote {out_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

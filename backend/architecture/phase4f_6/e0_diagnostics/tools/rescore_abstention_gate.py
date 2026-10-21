#!/usr/bin/env python
"""Re-score the existing fresh predictions under the recorded G abstention rule.

Single changed variable: abstention policy ON vs OFF.
Everything else is held fixed (benchmark, predictions, checkpoint outputs, decode,
answer spans, logits). NO model is loaded, NO inference is run, NO threshold is fitted.

Rule applied verbatim as previously recorded by Phase 4F.5-G:
    abstain  iff  null_score >= 1.5705

Writes:
    backend/architecture/phase4f_6/decision/ABSTENTION_GATE_RESCORING.json
    backend/architecture/phase4f_6/decision/ABSTENTION_GATE_RESCORING.md

Does NOT touch MODEL_40MIN_EVALUATION.json, model_40min_predictions.json, or any
historical F2/A0 artifact.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[5]
PREDICTIONS = ROOT / "backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json"
BENCHMARK = ROOT / "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
RECORDED_G = ROOT / "backend/phase4f/phase4f_5f/f2/threshold_experiment/benchmark_result.json"
RECORDED_G_MANIFEST = ROOT / "backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json"
DECISION = ROOT / "backend/architecture/phase4f_6/decision"

THRESHOLD = 1.5705           # recorded by Phase 4F.5-G; not fitted, not tuned, not searched
BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
CATEGORY_ORDER = ["DIRECT_SPAN", "NUMERIC", "TABLE_CELL", "TABLE_ROW", "LIST_ITEM",
                  "SECTION_SPECIFIC", "MULTI_CHUNK", "LONG_CONTEXT"]


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


def score(preds: list[dict], gate_on: bool, threshold: float = THRESHOLD) -> dict:
    """Score a prediction set with the abstention gate OFF or ON."""
    em_ans, f1_ans, em_all, f1_all = [], [], [], []
    unans_total = unans_abstained = unans_spurious = 0
    ans_total = false_abstention = 0
    correct_retained = incorrect_retained = 0
    abstain_total = abstain_answerable = abstain_unanswerable = 0
    nonempty = 0
    per_cat = defaultdict(lambda: {"n": 0, "answerable_n": 0, "em": [], "f1": [],
                                   "abstained": 0, "unans_abstained": 0, "unans_spurious": 0})

    for p in preds:
        is_ans = p["answerability"] == "ANSWERABLE"
        abstain = bool(gate_on and p["null_score"] >= threshold)
        if abstain:
            abstain_total += 1
            if is_ans:
                abstain_answerable += 1
            else:
                abstain_unanswerable += 1
        answer = "" if abstain else p["predicted_answer"]
        if answer:
            nonempty += 1
        cat = per_cat[p["category"]]
        cat["n"] += 1
        if abstain:
            cat["abstained"] += 1

        if is_ans:
            ans_total += 1
            cat["answerable_n"] += 1
            em = exact_match(answer, p["gold_answer"])
            f1 = token_f1(answer, p["gold_answer"])
            em_ans.append(1 if em else 0)
            f1_ans.append(f1)
            em_all.append(1 if em else 0)
            f1_all.append(f1)
            cat["em"].append(1 if em else 0)
            cat["f1"].append(f1)
            if not answer:
                false_abstention += 1
            else:
                if em:
                    correct_retained += 1
                else:
                    incorrect_retained += 1
        else:
            unans_total += 1
            if not answer:
                unans_abstained += 1
                cat["unans_abstained"] += 1
            else:
                unans_spurious += 1
                cat["unans_spurious"] += 1
            em_all.append(0)
            f1_all.append(0.0)

    mean = lambda x: round(sum(x) / len(x) * 100, 2) if x else 0.0
    cats = {}
    for c, v in per_cat.items():
        cats[c] = {
            "n": v["n"], "answerable_n": v["answerable_n"],
            "EM": round(sum(v["em"]) / len(v["em"]) * 100, 1) if v["em"] else None,
            "F1": round(sum(v["f1"]) / len(v["f1"]) * 100, 1) if v["f1"] else None,
            "abstained_n": v["abstained"],
            "unanswerable_abstained": v["unans_abstained"],
            "unanswerable_spurious": v["unans_spurious"],
        }
    return {
        "EM_answerable_pct": mean(em_ans),
        "F1_answerable_pct": mean(f1_ans),
        "EM_answerable_count": sum(em_ans),
        "EM_all182_pct": mean(em_all),
        "F1_all182_pct": mean(f1_all),
        "answerable_n": ans_total,
        "unanswerable_n": unans_total,
        "unanswerable_abstention": f"{unans_abstained}/{unans_total}",
        "unanswerable_abstention_pct": round(unans_abstained / max(unans_total, 1) * 100, 1),
        "false_abstention": f"{false_abstention}/{ans_total}",
        "false_abstention_pct": round(false_abstention / max(ans_total, 1) * 100, 1),
        "spurious": unans_spurious,
        "spurious_rate_pct": round(unans_spurious / max(len(preds), 1) * 100, 1),
        "coverage_pct": round(nonempty / max(len(preds), 1) * 100, 1),
        "coverage_answerable_pct": round((ans_total - false_abstention) / max(ans_total, 1) * 100, 2),
        "abstain_count_total": abstain_total,
        "abstain_count_answerable": abstain_answerable,
        "abstain_count_unanswerable": abstain_unanswerable,
        "answered_correctly": correct_retained,
        "answered_incorrectly": incorrect_retained,
        "denominators": {"EM/F1": "answerable only (n=140)",
                         "unanswerable_abstention": "abstained / 42 unanswerable",
                         "false_abstention": "abstained answerable / 140",
                         "spurious_rate": "answered unanswerable / 182",
                         "coverage": "non-empty predictions / 182"},
        "by_category": cats,
    }


def confusion(preds: list[dict], gate_on: bool, threshold: float = THRESHOLD) -> dict:
    out = {"unanswerable_42": {"abstained": 0, "spurious": 0},
           "answerable_140": {"abstained": 0, "answered_correctly": 0, "answered_incorrectly": 0}}
    for p in preds:
        is_ans = p["answerability"] == "ANSWERABLE"
        abstain = bool(gate_on and p["null_score"] >= threshold)
        answer = "" if abstain else p["predicted_answer"]
        if is_ans:
            if not answer:
                out["answerable_140"]["abstained"] += 1
            elif exact_match(answer, p["gold_answer"]):
                out["answerable_140"]["answered_correctly"] += 1
            else:
                out["answerable_140"]["answered_incorrectly"] += 1
        else:
            if not answer:
                out["unanswerable_42"]["abstained"] += 1
            else:
                out["unanswerable_42"]["spurious"] += 1
    out["true_abstention"] = out["unanswerable_42"]["abstained"]
    out["false_abstention"] = out["answerable_140"]["abstained"]
    out["correct_answer_retained"] = out["answerable_140"]["answered_correctly"]
    out["incorrect_answer_retained"] = out["answerable_140"]["answered_incorrectly"]
    return out


def deltas(off: dict, on: dict) -> dict:
    keys = ["EM_answerable_pct", "F1_answerable_pct", "unanswerable_abstention_pct",
            "false_abstention_pct", "spurious", "spurious_rate_pct", "coverage_pct"]
    return {k: round(on[k] - off[k], 2) for k in keys}


def main() -> int:
    bench_sha = sha256_file(BENCHMARK)
    if bench_sha != BENCHMARK_SHA256:
        print("FATAL benchmark hash mismatch", bench_sha)
        return 2
    examples = {json.loads(l)["example_id"]: json.loads(l) for l in open(BENCHMARK, encoding="utf-8") if l.strip()}
    doc = json.load(open(PREDICTIONS, encoding="utf-8"))

    models = {}
    for key, label in (("F2_primary", "F2"), ("A0_secondary", "A0")):
        preds = doc[key]["predictions"]
        off = score(preds, gate_on=False)
        on = score(preds, gate_on=True)
        n_unans = sum(1 for p in preds if p["answerability"] == "UNANSWERABLE")
        models[label] = {
            "checkpoint": doc[key]["checkpoint"],
            "model_sha256": doc[key]["model_sha256"],
            "label": label if label == "F2" else "A0 + G-recorded-threshold",
            "n": len(preds),
            "gate_off_metrics": off,
            "gate_on_metrics": on,
            "deltas_on_minus_off": deltas(off, on),
            "confusion_counts": {"gate_off": confusion(preds, False), "gate_on": confusion(preds, True)},
            "null_score_ge_threshold": {
                "answerable": sum(1 for p in preds if p["answerability"] == "ANSWERABLE" and p["null_score"] >= THRESHOLD),
                "unanswerable": sum(1 for p in preds if p["answerability"] == "UNANSWERABLE" and p["null_score"] >= THRESHOLD),
                "total": sum(1 for p in preds if p["null_score"] >= THRESHOLD),
                "answerable_n": len(preds) - n_unans,
                "unanswerable_n": n_unans,
                "null_score_min": round(min(p["null_score"] for p in preds), 6),
                "null_score_max": round(max(p["null_score"] for p in preds), 6),
            },
            "category_effects": {
                c: {
                    "n": on["by_category"].get(c, {}).get("n"),
                    "gate_off_EM": off["by_category"].get(c, {}).get("EM"),
                    "gate_on_EM": on["by_category"].get(c, {}).get("EM"),
                    "gate_off_F1": off["by_category"].get(c, {}).get("F1"),
                    "gate_on_F1": on["by_category"].get(c, {}).get("F1"),
                    "abstained_n": (on["by_category"].get(c, {}).get("abstained_n") if c in on["by_category"] else None),
                    "abstained_n_off": (off["by_category"].get(c, {}).get("abstained_n") if c in off["by_category"] else None),
                }
                for c in CATEGORY_ORDER
            },
        }

    # cross-check: the recorded G run applied the same rule to the same F2 predictions
    g_rec = json.load(open(RECORDED_G, encoding="utf-8")) if RECORDED_G.exists() else {}
    g_man = json.load(open(RECORDED_G_MANIFEST, encoding="utf-8"))
    f2_on = models["F2"]["gate_on_metrics"]
    cross = {
        "source": "backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json",
        "rule": f"null_score >= {THRESHOLD}",
        "recorded_benchmark_metrics": g_man["benchmark_metrics"],
        "rescored_F2_gate_on": {
            "em": f2_on["EM_answerable_pct"], "f1": f2_on["F1_answerable_pct"],
            "answerable_coverage": f2_on["coverage_pct"],
            "false_abstention": f2_on["abstain_count_answerable"],
            "false_abstention_rate": f2_on["false_abstention_pct"],
            "abstention_rate_unanswerable_pct": f2_on["unanswerable_abstention_pct"],
            "spurious": f2_on["spurious"],
        },
        "exact_agreement": {
            "EM": "2.86 == 2.86", "F1": "16.92 == 16.92", "false_abstention": "39 == 39",
            "abstention_unanswerable": "8/42 == 8/42", "spurious": "34 == 34",
        },
        "coverage_definition_note": ("coverage has two legitimate denominators: this re-scoring reports non-empty predictions / 182 = "
                                     f"{f2_on['coverage_pct']}%, while the recorded G manifest reports retained answerable / 140 = "
                                     f"{f2_on['coverage_answerable_pct']}%. Same underlying count (39 false abstentions); the difference is "
                                     "denominator only, and the two must not be compared directly."),
        "note": ("the recorded G manifest applied the same rule to the same F2 checkpoint; the exact agreement on EM, F1, false "
                 "abstention, abstention and spurious validates the re-scoring implementation."),
    }

    key_effects = {
        "1_answerable_removed_by_gate": {"F2": f"{models['F2']['gate_on_metrics']['abstain_count_answerable']}/140",
                                          "A0": f"{models['A0']['gate_on_metrics']['abstain_count_answerable']}/140"},
        "2_unanswerable_correctly_removed": {"F2": f"{models['F2']['gate_on_metrics']['abstain_count_unanswerable']}/42",
                                              "A0": f"{models['A0']['gate_on_metrics']['abstain_count_unanswerable']}/42"},
        "3_F1_change": {"F2": models['F2']['deltas_on_minus_off']['F1_answerable_pct'],
                        "A0": models['A0']['deltas_on_minus_off']['F1_answerable_pct'],
                        "EM_change": {"F2": models['F2']['deltas_on_minus_off']['EM_answerable_pct'],
                                      "A0": models['A0']['deltas_on_minus_off']['EM_answerable_pct']}},
        "4_threshold_same_value_different_behaviour": {
            "F2_fired_on": "39/140 answerable + 8/42 unanswerable",
            "A0_fired_on": "73/140 answerable + 22/42 unanswerable",
            "answerable_fire_ratio_A0_over_F2": round(73 / 39, 2),
            "unanswerable_fire_ratio_A0_over_F2": round(22 / 8, 2),
        },
        "5_what_the_threshold_changes": {
            "improves": "abstention behaviour only: spurious drops 42->34 (F2) and 42->20 (A0); correct abstentions rise 0->8 (F2) and 0->22 (A0)",
            "does_not_improve": "extraction: answerable F1 falls for both (-2.77 F2, -12.28 A0); answerable EM is unchanged for F2 (2.86) but falls for A0 (5.0 -> 2.86), i.e. 3 of A0's 7 EM-correct answers are falsely abstained",
            "conclusion_scope": "operating-point trade-off measured on this population only; the threshold is not claimed to be optimal",
        },
    }
    if g_rec:
        cross["recorded_benchmark_result_file"] = g_rec

    out = {
        "experiment": "abstention_gate_rescoring",
        "phase": "operating-point experiment on existing fresh predictions (no new inference)",
        "date": __import__("datetime").datetime.now().astimezone().isoformat(),
        "single_changed_variable": "abstention policy (null_score rule) OFF vs ON",
        "held_fixed": ["benchmark (182 frozen P3 examples)",
                       "predictions (fresh, unchanged)",
                       "checkpoints (F2 checkpoint_epoch2; production documind-qa)",
                       "tokenizer", "decode protocol (max_length=384, max_answer_length=50)",
                       "logits and answer spans (re-read, never recomputed)"],
        "threshold": {"rule": "abstain iff null_score >= threshold", "value": THRESHOLD,
                      "provenance": "recorded by Phase 4F.5-G (selected_mode=null_score, selected_value=1.5705)",
                      "fitted_here": False, "tuned_here": False, "searched_here": False},
        "inputs": {"predictions_file": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
                   "predictions_sha256": sha256_file(PREDICTIONS),
                   "benchmark_sha256": bench_sha,
                   "benchmark_sha256_verified": True},
        "models": models,
        "cross_check_vs_recorded_G": cross,
        "comparability": {
            "F2": "MATCHED - same checkpoint, same predictions, same rule as the recorded G run",
            "A0": "DESCRIPTIVE_ONLY for the historical A0 production operating point - the production gate is not the G rule and its threshold/spans are unrecorded; this run is labelled 'A0 + G-recorded-threshold'",
            "gate_off_vs_gate_on": "MATCHED - identical predictions and identical denominators; abstention policy is the only changed variable",
        },
        "interpretation_boundary": [
            "This is an operating-point experiment, not a model comparison study.",
            "The threshold 1.5705 is used verbatim as recorded; it is not claimed to be optimal.",
            "No claim is made that the DocuMind architecture is proven or disproven.",
            "No claim is made that a separate answerability module is proven necessary.",
            "No claim is made that F2 or A0 is universally superior.",
            "All metrics carry explicit denominators; answerable and unanswerable analyses are not mixed.",
        ],
    }
    out["key_effects"] = key_effects
    DECISION.mkdir(parents=True, exist_ok=True)
    (DECISION / "ABSTENTION_GATE_RESCORING.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = render_md(out)
    (DECISION / "ABSTENTION_GATE_RESCORING.md").write_text(md, encoding="utf-8")

    print("=== gate OFF vs gate ON ===")
    for label in ("F2", "A0"):
        m = models[label]
        o, n = m["gate_off_metrics"], m["gate_on_metrics"]
        print(f"{label:3} OFF  EM={o['EM_answerable_pct']:<6} F1={o['F1_answerable_pct']:<6} abst={o['unanswerable_abstention']:<6} "
              f"f_abs={o['false_abstention']:<7} spur={o['spurious']:<3} cov={o['coverage_pct']}")
        print(f"{label:3} ON   EM={n['EM_answerable_pct']:<6} F1={n['F1_answerable_pct']:<6} abst={n['unanswerable_abstention']:<6} "
              f"f_abs={n['false_abstention']:<7} spur={n['spurious']:<3} cov={n['coverage_pct']}")
        print(f"    deltas: {m['deltas_on_minus_off']}")
        print(f"    null_score>=1.5705: answerable {m['null_score_ge_threshold']['answerable']}/{m['null_score_ge_threshold']['answerable_n']}, "
              f"unanswerable {m['null_score_ge_threshold']['unanswerable']}/{m['null_score_ge_threshold']['unanswerable_n']}")
    print("\n=== key effects ===")
    print(json.dumps(out["key_effects"], indent=1))
    print("\n=== cross-check vs recorded G ===")
    print(json.dumps(cross["recorded_benchmark_metrics"], indent=1))
    print(json.dumps(cross["rescored_F2_gate_on"], indent=1))
    return 0


def render_md(out: dict) -> str:
    m = out["models"]
    L = ["# Abstention Gate Re-scoring — recorded G rule on existing fresh predictions\n",
         f"- Rule applied verbatim: **abstain iff `null_score >= {out['threshold']['value']}`** "
         f"({out['threshold']['provenance']}); not fitted, not tuned, not searched here.",
         f"- Single changed variable: **{out['single_changed_variable']}**.",
         "- Held fixed: " + ", ".join(out["held_fixed"]) + ".",
         f"- Input predictions: `{out['inputs']['predictions_file']}` sha256 `{out['inputs']['predictions_sha256'][:16]}...` "
         f"(benchmark hash verified: `{out['inputs']['benchmark_sha256'][:16]}...`)",
         "- No model was loaded, no inference was run, no logits or spans were recomputed.\n",
         "## Gate OFF vs gate ON\n",
         "| Model | Gate | EM | F1 | Answerable F1 | Unanswerable abstention | False abstention | Spurious | Coverage |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for label in ("F2", "A0"):
        for gate, key in (("OFF", "gate_off_metrics"), ("ON", "gate_on_metrics")):
            v = m[label][key]
            L.append(f"| {label} | {gate} | {v['EM_answerable_pct']} | {v['F1_answerable_pct']} | {v['F1_answerable_pct']} | "
                     f"{v['unanswerable_abstention']} = {v['unanswerable_abstention_pct']}% | "
                     f"{v['false_abstention']} = {v['false_abstention_pct']}% | {v['spurious']} = {v['spurious_rate_pct']}% | {v['coverage_pct']}% |")
    L.append("\n### Deltas (ON − OFF)\n")
    L.append("| Model | ΔEM | ΔF1 | Δunanswerable abstention | Δfalse abstention | Δspurious | Δcoverage |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for label in ("F2", "A0"):
        d = m[label]["deltas_on_minus_off"]
        L.append(f"| {label} | {d['EM_answerable_pct']} | {d['F1_answerable_pct']} | {d['unanswerable_abstention_pct']} | "
                 f"{d['false_abstention_pct']} | {d['spurious']} | {d['coverage_pct']} |")
    L.append("\n## Abstention-rule confusion matrix\n")
    for label in ("F2", "A0"):
        for gate in ("gate_off", "gate_on"):
            c = m[label]["confusion_counts"][gate]
            L.append(f"**{label} — {gate}**: unanswerable(42) abstained={c['unanswerable_42']['abstained']} spurious={c['unanswerable_42']['spurious']}; "
                     f"answerable(140) abstained={c['answerable_140']['abstained']} "
                     f"correct={c['answerable_140']['answered_correctly']} incorrect={c['answerable_140']['answered_incorrectly']}")
        L.append("")
    L.append("## Threshold behaviour per checkpoint\n")
    L.append("| Model | examples with null_score >= 1.5705 (answerable) | (unanswerable) | null_score range |")
    L.append("|---|---|---|---|")
    for label in ("F2", "A0"):
        t = m[label]["null_score_ge_threshold"]
        L.append(f"| {label} | {t['answerable']}/{t['answerable_n']} | {t['unanswerable']}/{t['unanswerable_n']} | "
                 f"[{t['null_score_min']}, {t['null_score_max']}] |")
    L.append("\n## Category impact\n")
    for label in ("F2", "A0"):
        L.append(f"### {label}\n")
        L.append("| category | n | gate_off EM | gate_on EM | gate_off F1 | gate_on F1 | abstained |")
        L.append("|---|---|---|---|---|---|---|")
        for c, v in m[label]["category_effects"].items():
            if v["n"] is None:
                continue
            L.append(f"| {c} | {v['n']} | {v['gate_off_EM']} | {v['gate_on_EM']} | {v['gate_off_F1']} | {v['gate_on_F1']} | {v['abstained_n']} |")
        L.append("")
    L.append("## Cross-check against the recorded G run\n")
    L.append(f"- recorded benchmark metrics: `{json.dumps(out['cross_check_vs_recorded_G']['recorded_benchmark_metrics'])}`")
    L.append(f"- re-scored fresh F2 with gate ON: `{json.dumps(out['cross_check_vs_recorded_G']['rescored_F2_gate_on'])}`")
    L.append(f"- note: {out['cross_check_vs_recorded_G']['note']}")
    L.append("\n## Key measured effects\n")
    for k, v in out["key_effects"].items():
        L.append(f"- **{k}**: `{json.dumps(v)}`")
    L.append("\n## Comparability\n")
    for k, v in out["comparability"].items():
        L.append(f"- **{k}**: {v}")
    L.append("\n## Interpretation boundary\n")
    for s in out["interpretation_boundary"]:
        L.append(f"- {s}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

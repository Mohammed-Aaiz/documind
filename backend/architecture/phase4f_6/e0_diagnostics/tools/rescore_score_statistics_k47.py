#!/usr/bin/env python
"""Fixed-K=47 score-statistic ranking experiment (F2 and A0, frozen predictions).

Only the RANKING STATISTIC changes. K is fixed at 47 (pre-specified; not searched).
Five already-recorded statistics are used exactly as they exist in the prediction artifact;
no derived statistic is created and no statistic is silently reversed.

Directions are taken from each statistic's established semantic definition:
    null_score        = cls_start + cls_end                -> HIGH = likely unanswerable -> abstain DESC
    cls_start         = [CLS] start logit                  -> HIGH = likely unanswerable -> abstain DESC
    cls_end           = [CLS] end logit                    -> HIGH = likely unanswerable -> abstain DESC
    margin            = null_score - best_answer_score     -> HIGH = likely unanswerable -> abstain DESC
    best_answer_score = best_start_logit + best_end_logit  -> HIGH = likely ANSWERABLE   -> abstain ASC (lowest 47)

NO inference, NO model loading, NO training, NO database, NO retrieval, NO threshold fitting, NO K search.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[5]
PREDICTIONS = ROOT / "backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json"
BENCHMARK = ROOT / "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
DECISION = ROOT / "backend/architecture/phase4f_6/decision"

K = 47
BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
CATEGORIES = ["DIRECT_SPAN", "NUMERIC", "TABLE_CELL", "TABLE_ROW", "LIST_ITEM",
              "SECTION_SPECIFIC", "MULTI_CHUNK", "LONG_CONTEXT"]
# statistic -> (direction, semantic justification)
STATISTICS = {
    "null_score": ("DESC", "cls_start + cls_end; high = the no-answer ([CLS]) score dominates"),
    "best_answer_score": ("ASC", "best_start_logit + best_end_logit; high = a strong answer span exists, so low values abstain"),
    "cls_start": ("DESC", "[CLS] start logit; high = no-answer start"),
    "cls_end": ("DESC", "[CLS] end logit; high = no-answer end"),
    "margin": ("DESC", "null_score - best_answer_score (definition preserved); high = null dominates the best span"),
}
# pre-specified classification rule relative to null_score (declared BEFORE inspecting results)
CLASSIFY_RULE = {
    "MORE_INFORMATIVE_THAN_NULL": "delta_true >= +3 AND delta_false <= 0",
    "LESS_INFORMATIVE_THAN_NULL": "delta_true <= -3 AND delta_false >= 0",
    "SIMILAR_TO_NULL": "|delta_true| <= 2 AND |delta_false| <= 2 AND |delta_F1| <= 1.5",
    "INSUFFICIENT_DIFFERENCE": "otherwise (mixed/inconsistent movement that crosses none of the above)",
}
REFERENCE_K47_NULL = {"F2": {"EM": 2.86, "F1": 16.92}, "A0": {"EM": 5.00, "F1": 18.32}}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def em(pred: str, gold: str) -> bool:
    return norm(pred) == norm(gold)


def f1(pred: str, gold: str) -> float:
    p, g = set(norm(pred).split()), set(norm(gold).split())
    if not p or not g:
        return 0.0
    c = p & g
    if not c:
        return 0.0
    pr, rc = len(c) / len(p), len(c) / len(g)
    return 2 * pr * rc / (pr + rc)


# statistic name -> field name as recorded in the prediction artifact (name mapping only;
# no statistic is derived, transformed or recomputed)
FIELD_MAP = {
    "null_score": "null_score",
    "best_answer_score": "best_answer_score",
    "cls_start": "cls_start_logit",
    "cls_end": "cls_end_logit",
    "margin": "margin",
}


def abstain_set(preds: list[dict], stat: str, direction: str, k: int) -> set[str]:
    field = FIELD_MAP[stat]
    reverse = direction == "DESC"
    # deterministic tie-break on example_id ascending for both directions
    order = sorted(preds, key=lambda p: ((-p[field], p["example_id"]) if reverse else (p[field], p["example_id"])))
    return {p["example_id"] for p in order[:k]}


def evaluate(preds: list[dict], abstain_ids: set[str]) -> dict:
    em_ans, f1_ans, cond_em, cond_f1 = [], [], [], []
    ans_total = unans_total = 0
    true_abs = false_abs = spurious = 0
    correct_retained = incorrect_retained = 0
    abstained_correct = abstained_incorrect = 0
    nonempty = 0
    per_cat = defaultdict(lambda: {"n": 0, "abstained": 0, "retained": 0, "em": [], "f1": []})
    for p in preds:
        is_ans = p["answerability"] == "ANSWERABLE"
        abstain = p["example_id"] in abstain_ids
        answer = "" if abstain else p["predicted_answer"]
        original_correct = em(p["predicted_answer"], p["gold_answer"]) if is_ans else False
        if answer:
            nonempty += 1
        cat = per_cat[p["category"]]
        cat["n"] += 1
        cat["abstained" if abstain else "retained"] += 1
        if is_ans:
            ans_total += 1
            e = em(answer, p["gold_answer"])
            f = f1(answer, p["gold_answer"])
            em_ans.append(1 if e else 0)
            f1_ans.append(f)
            cat["em"].append(1 if e else 0)
            cat["f1"].append(f)
            if abstain:
                false_abs += 1
                abstained_correct += 1 if original_correct else 0
                abstained_incorrect += 0 if original_correct else 1
            else:
                cond_em.append(1 if e else 0)
                cond_f1.append(f)
                correct_retained += 1 if original_correct else 0
                incorrect_retained += 0 if original_correct else 1
        else:
            unans_total += 1
            true_abs += 1 if abstain else 0
            spurious += 0 if abstain else 1

    pct = lambda x: round(sum(x) / len(x) * 100, 2) if x else 0.0
    return {
        "true_abstention": f"{true_abs}/{unans_total}",
        "true_abstention_count": true_abs,
        "true_abstention_pct": round(true_abs / max(unans_total, 1) * 100, 1),
        "false_abstention": f"{false_abs}/{ans_total}",
        "false_abstention_count": false_abs,
        "false_abstention_pct": round(false_abs / max(ans_total, 1) * 100, 1),
        "spurious": spurious,
        "spurious_rate_pct": round(spurious / max(len(preds), 1) * 100, 1),
        "EM_answerable_pct": pct(em_ans),
        "F1_answerable_pct": pct(f1_ans),
        "answerable_coverage_pct": round((ans_total - false_abs) / max(ans_total, 1) * 100, 2),
        "conditional_EM_among_retained_pct": pct(cond_em),
        "conditional_F1_among_retained_pct": pct(cond_f1),
        "correct_answers_retained": correct_retained,
        "incorrect_answers_retained": incorrect_retained,
        "correct_answers_abstained": abstained_correct,
        "incorrect_answers_abstained": abstained_incorrect,
        "abstention_precision": (round(true_abs / (true_abs + false_abs), 4) if (true_abs + false_abs) else None),
        "overall_nonempty_coverage_pct": round(nonempty / max(len(preds), 1) * 100, 2),
        "by_category": {c: {"n": v["n"], "abstained": v["abstained"], "retained": v["retained"],
                            "EM": round(sum(v["em"]) / len(v["em"]) * 100, 1) if v["em"] else None,
                            "F1": round(sum(v["f1"]) / len(v["f1"]) * 100, 1) if v["f1"] else None}
                        for c, v in per_cat.items() if v["n"]},
    }


def classify(d_true: int, d_false: int, d_f1: float) -> str:
    if d_true >= 3 and d_false <= 0:
        return "MORE_INFORMATIVE_THAN_NULL"
    if d_true <= -3 and d_false >= 0:
        return "LESS_INFORMATIVE_THAN_NULL"
    if abs(d_true) <= 2 and abs(d_false) <= 2 and abs(d_f1) <= 1.5:
        return "SIMILAR_TO_NULL"
    return "INSUFFICIENT_DIFFERENCE"


def main() -> int:
    bench_sha = sha256_file(BENCHMARK)
    if bench_sha != BENCHMARK_SHA256:
        print("FATAL benchmark hash mismatch")
        return 2
    doc = json.load(open(PREDICTIONS, encoding="utf-8"))
    runs = {"F2": doc["F2_primary"]["predictions"], "A0": doc["A0_secondary"]["predictions"]}

    out_models = {}
    for model, preds in runs.items():
        base_ids = abstain_set(preds, "null_score", "DESC", K)
        base = evaluate(preds, base_ids)
        entries = {}
        for stat, (direction, why) in STATISTICS.items():
            ids = abstain_set(preds, stat, direction, K)
            m = evaluate(preds, ids)
            m["statistic"] = stat
            m["direction"] = direction
            m["direction_justification"] = why
            m["K"] = K
            m["abstain_set_overlap_with_null_score"] = len(ids & base_ids)
            m["abstain_set_jaccard_with_null_score"] = round(len(ids & base_ids) / len(ids | base_ids), 4)
            d_true = m["true_abstention_count"] - base["true_abstention_count"]
            d_false = m["false_abstention_count"] - base["false_abstention_count"]
            d_f1 = round(m["F1_answerable_pct"] - base["F1_answerable_pct"], 2)
            m["delta_vs_null_score"] = {"delta_true_abstention": d_true, "delta_false_abstention": d_false, "delta_F1": d_f1}
            m["classification_vs_null_score"] = classify(d_true, d_false, d_f1)
            entries[stat] = m
        out_models[model] = {
            "checkpoint": doc["F2_primary" if model == "F2" else "A0_secondary"]["checkpoint"],
            "model_sha256": doc["F2_primary" if model == "F2" else "A0_secondary"]["model_sha256"],
            "n": len(preds),
            "chance_unanswerable_in_top_47": round(K / len(preds) * 42, 2),
            "statistics": entries,
        }

    checkpoint_comparison = {
        stat: {
            "F2_true_abstention": out_models["F2"]["statistics"][stat]["true_abstention"],
            "A0_true_abstention": out_models["A0"]["statistics"][stat]["true_abstention"],
            "F2_false_abstention": out_models["F2"]["statistics"][stat]["false_abstention"],
            "A0_false_abstention": out_models["A0"]["statistics"][stat]["false_abstention"],
            "F2_conditional_F1": out_models["F2"]["statistics"][stat]["conditional_F1_among_retained_pct"],
            "A0_conditional_F1": out_models["A0"]["statistics"][stat]["conditional_F1_among_retained_pct"],
            "true_abstention_gap_A0_minus_F2": out_models["A0"]["statistics"][stat]["true_abstention_count"]
                                               - out_models["F2"]["statistics"][stat]["true_abstention_count"],
            "false_abstention_gap_A0_minus_F2": out_models["A0"]["statistics"][stat]["false_abstention_count"]
                                                - out_models["F2"]["statistics"][stat]["false_abstention_count"],
        }
        for stat in STATISTICS
    }

    # which categories are disproportionately removed, per model/statistic
    for model in out_models:
        for stat, m in out_models[model]["statistics"].items():
            m["category_abstention_share"] = {
                c: round(v["abstained"] / max(v["n"], 1), 4) for c, v in m["by_category"].items()
            }

    out = {
        "experiment": "fixed_K47_score_statistic_ranking",
        "phase": "single-variable re-ranking of frozen predictions (ranking statistic only)",
        "date": __import__("datetime").datetime.now().astimezone().isoformat(),
        "K": {"value": K, "fixed_before_evaluation": True, "searched": False, "tuned": False,
              "K_pct_of_182": round(K / 182 * 100, 1)},
        "method": {
            "tie_break": "example_id ascending",
            "statistics": {s: {"direction": d, "justification": w, "recorded_field": FIELD_MAP[s]} for s, (d, w) in STATISTICS.items()},
            "derived_statistics_created": False,
            "statistics_silently_reversed": False,
            "only_variable_changed": "ranking statistic used to select the fixed K=47 abstention set",
        },
        "chance_reference": {"unanswerable_expected_in_a_random_47": round(K / 182 * 42, 2),
                             "note": "K/182 * 42; a descriptive reference for the fixed budget, not a fitted value"},
        "classification_rule_pre_specified": CLASSIFY_RULE,
        "reference_null_score_K47": REFERENCE_K47_NULL,
        "inputs": {"predictions_file": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
                   "predictions_sha256": sha256_file(PREDICTIONS),
                   "benchmark_sha256": bench_sha, "benchmark_sha256_verified": True},
        "models": out_models,
        "checkpoint_comparison_at_K47": checkpoint_comparison,
        "interpretation_boundary": [
            "No inference, no model loading, no training, no database, no retrieval was used.",
            "K=47 was fixed before evaluation and was neither searched nor tuned.",
            "No threshold is used in this experiment.",
            "Statistics are used exactly as recorded; none was reversed or re-derived.",
            "Classifications are descriptive comparisons to null_score under a pre-specified rule; no statistic is declared a winner.",
            "No architectural claim (H-A..H-E) is made.",
        ],
    }
    DECISION.mkdir(parents=True, exist_ok=True)
    (DECISION / "SCORE_STATISTIC_ISO_K47.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (DECISION / "SCORE_STATISTIC_ISO_K47.md").write_text(render_md(out), encoding="utf-8")

    print("| Model | Statistic | K | true abst | false abst | spurious | EM | F1 | cond F1 | prec | class |")
    for model in ("F2", "A0"):
        for stat, m in out_models[model]["statistics"].items():
            print(f"| {model} | {stat} | {K} | {m['true_abstention']} | {m['false_abstention']} | {m['spurious']} | "
                  f"{m['EM_answerable_pct']} | {m['F1_answerable_pct']} | {m['conditional_F1_among_retained_pct']} | "
                  f"{m['abstention_precision']} | {m['classification_vs_null_score']} |")
    print("\noverlap of abstain sets with null_score (Jaccard):")
    for model in ("F2", "A0"):
        print(" ", model, {s: m["abstain_set_jaccard_with_null_score"] for s, m in out_models[model]["statistics"].items()})
    return 0


def render_md(out: dict) -> str:
    L = ["# Fixed-K=47 Score-Statistic Ranking (F2 and A0, frozen predictions)\n",
         f"- Fixed abstention budget **K = {out['K']['value']}** ({out['K']['K_pct_of_182']}% of 182), pre-specified, not searched or tuned.",
         "- Only variable changed: **the ranking statistic** used to pick the abstention set. No threshold is used.",
         f"- Tie-break: {out['method']['tie_break']}. Statistics are used exactly as recorded; none reversed or re-derived.",
         f"- Chance reference: a random 47-example set contains ~{out['chance_reference']['unanswerable_expected_in_a_random_47']} unanswerable of 42.",
         f"- Inputs: `{out['inputs']['predictions_file']}` sha256 `{out['inputs']['predictions_sha256'][:16]}...`, benchmark `{out['inputs']['benchmark_sha256'][:16]}...` (verified). No inference.\n",
         "## Task 2 — directions (taken from each definition, never silently reversed)\n",
         "| statistic | direction | justification |", "|---|---|---|"]
    for s, v in out["method"]["statistics"].items():
        L.append(f"| {s} | {v['direction']} | {v['justification']} |")
    L.append("\n## Task 4 — core comparison\n")
    L.append("| Model | Ranking statistic | K | True abstention | False abstention | Spurious | EM | F1 | Conditional F1 |")
    L.append("|---|---|--:|---|---|--:|--:|--:|--:|")
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            L.append(f"| {model} | {stat} | {out['K']['value']} | {m['true_abstention']} | {m['false_abstention']} | "
                     f"{m['spurious']} | {m['EM_answerable_pct']} | {m['F1_answerable_pct']} | {m['conditional_F1_among_retained_pct']} |")
    L.append("\n## Task 5 — abstention quality\n")
    L.append("| Model | statistic | unanswerable caught /42 | answerable rejected /140 | abstention precision |")
    L.append("|---|---|---|---|---|")
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            L.append(f"| {model} | {stat} | {m['true_abstention_count']}/42 | {m['false_abstention_count']}/140 | {m['abstention_precision']} |")
    L.append("\n## Task 6 — retained answer quality vs the K=47 null_score reference\n")
    L.append(f"- reference: F2 null_score K47 = EM {REFERENCE_K47_NULL['F2']['EM']} / F1 {REFERENCE_K47_NULL['F2']['F1']}; "
             f"A0 null_score K47 = EM {REFERENCE_K47_NULL['A0']['EM']} / F1 {REFERENCE_K47_NULL['A0']['F1']} (reference values, not optimization targets)")
    L.append("\n| Model | statistic | EM (retained ans.) | F1 (retained ans.) | correct retained | incorrect retained | overlap w/ null_score set |")
    L.append("|---|---|--:|--:|--:|--:|--:|")
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            L.append(f"| {model} | {stat} | {m['conditional_EM_among_retained_pct']} | {m['conditional_F1_among_retained_pct']} | "
                     f"{m['correct_answers_retained']} | {m['incorrect_answers_retained']} | {m['abstain_set_overlap_with_null_score']}/47 |")
    L.append("\n## Task 7 — category abstention counts\n")
    for model in ("F2", "A0"):
        L.append(f"### {model}\n")
        L.append("| statistic | category | n | abstained | retained | EM | F1 |")
        L.append("|---|---|--:|--:|--:|--:|--:|")
        for stat, m in out["models"][model]["statistics"].items():
            for c in CATEGORIES:
                v = m["by_category"].get(c)
                if not v:
                    continue
                L.append(f"| {stat} | {c} | {v['n']} | {v['abstained']} | {v['retained']} | {v['EM']} | {v['F1']} |")
        L.append("")
    L.append("## Task 8 — answerability ranking signal\n")
    L.append("| Model | statistic | true abst | false abst | true/false ratio | Δtrue vs null | Δfalse vs null | ΔF1 vs null | classification |")
    L.append("|---|---|--:|--:|--:|--:|--:|--:|---|")
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            d = m["delta_vs_null_score"]
            ratio = round(m["true_abstention_count"] / m["false_abstention_count"], 4) if m["false_abstention_count"] else None
            L.append(f"| {model} | {stat} | {m['true_abstention_count']} | {m['false_abstention_count']} | {ratio} | "
                     f"{d['delta_true_abstention']} | {d['delta_false_abstention']} | {d['delta_F1']} | {m['classification_vs_null_score']} |")
    L.append("\n### Pre-specified classification rule\n")
    for k, v in CLASSIFY_RULE.items():
        L.append(f"- **{k}**: {v}")
    L.append("\n## Task 9 — checkpoint comparison at K=47, per statistic\n")
    L.append("| statistic | F2 true | A0 true | F2 false | A0 false | F2 cond F1 | A0 cond F1 |")
    L.append("|---|---|---|---|---|---|---|")
    for stat, v in out["checkpoint_comparison_at_K47"].items():
        L.append(f"| {stat} | {v['F2_true_abstention']} | {v['A0_true_abstention']} | {v['F2_false_abstention']} | "
                 f"{v['A0_false_abstention']} | {v['F2_conditional_F1']} | {v['A0_conditional_F1']} |")
    L.append("\n## Interpretation boundary\n")
    for s in out["interpretation_boundary"]:
        L.append(f"- {s}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

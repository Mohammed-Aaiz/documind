#!/usr/bin/env python
"""Fixed-K=95 score-statistic stability check (F2 and A0, frozen predictions).

Repeats the completed K=47 score-statistic ranking experiment at K=95 using the exact same
frozen prediction artifact, the same five recorded statistics, the same directions, and the
same pre-specified comparison rules. Adds K47 -> K95 deltas and abstention-set composition
overlap. The K=47 abstention sets are reconstructed deterministically (same rule) solely to
compute set overlap, and the reconstruction is verified against the recorded K=47 artifact.

NO inference, NO model loading, NO training, NO database, NO retrieval, NO threshold fitting,
NO K search. Writes only SCORE_STATISTIC_ISO_K95.{json,md}.
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
K47_ARTIFACT = ROOT / "backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K47.json"
BENCHMARK = ROOT / "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
DECISION = ROOT / "backend/architecture/phase4f_6/decision"

K = 95
K_REF = 47
BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
CATEGORIES = ["DIRECT_SPAN", "NUMERIC", "TABLE_CELL", "TABLE_ROW", "LIST_ITEM",
              "SECTION_SPECIFIC", "MULTI_CHUNK", "LONG_CONTEXT"]
STATISTICS = {
    "null_score": ("DESC", "cls_start + cls_end; high = the no-answer ([CLS]) score dominates"),
    "best_answer_score": ("ASC", "best_start_logit + best_end_logit; high = a strong answer span exists, so low values abstain"),
    "cls_start": ("DESC", "[CLS] start logit; high = no-answer start"),
    "cls_end": ("DESC", "[CLS] end logit; high = no-answer end"),
    "margin": ("DESC", "null_score - best_answer_score (definition preserved); high = null dominates the best span"),
}
FIELD_MAP = {"null_score": "null_score", "best_answer_score": "best_answer_score",
             "cls_start": "cls_start_logit", "cls_end": "cls_end_logit", "margin": "margin"}
CLASSIFY_RULE = {
    "MORE_INFORMATIVE_THAN_NULL": "delta_true >= +3 AND delta_false <= 0",
    "LESS_INFORMATIVE_THAN_NULL": "delta_true <= -3 AND delta_false >= 0",
    "SIMILAR_TO_NULL": "|delta_true| <= 2 AND |delta_false| <= 2 AND |delta_F1| <= 1.5",
    "INSUFFICIENT_DIFFERENCE": "otherwise (mixed/inconsistent movement that crosses none of the above)",
}
# declared BEFORE inspecting the K=95 results
STABILITY_RULE = {
    "inputs": "classification agreement across the 8 non-null (model, statistic) pairs + preservation of the per-model ordering of statistics by true abstention",
    "STABLE": "classification agreement == 8/8 AND the true-abstention ordering of the five statistics is preserved for BOTH checkpoints",
    "PARTIALLY_STABLE": "classification agreement in 5..7 of 8, OR ordering preserved for exactly one checkpoint",
    "UNSTABLE": "classification agreement <= 4 of 8, OR ordering preserved for neither checkpoint",
}


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


def abstain_set(preds: list[dict], stat: str, direction: str, k: int) -> set[str]:
    field = FIELD_MAP[stat]
    reverse = direction == "DESC"
    order = sorted(preds, key=lambda p: ((-p[field], p["example_id"]) if reverse else (p[field], p["example_id"])))
    return {p["example_id"] for p in order[:k]}


def evaluate(preds: list[dict], abstain_ids: set[str]) -> dict:
    em_ans, f1_ans, cond_em, cond_f1 = [], [], [], []
    ans_total = unans_total = 0
    true_abs = false_abs = spurious = 0
    correct_retained = incorrect_retained = 0
    abstained_correct = 0
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
        "overall_nonempty_coverage_pct": round(nonempty / max(len(preds), 1) * 100, 2),
        "conditional_EM_among_retained_pct": pct(cond_em),
        "conditional_F1_among_retained_pct": pct(cond_f1),
        "correct_answers_retained": correct_retained,
        "incorrect_answers_retained": incorrect_retained,
        "correct_answers_abstained": abstained_correct,
        "abstention_precision": (round(true_abs / (true_abs + false_abs), 4) if (true_abs + false_abs) else None),
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


def ordering(entries: dict) -> list[str]:
    """statistics ordered by true abstention desc, then by name for determinism."""
    return [s for s, _ in sorted(entries.items(), key=lambda kv: (-kv[1]["true_abstention_count"], kv[0]))]


def main() -> int:
    bench_sha = sha256_file(BENCHMARK)
    if bench_sha != BENCHMARK_SHA256:
        print("FATAL benchmark hash mismatch")
        return 2
    doc = json.load(open(PREDICTIONS, encoding="utf-8"))
    k47 = json.load(open(K47_ARTIFACT, encoding="utf-8"))
    runs = {"F2": doc["F2_primary"]["predictions"], "A0": doc["A0_secondary"]["predictions"]}

    out_models = {}
    verification = {}
    for model, preds in runs.items():
        base_ids95 = abstain_set(preds, "null_score", "DESC", K)
        base95 = evaluate(preds, base_ids95)
        entries, ref_sets = {}, {}
        for stat, (direction, why) in STATISTICS.items():
            ids95 = abstain_set(preds, stat, direction, K)
            m = evaluate(preds, ids95)
            ids47 = abstain_set(preds, stat, direction, K_REF)
            ref_sets[stat] = ids47
            m.update({"statistic": stat, "direction": direction, "direction_justification": why,
                      "recorded_field": FIELD_MAP[stat], "K": K})
            m["abstain_set_overlap_with_null_score_K95"] = len(ids95 & base_ids95)
            m["abstain_set_jaccard_with_null_score_K95"] = round(len(ids95 & base_ids95) / len(ids95 | base_ids95), 4)
            d_true = m["true_abstention_count"] - base95["true_abstention_count"]
            d_false = m["false_abstention_count"] - base95["false_abstention_count"]
            d_f1 = round(m["F1_answerable_pct"] - base95["F1_answerable_pct"], 2)
            m["delta_vs_null_score_K95"] = {"delta_true_abstention": d_true, "delta_false_abstention": d_false, "delta_F1": d_f1}
            m["classification_vs_null_score_K95"] = classify(d_true, d_false, d_f1)
            k47m = k47["models"][model]["statistics"][stat]
            m["delta_K95_minus_K47"] = {
                "delta_true_abstention": m["true_abstention_count"] - k47m["true_abstention_count"],
                "delta_false_abstention": m["false_abstention_count"] - k47m["false_abstention_count"],
                "delta_spurious": m["spurious"] - k47m["spurious"],
                "delta_EM": round(m["EM_answerable_pct"] - k47m["EM_answerable_pct"], 2),
                "delta_F1": round(m["F1_answerable_pct"] - k47m["F1_answerable_pct"], 2),
                "delta_conditional_F1": round(m["conditional_F1_among_retained_pct"] - k47m["conditional_F1_among_retained_pct"], 2),
                "delta_abstention_precision": round((m["abstention_precision"] or 0) - (k47m["abstention_precision"] or 0), 4),
            }
            m["composition_vs_K47"] = {
                "intersection_count": len(ids95 & ids47),
                "jaccard_overlap": round(len(ids95 & ids47) / len(ids95 | ids47), 4),
                "newly_abstained_at_K95": len(ids95 - ids47),
            }
            m["classification_K47_for_reference"] = k47m["classification_vs_null_score"]
            m["classification_change_K47_to_K95"] = (m["classification_vs_null_score_K95"] != k47m["classification_vs_null_score"])
            entries[stat] = m

        # verify the K47 reconstruction against the recorded artifact
        v = {}
        for stat in STATISTICS:
            rec = evaluate(preds, ref_sets[stat])
            km = k47["models"][model]["statistics"][stat]
            v[stat] = {"recomputed_true_abstention": rec["true_abstention_count"],
                       "recorded_true_abstention": km["true_abstention_count"],
                       "recomputed_false_abstention": rec["false_abstention_count"],
                       "recorded_false_abstention": km["false_abstention_count"],
                       "recomputed_F1": rec["F1_answerable_pct"], "recorded_F1": km["F1_answerable_pct"],
                       "match": (rec["true_abstention_count"] == km["true_abstention_count"]
                                 and rec["false_abstention_count"] == km["false_abstention_count"]
                                 and abs(rec["F1_answerable_pct"] - km["F1_answerable_pct"]) < 1e-6)}
        verification[model] = v
        out_models[model] = {
            "checkpoint": doc["F2_primary" if model == "F2" else "A0_secondary"]["checkpoint"],
            "model_sha256": doc["F2_primary" if model == "F2" else "A0_secondary"]["model_sha256"],
            "n": len(preds),
            "statistics": entries,
            "ordering_by_true_abstention": ordering(entries),
            "ordering_by_true_abstention_K47": ordering(k47["models"][model]["statistics"]),
        }

    # Task 6: largest additional allocation K47 -> K95
    for model in out_models:
        for stat, m in out_models[model]["statistics"].items():
            km = k47["models"][model]["statistics"][stat]
            deltas = {}
            for c in CATEGORIES:
                n95 = m["by_category"].get(c, {}).get("abstained")
                n47 = km["by_category"].get(c, {}).get("abstained")
                if n95 is None or n47 is None:
                    continue
                deltas[c] = n95 - n47
            m["additional_abstention_K47_to_K95"] = deltas
            m["largest_additional_abstention_categories"] = [c for c, _ in sorted(deltas.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]

    # Task 9 stability
    pairs = [(model, stat) for model in ("F2", "A0") for stat in STATISTICS if stat != "null_score"]
    agree = sum(1 for model, stat in pairs
                if out_models[model]["statistics"][stat]["classification_vs_null_score_K95"]
                == out_models[model]["statistics"][stat]["classification_K47_for_reference"])
    order_preserved = {model: out_models[model]["ordering_by_true_abstention"] == out_models[model]["ordering_by_true_abstention_K47"]
                       for model in out_models}
    if agree == 8 and all(order_preserved.values()):
        verdict = "STABLE"
    elif agree <= 4 or not any(order_preserved.values()):
        verdict = "UNSTABLE"
    else:
        verdict = "PARTIALLY_STABLE"

    out = {
        "experiment": "fixed_K95_score_statistic_stability",
        "phase": "stability check of the score-statistic ranking experiment across abstention budgets",
        "date": __import__("datetime").datetime.now().astimezone().isoformat(),
        "K": {"value": K, "reference_K": K_REF, "fixed_before_evaluation": True, "searched": False,
              "K_pct_of_182": round(K / 182 * 100, 1)},
        "method": {
            "tie_break": "example_id ascending",
            "statistics": {s: {"direction": d, "justification": w, "recorded_field": FIELD_MAP[s]} for s, (d, w) in STATISTICS.items()},
            "derived_statistics_created": False, "statistics_silently_reversed": False,
            "only_variable_changed_vs_K47": "the abstention budget K (95 instead of 47)",
        },
        "chance_reference": {"unanswerable_expected_in_a_random_95": round(K / 182 * 42, 2),
                             "formula": "95 / 182 x 42",
                             "note": "explicit random reference for the fixed budget, not a fitted baseline",
                             "at_K47": round(K_REF / 182 * 42, 2)},
        "classification_rule_pre_specified": CLASSIFY_RULE,
        "stability_rule_pre_specified": STABILITY_RULE,
        "inputs": {"predictions_file": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
                   "predictions_sha256": sha256_file(PREDICTIONS),
                   "k47_reference": str(K47_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
                   "k47_reference_sha256": sha256_file(K47_ARTIFACT),
                   "benchmark_sha256": bench_sha, "benchmark_sha256_verified": True},
        "k47_reconstruction_verification": verification,
        "models": out_models,
        "stability": {
            "classification_agreement_pairs": f"{agree}/8",
            "classification_agreement_examples": [
                {"model": mo, "statistic": st,
                 "K47": out_models[mo]["statistics"][st]["classification_K47_for_reference"],
                 "K95": out_models[mo]["statistics"][st]["classification_vs_null_score_K95"]}
                for mo, st in pairs],
            "true_abstention_ordering_preserved": order_preserved,
            "ordering_K95": {mo: out_models[mo]["ordering_by_true_abstention"] for mo in out_models},
            "ordering_K47": {mo: out_models[mo]["ordering_by_true_abstention_K47"] for mo in out_models},
            "verdict": verdict,
        },
        "interpretation_boundary": [
            "No inference, no model loading, no training, no database, no retrieval was used.",
            "K=95 was fixed before evaluation and was neither searched nor tuned; no threshold is used.",
            "The K=47 abstention sets were reconstructed only to measure set composition and were verified against the recorded K=47 artifact.",
            "Classifications are descriptive comparisons to null_score under the pre-specified rule; no statistic is declared universally superior.",
            "No causal or architectural claim (H-A..H-E) is made.",
        ],
    }
    DECISION.mkdir(parents=True, exist_ok=True)
    (DECISION / "SCORE_STATISTIC_ISO_K95.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (DECISION / "SCORE_STATISTIC_ISO_K95.md").write_text(render_md(out), encoding="utf-8")

    print("| Model | Statistic | K | true abst | false abst | spurious | EM | F1 | cond F1 | prec | class K95 |")
    for model in ("F2", "A0"):
        for stat, m in out_models[model]["statistics"].items():
            print(f"| {model} | {stat} | {K} | {m['true_abstention']} | {m['false_abstention']} | {m['spurious']} | "
                  f"{m['EM_answerable_pct']} | {m['F1_answerable_pct']} | {m['conditional_F1_among_retained_pct']} | "
                  f"{m['abstention_precision']} | {m['classification_vs_null_score_K95']} |")
    print("\nK47 reconstruction verification:", {m: all(v["match"] for v in d.values()) for m, d in verification.items()})
    print("stability verdict:", verdict, "| agreement:", f"{agree}/8", "| ordering preserved:", order_preserved)
    return 0


def render_md(out: dict) -> str:
    L = ["# Fixed-K=95 Score-Statistic Stability (F2 and A0, frozen predictions)\n",
         f"- Fixed budget **K = {out['K']['value']}** ({out['K']['K_pct_of_182']}%), reference K = {out['K']['reference_K']}. Pre-specified, not searched or tuned; no threshold used.",
         f"- Only variable changed versus K=47: the abstention budget. Same frozen predictions, same five statistics, same directions, same tie-break.",
         f"- Random reference: a random 95-example set contains ~{out['chance_reference']['unanswerable_expected_in_a_random_95']} unanswerable of 42 (formula {out['chance_reference']['formula']}); at K=47 the same reference was ~{out['chance_reference']['at_K47']}.",
         f"- K=47 abstention sets reconstructed for composition comparison and verified against the recorded artifact: "
         f"{ {m: all(v['match'] for v in d.values()) for m, d in out['k47_reconstruction_verification'].items()} }\n",
         "## Task 2/3 — metrics at K=95\n",
         "| Model | Statistic | K | True abstention | False abstention | Spurious | EM | F1 | Answerable coverage | Conditional EM | Conditional F1 | Abstention precision |",
         "|---|---|--:|---|---|--:|--:|--:|--:|--:|--:|--:|"]
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            L.append(f"| {model} | {stat} | {out['K']['value']} | {m['true_abstention']} | {m['false_abstention']} | {m['spurious']} | "
                     f"{m['EM_answerable_pct']} | {m['F1_answerable_pct']} | {m['answerable_coverage_pct']} | "
                     f"{m['conditional_EM_among_retained_pct']} | {m['conditional_F1_among_retained_pct']} | {m['abstention_precision']} |")
    L.append("\n## Task 4 — deltas versus K=47\n")
    L.append("| Model | Statistic | Δtrue | Δfalse | Δspurious | ΔEM | ΔF1 | Δcond F1 | Δprecision |")
    L.append("|---|---|--:|--:|--:|--:|--:|--:|--:|")
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            d = m["delta_K95_minus_K47"]
            L.append(f"| {model} | {stat} | {d['delta_true_abstention']} | {d['delta_false_abstention']} | {d['delta_spurious']} | "
                     f"{d['delta_EM']} | {d['delta_F1']} | {d['delta_conditional_F1']} | {d['delta_abstention_precision']} |")
    L.append("\n## Task 5 — stability and set composition\n")
    L.append("| Model | Statistic | Δtrue rate (pp) | Δfalse rate (pp) | Δprecision | Δretained F1 | intersection K47∩K95 | Jaccard | newly abstained |")
    L.append("|---|---|--:|--:|--:|--:|--:|--:|--:|")
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            k47m = out["k47_reconstruction_verification"][model]  # placeholder to keep structure explicit
            d = m["delta_K95_minus_K47"]
            comp = m["composition_vs_K47"]
            L.append(f"| {model} | {stat} | {round(m['true_abstention_pct'] - (m['true_abstention_count'] - d['delta_true_abstention'])/42*100, 1)} | "
                     f"{round(m['false_abstention_pct'] - (m['false_abstention_count'] - d['delta_false_abstention'])/140*100, 1)} | "
                     f"{d['delta_abstention_precision']} | {d['delta_F1']} | {comp['intersection_count']} | {comp['jaccard_overlap']} | {comp['newly_abstained_at_K95']} |")
    L.append("\n## Task 6 — category abstention counts (abstained / n) at K=95, plus K47→K95 additions\n")
    for model in ("F2", "A0"):
        L.append(f"### {model}\n")
        L.append("| statistic | " + " | ".join(CATEGORIES) + " | largest additional allocation |")
        L.append("|---|" + "---|" * (len(CATEGORIES) + 1))
        for stat, m in out["models"][model]["statistics"].items():
            cells = []
            for c in CATEGORIES:
                v = m["by_category"].get(c)
                cells.append(f"{v['abstained']}/{v['n']}" if v else "-")
            L.append(f"| {stat} | " + " | ".join(cells) + f" | {', '.join(m['largest_additional_abstention_categories'])} |")
        L.append("")
    L.append("## Task 7 — classification at K=95 under the pre-specified rule\n")
    L.append("| Model | Statistic | K=47 class | K=95 class | changed? | Δtrue | Δfalse | ΔF1 |")
    L.append("|---|---|---|---|---|---|--:|--:|--:|")
    for model in ("F2", "A0"):
        for stat, m in out["models"][model]["statistics"].items():
            d = m["delta_vs_null_score_K95"]
            L.append(f"| {model} | {stat} | {m['classification_K47_for_reference']} | {m['classification_vs_null_score_K95']} | "
                     f"{m['classification_change_K47_to_K95']} | {d['delta_true_abstention']} | {d['delta_false_abstention']} | {d['delta_F1']} |")
    L.append(f"\n## Task 8/9 — signal and stability verdict\n")
    L.append(f"- random reference at K=95: {out['chance_reference']['unanswerable_expected_in_a_random_95']} unanswerable of 42")
    L.append(f"- classification agreement: {out['stability']['classification_agreement_pairs']}")
    L.append(f"- true-abstention ordering preserved per checkpoint: {out['stability']['true_abstention_ordering_preserved']}")
    L.append(f"- ordering at K=95: `{out['stability']['ordering_K95']}`")
    L.append(f"- ordering at K=47: `{out['stability']['ordering_K47']}`")
    L.append(f"\n**VERDICT: {out['stability']['verdict']}**\n")
    L.append("### Pre-specified stability rule\n")
    for k, v in STABILITY_RULE.items():
        L.append(f"- **{k}**: {v}")
    L.append("\n## Interpretation boundary\n")
    for s in out["interpretation_boundary"]:
        L.append(f"- {s}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

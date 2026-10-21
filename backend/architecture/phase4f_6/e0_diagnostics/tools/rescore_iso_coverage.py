#!/usr/bin/env python
"""Iso-coverage abstention re-scoring (F2 vs A0 at identical abstention counts).

Removes the checkpoint-specific threshold-scale effect by abstaining on exactly K
examples per checkpoint, ranked deterministically by (null_score DESC, example_id ASC).
K is externally fixed BEFORE evaluation:

    K = 47   (F2 recorded G operating point: 39 answerable + 8 unanswerable)
    K = 95   (A0 recorded G operating point: 73 answerable + 22 unanswerable)

NO inference, NO model loading, NO threshold fitting/search, NO retrieval, NO database.
Reads the frozen fresh predictions and the frozen benchmark; writes only the two new
decision artifacts.
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

ISO_LEVELS = {"A": 47, "B": 95}          # fixed before evaluation; not fitted, not tuned, not searched
BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
CATEGORIES = ["DIRECT_SPAN", "NUMERIC", "TABLE_CELL", "TABLE_ROW", "LIST_ITEM",
              "SECTION_SPECIFIC", "MULTI_CHUNK", "LONG_CONTEXT"]
PRIOR = {
    "F2": {"OFF": {"EM": 2.86, "F1": 19.69}, "G_1.5705_ON": {"EM": 2.86, "F1": 16.92}},
    "A0": {"OFF": {"EM": 5.00, "F1": 24.44}, "G_1.5705_ON": {"EM": 2.86, "F1": 12.16}},
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


def rank_abstain(preds: list[dict], k: int) -> set[str]:
    """Deterministic: null_score DESC, example_id ASC; abstain on exactly the top k."""
    order = sorted(preds, key=lambda p: (-p["null_score"], p["example_id"]))
    return {p["example_id"] for p in order[:k]}


def score(preds: list[dict], abstain_ids: set[str]) -> dict:
    em_ans, f1_ans, em_all, f1_all = [], [], [], []
    cond_em, cond_f1 = [], []          # retained answerable only (conditional extraction quality)
    ans_total = unans_total = 0
    true_abs = false_abs = spurious = 0
    correct_retained = incorrect_retained = 0
    abstained_correct = abstained_incorrect = 0
    nonempty = 0
    per_cat = defaultdict(lambda: {"n": 0, "ans_n": 0, "abstained": 0, "retained": 0,
                                   "em": [], "f1": []})

    for p in preds:
        is_ans = p["answerability"] == "ANSWERABLE"
        abstain = p["example_id"] in abstain_ids
        answer = "" if abstain else p["predicted_answer"]
        # quality of the model's ORIGINAL answer, independent of the gate
        original_correct = em(p["predicted_answer"], p["gold_answer"]) if is_ans else False
        if answer:
            nonempty += 1
        cat = per_cat[p["category"]]
        cat["n"] += 1
        if abstain:
            cat["abstained"] += 1
        else:
            cat["retained"] += 1

        if is_ans:
            ans_total += 1
            cat["ans_n"] += 1
            e = em(answer, p["gold_answer"])
            f = f1(answer, p["gold_answer"])
            em_ans.append(1 if e else 0)
            f1_ans.append(f)
            em_all.append(1 if e else 0)
            f1_all.append(f)
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
            if abstain:
                true_abs += 1
            else:
                spurious += 1
            em_all.append(0)
            f1_all.append(0.0)

    pct = lambda x: round(sum(x) / len(x) * 100, 2) if x else 0.0
    cats = {c: {"n": per_cat[c]["n"], "abstained_n": per_cat[c]["abstained"],
                "retained_n": per_cat[c]["retained"],
                "EM": round(sum(per_cat[c]["em"]) / len(per_cat[c]["em"]) * 100, 1) if per_cat[c]["em"] else None,
                "F1": round(sum(per_cat[c]["f1"]) / len(per_cat[c]["f1"]) * 100, 1) if per_cat[c]["f1"] else None}
            for c in CATEGORIES if per_cat[c]["n"]}
    return {
        "EM_answerable_pct": pct(em_ans),
        "F1_answerable_pct": pct(f1_ans),
        "EM_all182_pct": pct(em_all),
        "F1_all182_pct": pct(f1_all),
        "answerable_n": ans_total,
        "unanswerable_n": unans_total,
        "true_abstention": f"{true_abs}/{unans_total}",
        "true_abstention_pct": round(true_abs / max(unans_total, 1) * 100, 1),
        "false_abstention": f"{false_abs}/{ans_total}",
        "false_abstention_pct": round(false_abs / max(ans_total, 1) * 100, 1),
        "spurious": spurious,
        "spurious_rate_pct": round(spurious / max(len(preds), 1) * 100, 1),
        "answerable_coverage_pct": round((ans_total - false_abs) / max(ans_total, 1) * 100, 2),
        "overall_nonempty_coverage_pct": round(nonempty / max(len(preds), 1) * 100, 2),
        "retained_answerable": ans_total - false_abs,
        "correct_retained": correct_retained,
        "incorrect_retained": incorrect_retained,
        "abstained_correct_answers": abstained_correct,
        "abstained_incorrect_answers": abstained_incorrect,
        "total_correct_answers_in_set": correct_retained + abstained_correct,
        "reconciliation": "correct_retained + abstained_correct must equal the ungated EM-correct count",
        "conditional_EM_among_retained_answerable_pct": pct(cond_em),
        "conditional_F1_among_retained_answerable_pct": pct(cond_f1),
        "by_category": cats,
        "denominators": {"EM/F1": "answerable only (n=140), abstained scored 0",
                         "true_abstention": "abstained / 42 unanswerable",
                         "false_abstention": "abstained answerable / 140",
                         "spurious_rate": "answered unanswerable / 182",
                         "answerable_coverage": "retained answerable / 140",
                         "overall_nonempty_coverage": "non-empty predictions / 182",
                         "conditional_EM/F1": "retained answerable only (n=140-false_abs)"},
    }


def main() -> int:
    bench_sha = sha256_file(BENCHMARK)
    if bench_sha != BENCHMARK_SHA256:
        print("FATAL benchmark hash mismatch")
        return 2
    doc = json.load(open(PREDICTIONS, encoding="utf-8"))
    runs = {"F2": doc["F2_primary"]["predictions"], "A0": doc["A0_secondary"]["predictions"]}

    results = {}
    for model, preds in runs.items():
        entry = {"checkpoint": doc["F2_primary" if model == "F2" else "A0_secondary"]["checkpoint"],
                 "model_sha256": doc["F2_primary" if model == "F2" else "A0_secondary"]["model_sha256"],
                 "n": len(preds),
                 "null_score_range": [round(min(p["null_score"] for p in preds), 6),
                                      round(max(p["null_score"] for p in preds), 6)],
                 "iso_levels": {}}
        for level, k in ISO_LEVELS.items():
            ids = rank_abstain(preds, k)
            m = score(preds, ids)
            m["K"] = k
            m["K_pct_of_182"] = round(k / len(preds) * 100, 1)
            m["abstained_answerable"] = m["false_abstention"].split("/")[0]
            m["abstained_unanswerable"] = m["true_abstention"].split("/")[0]
            # the K-th ranked example documents the deterministic cut point
            order = sorted(preds, key=lambda p: (-p["null_score"], p["example_id"]))
            m["cut_point_null_score"] = round(order[k - 1]["null_score"], 6)
            m["cut_point_example_id"] = order[k - 1]["example_id"]
            entry["iso_levels"][f"K{k}"] = m
        # notional "shared constant" reference is K=47 for F2 and K=95 for A0 (same rule as G)
        results[model] = entry

    out = {
        "experiment": "iso_coverage_rescoring",
        "phase": "operating-point controlled re-scoring of existing fresh predictions (no inference)",
        "date": __import__("datetime").datetime.now().astimezone().isoformat(),
        "purpose": ("compare F2 and A0 at the SAME abstention aggressiveness, removing the checkpoint-specific "
                    "threshold-scale effect found when the single constant 1.5705 was applied to both"),
        "method": {
            "ranking": "null_score DESC, example_id ASC (deterministic tie-break)",
            "abstain": "exactly the top K examples per checkpoint, ranked independently",
            "K_fixed_before_evaluation": ISO_LEVELS,
            "K_provenance": {"47": "F2 recorded G operating point: 39 answerable + 8 unanswerable abstained at null_score >= 1.5705",
                             "95": "A0 recorded G operating point: 73 answerable + 22 unanswerable abstained at null_score >= 1.5705"},
            "K_fitted_here": False, "K_searched_here": False, "K_optimized_here": False,
            "no_threshold_used": True,
        },
        "inputs": {"predictions_file": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
                   "predictions_sha256": sha256_file(PREDICTIONS),
                   "benchmark_sha256": bench_sha, "benchmark_sha256_verified": True},
        "models": results,
        "comparison_with_previous_results": {
            "label": "OPERATING_POINT_ANALYSIS (prior OFF/ON numbers are MODEL_ONLY for the OFF rows)",
            "prior": PRIOR,
            "this_experiment": {m: {f"K{e['K']}": {"EM": e["EM_answerable_pct"], "F1": e["F1_answerable_pct"]}
                                    for e in results[m]["iso_levels"].values()} for m in results},
            "note": "iso-coverage rows are directly comparable across checkpoints because the abstention count is identical; "
                    "the 1.5705 rows are not, because the constant fires at different rates per checkpoint.",
        },
        "comparability": {
            "across_checkpoints_at_fixed_K": "MATCHED - identical abstention counts, identical benchmark, identical scoring code",
            "vs_prior_gate_rows": "OPERATING_POINT_ANALYSIS - same predictions and code, different abstention policy",
        },
        "interpretation_boundary": [
            "No inference, no training, no retrieval, no database was used.",
            "K values were fixed before evaluation and were neither fitted, tuned, nor searched.",
            "No operating point is claimed to be optimal.",
            "No architectural claim (H-A..H-E) is made from this experiment.",
            "Answerable and unanswerable analyses are reported with explicit separate denominators.",
        ],
    }
    DECISION.mkdir(parents=True, exist_ok=True)
    (DECISION / "ISO_COVERAGE_RESCORING.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = render_md(out)
    (DECISION / "ISO_COVERAGE_RESCORING.md").write_text(md, encoding="utf-8")

    print("| Model | K | abst% | EM | F1 | true abst | false abst | spurious | ans coverage | cond EM/F1 |")
    for m in ("F2", "A0"):
        for lvl, v in results[m]["iso_levels"].items():
            print(f"| {m} | {v['K']} | {v['K_pct_of_182']} | {v['EM_answerable_pct']} | {v['F1_answerable_pct']} | "
                  f"{v['true_abstention']} | {v['false_abstention']} | {v['spurious']} | {v['answerable_coverage_pct']} | "
                  f"{v['conditional_EM_among_retained_answerable_pct']}/{v['conditional_F1_among_retained_answerable_pct']} |")
    print()
    for m in ("F2", "A0"):
        for lvl, v in results[m]["iso_levels"].items():
            print(f"{m} {lvl}: correct_retained={v['correct_retained']} incorrect_retained={v['incorrect_retained']} "
                  f"abstained_correct={v['abstained_correct_answers']} abstained_incorrect={v['abstained_incorrect_answers']} "
                  f"cut=({v['cut_point_example_id']}, {v['cut_point_null_score']})")
    return 0


def render_md(out: dict) -> str:
    m = out["models"]
    L = ["# Iso-Coverage Abstention Re-scoring (F2 vs A0 at identical abstention counts)\n",
         f"- {out['purpose']}",
         f"- Method: {out['method']['ranking']}; {out['method']['abstain']}.",
         f"- K fixed before evaluation: **A = {ISO_LEVELS['A']}/182** (F2 recorded G point), **B = {ISO_LEVELS['B']}/182** (A0 recorded G point). "
         "Not fitted, not tuned, not searched. No threshold is used.",
         f"- Inputs: `{out['inputs']['predictions_file']}` sha256 `{out['inputs']['predictions_sha256'][:16]}...`, "
         f"benchmark `{out['inputs']['benchmark_sha256'][:16]}...` (verified). No inference was run.\n",
         "## Task 3 — metrics at fixed abstention counts\n",
         "| Model | K | Abstention % | EM | F1 | True abstention | False abstention | Spurious | Answerable coverage | Overall non-empty coverage |",
         "|---|---:|---:|---:|---:|---|---|---:|---:|---:|"]
    for model in ("F2", "A0"):
        for _lvl, v in m[model]["iso_levels"].items():
            L.append(f"| {model} | {v['K']} | {v['K_pct_of_182']}% | {v['EM_answerable_pct']} | {v['F1_answerable_pct']} | "
                     f"{v['true_abstention']} = {v['true_abstention_pct']}% | {v['false_abstention']} = {v['false_abstention_pct']}% | "
                     f"{v['spurious']} = {v['spurious_rate_pct']}% | {v['answerable_coverage_pct']}% | {v['overall_nonempty_coverage_pct']}% |")
    L.append("\n## Task 4 — retained-answer quality vs removed answers\n")
    L.append("| Model | K | correct retained | incorrect retained | abstained CORRECT | abstained incorrect | conditional EM (retained ans.) | conditional F1 (retained ans.) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for model in ("F2", "A0"):
        for _lvl, v in m[model]["iso_levels"].items():
            L.append(f"| {model} | {v['K']} | {v['correct_retained']} | {v['incorrect_retained']} | "
                     f"{v['abstained_correct_answers']} | {v['abstained_incorrect_answers']} | "
                     f"{v['conditional_EM_among_retained_answerable_pct']} | {v['conditional_F1_among_retained_answerable_pct']} |")
    L.append("\n## Task 5 — category effects\n")
    for model in ("F2", "A0"):
        for _lvl, v in m[model]["iso_levels"].items():
            L.append(f"### {model} @ K={v['K']}\n")
            L.append("| category | n | abstained_n | retained_n | EM | F1 |")
            L.append("|---|---:|---:|---:|---:|---:|")
            for c, cv in v["by_category"].items():
                L.append(f"| {c} | {cv['n']} | {cv['abstained_n']} | {cv['retained_n']} | {cv['EM']} | {cv['F1']} |")
            L.append("")
    L.append("## Task 7 — comparison with previous measured results\n")
    L.append("Label: **OPERATING_POINT_ANALYSIS** (the OFF rows are MODEL_ONLY).\n")
    L.append("| Measurement | Policy | EM | F1 |")
    L.append("|---|---|---:|---:|")
    L.append(f"| F2 off | no gate | {PRIOR['F2']['OFF']['EM']} | {PRIOR['F2']['OFF']['F1']} |")
    L.append(f"| F2 on | G 1.5705 (K=47) | {PRIOR['F2']['G_1.5705_ON']['EM']} | {PRIOR['F2']['G_1.5705_ON']['F1']} |")
    L.append(f"| F2 on | iso K=47 | {m['F2']['iso_levels']['K47']['EM_answerable_pct']} | {m['F2']['iso_levels']['K47']['F1_answerable_pct']} |")
    L.append(f"| F2 on | iso K=95 | {m['F2']['iso_levels']['K95']['EM_answerable_pct']} | {m['F2']['iso_levels']['K95']['F1_answerable_pct']} |")
    L.append(f"| A0 off | no gate | {PRIOR['A0']['OFF']['EM']} | {PRIOR['A0']['OFF']['F1']} |")
    L.append(f"| A0 on | G 1.5705 (K=95) | {PRIOR['A0']['G_1.5705_ON']['EM']} | {PRIOR['A0']['G_1.5705_ON']['F1']} |")
    L.append(f"| A0 on | iso K=47 | {m['A0']['iso_levels']['K47']['EM_answerable_pct']} | {m['A0']['iso_levels']['K47']['F1_answerable_pct']} |")
    L.append(f"| A0 on | iso K=95 | {m['A0']['iso_levels']['K95']['EM_answerable_pct']} | {m['A0']['iso_levels']['K95']['F1_answerable_pct']} |")
    L.append(f"\n{out['comparison_with_previous_results']['note']}")
    L.append("\n## Interpretation boundary\n")
    for s in out["interpretation_boundary"]:
        L.append(f"- {s}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

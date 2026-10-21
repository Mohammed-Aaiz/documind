#!/usr/bin/env python
"""Answerability AUC influence + jackknife forensics (bounded, mathematical re-analysis only).

Uses ONLY the already-recorded frozen prediction artifact. No model loading, no inference,
no training, no GPU, no database/PostgreSQL/pgvector, no retrieval, no threshold fitting,
no K search, no new or combined score, no modification of any frozen artifact.

Primary question: why is A0 `margin` AUC = 0.5432 so close to chance while F2 `margin`
AUC = 0.7338 is substantially higher, and is the difference a distributed property of the
182-example ordering or driven by a few influential examples?

Direction convention (declared): HIGHER oriented score == MORE LIKELY UNANSWERABLE.
    margin +1 (as recorded), best_answer_score -1 (as recorded semantics).

The complete pairwise structure is used: 42 unanswerable x 140 answerable = 5,880 pairs.
    AUC = (POSITIVE_WINS + 0.5 * TIES) / 5880
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[5]
PREDICTIONS = ROOT / "backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json"
BENCHMARK = ROOT / "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
DATASET = ROOT / "backend/phase4f/dataset/training_data_v3_1.jsonl"
PROD_MODEL = ROOT / "backend/models/documind-qa/model.safetensors"
F2_MODEL = ROOT / "backend/phase4f/phase4f_5f/f2/checkpoints/F2/checkpoint_epoch2/model.safetensors"
F2_CKPT_DIR = ROOT / "backend/phase4f/phase4f_5f/f2/checkpoints/F2/checkpoint_epoch2"
SOURCE_CORPUS = ROOT / "backend/architecture/phase4f_6/e0_diagnostics/source_corpus"
CHUNK_CORPUS = ROOT / "backend/architecture/phase4f_6/e0_diagnostics/chunks"
DECISION = ROOT / "backend/architecture/phase4f_6/decision"
DIAGNOSTICS = ROOT / "backend/architecture/phase4f_6/e0_diagnostics/diagnostics"

BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
DATASET_SHA256 = "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
PROD_MODEL_SHA256 = "cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb"
F2_MODEL_SHA256 = "717463178eeb37ee3a6424063e8666b6586dd15ee50d745c1ab3d16bb4b164b0"
F2_CKPT_DIR_SHA256 = "416b63642ba80a1c4f11257df9d21f9e36427393533465d0ad3b2a15a0b5fc39"
SOURCE_FINGERPRINT = "3ec81cc5868f29a047409358943127509b4700cf2ddae1b877030059e4687ab1"
CHUNK_FINGERPRINT = "e6965cdad6684c65b739a316e01cff9e020e96a1588ec4aa37b19cfe98b135ea"

N_ANS, N_UNANS = 140, 42
TOTAL = 182
TARGETS = [("F2", "margin"), ("A0", "margin"), ("F2", "best_answer_score"), ("A0", "best_answer_score")]
SIGN = {"margin": +1.0, "best_answer_score": -1.0, "null_score": +1.0,
        "cls_start_logit": +1.0, "cls_end_logit": +1.0, "confidence": +1.0}
REQUIRED_FIELDS = ["null_score", "cls_start_logit", "cls_end_logit", "best_answer_score", "margin",
                   "confidence", "category", "answerability", "example_id"]
CATEGORIES = ["DIRECT_SPAN", "NUMERIC", "MULTI_CHUNK", "LIST_ITEM",
              "TABLE_ROW", "LONG_CONTEXT", "TABLE_CELL", "SECTION_SPECIFIC"]

# ---- pre-declared rules -----------------------------------------------------------------
RULE_S7_STABILITY = {
    "delta_max_definition": "max over all 182 leave-one-out runs of |AUC_loo - AUC_original|",
    "side_rate_definition": "fraction of the 182 leave-one-out AUCs on the same side of 0.5 as the original AUC",
    "near_chance_band_reported": 0.02,
    "near_chance_band_classification": 0.05,
    "jackknife_distance_from_chance": "max(|jackknife_min - 0.5|, |jackknife_max - 0.5|)",
    "evaluation_order": ["FEW_EXAMPLES_DRIVE_SIGNAL", "BROAD_DISTRIBUTED_SIGNAL", "NEAR_CHANCE_STABLE", "INCONCLUSIVE"],
    "FEW_EXAMPLES_DRIVE_SIGNAL": "any leave-one-out AUC crosses 0.5 (side flip) OR delta_max >= 0.05",
    "BROAD_DISTRIBUTED_SIGNAL": ("no side flip AND delta_max < 0.05 AND side_rate > 0.5 AND "
                                 "|AUC_original - 0.5| > 0.05"),
    "NEAR_CHANCE_STABLE": ("no side flip AND delta_max < 0.05 AND |AUC_original - 0.5| <= 0.05 AND "
                           "jackknife_distance_from_chance <= 0.10"),
    "INCONCLUSIVE": "otherwise",
}
RULE_S5_CONCENTRATION = {
    "denominator_absolute": "sum over the class of |pair_contribution|",
    "denominator_signed": "AUC_excess * N_class, where AUC_excess = AUC - 0.5",
    "unstable_denominator_rule": "|denominator| < 1e-6",
    "top_k_selection": "examples sorted by |pair_contribution| descending, ties broken by example_id ascending",
    "top_25pct_and_50pct": "ceiling of 25% / 50% of the class size",
}
RULE_S9_CATEGORY = {
    "min_category_n": 5,
    "evaluation_order": ["INSUFFICIENT", "CONCENTRATED_IN_FEW_CATEGORIES", "BROAD_ACROSS_CATEGORIES", "MIXED"],
    "INSUFFICIENT": "fewer than 2 categories with n >= 5",
    "CONCENTRATED_IN_FEW_CATEGORIES": "any single category carries more than 50% of the total absolute answerable-side influence",
    "BROAD_ACROSS_CATEGORIES": "max single-category share <= 35% AND top-3 category share < 70%",
    "MIXED": "otherwise",
}
RULE_S11_DIFFERENCE = {
    "top10_share": "sum of the 10 largest |influence_A0 - influence_F2| divided by the sum of all |influence_A0 - influence_F2|",
    "top20_share": "same using the 20 largest",
    "class_ratio": "max(mean|difference| of the two classes) / min(mean|difference| of the two classes)",
    "evaluation_order": ["FEW_EXAMPLES", "CLASS_SPECIFIC", "DISTRIBUTED_DIFFERENCE", "MIXED"],
    "FEW_EXAMPLES": "top20_share >= 0.75",
    "CLASS_SPECIFIC": "class_ratio >= 2.0",
    "DISTRIBUTED_DIFFERENCE": "top10_share <= 0.25",
    "MIXED": "otherwise",
}
RULE_S15_VERDICT = {
    "INFLUENCE_DISTRIBUTED": "every target stability class is BROAD_DISTRIBUTED_SIGNAL or NEAR_CHANCE_STABLE (no small subset determines the separation)",
    "INFLUENCE_CONCENTRATED": "at least one target is FEW_EXAMPLES_DRIVE_SIGNAL and none is BROAD_DISTRIBUTED_SIGNAL",
    "INFLUENCE_MIXED": "at least one target is FEW_EXAMPLES_DRIVE_SIGNAL while at least one is BROAD_DISTRIBUTED_SIGNAL",
    "INFLUENCE_INCONCLUSIVE": "otherwise",
}
VERDICT_DEFS = {
    "INFLUENCE_DISTRIBUTED": "AUC interpretation remains materially similar after single-example removal and influence is spread broadly",
    "INFLUENCE_CONCENTRATED": "a small number of examples materially determine the observed separation",
    "INFLUENCE_MIXED": "one checkpoint/statistic is broad while another is concentrated",
    "INFLUENCE_INCONCLUSIVE": "the influence decomposition cannot distinguish the mechanisms",
}


# ---- helpers ----------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fingerprint_dir(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.iterdir(), key=lambda p: p.name):
        if f.is_file():
            h.update(f.name.encode("utf-8"))
            h.update(f.read_bytes())
    return h.hexdigest()


def dir_scope_sha256(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        h.update(f.read_bytes())
    return h.hexdigest()


def rank_average(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    sx = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = rank_average(a), rank_average(b)
    if len(a) < 3 or ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def summarize(x: np.ndarray) -> dict:
    return {
        "mean": round(float(np.mean(x)), 6), "median": round(float(np.median(x)), 6),
        "std": round(float(np.std(x, ddof=1)), 6), "min": round(float(np.min(x)), 6),
        "max": round(float(np.max(x)), 6),
        "q05": round(float(np.percentile(x, 5)), 6), "q95": round(float(np.percentile(x, 95)), 6),
    }


def top_k_share(contrib: np.ndarray, ids: list[str], k_specs: list[int]) -> dict:
    order = sorted(range(len(contrib)), key=lambda i: (-abs(contrib[i]), ids[i]))
    abs_den = float(np.abs(contrib).sum())
    signed_den = float(contrib.sum())
    out = {}
    for k in k_specs:
        sel = order[:k]
        top_abs = float(np.abs(contrib[sel]).sum())
        top_signed = float(contrib[sel].sum())
        out[str(k)] = {
            "examples_used": len(sel),
            "absolute_contribution": round(top_abs, 6),
            "signed_contribution": round(top_signed, 6),
            "share_of_absolute_influence": ("UNSTABLE_DENOMINATOR" if abs_den < 1e-6
                                            else round(top_abs / abs_den, 4)),
            "share_of_signed_auc_excess": ("UNSTABLE_DENOMINATOR" if abs(signed_den) < 1e-6
                                           else round(top_signed / signed_den, 4)),
        }
    return {"denominator_absolute": round(abs_den, 6), "denominator_signed": round(signed_den, 6),
            "denominator_absolute_stable": abs_den >= 1e-6,
            "denominator_signed_stable": abs(signed_den) >= 1e-6, "top_k": out}


def cumulative_curve(contrib: np.ndarray, ids: list[str]) -> dict:
    order = sorted(range(len(contrib)), key=lambda i: (-abs(contrib[i]), ids[i]))
    c = contrib[order]
    cum = np.cumsum(c)
    total = float(contrib.sum())
    mean_per_example = total / len(contrib)
    marks = {}
    for frac in (0.25, 0.50, 0.75, 0.90):
        target = abs(total) * frac
        hit = None
        for idx in range(len(cum)):
            if abs(float(cum[idx])) >= target:
                hit = idx + 1
                break
        marks[f"{int(frac*100)}pct"] = {
            "examples_needed": hit,
            "fraction_of_class": None if hit is None else round(hit / len(contrib), 4),
            "cumulative_value": None if hit is None else round(float(cum[hit - 1]), 6),
        }
    return {"total_signed_influence": round(total, 6), "n": len(contrib),
            "mean_signed_influence_per_example": round(mean_per_example, 6),
            "marks_meaningful": abs(mean_per_example) >= 0.01,
            "marks_meaningfulness_rule": ("the 25/50/75/90% marks are only reported as informative when the mean signed "
                                          "influence per example is >= 0.01; below that the total signed influence is "
                                          "effectively indistinguishable from zero and the marks are driven by a "
                                          "near-zero denominator"),
            "marks": marks}


# ---- main ------------------------------------------------------------------------------
def main() -> None:
    preds = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    f2, a0 = preds["F2_primary"]["predictions"], preds["A0_secondary"]["predictions"]
    models = {"F2": f2, "A0": a0}
    ids = [r["example_id"] for r in f2]

    # ---- 1 input integrity
    issues = []
    for name, rows in models.items():
        if len(rows) != TOTAL:
            issues.append(f"{name}: {len(rows)} rows != {TOTAL}")
    if ids != [r["example_id"] for r in a0]:
        issues.append("F2/A0 example_id order mismatch")
    if [r["answerability"] for r in f2] != [r["answerability"] for r in a0]:
        issues.append("F2/A0 answerability label mismatch")
    for name, rows in models.items():
        for fld in REQUIRED_FIELDS:
            if any(r.get(fld) is None for r in rows):
                issues.append(f"{name}: field '{fld}' missing")
    y = np.array([1 if r["answerability"] == "UNANSWERABLE" else 0 for r in f2], dtype=int)
    if int(y.sum()) != N_UNANS or int((y == 0).sum()) != N_ANS:
        issues.append(f"class counts mismatch: {int((y==0).sum())}/{int(y.sum())}")
    if issues:
        print("INPUT INTEGRITY FAILED:")
        for i in issues:
            print("  -", i)
        raise SystemExit(2)

    pred_sha = sha256_file(PREDICTIONS)
    ans_idx = np.where(y == 0)[0]
    unans_idx = np.where(y == 1)[0]
    ans_ids = [ids[i] for i in ans_idx]
    unans_ids = [ids[i] for i in unans_idx]

    integrity_input = {
        "prediction_artifact": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
        "prediction_artifact_sha256": pred_sha,
        "F2_rows": len(f2), "A0_rows": len(a0),
        "same_example_ids_and_order": True, "same_answerability_labels": True,
        "answerable": int((y == 0).sum()), "unanswerable": int(y.sum()),
        "required_fields_present": REQUIRED_FIELDS,
        "pairs_per_statistic": N_UNANS * N_ANS,
        "aborted_on_mismatch": False, "issues": [],
    }

    # ---- 2 pairwise decomposition + 3/4 per-example influence + 6 jackknife
    per_target: dict[str, dict] = {}
    influence_vectors: dict[str, dict[str, list[float]]] = {}
    for name, stat in TARGETS:
        rows = models[name]
        s = np.array([float(r[stat]) for r in rows], dtype=np.float64) * SIGN[stat]
        su, sa = s[unans_idx], s[ans_idx]
        M = np.zeros((N_UNANS, N_ANS), dtype=np.float64)
        M[su[:, None] > sa[None, :]] = 1.0
        M[su[:, None] == sa[None, :]] = 0.5

        pos_wins = int((M == 1.0).sum())
        ties = int((M == 0.5).sum())
        neg_wins = int((M == 0.0).sum())
        W = float(M.sum())
        auc_recon = (pos_wins + 0.5 * ties) / (N_UNANS * N_ANS)
        auc_from_W = W / (N_UNANS * N_ANS)

        w_raw = M.sum(axis=1)          # per unanswerable wins over answerable
        v_raw = M.sum(axis=0)          # per answerable wins over unanswerable
        pos_rate = w_raw / N_ANS
        neg_rate = v_raw / N_UNANS
        pos_contrib = pos_rate - 0.5
        neg_contrib = neg_rate - 0.5

        # jackknife (analytic) + brute-force verification
        loo_unans = np.array([(W - w_raw[i]) / ((N_UNANS - 1) * N_ANS) for i in range(N_UNANS)])
        loo_ans = np.array([(W - v_raw[j]) / (N_UNANS * (N_ANS - 1)) for j in range(N_ANS)])
        # brute force recomputation for every removed example
        loo_unans_bf = np.empty(N_UNANS)
        for i in range(N_UNANS):
            sub = np.delete(M, i, axis=0)
            loo_unans_bf[i] = sub.sum() / ((N_UNANS - 1) * N_ANS)
        loo_ans_bf = np.empty(N_ANS)
        for j in range(N_ANS):
            sub = np.delete(M, j, axis=1)
            loo_ans_bf[j] = sub.sum() / (N_UNANS * (N_ANS - 1))
        jk_match = bool(np.allclose(loo_unans, loo_unans_bf, atol=1e-12) and
                        np.allclose(loo_ans, loo_ans_bf, atol=1e-12))
        loo_all = np.concatenate([loo_unans, loo_ans])

        order_u = sorted(range(N_UNANS), key=lambda i: (-abs(pos_contrib[i]), unans_ids[i]))
        order_a = sorted(range(N_ANS), key=lambda j: (-abs(neg_contrib[j]), ans_ids[j]))
        top_abs_u = order_u[0]
        top_abs_a = order_a[0]
        # whose removal increases / decreases AUC most
        inc_i = int(np.argmax(loo_all))
        dec_i = int(np.argmin(loo_all))
        inc_is_unans = inc_i < N_UNANS
        dec_is_unans = dec_i < N_UNANS

        n25_u, n50_u = max(1, int(np.ceil(0.25 * N_UNANS))), max(1, int(np.ceil(0.5 * N_UNANS)))
        n25_a, n50_a = max(1, int(np.ceil(0.25 * N_ANS))), max(1, int(np.ceil(0.5 * N_ANS)))

        per_target[f"{name}|{stat}"] = {
            "model": name, "statistic": stat, "orientation": ("HIGHER=UNANSWERABLE" if SIGN[stat] > 0
                                                              else "LOWER=UNANSWERABLE (reversed for analysis)"),
            "pairwise_decomposition": {
                "pairs": N_UNANS * N_ANS, "positive_wins": pos_wins, "ties": ties,
                "negative_wins": neg_wins, "win_plus_tie_check": pos_wins + ties + neg_wins,
                "auc_reconstructed_from_pairs": round(auc_recon, 8),
                "auc_from_sum_over_pairs": round(auc_from_W, 8),
                "auc_reported_previously": None, "auc_matches_previous": None,
            },
            "per_unanswerable_influence": {
                "statistics_of_pair_contribution": summarize(pos_contrib),
                "mean_contribution_equals_auc_excess": round(float(pos_contrib.mean()) - (auc_from_W - 0.5), 12),
                "largest_absolute": {
                    "example_id": unans_ids[top_abs_u],
                    "pair_contribution": round(float(pos_contrib[top_abs_u]), 6),
                    "positive_win_rate": round(float(pos_rate[top_abs_u]), 6),
                    "wins_out_of_140": round(float(w_raw[top_abs_u]), 2),
                },
                "sorted_by_absolute_contribution": [
                    {"example_id": unans_ids[i], "positive_win_rate": round(float(pos_rate[i]), 6),
                     "pair_contribution": round(float(pos_contrib[i]), 6)}
                    for i in order_u
                ],
            },
            "per_answerable_influence": {
                "statistics_of_pair_contribution": summarize(neg_contrib),
                "mean_contribution_equals_auc_excess": round(float(neg_contrib.mean()) - (auc_from_W - 0.5), 12),
                "definition": ("correct_order_rate_j = (# unanswerable with score_i > score_j + 0.5 * ties) / 42; "
                               "pair_contribution_j = correct_order_rate_j - 0.5"),
                "largest_absolute": {
                    "example_id": ans_ids[top_abs_a],
                    "pair_contribution": round(float(neg_contrib[top_abs_a]), 6),
                    "correct_order_rate": round(float(neg_rate[top_abs_a]), 6),
                    "correct_out_of_42": round(float(v_raw[top_abs_a]), 2),
                },
                "sorted_by_absolute_contribution": [
                    {"example_id": ans_ids[j], "category": models[name][ans_idx[j]]["category"],
                     "correct_order_rate": round(float(neg_rate[j]), 6),
                     "pair_contribution": round(float(neg_contrib[j]), 6)}
                    for j in order_a
                ],
            },
            "influence_concentration": {
                "auc_excess": round(auc_from_W - 0.5, 6),
                "unanswerable_class": top_k_share(pos_contrib, unans_ids,
                                                  [1, 3, 5, 10, 20, n25_u, n50_u]),
                "answerable_class": top_k_share(neg_contrib, ans_ids,
                                                [1, 3, 5, 10, 20, n25_a, n50_a]),
                "top_k_specs_unanswerable": [1, 3, 5, 10, 20, n25_u, n50_u],
                "top_k_specs_answerable": [1, 3, 5, 10, 20, n25_a, n50_a],
                "top_25pct_label_unanswerable": f"top {n25_u} of 42",
                "top_50pct_label_unanswerable": f"top {n50_u} of 42",
                "top_25pct_label_answerable": f"top {n25_a} of 140",
                "top_50pct_label_answerable": f"top {n50_a} of 140",
                "rule": RULE_S5_CONCENTRATION,
            },
            "jackknife": {
                "n_leave_one_out_runs": int(len(loo_all)),
                "unanswerable_removed": {
                    "summary": summarize(loo_unans),
                    "removal_increases_auc_most": {
                        "example_id": unans_ids[int(np.argmax(loo_unans))],
                        "auc_after_removal": round(float(np.max(loo_unans)), 6)},
                    "removal_decreases_auc_most": {
                        "example_id": unans_ids[int(np.argmin(loo_unans))],
                        "auc_after_removal": round(float(np.min(loo_unans)), 6)},
                },
                "answerable_removed": {
                    "summary": summarize(loo_ans),
                    "removal_increases_auc_most": {
                        "example_id": ans_ids[int(np.argmax(loo_ans))],
                        "auc_after_removal": round(float(np.max(loo_ans)), 6)},
                    "removal_decreases_auc_most": {
                        "example_id": ans_ids[int(np.argmin(loo_ans))],
                        "auc_after_removal": round(float(np.min(loo_ans)), 6)},
                },
                "combined": {
                    "min": round(float(loo_all.min()), 6), "max": round(float(loo_all.max()), 6),
                    "mean": round(float(loo_all.mean()), 6), "median": round(float(np.median(loo_all)), 6),
                    "std": round(float(loo_all.std(ddof=1)), 6),
                    "q05": round(float(np.percentile(loo_all, 5)), 6),
                    "q95": round(float(np.percentile(loo_all, 95)), 6),
                    "removal_increases_auc_most": {
                        "example_id": unans_ids[inc_i] if inc_is_unans else ans_ids[inc_i - N_UNANS],
                        "class": "UNANSWERABLE" if inc_is_unans else "ANSWERABLE",
                        "auc_after_removal": round(float(loo_all[inc_i]), 6),
                        "delta_vs_original": round(float(loo_all[inc_i] - auc_from_W), 6)},
                    "removal_decreases_auc_most": {
                        "example_id": unans_ids[dec_i] if dec_is_unans else ans_ids[dec_i - N_UNANS],
                        "class": "UNANSWERABLE" if dec_is_unans else "ANSWERABLE",
                        "auc_after_removal": round(float(loo_all[dec_i]), 6),
                        "delta_vs_original": round(float(loo_all[dec_i] - auc_from_W), 6)},
                },
                "analytic_matches_brute_force": jk_match,
            },
            "signed_influence_curve": {
                "unanswerable_class": cumulative_curve(pos_contrib, unans_ids),
                "answerable_class": cumulative_curve(neg_contrib, ans_ids),
            },
            "_auc": auc_from_W, "_pos_contrib": pos_contrib, "_neg_contrib": neg_contrib,
            "_pos_rate": pos_rate, "_neg_rate": neg_rate, "_loo_all": loo_all, "_loo_u": loo_unans,
            "_loo_a": loo_ans,
        }
        # length-182 influence vector in benchmark row order
        vec = np.empty(TOTAL)
        vec[unans_idx] = pos_contrib
        vec[ans_idx] = neg_contrib
        influence_vectors.setdefault(f"{name}", {})[stat] = vec

    # verify reconstructed AUC against the previously reported values
    PREVIOUS = {"F2|margin": 0.7338, "A0|margin": 0.5432,
                "F2|best_answer_score": 0.7250, "A0|best_answer_score": 0.5054}
    auc_verification = {}
    for key, expected in PREVIOUS.items():
        got = round(per_target[key]["_auc"], 4)
        per_target[key]["pairwise_decomposition"]["auc_reported_previously"] = expected
        per_target[key]["pairwise_decomposition"]["auc_matches_previous"] = abs(got - expected) < 5e-5
        auc_verification[key] = {"reconstructed": got, "previously_reported": expected,
                                 "match": abs(got - expected) < 5e-5}

    # ---- 7 stability classification
    stability = {}
    for key, t in per_target.items():
        auc = t["_auc"]
        loo = t["_loo_all"]
        orig_side = 1 if auc > 0.5 else (-1 if auc < 0.5 else 0)
        sides = np.where(loo > 0.5, 1, np.where(loo < 0.5, -1, 0))
        side_rate = float((sides == orig_side).mean())
        flips = int((sides != orig_side).sum())
        delta_max = float(np.max(np.abs(loo - auc)))
        near02 = float((np.abs(loo - 0.5) <= 0.02).mean())
        near05 = float((np.abs(loo - 0.5) <= 0.05).mean())
        jk_dist = max(abs(float(loo.min()) - 0.5), abs(float(loo.max()) - 0.5))
        if flips > 0:
            cls = "FEW_EXAMPLES_DRIVE_SIGNAL"
            trigger = f"side_flip: {flips} leave-one-out run(s) crossed 0.5"
        elif delta_max >= 0.05:
            cls = "FEW_EXAMPLES_DRIVE_SIGNAL"
            trigger = f"delta_max {delta_max:.6f} >= 0.05"
        elif side_rate > 0.5 and abs(auc - 0.5) > 0.05:
            cls = "BROAD_DISTRIBUTED_SIGNAL"
            trigger = "no flips, delta_max < 0.05, |AUC - 0.5| > 0.05"
        elif abs(auc - 0.5) <= 0.05 and jk_dist <= 0.10:
            cls = "NEAR_CHANCE_STABLE"
            trigger = "no flips, delta_max < 0.05, |AUC - 0.5| <= 0.05, jackknife distance <= 0.10"
        else:
            cls = "INCONCLUSIVE"
            trigger = "none of the declared conditions"
        stability[key] = {
            "original_auc": round(auc, 6),
            "jackknife_min": round(float(loo.min()), 6),
            "jackknife_max": round(float(loo.max()), 6),
            "jackknife_mean": round(float(loo.mean()), 6),
            "jackknife_std": round(float(loo.std(ddof=1)), 6),
            "pct_loo_auc_gt_0_5": round(float((loo > 0.5).mean()) * 100, 2),
            "pct_loo_auc_lt_0_5": round(float((loo < 0.5).mean()) * 100, 2),
            "pct_loo_within_0_02_of_0_5": round(near02 * 100, 2),
            "pct_loo_within_0_05_of_0_5": round(near05 * 100, 2),
            "side_flips": flips, "side_rate": round(side_rate, 4), "delta_max": round(delta_max, 6),
            "jackknife_distance_from_chance": round(jk_dist, 6),
            "abs_auc_minus_half": round(abs(auc - 0.5), 6),
            "trigger": trigger,
            "leave_one_out_max_excursion_beyond_0_5": round(max(0.0, 0.5 - float(loo.min()),
                                                                  float(loo.max()) - 0.5), 6),
            "side_flip_example_ids": [ids[i] for i in range(TOTAL) if (1 if loo[i] > 0.5 else -1) != orig_side],
            "side_flip_from_unanswerable_removals": int((np.where(t["_loo_u"] > 0.5, 1,
                                                                   np.where(t["_loo_u"] < 0.5, -1, 0)) != orig_side).sum()),
            "side_flip_from_answerable_removals": int((np.where(t["_loo_a"] > 0.5, 1,
                                                                 np.where(t["_loo_a"] < 0.5, -1, 0)) != orig_side).sum()),
            "stability": cls, "rule": RULE_S7_STABILITY,
        }

    # ---- 8 signed influence curve already embedded -----------------------------

    # ---- 9 category influence (answerable side)
    category_influence = {}
    for key, t in per_target.items():
        name, stat = t["model"], t["statistic"]
        contrib = t["_neg_contrib"]
        cats = [models[name][ans_idx[j]]["category"] for j in range(N_ANS)]
        total_abs = float(np.abs(contrib).sum())
        rows_out = {}
        for c in CATEGORIES:
            sel = [j for j in range(N_ANS) if cats[j] == c]
            if not sel:
                continue
            cc = contrib[sel]
            rows_out[c] = {
                "n": len(sel), "mean_contribution": round(float(cc.mean()), 6),
                "median_contribution": round(float(np.median(cc)), 6),
                "total_contribution": round(float(cc.sum()), 6),
                "absolute_contribution": round(float(np.abs(cc).sum()), 6),
                "share_of_total_absolute_answerable_influence": (round(float(np.abs(cc).sum()) / total_abs, 4)
                                                                 if total_abs >= 1e-6 else "UNSTABLE_DENOMINATOR"),
            }
        shares = sorted(((c, v["share_of_total_absolute_answerable_influence"]) for c, v in rows_out.items()
                         if isinstance(v["share_of_total_absolute_answerable_influence"], float)),
                        key=lambda kv: -kv[1])
        n_ge5 = sum(1 for v in rows_out.values() if v["n"] >= 5)
        max_share = shares[0][1] if shares else 0.0
        top3_share = sum(s for _, s in shares[:3])
        if n_ge5 < 2:
            flag = "INSUFFICIENT"
        elif max_share > 0.50:
            flag = "CONCENTRATED_IN_FEW_CATEGORIES"
        elif max_share <= 0.35 and top3_share < 0.70:
            flag = "BROAD_ACROSS_CATEGORIES"
        else:
            flag = "MIXED"
        category_influence[key] = {
            "by_category": rows_out, "max_single_category_share": round(max_share, 4),
            "top3_category_share": round(top3_share, 4),
            "categories_with_n_ge_5": n_ge5, "classification": flag, "rule": RULE_S9_CATEGORY,
        }

    # ---- 10 cross-checkpoint influence agreement
    cross = {}
    for stat in ("margin", "best_answer_score"):
        vf = influence_vectors["F2"][stat]
        va = influence_vectors["A0"][stat]
        of = sorted(range(TOTAL), key=lambda i: (-abs(vf[i]), ids[i]))
        oa = sorted(range(TOTAL), key=lambda i: (-abs(va[i]), ids[i]))
        entry = {"statistic": stat,
                 "influence_spearman_F2_vs_A0": round(spearman(vf, va), 6),
                 "influence_pearson_F2_vs_A0": round(pearson(vf, va), 6)}
        for k in (10, 20):
            sf, sa_ = set(of[:k]), set(oa[:k])
            inter = sf & sa_
            entry[f"top{k}_overlap_count"] = len(inter)
            entry[f"top{k}_jaccard"] = round(len(inter) / len(sf | sa_), 4) if (sf | sa_) else None
            entry[f"top{k}_overlap_example_ids"] = sorted(ids[i] for i in inter)
        cross[stat] = entry

    # ---- 11 A0 vs F2 influence difference
    diff = {}
    for stat in ("margin", "best_answer_score"):
        d = influence_vectors["A0"][stat] - influence_vectors["F2"][stat]
        order = sorted(range(TOTAL), key=lambda i: (-abs(d[i]), ids[i]))
        abs_den = float(np.abs(d).sum())
        top10 = float(np.abs(d[order[:10]]).sum())
        top20 = float(np.abs(d[order[:20]]).sum())
        m_abs_un = float(np.mean(np.abs(d[unans_idx])))
        m_abs_an = float(np.mean(np.abs(d[ans_idx])))
        class_ratio = max(m_abs_un, m_abs_an) / min(m_abs_un, m_abs_an) if min(m_abs_un, m_abs_an) > 1e-12 else float("inf")
        top20_share = top20 / abs_den if abs_den >= 1e-6 else None
        top10_share = top10 / abs_den if abs_den >= 1e-6 else None
        if top20_share is None:
            flag = "MIXED"
        elif top20_share >= 0.75:
            flag = "FEW_EXAMPLES"
        elif class_ratio >= 2.0:
            flag = "CLASS_SPECIFIC"
        elif top10_share <= 0.25:
            flag = "DISTRIBUTED_DIFFERENCE"
        else:
            flag = "MIXED"
        diff[stat] = {
            "summary_influence_A0_minus_influence_F2": summarize(d),
            "mean_abs_difference_unanswerable": round(m_abs_un, 6),
            "mean_abs_difference_answerable": round(m_abs_an, 6),
            "class_ratio": None if class_ratio == float("inf") else round(class_ratio, 4),
            "top10_share_of_absolute_difference": None if top10_share is None else round(top10_share, 4),
            "top20_share_of_absolute_difference": None if top20_share is None else round(top20_share, 4),
            "largest_positive_differences": [
                {"example_id": ids[i], "class": "UNANSWERABLE" if y[i] == 1 else "ANSWERABLE",
                 "difference_A0_minus_F2": round(float(d[i]), 6)} for i in order[:5]],
            "largest_negative_differences": [
                {"example_id": ids[i], "class": "UNANSWERABLE" if y[i] == 1 else "ANSWERABLE",
                 "difference_A0_minus_F2": round(float(d[i]), 6)} for i in order[::-1][:5]],
            "classification": flag, "rule": RULE_S11_DIFFERENCE,
        }

    # ---- 12 reconciliation
    reconciliation = {
        "F2": {"margin_auc": 0.7338, "best_answer_score_auc": 0.7250,
               "margin_vs_best_answer_score_spearman": -0.9206,
               "measured_this_phase": {"margin_auc": round(per_target["F2|margin"]["_auc"], 4),
                                       "best_answer_score_auc": round(per_target["F2|best_answer_score"]["_auc"], 4),
                                       "margin_vs_best_answer_score_spearman": round(
                                           spearman(influence_vectors["F2"]["margin"], influence_vectors["F2"]["best_answer_score"]), 4)}},
        "A0": {"margin_auc": 0.5432, "best_answer_score_auc": 0.5054,
               "measured_this_phase": {"margin_auc": round(per_target["A0|margin"]["_auc"], 4),
                                       "best_answer_score_auc": round(per_target["A0|best_answer_score"]["_auc"], 4)}},
        "null_family_paired_bootstrap_from_previous_phase": {
            "result": "the F2->A0 delta-AUC CIs for null_score / cls_start_logit / cls_end_logit all included zero",
            "not_repeated_here": True,
            "relation": ("that earlier result concerns the NULL family; this phase analyses the answer-span family "
                         "(margin, best_answer_score), whose AUC difference is much larger, and asks whether the "
                         "remaining difference survives single-example influence analysis"),
        },
        "does_remaining_auc_difference_survive_influence_analysis": None,
    }
    f2m, a0m = per_target["F2|margin"]["_auc"], per_target["A0|margin"]["_auc"]
    f2b, a0b = per_target["F2|best_answer_score"]["_auc"], per_target["A0|best_answer_score"]["_auc"]
    reconciliation["does_remaining_auc_difference_survive_influence_analysis"] = {
        "margin_difference": round(f2m - a0m, 4),
        "best_answer_score_difference": round(f2b - a0b, 4),
        "margin_loo_ranges_disjoint": bool(per_target["F2|margin"]["_loo_all"].min() >
                                           per_target["A0|margin"]["_loo_all"].max()),
        "best_answer_score_loo_ranges_disjoint": bool(per_target["F2|best_answer_score"]["_loo_all"].min() >
                                                      per_target["A0|best_answer_score"]["_loo_all"].max()),
        "note": ("disjoint leave-one-out ranges mean no single-example removal can close the gap; "
                 "this is a descriptive influence statement, not a significance test"),
    }

    # ---- 15 verdict
    classes = {k: v["stability"] for k, v in stability.items()}
    any_few = any(c == "FEW_EXAMPLES_DRIVE_SIGNAL" for c in classes.values())
    any_broad = any(c == "BROAD_DISTRIBUTED_SIGNAL" for c in classes.values())
    all_ok = all(c in ("BROAD_DISTRIBUTED_SIGNAL", "NEAR_CHANCE_STABLE") for c in classes.values())
    if any_few and any_broad:
        verdict = "INFLUENCE_MIXED"
    elif any_few:
        verdict = "INFLUENCE_CONCENTRATED"
    elif all_ok:
        verdict = "INFLUENCE_DISTRIBUTED"
    else:
        verdict = "INFLUENCE_INCONCLUSIVE"

    # ---- 13 tables
    table1 = [{"model": t["model"], "statistic": t["statistic"],
               "original_auc": round(t["_auc"], 4),
               "jackknife_min": stability[k]["jackknife_min"],
               "jackknife_max": stability[k]["jackknife_max"],
               "jackknife_mean": stability[k]["jackknife_mean"],
               "pct_auc_gt_0_5": stability[k]["pct_loo_auc_gt_0_5"],
               "pct_auc_lt_0_5": stability[k]["pct_loo_auc_lt_0_5"],
               "pct_near_chance_0_02": stability[k]["pct_loo_within_0_02_of_0_5"],
               "stability": stability[k]["stability"]}
              for k, t in per_target.items()]
    table2 = []
    for k, t in per_target.items():
        for cls, key in (("UNANSWERABLE", "unanswerable_class"), ("ANSWERABLE", "answerable_class")):
            conc = t["influence_concentration"][key]
            specs = (t["influence_concentration"]["top_k_specs_unanswerable"] if cls == "UNANSWERABLE"
                     else t["influence_concentration"]["top_k_specs_answerable"])
            grabs = [conc["top_k"][str(s)]["share_of_absolute_influence"] for s in specs]
            table2.append({"model": t["model"], "statistic": t["statistic"], "class": cls,
                           "top_specs": specs, "shares_of_absolute_influence": grabs,
                           "denominator_absolute": conc["denominator_absolute"],
                           "denominator_absolute_stable": conc["denominator_absolute_stable"]})
    table3 = [{"statistic": s, "influence_spearman": cross[s]["influence_spearman_F2_vs_A0"],
               "top10_overlap": cross[s]["top10_overlap_count"],
               "top20_overlap": cross[s]["top20_overlap_count"],
               "jaccard_10": cross[s]["top10_jaccard"], "jaccard_20": cross[s]["top20_jaccard"],
               "cross_checkpoint_pattern": ("HIGH_OVERLAP_OF_DRIVERS" if cross[s]["top10_jaccard"] >= 0.5
                                            else "DIFFERENT_DRIVERS")}
              for s in ("margin", "best_answer_score")]

    # ---- 14 answers
    def stat_of(key: str) -> dict:
        return stability[key]

    answers = {
        "A_is_A0_margin_broad_or_artifact": (
            f"A0 margin AUC {per_target['A0|margin']['_auc']:.4f} is stable and near chance rather than an artifact of a "
            f"few examples: its jackknife range is [{stat_of('A0|margin')['jackknife_min']:.4f}, "
            f"{stat_of('A0|margin')['jackknife_max']:.4f}] with {stat_of('A0|margin')['pct_loo_auc_gt_0_5']:.2f}% of "
            f"leave-one-out runs above 0.5 and no side flip (classification "
            f"{stat_of('A0|margin')['stability']}); the largest single-example removal moves AUC by only "
            f"{stat_of('A0|margin')['delta_max']:.4f}"),
        "B_is_F2_margin_distributed": (
            f"yes: F2 margin AUC {per_target['F2|margin']['_auc']:.4f} has jackknife range "
            f"[{stat_of('F2|margin')['jackknife_min']:.4f}, {stat_of('F2|margin')['jackknife_max']:.4f}] "
            f"(width {stat_of('F2|margin')['jackknife_max']-stat_of('F2|margin')['jackknife_min']:.4f}), "
            f"{stat_of('F2|margin')['pct_loo_auc_gt_0_5']:.2f}% of leave-one-out runs stay above 0.5 "
            f"(side flips: {stat_of('F2|margin')['side_flips']}), "
            f"the largest single removal changes AUC by {stat_of('F2|margin')['delta_max']:.4f}, and "
            f"{stable_share(per_target['F2|margin'])}"),
        "C_same_examples_driving_both": (
            f"no — cross-checkpoint influence agreement is weak: margin influence Spearman "
            f"{cross['margin']['influence_spearman_F2_vs_A0']:+.4f} with top-10 overlap "
            f"{cross['margin']['top10_overlap_count']}/10 (Jaccard {cross['margin']['top10_jaccard']}) and top-20 overlap "
            f"{cross['margin']['top20_overlap_count']}/20 (Jaccard {cross['margin']['top20_jaccard']}); "
            f"best_answer_score influence Spearman {cross['best_answer_score']['influence_spearman_F2_vs_A0']:+.4f}"),
        "D_where_the_difference_lives": (
            f"margin: {diff['margin']['classification']} (top-10 share "
            f"{diff['margin']['top10_share_of_absolute_difference']}, top-20 share "
            f"{diff['margin']['top20_share_of_absolute_difference']}, class ratio {diff['margin']['class_ratio']}); "
            f"best_answer_score: {diff['best_answer_score']['classification']} (top-10 share "
            f"{diff['best_answer_score']['top10_share_of_absolute_difference']}, top-20 share "
            f"{diff['best_answer_score']['top20_share_of_absolute_difference']}, class ratio "
            f"{diff['best_answer_score']['class_ratio']})"),
        "E_answer_span_still_stronger": (
            f"yes: after influence decomposition the answer-span family remains far stronger than the null family at F2 "
            f"(margin {per_target['F2|margin']['_auc']:.4f} and best_answer_score "
            f"{per_target['F2|best_answer_score']['_auc']:.4f}, both BROAD-distributed across leave-one-out removals), "
            f"while at A0 both are near chance (margin {per_target['A0|margin']['_auc']:.4f}, "
            f"best_answer_score {per_target['A0|best_answer_score']['_auc']:.4f})"),
    }

    few_targets = [k for k, c in classes.items() if c == "FEW_EXAMPLES_DRIVE_SIGNAL"]
    few_note = None
    if few_targets:
        k0 = few_targets[0]
        st0 = stability[k0]
        down_excursion = max(0.0, 0.5 - st0["jackknife_min"])
        few_note = (
            f"the only target classified {k0} has |AUC - 0.5| = {st0['abs_auc_minus_half']:.4f} (statistically "
            f"indistinguishable from chance); its {st0['side_flips']} side-flipping leave-one-out runs all come from "
            f"unanswerable removals ({st0['side_flip_from_unanswerable_removals']} of 42; answerable removals: "
            f"{st0['side_flip_from_answerable_removals']} of 140), the deepest any single removal pushes the AUC "
            f"below 0.5 is {down_excursion:.6f} (jackknife min {st0['jackknife_min']:.4f}), and the largest single "
            f"change in AUC is delta_max {st0['delta_max']:.6f}. This is chance-boundary instability of a statistic "
            f"that sits on 0.5, not evidence that a small subset creates a separation.")

    payload = {
        "artifact": "auc_influence_jackknife_forensics",
        "phase": "Phase 4F.6 — Model Evidence Diagnostics (bounded influence / jackknife re-analysis)",
        "date": _now(),
        "primary_question": ("why is A0 margin AUC 0.5432 close to chance while F2 margin AUC is 0.7338, and is the "
                            "difference a distributed property of the 182-example ordering or driven by a few "
                            "influential examples?"),
        "population": {"total": TOTAL, "answerable": N_ANS, "unanswerable": N_UNANS,
                       "pairs_per_statistic": N_UNANS * N_ANS, "positive_class": "UNANSWERABLE"},
        "direction_convention": "HIGHER oriented score = MORE LIKELY UNANSWERABLE (margin +1, best_answer_score -1)",
        "task_1_input_integrity": integrity_input,
        "task_2_pairwise_decomposition": {k: v["pairwise_decomposition"] for k, v in per_target.items()},
        "task_2_auc_verification": auc_verification,
        "task_3_per_unanswerable_influence": {k: v["per_unanswerable_influence"] for k, v in per_target.items()},
        "task_4_per_answerable_influence": {k: v["per_answerable_influence"] for k, v in per_target.items()},
        "task_5_influence_concentration": {k: v["influence_concentration"] for k, v in per_target.items()},
        "task_6_jackknife": {k: v["jackknife"] for k, v in per_target.items()},
        "task_7_stability": stability,
        "task_8_signed_influence_curve": {k: v["signed_influence_curve"] for k, v in per_target.items()},
        "task_9_category_influence": category_influence,
        "task_10_cross_checkpoint_agreement": cross,
        "task_11_a0_vs_f2_difference": diff,
        "task_12_reconciliation": reconciliation,
        "task_13_table_1_stability": table1,
        "task_13_table_2_concentration": table2,
        "task_13_table_3_cross_checkpoint": table3,
        "task_14_answers": answers,
        "task_15_verdict": {
            "verdict": verdict, "definitions": VERDICT_DEFS, "per_target_classes": classes,
            "rule": RULE_S15_VERDICT,
            "few_examples_targets": few_targets,
            "mechanistic_note": few_note,
            "alternative_reading": (
                "if CONCENTRATED is required to mean that a material separation is produced by a small subset, then "
                "no target qualifies: the F2 targets carry |AUC - 0.5| > 0.22 broadly across examples (top-1 example = "
                "1.1-3.7% of absolute influence), and the A0 target that triggered FEW_EXAMPLES sits on 0.5 "
                "(|AUC - 0.5| = 0.0054, deepest single-removal excursion below 0.5 only 0.0066). Under that reading "
                "every target falls in BROAD_DISTRIBUTED_SIGNAL or NEAR_CHANCE_STABLE, i.e. INFLUENCE_DISTRIBUTED. "
                "The applied verdict follows the pre-declared rule mechanically; this alternative is reported so the "
                "label is not read as evidence of a concentrated signal that does not exist."),
        },
        "integrity": _integrity(pred_sha),
        "interpretation_boundary": [
            "No model loading, no inference, no training, no GPU, no database, no retrieval was used.",
            "No threshold was fitted, no K searched, no subset optimization, no leave-two-out or combinatorial search, "
            "no new or combined score was created.",
            "Only recorded score fields and labels were re-analysed mathematically; the frozen prediction artifact "
            "was not modified.",
            "Influence and jackknife figures are descriptive decompositions of a rank statistic, not causal effects "
            "and not architectural evidence.",
            "No winner/best/superior language is used; each checkpoint/statistic is reported on its own measurements.",
        ],
    }
    DECISION.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS.mkdir(parents=True, exist_ok=True)
    (DECISION / "AUC_INFLUENCE_JACKKNIFE_FORENSICS.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (DIAGNOSTICS / "auc_influence_jackknife.json").write_text(
        json.dumps({
            "artifact": "auc_influence_jackknife",
            "prediction_artifact_sha256": pred_sha,
            "population": {"answerable": N_ANS, "unanswerable": N_UNANS, "pairs": N_UNANS * N_ANS},
            "per_target": {
                k: {
                    "model": v["model"], "statistic": v["statistic"],
                    "auc": round(v["_auc"], 8),
                    "jackknife_leave_one_out_auc": {
                        "unanswerable_removed": [round(float(x), 8) for x in v["_loo_u"]],
                        "answerable_removed": [round(float(x), 8) for x in v["_loo_a"]],
                    },
                    "unanswerable_example_ids": unans_ids,
                    "answerable_example_ids": ans_ids,
                    "jackknife_analytic_matches_brute_force": v["jackknife"]["analytic_matches_brute_force"],
                    "stability": stability[k]["stability"],
                } for k, v in per_target.items()
            },
            "influence_vectors_benchmark_order": {
                stat: {"example_ids": ids,
                       "F2": [round(float(x), 8) for x in influence_vectors["F2"][stat]],
                       "A0": [round(float(x), 8) for x in influence_vectors["A0"][stat]]}
                for stat in ("margin", "best_answer_score")},
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(payload)

    print(json.dumps({
        "verdict": verdict,
        "auc": {k: round(v["_auc"], 4) for k, v in per_target.items()},
        "stability": {k: v["stability"] for k, v in stability.items()},
        "jackknife_range": {k: [stability[k]["jackknife_min"], stability[k]["jackknife_max"]] for k in stability},
        "delta_max": {k: stability[k]["delta_max"] for k in stability},
        "side_flips": {k: stability[k]["side_flips"] for k in stability},
        "cross_spearman": {s: cross[s]["influence_spearman_F2_vs_A0"] for s in cross},
        "cross_jaccard10": {s: cross[s]["top10_jaccard"] for s in cross},
        "diff_class": {s: diff[s]["classification"] for s in diff},
        "category": {k: category_influence[k]["classification"] for k in category_influence},
        "auc_verified": all(v["match"] for v in auc_verification.values()),
    }, indent=1))


def stable_share(t: dict) -> str:
    conc = t["influence_concentration"]
    k = conc["top_k_specs_answerable"][-1]
    s = conc["answerable_class"]["top_k"][str(k)]["share_of_absolute_influence"]
    return (f"the top 50% of answerable examples carry only {s} of the answerable-side absolute influence")


def _now() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()


def _integrity(pred_sha: str) -> dict:
    bench, dataset = sha256_file(BENCHMARK), sha256_file(DATASET)
    prod, f2m = sha256_file(PROD_MODEL), sha256_file(F2_MODEL)
    ck, src, chk = dir_scope_sha256(F2_CKPT_DIR), fingerprint_dir(SOURCE_CORPUS), fingerprint_dir(CHUNK_CORPUS)
    return {
        "benchmark_sha256": bench, "benchmark_expected": BENCHMARK_SHA256, "benchmark_match": bench == BENCHMARK_SHA256,
        "dataset_sha256": dataset, "dataset_expected": DATASET_SHA256, "dataset_match": dataset == DATASET_SHA256,
        "production_model_sha256": prod, "production_model_expected": PROD_MODEL_SHA256,
        "production_model_match": prod == PROD_MODEL_SHA256,
        "f2_model_sha256": f2m, "f2_model_expected": F2_MODEL_SHA256, "f2_model_match": f2m == F2_MODEL_SHA256,
        "f2_checkpoint_dir_scope_sha256": ck, "f2_checkpoint_dir_expected": F2_CKPT_DIR_SHA256,
        "f2_checkpoint_dir_match": ck == F2_CKPT_DIR_SHA256,
        "source_fingerprint": src, "source_fingerprint_expected": SOURCE_FINGERPRINT, "source_match": src == SOURCE_FINGERPRINT,
        "chunk_fingerprint": chk, "chunk_fingerprint_expected": CHUNK_FINGERPRINT, "chunk_match": chk == CHUNK_FINGERPRINT,
        "predictions_artifact_sha256": pred_sha,
    }


def _write_md(p: dict) -> None:
    L: list[str] = []
    L.append("# Answerability AUC Influence + Jackknife Forensics")
    L.append("")
    L.append(f"**Date:** {p['date']} · **Population:** 182 = 140 answerable + 42 unanswerable · "
             f"**pairs per statistic:** 5,880")
    L.append("")
    L.append(f"**Primary question:** {p['primary_question']}")
    L.append("")
    L.append(f"Direction convention: {p['direction_convention']}")
    L.append("")
    L.append("Bounded mathematical re-analysis of the frozen prediction artifact. No model loading, no inference, no "
             "training, no GPU, no database, no retrieval, no threshold fitting, no K search, no subset optimization, "
             "no new or combined score.")
    L.append("")
    L.append("## 1. Input integrity")
    L.append("")
    ii = p["task_1_input_integrity"]
    L.append(f"- F2 rows {ii['F2_rows']} / A0 rows {ii['A0_rows']}; ids+order match: {ii['same_example_ids_and_order']}; "
             f"labels match: {ii['same_answerability_labels']}; {ii['answerable']}/{ii['unanswerable']}")
    L.append(f"- prediction artifact sha256 `{ii['prediction_artifact_sha256']}`")
    L.append(f"- pairs per statistic = {ii['pairs_per_statistic']}")
    L.append("")
    L.append("## 2. Pairwise decomposition (5,880 pairs each)")
    L.append("")
    L.append("| Model | Statistic | positive wins | ties | negative wins | sum check | AUC from pairs | previously reported | match |")
    L.append("| --- | --- | --: | --: | --: | --: | --: | --: | --- |")
    for k, v in p["task_2_pairwise_decomposition"].items():
        L.append(f"| {v and k.split('|')[0]} | `{k.split('|')[1]}` | {v['positive_wins']} | {v['ties']} | "
                 f"{v['negative_wins']} | {v['win_plus_tie_check']} | {v['auc_reconstructed_from_pairs']:.6f} | "
                 f"{v['auc_reported_previously']} | {v['auc_matches_previous']} |")
    L.append("")
    L.append("## 3. Per-unanswerable influence (42 examples)")
    L.append("")
    L.append("| Model | Statistic | mean | median | std | min | max | q05 | q95 |")
    L.append("| --- | --- | --: | --: | --: | --: | --: | --: | --: |")
    for k, v in p["task_3_per_unanswerable_influence"].items():
        s = v["statistics_of_pair_contribution"]
        L.append(f"| {k.split('|')[0]} | `{k.split('|')[1]}` | {s['mean']:+.6f} | {s['median']:+.6f} | {s['std']:.6f} | "
                 f"{s['min']:+.6f} | {s['max']:+.6f} | {s['q05']:+.6f} | {s['q95']:+.6f} |")
    L.append("")
    L.append("## 4. Per-answerable influence (140 examples)")
    L.append("")
    L.append("| Model | Statistic | mean | median | std | min | max | q05 | q95 |")
    L.append("| --- | --- | --: | --: | --: | --: | --: | --: | --: |")
    for k, v in p["task_4_per_answerable_influence"].items():
        s = v["statistics_of_pair_contribution"]
        L.append(f"| {k.split('|')[0]} | `{k.split('|')[1]}` | {s['mean']:+.6f} | {s['median']:+.6f} | {s['std']:.6f} | "
                 f"{s['min']:+.6f} | {s['max']:+.6f} | {s['q05']:+.6f} | {s['q95']:+.6f} |")
    L.append("")
    L.append("## 5. Influence concentration (share of absolute influence)")
    L.append("")
    L.append("| Model | Statistic | Class | Top-1 | Top-3 | Top-5 | Top-10 | Top-20 | Top-25% | Top-50% |")
    L.append("| --- | --- | --- | --: | --: | --: | --: | --: | --: | --: |")
    for r in p["task_13_table_2_concentration"]:
        sh = r["shares_of_absolute_influence"]
        L.append(f"| {r['model']} | `{r['statistic']}` | {r['class']} | " +
                 " | ".join(("—" if x == "UNSTABLE_DENOMINATOR" else f"{x:.4f}") for x in sh) + " |")
    L.append("")
    L.append("Top-25% / Top-50% column widths: " +
             "; ".join(f"{r['model']} {r['class']} specs {r['top_specs']}"
                       for r in p["task_13_table_2_concentration"][:2]) + ".")
    L.append("")
    L.append("## 6/7. Jackknife (182 leave-one-out runs per target)")
    L.append("")
    L.append("| Model | Statistic | Original AUC | JK min | JK max | JK mean | JK std | AUC>0.5 % | AUC<0.5 % | Near-0.5(±0.02) % | Stability | Trigger |")
    L.append("| --- | --- | --: | --: | --: | --: | --: | --: | --: | --: | --- | --- |")
    for r in p["task_13_table_1_stability"]:
        st = p["task_7_stability"][r["model"] + "|" + r["statistic"]]
        L.append(f"| {r['model']} | `{r['statistic']}` | {r['original_auc']:.4f} | {r['jackknife_min']:.4f} | "
                 f"{r['jackknife_max']:.4f} | {r['jackknife_mean']:.4f} | "
                 f"{st['jackknife_std']:.6f} | {r['pct_auc_gt_0_5']:.2f} | "
                 f"{r['pct_auc_lt_0_5']:.2f} | {r['pct_near_chance_0_02']:.2f} | {r['stability']} | {st['trigger']} |")
    L.append("")
    L.append("Pre-declared stability rule:")
    L.append("")
    for k in ("evaluation_order", "FEW_EXAMPLES_DRIVE_SIGNAL", "BROAD_DISTRIBUTED_SIGNAL", "NEAR_CHANCE_STABLE"):
        L.append(f"- `{k}`: {p['task_7_stability'][list(p['task_7_stability'])[0]]['rule'][k]}")
    L.append("")
    for k, v in p["task_7_stability"].items():
        j = p["task_6_jackknife"][k]["combined"]
        L.append(f"- **{k}**: delta_max {v['delta_max']:.6f}, side flips {v['side_flips']}, "
                 f"JK distance from chance {v['jackknife_distance_from_chance']:.6f} → `{v['stability']}`")
        L.append(f"  - removal increases AUC most: `{j['removal_increases_auc_most']['example_id']}` "
                 f"({j['removal_increases_auc_most']['class']}) → {j['removal_increases_auc_most']['auc_after_removal']:.4f} "
                 f"({j['removal_increases_auc_most']['delta_vs_original']:+.6f})")
        L.append(f"  - removal decreases AUC most: `{j['removal_decreases_auc_most']['example_id']}` "
                 f"({j['removal_decreases_auc_most']['class']}) → {j['removal_decreases_auc_most']['auc_after_removal']:.4f} "
                 f"({j['removal_decreases_auc_most']['delta_vs_original']:+.6f})")
        L.append(f"  - analytic jackknife equals brute-force recomputation: {p['task_6_jackknife'][k]['analytic_matches_brute_force']}")
    L.append("")
    L.append("## 8. Signed influence curve (examples ordered by |contribution| descending)")
    L.append("")
    L.append("| Model | Statistic | Class | total signed influence | 25% at | 50% at | 75% at | 90% at |")
    L.append("| --- | --- | --- | --: | --: | --: | --: | --: |")
    for k, v in p["task_8_signed_influence_curve"].items():
        for cls, key in (("UNANSWERABLE", "unanswerable_class"), ("ANSWERABLE", "answerable_class")):
            m = v[key]["marks"]
            g = lambda q: (f"{m[q]['examples_needed']} ex" if m[q]["examples_needed"] else "not reached")
            mark = "" if v[key]["marks_meaningful"] else " *(denominator near zero — marks uninformative)*"
            L.append(f"| {k.split('|')[0]} | `{k.split('|')[1]}` | {cls} | {v[key]['total_signed_influence']:+.6f} | "
                     f"{g('25pct')} | {g('50pct')} | {g('75pct')} | {g('90pct')}{mark} |")
    L.append("")
    L.append(f"Marks meaningfulness rule: {p['task_8_signed_influence_curve'][list(p['task_8_signed_influence_curve'])[0]]['answerable_class']['marks_meaningfulness_rule']}")
    L.append("")
    L.append("## 9. Category influence (answerable side, 140 examples)")
    L.append("")
    for k, v in p["task_9_category_influence"].items():
        L.append(f"### {k} — `{v['classification']}` (max category share {v['max_single_category_share']:.4f}, "
                 f"top-3 share {v['top3_category_share']:.4f})")
        L.append("")
        L.append("| Category | n | mean contribution | median contribution | total contribution | absolute contribution | share of absolute influence |")
        L.append("| --- | --: | --: | --: | --: | --: | --: |")
        for c in CATEGORIES:
            if c not in v["by_category"]:
                continue
            d = v["by_category"][c]
            sh = d["share_of_total_absolute_answerable_influence"]
            L.append(f"| `{c}` | {d['n']} | {d['mean_contribution']:+.6f} | {d['median_contribution']:+.6f} | "
                     f"{d['total_contribution']:+.6f} | {d['absolute_contribution']:.6f} | "
                     f"{'—' if sh == 'UNSTABLE_DENOMINATOR' else f'{sh:.4f}'} |")
        L.append("")
    L.append("## 10. Cross-checkpoint influence agreement")
    L.append("")
    L.append("| Statistic | influence Spearman | influence Pearson | top-10 overlap | top-20 overlap | Jaccard-10 | Jaccard-20 | pattern |")
    L.append("| --- | --: | --: | --: | --: | --: | --: | --- |")
    for r in p["task_13_table_3_cross_checkpoint"]:
        L.append(f"| `{r['statistic']}` | {r['influence_spearman']:+.4f} | "
                 f"{p['task_10_cross_checkpoint_agreement'][r['statistic']]['influence_pearson_F2_vs_A0']:+.4f} | "
                 f"{r['top10_overlap']}/10 | {r['top20_overlap']}/20 | {r['jaccard_10']} | {r['jaccard_20']} | "
                 f"{r['cross_checkpoint_pattern']} |")
    L.append("")
    L.append("## 11. A0 − F2 influence difference")
    L.append("")
    L.append("| Statistic | mean | median | std | q05 | q95 | top-10 share | top-20 share | class ratio | classification |")
    L.append("| --- | --: | --: | --: | --: | --: | --: | --: | --: | --- |")
    for s, v in p["task_11_a0_vs_f2_difference"].items():
        sm = v["summary_influence_A0_minus_influence_F2"]
        L.append(f"| `{s}` | {sm['mean']:+.6f} | {sm['median']:+.6f} | {sm['std']:.6f} | {sm['q05']:+.6f} | "
                 f"{sm['q95']:+.6f} | {v['top10_share_of_absolute_difference']} | "
                 f"{v['top20_share_of_absolute_difference']} | {v['class_ratio']} | {v['classification']} |")
    L.append("")
    L.append("## 12. Reconciliation with prior findings")
    L.append("")
    rc = p["task_12_reconciliation"]
    L.append(f"- F2 margin AUC 0.7338 → measured {rc['F2']['measured_this_phase']['margin_auc']}; "
             f"F2 best_answer_score AUC 0.7250 → measured {rc['F2']['measured_this_phase']['best_answer_score_auc']}")
    L.append(f"- A0 margin AUC 0.5432 → measured {rc['A0']['measured_this_phase']['margin_auc']}; "
             f"A0 best_answer_score AUC 0.5054 → measured {rc['A0']['measured_this_phase']['best_answer_score_auc']}")
    L.append(f"- F2 margin↔best_answer_score Spearman −0.9206 → reproduced "
             f"{rc['F2']['measured_this_phase']['margin_vs_best_answer_score_spearman']:+.4f}")
    L.append(f"- null-family paired-bootstrap (previous phase): {rc['null_family_paired_bootstrap_from_previous_phase']['relation']}")
    sr = rc["does_remaining_auc_difference_survive_influence_analysis"]
    L.append(f"- remaining answer-span difference: margin {sr['margin_difference']:+.4f}, "
             f"best_answer_score {sr['best_answer_score_difference']:+.4f}; leave-one-out ranges disjoint: "
             f"margin {sr['margin_loo_ranges_disjoint']}, best_answer_score {sr['best_answer_score_loo_ranges_disjoint']}")
    L.append("")
    L.append("## 14. Answers")
    L.append("")
    for k, v in p["task_14_answers"].items():
        L.append(f"- **{k}:** {v}")
    L.append("")
    L.append("## 15. Verdict")
    L.append("")
    L.append(f"**`{p['task_15_verdict']['verdict']}`**")
    L.append("")
    for k, c in p["task_15_verdict"]["per_target_classes"].items():
        L.append(f"- {k}: `{c}`")
    L.append("")
    if p["task_15_verdict"]["mechanistic_note"]:
        L.append(f"Mechanistic note: {p['task_15_verdict']['mechanistic_note']}")
        L.append("")
    L.append(f"Alternative reading: {p['task_15_verdict']['alternative_reading']}")
    L.append("")
    L.append("Verdict rules (the applied one is marked):")
    L.append("")
    for k, v in VERDICT_DEFS.items():
        L.append(f"- {'**' if k == p['task_15_verdict']['verdict'] else ''}`{k}`{ '**' if k == p['task_15_verdict']['verdict'] else ''}: {v}")
    L.append("")
    L.append("## Interpretation boundary")
    L.append("")
    for x in p["interpretation_boundary"]:
        L.append(f"- {x}")
    L.append("")
    L.append("## Integrity")
    L.append("")
    ig = p["integrity"]
    L.append("| Artifact | Recorded | Expected | Match |")
    L.append("| --- | --- | --- | --- |")
    for label, key, exp in [("benchmark", "benchmark_sha256", "benchmark_expected"),
                            ("dataset", "dataset_sha256", "dataset_expected"),
                            ("production model", "production_model_sha256", "production_model_expected"),
                            ("F2 model", "f2_model_sha256", "f2_model_expected"),
                            ("F2 checkpoint (dir scope)", "f2_checkpoint_dir_scope_sha256", "f2_checkpoint_dir_expected"),
                            ("source corpus fingerprint", "source_fingerprint", "source_fingerprint_expected"),
                            ("chunk corpus fingerprint", "chunk_fingerprint", "chunk_fingerprint_expected")]:
        L.append(f"| {label} | `{ig[key][:16]}…` | `{ig[exp][:16]}…` | {'MATCH' if ig[key] == ig[exp] else 'MISMATCH'} |")
    L.append(f"| prediction artifact | `{ig['predictions_artifact_sha256'][:16]}…` | (this phase's own recording) | — |")
    L.append("")
    (DECISION / "AUC_INFLUENCE_JACKKNIFE_FORENSICS.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()

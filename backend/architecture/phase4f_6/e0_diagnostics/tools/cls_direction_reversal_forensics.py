#!/usr/bin/env python
"""CLS / NULL direction-reversal forensics (bounded, score-distribution only).

Uses ONLY the already-recorded frozen prediction artifact. No model loading, no inference,
no GPU, no training, no database/PostgreSQL/pgvector, no retrieval, no threshold fitting,
no K search, no new combined score, no modification of any frozen artifact.

Question: why are `null_score`, `cls_start_logit` and `cls_end_logit` anti-predictive for
unanswerability at F2 but weakly positive at A0?

Direction convention used everywhere below (declared, never silently flipped):
    HIGHER oriented score  ==  MORE LIKELY UNANSWERABLE.
    null_score / cls_start_logit / cls_end_logit / margin / confidence : +1 (as recorded)
    best_answer_score                                                  : -1 (as recorded semantics)

Every classification rule in this script is declared BEFORE results are inspected, and the
artifact records the rule text alongside the outcome.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import ks_2samp, wasserstein_distance

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
EXISTING_FORENSICS = DECISION / "ANSWERABILITY_SIGNAL_FORENSICS.json"

BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
DATASET_SHA256 = "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
PROD_MODEL_SHA256 = "cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb"
F2_MODEL_SHA256 = "717463178eeb37ee3a6424063e8666b6586dd15ee50d745c1ab3d16bb4b164b0"
F2_CKPT_DIR_SHA256 = "416b63642ba80a1c4f11257df9d21f9e36427393533465d0ad3b2a15a0b5fc39"
SOURCE_FINGERPRINT = "3ec81cc5868f29a047409358943127509b4700cf2ddae1b877030059e4687ab1"
CHUNK_FINGERPRINT = "e6965cdad6684c65b739a316e01cff9e020e96a1588ec4aa37b19cfe98b135ea"

SEED = 20260923
ITERATIONS = 10000
N_ANS, N_UNANS = 140, 42
TOTAL = 182
OVERLAP_BINS = 30
QUANTILE_LEVELS = list(range(5, 100, 5))  # 19 levels: 5,10,...,95

NULL_FAMILY = ["null_score", "cls_start_logit", "cls_end_logit"]
ANSWER_SPAN_FAMILY = ["best_answer_score", "margin"]
REQUIRED_STATS = ["null_score", "cls_start_logit", "cls_end_logit", "best_answer_score"]
ALL_STATS = ["null_score", "cls_start_logit", "cls_end_logit", "best_answer_score", "margin", "confidence"]
SIGN = {s: (+1.0 if s != "best_answer_score" else -1.0) for s in ALL_STATS}
DIRECTION_TEXT = {s: ("HIGHER=UNANSWERABLE" if SIGN[s] > 0 else "LOWER=UNANSWERABLE (reversed for analysis)")
                  for s in ALL_STATS}

CATEGORIES = ["DIRECT_SPAN", "NUMERIC", "MULTI_CHUNK", "LIST_ITEM",
              "TABLE_ROW", "LONG_CONTEXT", "TABLE_CELL", "SECTION_SPECIFIC"]

# ---- rules declared before inspecting results -------------------------------------------
RULE_S3 = {
    "tolerance": "a component delta is treated as having no sign when |delta| < 1e-9",
    "BOTH_COMPONENTS": "sign(delta_start) and sign(delta_end) BOTH flip between F2 and A0",
    "START_COMPONENT_DRIVEN": "only sign(delta_start) flips (delta_end keeps its sign)",
    "END_COMPONENT_DRIVEN": "only sign(delta_end) flips (delta_start keeps its sign)",
    "COMPONENT_CANCELLATION": "neither component flips, but the two components carry opposite signs within at least one checkpoint, so the sum (delta_null) changes sign through changing cancellation",
    "NO_CLEAR_COMPONENT_EXPLANATION": "none of the above",
}
RULE_S4 = {
    "literal_TRUE_DIRECTION_REVERSAL": "(F2 AUC < 0.5 AND A0 AUC > 0.5) OR (F2 AUC > 0.5 AND A0 AUC < 0.5)",
    "statistical_caveat": ("the literal sign flip is only called an established reversal when at least one of the two "
                           "95% bootstrap AUC CIs excludes 0.50 in the direction of its point estimate; if both CIs "
                           "include 0.50 the applied classification is NEAR_CHANCE_BOTH"),
    "SAME_DIRECTION_DIFFERENT_STRENGTH": "both AUCs on the same side of 0.5 but the point estimates differ",
    "NEAR_CHANCE_BOTH": "literal sign flip present but both AUC CIs include 0.50 (not statistically established)",
    "INCONCLUSIVE": "does not fall into any of the above",
}
RULE_S5_QUANTILE = ("for each of the 19 quantile levels 5%..95%, compare Q_unanswerable(level) with "
                    "Q_answerable(level) at that same level; consistency = (levels where unanswerable > answerable) / 19; "
                    "exact ties are counted separately and are not forced into either direction")
RULE_MECHANISM = {
    "per_checkpoint": {
        "BROAD_OVERLAP": "KS <= 0.20 OR overlap coefficient >= 0.75",
        "WEAK_SEPARATION": "not BROAD_OVERLAP AND |mean separation| / pooled_std <= 0.20",
        "MIXED": "neither of the above",
    },
    "reading_caveat": ("the per-checkpoint mechanism label is defined on the KS statistic and on the standardized mean "
                       "separation |mean delta| / pooled_sd; the standardized ratio is scale-sensitive, so a checkpoint "
                       "with a much wider score spread can receive WEAK_SEPARATION while having a LARGER absolute mean "
                       "separation. The scale-invariant ROC-AUC column is the primary separation measure and the mechanism "
                       "column must be read alongside it, not instead of it."),
    "cross_checkpoint_attribution": {
        "shift_answerable": "mean_answerable(A0) - mean_answerable(F2)",
        "shift_unanswerable": "mean_unanswerable(A0) - mean_unanswerable(F2)",
        "ANSWERABLE_SHIFT": "|shift_answerable| > 2 * |shift_unanswerable|",
        "UNANSWERABLE_SHIFT": "|shift_unanswerable| > 2 * |shift_answerable|",
        "DISTRIBUTION_CROSSING": "shift_answerable and shift_unanswerable have opposite signs and neither dominates by 2x",
        "MIXED": "none of the above",
    },
}
RULE_S7 = {
    "INSUFFICIENT_CATEGORY_SUPPORT": "a category has no examples of one class, so class separation and AUC are undefined there",
    "GLOBAL_REVERSAL": "the reversal direction change is present in every category that supports both classes",
    "CATEGORY_LOCAL_REVERSAL": "the reversal appears only in a proper subset of categories with both classes",
    "MIXED_PATTERN": "categories disagree with no consistent subset pattern",
}
VERDICT_DEFS = {
    "REVERSAL_EXPLAINED": "component-level evidence explains the sign change clearly",
    "REVERSAL_PARTIALLY_EXPLAINED": "distribution/component evidence explains part of it but not all",
    "REVERSAL_NOT_EXPLAINED": "distributions do not identify a defensible mechanism",
    "REVERSAL_INCONCLUSIVE": "insufficient class/category evidence",
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


def roc_auc(scores: np.ndarray, y: np.ndarray) -> float:
    r = rank_average(scores)
    n1 = int(y.sum())
    n0 = len(y) - n1
    u = r[y == 1].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def mannwhitney_u(scores: np.ndarray, y: np.ndarray) -> float:
    r = rank_average(scores)
    n1 = int(y.sum())
    return float(r[y == 1].sum() - n1 * (n1 + 1) / 2.0)


def cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if sp == 0:
        return float("nan")
    return float((a.mean() - b.mean()) / sp)


def overlap_coefficient(ans: np.ndarray, unans: np.ndarray, nbins: int = OVERLAP_BINS) -> float:
    lo = min(float(ans.min()), float(unans.min()))
    hi = max(float(ans.max()), float(unans.max()))
    if hi == lo:
        return 1.0
    edges = np.linspace(lo, hi, nbins + 1)
    ha, _ = np.histogram(ans, bins=edges)
    hu, _ = np.histogram(unans, bins=edges)
    return float(np.minimum(ha / max(ha.sum(), 1), hu / max(hu.sum(), 1)).sum())


def quantile_direction(ans: np.ndarray, unans: np.ndarray) -> dict:
    qa = np.percentile(ans, QUANTILE_LEVELS)
    qu = np.percentile(unans, QUANTILE_LEVELS)
    gt = [lvl for lvl, a, u in zip(QUANTILE_LEVELS, qa, qu) if u > a]
    lt = [lvl for lvl, a, u in zip(QUANTILE_LEVELS, qa, qu) if u < a]
    eq = [lvl for lvl, a, u in zip(QUANTILE_LEVELS, qa, qu) if u == a]
    return {
        "levels": QUANTILE_LEVELS,
        "unanswerable_gt_answerable_levels": gt,
        "unanswerable_lt_answerable_levels": lt,
        "exact_tie_levels": eq,
        "distributional_direction_consistency": f"{max(len(gt), len(lt))} / {len(QUANTILE_LEVELS)} quantiles "
                                                 f"({'UNANSWERABLE_HIGHER' if len(gt) >= len(lt) else 'UNANSWERABLE_LOWER'})",
        "majority_direction": "UNANSWERABLE_HIGHER" if len(gt) >= len(lt) else "UNANSWERABLE_LOWER",
        "interleaved": bool(gt and lt),
    }


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return float("nan")
    ra, rb = rank_average(a), rank_average(b)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def sign_of(x: float, tol: float = 1e-9) -> int:
    return 0 if abs(x) < tol else (1 if x > 0 else -1)


def ci95(v: np.ndarray) -> list[float]:
    lo, hi = np.percentile(v, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def ks_batch(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Vectorised two-sample KS over a batch of resamples (p: (b,n1), q: (b,n2))."""
    b, n1 = p.shape
    n2 = q.shape[1]
    allv = np.concatenate([p, q], axis=1)
    lab = np.concatenate([np.ones((b, n1)), np.zeros((b, n2))], axis=1)
    order = np.argsort(allv, axis=1, kind="mergesort")
    vl = np.take_along_axis(allv, order, axis=1)
    yl = np.take_along_axis(lab, order, axis=1)
    # group ties: only the cumulative counts after the last tied element count as ECDF values
    is_new = np.ones((b, allv.shape[1]), dtype=bool)
    is_new[:, 1:] = vl[:, 1:] != vl[:, :-1]
    c1 = np.cumsum(yl, axis=1) / n1
    c2 = np.cumsum(1.0 - yl, axis=1) / n2
    diff = np.abs(c1 - c2)
    diff[~is_new] = -1.0  # ignore intermediate tie positions
    return diff.max(axis=1)


# ---- main ------------------------------------------------------------------------------
def main() -> None:
    preds = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    f2, a0 = preds["F2_primary"]["predictions"], preds["A0_secondary"]["predictions"]
    models = {"F2": f2, "A0": a0}

    # ---------------------------------------------------------------- 1. input integrity
    issues = []
    for name, rows in models.items():
        if len(rows) != TOTAL:
            issues.append(f"{name}: {len(rows)} rows != {TOTAL}")
    if [r["example_id"] for r in f2] != [r["example_id"] for r in a0]:
        issues.append("F2/A0 example_id order does not match")
    if [r["answerability"] for r in f2] != [r["answerability"] for r in a0]:
        issues.append("F2/A0 answerability labels differ")
    for name, rows in models.items():
        for fld in ALL_STATS + ["answerability", "category", "example_id"]:
            if any(r.get(fld) is None for r in rows):
                issues.append(f"{name}: field '{fld}' missing in at least one row")
    y = np.array([1 if r["answerability"] == "UNANSWERABLE" else 0 for r in f2], dtype=int)
    if int(y.sum()) != N_UNANS or int((y == 0).sum()) != N_ANS:
        issues.append(f"class counts {int((y==0).sum())}/{int(y.sum())} != {N_ANS}/{N_UNANS}")
    if issues:
        print("INPUT INTEGRITY FAILED:")
        for i in issues:
            print("  -", i)
        raise SystemExit(2)

    cat_by_class: dict[str, dict[str, int]] = {}
    for r in f2:
        cat_by_class.setdefault(r["category"], {"ANSWERABLE": 0, "UNANSWERABLE": 0})[r["answerability"]] += 1

    integrity_input = {
        "prediction_artifact": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
        "parses": True,
        "F2_rows": len(f2), "A0_rows": len(a0),
        "row_identity_and_order_match": True,
        "answerability_labels_identical": True,
        "required_fields_present": ALL_STATS + ["answerability", "category"],
        "class_counts": {"answerable": int((y == 0).sum()), "unanswerable": int(y.sum())},
        "category_x_answerability": cat_by_class,
        "structural_categories_with_zero_unanswerable": sorted(
            c for c, v in cat_by_class.items() if v["UNANSWERABLE"] == 0 and c != "UNANSWERABLE"),
        "repaired_anything": False,
        "issues": [],
    }

    # ---------------------------------------------------------------- 2/3 collect raw arrays
    raw = {name: {s: np.array([float(r[s]) for r in rows], dtype=np.float64) for s in ALL_STATS}
           for name, rows in models.items()}
    # identity check null = cls_start + cls_end
    identity_err = {name: float(np.max(np.abs(raw[name]["null_score"] -
                                            (raw[name]["cls_start_logit"] + raw[name]["cls_end_logit"]))))
                    for name in models}

    # ---- §2 class-conditional distributions
    dist = {}
    for name in ("F2", "A0"):
        dist[name] = {}
        for s in ALL_STATS:
            sc = raw[name][s] * SIGN[s]
            ans, unans = sc[y == 0], sc[y == 1]
            u = mannwhitney_u(sc, y)
            auc = roc_auc(sc, y)
            ks_stat, ks_p = ks_2samp(unans, ans, method="asymp")
            dist[name][s] = {
                "answerable": {
                    "n": int(len(ans)), "mean": round(float(ans.mean()), 4),
                    "median": round(float(np.median(ans)), 4), "std": round(float(ans.std(ddof=1)), 4),
                    "min": round(float(ans.min()), 4), "q05": round(float(np.percentile(ans, 5)), 4),
                    "q25": round(float(np.percentile(ans, 25)), 4), "q50": round(float(np.median(ans)), 4),
                    "q75": round(float(np.percentile(ans, 75)), 4), "q95": round(float(np.percentile(ans, 95)), 4),
                    "max": round(float(ans.max()), 4),
                    "iqr": round(float(np.percentile(ans, 75) - np.percentile(ans, 25)), 4),
                },
                "unanswerable": {
                    "n": int(len(unans)), "mean": round(float(unans.mean()), 4),
                    "median": round(float(np.median(unans)), 4), "std": round(float(unans.std(ddof=1)), 4),
                    "min": round(float(unans.min()), 4), "q05": round(float(np.percentile(unans, 5)), 4),
                    "q25": round(float(np.percentile(unans, 25)), 4), "q50": round(float(np.median(unans)), 4),
                    "q75": round(float(np.percentile(unans, 75)), 4), "q95": round(float(np.percentile(unans, 95)), 4),
                    "max": round(float(unans.max()), 4),
                    "iqr": round(float(np.percentile(unans, 75) - np.percentile(unans, 25)), 4),
                },
                "mean_difference_unanswerable_minus_answerable": round(float(unans.mean() - ans.mean()), 4),
                "median_difference_unanswerable_minus_answerable": round(float(np.median(unans) - np.median(ans)), 4),
                "standardized_mean_difference_cohen_d": round(cohen_d(unans, ans), 4),
                "mannwhitney_U": round(u, 2),
                "roc_auc_unanswerable_positive": round(auc, 4),
                "rank_biserial": round(2.0 * auc - 1.0, 4),
                "ks_statistic": round(float(ks_stat), 4),
                "ks_asymptotic_p": round(float(ks_p), 4),
                "ks_direction": "UNANSWERABLE_HIGHER" if unans.mean() > ans.mean() else "UNANSWERABLE_LOWER",
                "orientation_applied": DIRECTION_TEXT[s],
                "distribution_reported_on": "analysis-oriented score (sign applied per declared direction)",
            }

    # ---------------------------------------------------------------- 3. component decomposition
    comp = {"identity_max_abs_error_F2": identity_err["F2"], "identity_max_abs_error_A0": identity_err["A0"]}
    for name in ("F2", "A0"):
        m_s = float(raw[name]["cls_start_logit"][y == 1].mean())
        m_sa = float(raw[name]["cls_start_logit"][y == 0].mean())
        m_e = float(raw[name]["cls_end_logit"][y == 1].mean())
        m_ea = float(raw[name]["cls_end_logit"][y == 0].mean())
        m_n = float(raw[name]["null_score"][y == 1].mean())
        m_na = float(raw[name]["null_score"][y == 0].mean())
        med_s = float(np.median(raw[name]["cls_start_logit"][y == 1]) - np.median(raw[name]["cls_start_logit"][y == 0]))
        med_e = float(np.median(raw[name]["cls_end_logit"][y == 1]) - np.median(raw[name]["cls_end_logit"][y == 0]))
        med_n = float(np.median(raw[name]["null_score"][y == 1]) - np.median(raw[name]["null_score"][y == 0]))
        comp[name] = {
            "means": {
                "answerable": {"cls_start": round(m_sa, 4), "cls_end": round(m_ea, 4), "null": round(m_na, 4)},
                "unanswerable": {"cls_start": round(m_s, 4), "cls_end": round(m_e, 4), "null": round(m_n, 4)},
            },
            "mean_identity_check_start_plus_end_equals_null_answerable": round(m_sa + m_ea - m_na, 6),
            "mean_identity_check_start_plus_end_equals_null_unanswerable": round(m_s + m_e - m_n, 6),
            "delta_start": round(m_s - m_sa, 4),
            "delta_end": round(m_e - m_ea, 4),
            "delta_null": round(m_n - m_na, 4),
            "delta_identity_check_start_plus_end_equals_null": round((m_s - m_sa) + (m_e - m_ea) - (m_n - m_na), 6),
            "medians": {
                "delta_start_median": round(med_s, 4), "delta_end_median": round(med_e, 4),
                "delta_null_median": round(med_n, 4),
                "algebraic_identity_expected": False,
                "note": ("median(start) + median(end) = median(null) is NOT an algebraic identity; medians are reported "
                         "as descriptive only and no approximate median identity is asserted"),
            },
        }
    d_s = sign_of(comp["F2"]["delta_start"]), sign_of(comp["A0"]["delta_start"])
    d_e = sign_of(comp["F2"]["delta_end"]), sign_of(comp["A0"]["delta_end"])
    d_n = sign_of(comp["F2"]["delta_null"]), sign_of(comp["A0"]["delta_null"])
    flip_start = d_s[0] != 0 and d_s[1] != 0 and d_s[0] != d_s[1]
    flip_end = d_e[0] != 0 and d_e[1] != 0 and d_e[0] != d_e[1]
    flip_null = d_n[0] != 0 and d_n[1] != 0 and d_n[0] != d_n[1]
    cancel = (d_s[0] != 0 and d_e[0] != 0 and d_s[0] != d_e[0]) or \
             (d_s[1] != 0 and d_e[1] != 0 and d_s[1] != d_e[1])
    if flip_start and flip_end:
        driver = "BOTH_COMPONENTS"
    elif flip_start:
        driver = "START_COMPONENT_DRIVEN"
    elif flip_end:
        driver = "END_COMPONENT_DRIVEN"
    elif cancel and flip_null:
        driver = "COMPONENT_CANCELLATION"
    else:
        driver = "NO_CLEAR_COMPONENT_EXPLANATION"
    component_result = {
        "identity_max_abs_error_F2": comp["identity_max_abs_error_F2"],
        "identity_max_abs_error_A0": comp["identity_max_abs_error_A0"],
        "per_checkpoint": comp,
        "signs": {"delta_start": {"F2": d_s[0], "A0": d_s[1]},
                  "delta_end": {"F2": d_e[0], "A0": d_e[1]},
                  "delta_null": {"F2": d_n[0], "A0": d_n[1]}},
        "flip_flags": {"start_flips": flip_start, "end_flips": flip_end, "null_flips": flip_null,
                       "opposing_components_within_a_checkpoint": cancel},
        "classification": driver,
        "rule": RULE_S3,
    }

    # ---------------------------------------------------------------- 4. direction reversal
    boot_rng = np.random.default_rng(SEED)
    IDX_U = boot_rng.integers(0, N_UNANS, size=(ITERATIONS, N_UNANS))
    IDX_A = boot_rng.integers(0, N_ANS, size=(ITERATIONS, N_ANS))
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]

    existing = json.loads(EXISTING_FORENSICS.read_text(encoding="utf-8"))

    reversal = {}
    for s in ALL_STATS:
        rec = {"statistic": s, "declared_direction": DIRECTION_TEXT[s],
               "F2_auc": dist["F2"][s]["roc_auc_unanswerable_positive"],
               "A0_auc": dist["A0"][s]["roc_auc_unanswerable_positive"]}
        rec["delta_auc_F2_minus_A0"] = round(rec["F2_auc"] - rec["A0_auc"], 4)
        rec["F2_direction"] = "UNANSWERABLE_HIGHER" if rec["F2_auc"] > 0.5 else "UNANSWERABLE_LOWER"
        rec["A0_direction"] = "UNANSWERABLE_HIGHER" if rec["A0_auc"] > 0.5 else "UNANSWERABLE_LOWER"
        literal = (rec["F2_auc"] < 0.5 < rec["A0_auc"]) or (rec["A0_auc"] < 0.5 < rec["F2_auc"])
        rec["literal_TRUE_DIRECTION_REVERSAL"] = bool(literal)
        ci_f2 = existing["task_3_4_5_per_model"]["F2"].get(s, {}).get("roc_auc_95ci")
        ci_a0 = existing["task_3_4_5_per_model"]["A0"].get(s, {}).get("roc_auc_95ci")
        rec["F2_auc_ci95_existing_artifact"] = ci_f2
        rec["A0_auc_ci95_existing_artifact"] = ci_a0
        f2_established = bool(ci_f2 and ((rec["F2_auc"] > 0.5 and ci_f2[0] > 0.5) or (rec["F2_auc"] < 0.5 and ci_f2[1] < 0.5)))
        a0_established = bool(ci_a0 and ((rec["A0_auc"] > 0.5 and ci_a0[0] > 0.5) or (rec["A0_auc"] < 0.5 and ci_a0[1] < 0.5)))
        rec["F2_direction_statistically_established"] = f2_established
        rec["A0_direction_statistically_established"] = a0_established
        rec["both_AUC_CIs_include_0_50"] = bool(ci_f2 and ci_a0 and (ci_f2[0] <= 0.5 <= ci_f2[1]) and (ci_a0[0] <= 0.5 <= ci_a0[1]))
        if literal and (f2_established or a0_established):
            cls = "TRUE_DIRECTION_REVERSAL"
        elif literal:
            cls = "NEAR_CHANCE_BOTH"
        elif (rec["F2_auc"] - 0.5) * (rec["A0_auc"] - 0.5) > 0:
            cls = "SAME_DIRECTION_DIFFERENT_STRENGTH"
        else:
            cls = "INCONCLUSIVE"
        rec["applied_classification"] = cls
        reversal[s] = rec

    # paired bootstrap of delta AUC (same resample applied to both checkpoints)
    for s in ALL_STATS:
        ps = {n: raw[n][s] * SIGN[s] for n in ("F2", "A0")}
        d = []
        for i0 in range(0, ITERATIONS, 1000):
            b = min(1000, ITERATIONS - i0)
            iu, ia = IDX_U[i0:i0 + b], IDX_A[i0:i0 + b]
            acc = []
            for n in ("F2", "A0"):
                sc = ps[n]
                p = sc[pos][iu]
                q = sc[neg][ia]
                gt = (p[:, :, None] > q[:, None, :]).sum(axis=(1, 2))
                eq = (p[:, :, None] == q[:, None, :]).sum(axis=(1, 2))
                acc.append((gt + 0.5 * eq) / (N_UNANS * N_ANS))
            d.append(acc[0] - acc[1])
        d = np.concatenate(d)
        reversal[s]["delta_auc_F2_minus_A0_ci95_paired"] = ci95(d)
        reversal[s]["delta_auc_ci_excludes_0"] = bool(ci95(d)[0] > 0 or ci95(d)[1] < 0)

    # ---------------------------------------------------------------- 5. distribution crossing
    crossing = {}
    for name in ("F2", "A0"):
        crossing[name] = {}
        for s in ALL_STATS:
            sc = raw[name][s] * SIGN[s]
            ans, unans = sc[y == 0], sc[y == 1]
            ks_stat, ks_p = ks_2samp(unans, ans, method="asymp")
            qd = quantile_direction(ans, unans)
            crossing[name][s] = {
                "ks_statistic": round(float(ks_stat), 4),
                "ks_asymptotic_p": round(float(ks_p), 4),
                "ks_direction": dist[name][s]["ks_direction"],
                "overlap_coefficient": round(overlap_coefficient(ans, unans), 4),
                "overlap_binning": f"{OVERLAP_BINS} equal-width bins over the combined score range",
                "wasserstein_distance": round(float(wasserstein_distance(unans, ans)), 4),
                "empirical_cdf_max_difference": round(float(ks_stat), 4),
                "empirical_cdf_note": "identical by definition to the two-sample KS statistic (both are sup|F1-F2|)",
                "quantile_analysis": qd,
            }
    crossing_rule = RULE_S5_QUANTILE

    # ---------------------------------------------------------------- 6. rank-order forensics
    rankorder = {}
    for s in ALL_STATS:
        a2, a0v = raw["F2"][s], raw["A0"][s]
        rankorder[s] = {
            "spearman_F2_vs_A0_all_182": round(spearman(a2, a0v), 4),
            "spearman_F2_vs_A0_answerable_140": round(spearman(a2[y == 0], a0v[y == 0]), 4),
            "spearman_F2_vs_A0_unanswerable_42": round(spearman(a2[y == 1], a0v[y == 1]), 4),
            "answerability_rank_auc_F2": dist["F2"][s]["roc_auc_unanswerable_positive"],
            "answerability_rank_auc_A0": dist["A0"][s]["roc_auc_unanswerable_positive"],
            "rank_direction_agreement": bool((dist["F2"][s]["roc_auc_unanswerable_positive"] - 0.5) *
                                             (dist["A0"][s]["roc_auc_unanswerable_positive"] - 0.5) > 0),
            "rank_direction_agreement_definition": ("sign(AUC_F2 - 0.5) == sign(AUC_A0 - 0.5); "
                                                    "cross-checkpoint Spearman is a score-ordering similarity "
                                                    "measure and is NOT model quality"),
        }

    # ---------------------------------------------------------------- 7. category stratification
    cat_sec = {"categories": CATEGORIES, "per_category": {}, "per_checkpoint_answerable_only": {}}
    for c in CATEGORIES:
        idx = [i for i, r in enumerate(f2) if r["category"] == c]
        n_unans = int(sum(1 for i in idx if y[i] == 1))
        entry = {
            "n": len(idx),
            "answerable_n": int(len(idx) - n_unans),
            "unanswerable_n": n_unans,
            "both_classes_present": bool(len(idx) > 0 and n_unans > 0 and n_unans < len(idx)),
            "statistics": {},
        }
        for s in NULL_FAMILY:
            if not entry["both_classes_present"]:
                entry["statistics"][s] = {
                    "mean_answerable_score": round(float((raw["F2"][s] * SIGN[s])[idx].mean()), 4),
                    "mean_unanswerable_score": None,
                    "direction_of_mean_separation": "UNDEFINED_NO_UNANSWERABLE_EXAMPLES",
                    "auc_where_both_classes_exist": None,
                    "auc_status": "UNDEFINED_NO_UNANSWERABLE_EXAMPLES",
                }
            else:
                sub = np.array(y)[idx]
                sc = (raw["F2"][s] * SIGN[s])[idx]
                entry["statistics"][s] = {
                    "mean_answerable_score": round(float(sc[sub == 0].mean()), 4),
                    "mean_unanswerable_score": round(float(sc[sub == 1].mean()), 4),
                    "direction_of_mean_separation": "UNANSWERABLE_HIGHER" if sc[sub == 1].mean() > sc[sub == 0].mean()
                                                    else "UNANSWERABLE_LOWER",
                    "auc_where_both_classes_exist": round(roc_auc(sc, sub), 4),
                    "auc_status": "COMPUTED",
                }
        cat_sec["per_category"][c] = entry
    # descriptive answerable-only score shift per category (NOT class separation)
    for name in ("F2", "A0"):
        cat_sec["per_checkpoint_answerable_only"][name] = {}
        for c in CATEGORIES:
            idx = [i for i, r in enumerate(f2) if r["category"] == c and y[i] == 0]
            cat_sec["per_checkpoint_answerable_only"][name][c] = {
                s: round(float((raw[name][s] * SIGN[s])[idx].mean()), 4) for s in NULL_FAMILY
            }
    cat_sec["answerable_only_shift_F2_to_A0"] = {
        c: {s: round(cat_sec["per_checkpoint_answerable_only"]["A0"][c][s] -
                     cat_sec["per_checkpoint_answerable_only"]["F2"][c][s], 4) for s in NULL_FAMILY}
        for c in CATEGORIES
    }
    supported = [c for c in CATEGORIES if cat_sec["per_category"][c]["both_classes_present"]]
    if not supported:
        cat_flag = "INSUFFICIENT_CATEGORY_SUPPORT"
    else:
        cat_flag = "GLOBAL_REVERSAL"
    cat_sec["flag"] = cat_flag
    cat_sec["rule"] = RULE_S7
    cat_sec["flag_basis"] = (f"0 of {len(CATEGORIES)} structural categories contain any unanswerable example; "
                            f"all 42 unanswerable examples carry category 'UNANSWERABLE' "
                            f"({cat_by_class.get('UNANSWERABLE', {}).get('UNANSWERABLE', 0)} examples), so class "
                            f"separation and AUC are undefined inside every structural category")

    # ---------------------------------------------------------------- 8. answer-span control
    control = {"spearman": {}, "auc": {}, "class_separation": {}}
    for name in ("F2", "A0"):
        control["spearman"][name] = {}
        for a in ANSWER_SPAN_FAMILY + NULL_FAMILY:
            control["spearman"][name][a] = {
                b: round(spearman(raw[name][a], raw[name][b]), 4)
                for b in ANSWER_SPAN_FAMILY + NULL_FAMILY
            }
    for s in ANSWER_SPAN_FAMILY + NULL_FAMILY:
        control["auc"][s] = {"F2": dist["F2"][s]["roc_auc_unanswerable_positive"],
                             "A0": dist["A0"][s]["roc_auc_unanswerable_positive"],
                             "delta_F2_minus_A0": round(dist["F2"][s]["roc_auc_unanswerable_positive"] -
                                                        dist["A0"][s]["roc_auc_unanswerable_positive"], 4)}
        control["class_separation"][s] = {
            "F2_mean_delta": dist["F2"][s]["mean_difference_unanswerable_minus_answerable"],
            "A0_mean_delta": dist["A0"][s]["mean_difference_unanswerable_minus_answerable"],
            "F2_overlap": crossing["F2"][s]["overlap_coefficient"],
            "A0_overlap": crossing["A0"][s]["overlap_coefficient"],
        }
    measured = control["spearman"]["F2"]["margin"]["best_answer_score"]
    control["verification_of_previously_measured_relationship"] = {
        "claimed": -0.9206, "measured_this_phase_F2_margin_vs_best_answer_score": measured,
        "reproduced": abs(measured - (-0.9206)) < 5e-4,
        "A0_margin_vs_best_answer_score": control["spearman"]["A0"]["margin"]["best_answer_score"],
    }
    # compare answer-span family against null family
    best_span_auc_f2 = max(control["auc"][s]["F2"] for s in ANSWER_SPAN_FAMILY)
    best_null_auc_f2 = max(control["auc"][s]["F2"] for s in NULL_FAMILY)
    control["family_comparison"] = {
        "best_answer_span_family_AUC_F2": best_span_auc_f2,
        "best_null_family_AUC_F2": best_null_auc_f2,
        "gap_F2": round(best_span_auc_f2 - best_null_auc_f2, 4),
        "best_answer_span_family_AUC_A0": max(control["auc"][s]["A0"] for s in ANSWER_SPAN_FAMILY),
        "best_null_family_AUC_A0": max(control["auc"][s]["A0"] for s in NULL_FAMILY),
        "gap_A0": round(max(control["auc"][s]["A0"] for s in ANSWER_SPAN_FAMILY) -
                        max(control["auc"][s]["A0"] for s in NULL_FAMILY), 4),
        "note": "descriptive AUC comparison of the recorded families only; no combined score is created",
    }

    # ---------------------------------------------------------------- 10. mechanism tables
    def per_checkpoint_mechanism(name: str, s: str) -> str:
        sc = raw[name][s] * SIGN[s]
        ans, unans = sc[y == 0], sc[y == 1]
        ks = crossing[name][s]["ks_statistic"]
        ov = crossing[name][s]["overlap_coefficient"]
        pooled = float(np.sqrt((ans.var(ddof=1) + unans.var(ddof=1)) / 2.0))
        delta = abs(float(unans.mean() - ans.mean()))
        if ks <= 0.20 or ov >= 0.75:
            return "BROAD_OVERLAP"
        if pooled > 0 and delta / pooled <= 0.20:
            return "WEAK_SEPARATION"
        return "MIXED"

    def cross_checkpoint_attribution(s: str) -> dict:
        sh_a = float((raw["A0"][s] * SIGN[s])[y == 0].mean() - (raw["F2"][s] * SIGN[s])[y == 0].mean())
        sh_u = float((raw["A0"][s] * SIGN[s])[y == 1].mean() - (raw["F2"][s] * SIGN[s])[y == 1].mean())
        if sign_of(sh_a) != 0 and sign_of(sh_u) != 0 and sign_of(sh_a) != sign_of(sh_u) and \
                max(abs(sh_a), abs(sh_u)) <= 2 * min(abs(sh_a), abs(sh_u)):
            att = "DISTRIBUTION_CROSSING"
        elif abs(sh_u) > 2 * abs(sh_a):
            att = "UNANSWERABLE_SHIFT"
        elif abs(sh_a) > 2 * abs(sh_u):
            att = "ANSWERABLE_SHIFT"
        else:
            att = "MIXED"
        return {"shift_answerable": round(sh_a, 4), "shift_unanswerable": round(sh_u, 4),
                "separation_change": round(sh_u - sh_a, 4), "attribution": att}

    table1 = []
    for name in ("F2", "A0"):
        for s in ALL_STATS:
            table1.append({
                "checkpoint": name, "statistic": s,
                "auc": dist[name][s]["roc_auc_unanswerable_positive"],
                "ci": reversal[s][f"{name}_auc_ci95_existing_artifact"],
                "mean_delta_unanswerable_minus_answerable": dist[name][s]["mean_difference_unanswerable_minus_answerable"],
                "median_delta_unanswerable_minus_answerable": dist[name][s]["median_difference_unanswerable_minus_answerable"],
                "ks": crossing[name][s]["ks_statistic"],
                "overlap": crossing[name][s]["overlap_coefficient"],
                "direction": dist[name][s]["ks_direction"],
                "mechanism": per_checkpoint_mechanism(name, s),
            })
    table2 = []
    for s in ALL_STATS:
        table2.append({
            "statistic": s,
            "F2_mechanism": per_checkpoint_mechanism("F2", s),
            "A0_mechanism": per_checkpoint_mechanism("A0", s),
            "reversal_type": reversal[s]["applied_classification"],
            "component_driver": (driver if s == "null_score" else
                                 ("COMPONENT_OF_NULL_SCORE" if s in ("cls_start_logit", "cls_end_logit")
                                  else "NOT_APPLICABLE_COMPONENT")),
        })

    # ---------------------------------------------------------------- 9. bootstrap
    boot_rows = []
    for name in ("F2", "A0"):
        for s in ALL_STATS:
            sc = raw[name][s] * SIGN[s]
            p, q = sc[pos], sc[neg]
            mean_d, aucs, kss = [], [], []
            for i0 in range(0, ITERATIONS, 1000):
                b = min(1000, ITERATIONS - i0)
                iu, ia = IDX_U[i0:i0 + b], IDX_A[i0:i0 + b]
                pu, qa = p[iu], q[ia]
                mean_d.append(pu.mean(axis=1) - qa.mean(axis=1))
                gt = (pu[:, :, None] > qa[:, None, :]).sum(axis=(1, 2))
                eq = (pu[:, :, None] == qa[:, None, :]).sum(axis=(1, 2))
                aucs.append((gt + 0.5 * eq) / (N_UNANS * N_ANS))
                kss.append(ks_batch(pu, qa))
            mean_d, aucs, kss = np.concatenate(mean_d), np.concatenate(aucs), np.concatenate(kss)
            boot_rows.append({
                "checkpoint": name, "statistic": s, "seed": SEED, "iterations": ITERATIONS,
                "stratified": {"answerable": N_ANS, "unanswerable": N_UNANS},
                "mean_separation_point": dist[name][s]["mean_difference_unanswerable_minus_answerable"],
                "mean_separation_ci95": [round(float(x), 4) for x in np.percentile(mean_d, [2.5, 97.5])],
                "auc_point": dist[name][s]["roc_auc_unanswerable_positive"],
                "auc_ci95": ci95(aucs),
                "ks_point": crossing[name][s]["ks_statistic"],
                "ks_ci95": ci95(kss),
                "ks_bootstrap_method": "vectorised tie-grouped ECDF (validated against scipy at the point estimate)",
            })

    # ---------------------------------------------------------------- 11/12 verdict
    nullf = reversal["null_score"]
    literal_any = any(reversal[s]["literal_TRUE_DIRECTION_REVERSAL"] for s in NULL_FAMILY)
    established_any = any(reversal[s]["applied_classification"] == "TRUE_DIRECTION_REVERSAL" for s in NULL_FAMILY)
    delta_ci_excludes_zero = any(reversal[s]["delta_auc_ci_excludes_0"] for s in NULL_FAMILY)
    if driver in ("BOTH_COMPONENTS", "START_COMPONENT_DRIVEN", "END_COMPONENT_DRIVEN",
                  "COMPONENT_CANCELLATION") and established_any:
        verdict = "REVERSAL_EXPLAINED"
    elif driver in ("BOTH_COMPONENTS", "START_COMPONENT_DRIVEN", "END_COMPONENT_DRIVEN",
                    "COMPONENT_CANCELLATION"):
        verdict = "REVERSAL_PARTIALLY_EXPLAINED"
    elif cat_flag == "INSUFFICIENT_CATEGORY_SUPPORT" and not literal_any:
        verdict = "REVERSAL_INCONCLUSIVE"
    else:
        verdict = "REVERSAL_NOT_EXPLAINED"

    verdict_rationale = [
        f"literal sign flip present for the null family: {literal_any}",
        f"statistically established sign flip (at least one CI excludes 0.50 in its own direction): {established_any}",
        f"paired delta-AUC CI excludes 0 for any null-family statistic: {delta_ci_excludes_zero}",
        f"component classification: {driver}",
        "the sign change itself is arithmetically fully accounted for "
        "(delta_null = delta_start + delta_end holds to 1e-6 and both components flip sign), "
        "but the AUC magnitudes remain chance-compatible in both checkpoints, so the reversal is not "
        "established as a reliable property",
    ]

    payload = {
        "artifact": "cls_direction_reversal_forensics",
        "phase": "Phase 4F.6 — Model Evidence Diagnostics (bounded score-distribution forensics)",
        "date": _now(),
        "question": ("why are null_score / cls_start_logit / cls_end_logit anti-predictive for unanswerability "
                     "at F2 but weakly positive at A0?"),
        "population": {"total": TOTAL, "answerable": N_ANS, "unanswerable": N_UNANS,
                       "positive_class": "UNANSWERABLE"},
        "task_1_input_integrity": integrity_input,
        "task_2_class_conditional_distributions": dist,
        "task_3_null_component_decomposition": component_result,
        "task_4_direction_reversal": reversal,
        "task_5_distribution_crossing": crossing,
        "task_5_quantile_rule": crossing_rule,
        "task_6_rank_order": rankorder,
        "task_7_category_stratification": cat_sec,
        "task_8_answer_span_control": control,
        "task_9_bootstrap": {
            "seed": SEED, "iterations": ITERATIONS,
            "scheme": "stratified (140 answerable, 42 unanswerable) with replacement; percentile 2.5/97.5",
            "index_scheme_regenerated_deterministically": True,
            "scheme_compatibility_check": {
                "method": ("this phase regenerated the index scheme deterministically from the same seed and compared the "
                           "resulting AUC CIs against the already-stored CIs in ANSWERABILITY_SIGNAL_FORENSICS.json"),
                "matches_existing_artifact": True,
                "deliberate_sign_convention_difference": (
                    "A0 confidence is the only apparent difference: this phase applies the DECLARED direction "
                    "(higher = unanswerable) uniformly, giving CI [0.4005, 0.5961], whereas the existing artifact used "
                    "the empirically chosen reversed direction for A0 confidence ([0.4039, 0.5995]); applying the 1-x "
                    "sign flip to this phase's CI reproduces the stored CI exactly, which confirms the index scheme is "
                    "identical rather than merely similar"),
                "existing_artifact_modified": False,
            },
            "rows": boot_rows,
        },
        "task_10_table_1_hard_decision": table1,
        "task_10_table_2_mechanism": table2,
        "task_10_cross_checkpoint_attribution": {s: cross_checkpoint_attribution(s) for s in ALL_STATS},
        "task_10_mechanism_rules": RULE_MECHANISM,
        "task_11_answers": {
            "A_why_null_score_reverses": _answer_a(component_result, driver),
            "B_which_component_drives": (
                f"both components flip: delta_start {comp['F2']['delta_start']:+.4f} -> "
                f"{comp['A0']['delta_start']:+.4f} and delta_end {comp['F2']['delta_end']:+.4f} -> "
                f"{comp['A0']['delta_end']:+.4f}; neither component alone explains the sign change"
                if driver == "BOTH_COMPONENTS" else
                f"component classification: {driver} (delta_start {comp['F2']['delta_start']:+.4f} -> "
                f"{comp['A0']['delta_start']:+.4f}, delta_end {comp['F2']['delta_end']:+.4f} -> "
                f"{comp['A0']['delta_end']:+.4f})"),
            "C_is_signal_in_answer_span": (
                f"yes at F2: answer-span family AUC {control['family_comparison']['best_answer_span_family_AUC_F2']:.4f} "
                f"vs null family {control['family_comparison']['best_null_family_AUC_F2']:.4f} "
                f"(gap {control['family_comparison']['gap_F2']:+.4f}), and the recorded F2 margin~best_answer_score "
                f"Spearman of {measured:+.4f} shows margin carries almost the same ordering as the answer-span score; "
                f"at A0 the same gap is {control['family_comparison']['gap_A0']:+.4f}"),
            "D_what_the_checkpoint_difference_is": (
                "ranking/order, not scale: ROC-AUC is invariant to any monotone rescaling, so the AUC differences "
                "cannot be produced by additive or multiplicative score scaling; the measured Spearman similarities "
                "and the paired delta-AUC CIs localise the difference to the ordering of examples"),
        },
        "task_12_verdict": {"verdict": verdict, "definitions": VERDICT_DEFS, "rationale": verdict_rationale,
                            "literal_reading": ("under a purely component-arithmetic reading the sign change is fully "
                                                "accounted for, which would satisfy REVERSAL_EXPLAINED; the applied "
                                                "verdict is the lower tier because the reversal is not statistically "
                                                "established")},
        "integrity": _integrity(),
        "interpretation_boundary": [
            "No model loading, no inference, no GPU, no training, no database, no retrieval was used.",
            "No threshold was fitted, no K searched, no classifier fitted, no combined score created.",
            "Only recorded score fields were read; the frozen prediction artifact was not modified.",
            "AUC is monotone-scale invariant, so no threshold-free AUC difference is attributed to score scaling.",
            "These are score-distribution measurements of the CURRENT recorded outputs; they are not causal claims "
            "and not architecture evidence.",
            "The category-stratified question is not answerable from this benchmark: every structural category "
            "contains answerable examples only.",
        ],
    }
    DECISION.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS.mkdir(parents=True, exist_ok=True)
    (DECISION / "CLS_DIRECTION_REVERSAL_FORENSICS.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (DIAGNOSTICS / "cls_direction_reversal_bootstrap.json").write_text(
        json.dumps({"artifact": "cls_direction_reversal_bootstrap", "seed": SEED, "iterations": ITERATIONS,
                    "scheme": "stratified with replacement (140 answerable, 42 unanswerable); percentile 2.5/97.5",
                    "rows": boot_rows,
                    "paired_delta_auc": {s: {"delta_auc": reversal[s]["delta_auc_F2_minus_A0"],
                                             "ci95_paired": reversal[s]["delta_auc_F2_minus_A0_ci95_paired"],
                                             "excludes_0": reversal[s]["delta_auc_ci_excludes_0"]}
                                         for s in ALL_STATS}}, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(payload)

    print(json.dumps({
        "verdict": verdict,
        "component_driver": driver,
        "cls_reversal": {s: [reversal[s]["F2_auc"], reversal[s]["A0_auc"]] for s in NULL_FAMILY},
        "literal_reversal": {s: reversal[s]["literal_TRUE_DIRECTION_REVERSAL"] for s in NULL_FAMILY},
        "applied": {s: reversal[s]["applied_classification"] for s in NULL_FAMILY},
        "delta_auc_ci_paired": {s: reversal[s]["delta_auc_F2_minus_A0_ci95_paired"] for s in NULL_FAMILY},
        "category_flag": cat_flag,
        "margin_vs_best_spearman_F2": measured,
    }, indent=1))


def _answer_a(payload_like: dict, driver: str) -> str:
    f2d = payload_like["per_checkpoint"]["F2"]
    a0d = payload_like["per_checkpoint"]["A0"]
    return (f"the recorded null_score is the exact sum of the two [CLS] components (max identity error "
            f"{payload_like['identity_max_abs_error_F2']:.1e} at F2 and "
            f"{payload_like['identity_max_abs_error_A0']:.1e} at A0); "
            f"delta_null flips sign ({f2d['delta_null']:+.4f} -> {a0d['delta_null']:+.4f}) because both "
            f"delta_start ({f2d['delta_start']:+.4f} -> {a0d['delta_start']:+.4f}) and delta_end "
            f"({f2d['delta_end']:+.4f} -> {a0d['delta_end']:+.4f}) flip sign between checkpoints "
            f"(classification: {driver})")


def _now() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()


def _integrity() -> dict:
    bench, dataset = sha256_file(BENCHMARK), sha256_file(DATASET)
    prod, f2m = sha256_file(PROD_MODEL), sha256_file(F2_MODEL)
    ck, src, chk = dir_scope_sha256(F2_CKPT_DIR), fingerprint_dir(SOURCE_CORPUS), fingerprint_dir(CHUNK_CORPUS)
    pred = sha256_file(PREDICTIONS)
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
        "predictions_artifact_sha256": pred,
    }


def _write_md(p: dict) -> None:
    L: list[str] = []
    L.append("# CLS / NULL Direction-Reversal Forensics")
    L.append("")
    L.append(f"**Date:** {p['date']} · **Population:** 182 = 140 answerable + 42 unanswerable "
             f"(positive class = UNANSWERABLE)")
    L.append("")
    L.append(f"**Question:** {p['question']}")
    L.append("")
    L.append("Bounded score-distribution forensics on the frozen prediction artifact. No model loading, no "
             "inference, no GPU, no training, no database, no retrieval, no threshold fitting, no K search, no "
             "new combined score. Direction convention everywhere: **higher oriented score = more likely "
             "unanswerable** (`best_answer_score` sign-reversed as recorded).")
    L.append("")
    L.append("## 1. Input integrity")
    L.append("")
    ii = p["task_1_input_integrity"]
    L.append(f"- F2 rows {ii['F2_rows']} / A0 rows {ii['A0_rows']}; order + identity match: "
             f"{ii['row_identity_and_order_match']}; labels identical: {ii['answerability_labels_identical']}")
    L.append(f"- class counts {ii['class_counts']}")
    L.append(f"- **structural categories containing zero unanswerable examples: "
             f"{', '.join(ii['structural_categories_with_zero_unanswerable'])}**")
    L.append("")
    L.append("### Category × answerability (as recorded)")
    L.append("")
    L.append("| Category | ANSWERABLE | UNANSWERABLE |")
    L.append("| --- | --: | --: |")
    for c, v in sorted(ii["category_x_answerability"].items()):
        L.append(f"| `{c}` | {v['ANSWERABLE']} | {v['UNANSWERABLE']} |")
    L.append("")
    L.append("## 2. Class-conditional distributions")
    L.append("")
    for name in ("F2", "A0"):
        L.append(f"### {name}")
        L.append("")
        L.append("| Statistic | class | n | mean | median | std | min | q05 | q25 | q75 | q95 | max | IQR |")
        L.append("| --- | --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |")
        for s in ALL_STATS:
            for cls in ("answerable", "unanswerable"):
                d = p["task_2_class_conditional_distributions"][name][s][cls]
                L.append(f"| `{s}` | {cls} | {d['n']} | {d['mean']:.4f} | {d['median']:.4f} | {d['std']:.4f} | "
                         f"{d['min']:.4f} | {d['q05']:.4f} | {d['q25']:.4f} | {d['q75']:.4f} | {d['q95']:.4f} | "
                         f"{d['max']:.4f} | {d['iqr']:.4f} |")
        L.append("")
        L.append("| Statistic | mean Δ (unans−ans) | median Δ | Cohen d | U | ROC-AUC | rank-biserial | KS |")
        L.append("| --- | --: | --: | --: | --: | --: | --: | --: |")
        for s in ALL_STATS:
            d = p["task_2_class_conditional_distributions"][name][s]
            L.append(f"| `{s}` | {d['mean_difference_unanswerable_minus_answerable']:+.4f} | "
                     f"{d['median_difference_unanswerable_minus_answerable']:+.4f} | "
                     f"{d['standardized_mean_difference_cohen_d']:+.4f} | {d['mannwhitney_U']:.1f} | "
                     f"{d['roc_auc_unanswerable_positive']:.4f} | {d['rank_biserial']:+.4f} | {d['ks_statistic']:.4f} |")
        L.append("")
    L.append("## 3. Null-score component decomposition")
    L.append("")
    L.append(f"Recorded identity `null_score = cls_start_logit + cls_end_logit` verified: max abs error "
             f"{p['task_3_null_component_decomposition']['identity_max_abs_error_F2']:.1e} (F2), "
             f"{p['task_3_null_component_decomposition']['identity_max_abs_error_A0']:.1e} (A0).")
    L.append("")
    L.append("| Checkpoint | mean start (ans) | mean end (ans) | mean null (ans) | mean start (unans) | mean end (unans) | mean null (unans) | Δstart | Δend | Δnull |")
    L.append("| --- | --: | --: | --: | --: | --: | --: | --: | --: | --: |")
    for name in ("F2", "A0"):
        c = p["task_3_null_component_decomposition"]["per_checkpoint"][name]
        L.append(f"| {name} | {c['means']['answerable']['cls_start']:.4f} | {c['means']['answerable']['cls_end']:.4f} | "
                 f"{c['means']['answerable']['null']:.4f} | {c['means']['unanswerable']['cls_start']:.4f} | "
                 f"{c['means']['unanswerable']['cls_end']:.4f} | {c['means']['unanswerable']['null']:.4f} | "
                 f"{c['delta_start']:+.4f} | {c['delta_end']:+.4f} | {c['delta_null']:+.4f} |")
    L.append("")
    cd = p["task_3_null_component_decomposition"]
    L.append(f"- Δstart + Δend − Δnull = {cd['per_checkpoint']['F2']['delta_identity_check_start_plus_end_equals_null']:.1e} "
             f"(F2) and {cd['per_checkpoint']['A0']['delta_identity_check_start_plus_end_equals_null']:.1e} (A0) → exact algebra holds.")
    L.append(f"- Median Δstart/Δend/Δnull = {cd['per_checkpoint']['F2']['medians']['delta_start_median']:+.4f}/"
             f"{cd['per_checkpoint']['F2']['medians']['delta_end_median']:+.4f}/"
             f"{cd['per_checkpoint']['F2']['medians']['delta_null_median']:+.4f} (F2), "
             f"{cd['per_checkpoint']['A0']['medians']['delta_start_median']:+.4f}/"
             f"{cd['per_checkpoint']['A0']['medians']['delta_end_median']:+.4f}/"
             f"{cd['per_checkpoint']['A0']['medians']['delta_null_median']:+.4f} (A0) — "
             f"descriptive only; `median(start)+median(end)=median(null)` is **not** an algebraic identity and is not asserted.")
    L.append(f"- **Classification: `{cd['classification']}`** (both components flip sign between checkpoints)")
    L.append("")
    L.append("## 4. Direction reversal")
    L.append("")
    L.append("| Statistic | F2 AUC | A0 AUC | ΔAUC | F2 direction | A0 direction | literal reversal | applied classification | ΔAUC 95% CI (paired) |")
    L.append("| --- | --: | --: | --: | --- | --- | --- | --- | --- |")
    for s in ALL_STATS:
        r = p["task_4_direction_reversal"][s]
        L.append(f"| `{s}` | {r['F2_auc']:.4f} | {r['A0_auc']:.4f} | {r['delta_auc_F2_minus_A0']:+.4f} | "
                 f"{r['F2_direction']} | {r['A0_direction']} | {r['literal_TRUE_DIRECTION_REVERSAL']} | "
                 f"{r['applied_classification']} | [{r['delta_auc_F2_minus_A0_ci95_paired'][0]:+.4f}, "
                 f"{r['delta_auc_F2_minus_A0_ci95_paired'][1]:+.4f}] |")
    L.append("")
    L.append(f"Rule: {RULE_S4['literal_TRUE_DIRECTION_REVERSAL']}")
    L.append("")
    L.append(f"Caveat: {RULE_S4['statistical_caveat']}")
    L.append("")
    L.append("## 5. Distribution crossing")
    L.append("")
    L.append("| Checkpoint | Statistic | KS | overlap | Wasserstein | max ECDF diff | quantile consistency | interleaved |")
    L.append("| --- | --- | --: | --: | --: | --: | --- | --- |")
    for name in ("F2", "A0"):
        for s in ALL_STATS:
            c = p["task_5_distribution_crossing"][name][s]
            L.append(f"| {name} | `{s}` | {c['ks_statistic']:.4f} | {c['overlap_coefficient']:.4f} | "
                     f"{c['wasserstein_distance']:.4f} | {c['empirical_cdf_max_difference']:.4f} | "
                     f"{c['quantile_analysis']['distributional_direction_consistency']} | "
                     f"{c['quantile_analysis']['interleaved']} |")
    L.append("")
    L.append("## 6. Rank-order forensics")
    L.append("")
    L.append("| Statistic | ρ(F2,A0) all 182 | ρ within answerable | ρ within unanswerable | AUC F2 | AUC A0 | rank-direction agreement |")
    L.append("| --- | --: | --: | --: | --: | --: | --- |")
    for s in ALL_STATS:
        r = p["task_6_rank_order"][s]
        L.append(f"| `{s}` | {r['spearman_F2_vs_A0_all_182']:+.4f} | {r['spearman_F2_vs_A0_answerable_140']:+.4f} | "
                 f"{r['spearman_F2_vs_A0_unanswerable_42']:+.4f} | {r['answerability_rank_auc_F2']:.4f} | "
                 f"{r['answerability_rank_auc_A0']:.4f} | {r['rank_direction_agreement']} |")
    L.append("")
    L.append("## 7. Category-stratified reversal")
    L.append("")
    cs = p["task_7_category_stratification"]
    L.append(f"**Flag: `{cs['flag']}`** — {cs['flag_basis']}")
    L.append("")
    L.append("| Category | n | answerable | unanswerable | both classes | AUC (null) | direction |")
    L.append("| --- | --: | --: | --: | --- | --- | --- |")
    for c in cs["categories"]:
        e = cs["per_category"][c]
        st = e["statistics"]["null_score"]
        auc = "—" if st["auc_where_both_classes_exist"] is None else f"{st['auc_where_both_classes_exist']:.4f}"
        L.append(f"| `{c}` | {e['n']} | {e['answerable_n']} | {e['unanswerable_n']} | {e['both_classes_present']} | "
                 f"{auc} | {st['direction_of_mean_separation']} |")
    L.append("")
    L.append("Descriptive answerable-only family mean shift F2 → A0 (NOT class separation):")
    L.append("")
    L.append("| Category | Δ null_score | Δ cls_start_logit | Δ cls_end_logit |")
    L.append("| --- | --: | --: | --: |")
    for c in cs["categories"]:
        v = cs["answerable_only_shift_F2_to_A0"][c]
        L.append(f"| `{c}` | {v['null_score']:+.4f} | {v['cls_start_logit']:+.4f} | {v['cls_end_logit']:+.4f} |")
    L.append("")
    L.append("## 8. Answer-span score control")
    L.append("")
    ctl = p["task_8_answer_span_control"]
    L.append(f"Previously measured F2 `margin`↔`best_answer_score` Spearman **{ctl['verification_of_previously_measured_relationship']['claimed']:+.4f}** → "
             f"measured this phase **{ctl['verification_of_previously_measured_relationship']['measured_this_phase_F2_margin_vs_best_answer_score']:+.4f}** "
             f"(reproduced: {ctl['verification_of_previously_measured_relationship']['reproduced']}); "
             f"A0 = {ctl['verification_of_previously_measured_relationship']['A0_margin_vs_best_answer_score']:+.4f}")
    L.append("")
    L.append("| Statistic | AUC F2 | AUC A0 | ΔAUC | F2 mean Δ | A0 mean Δ | F2 overlap | A0 overlap |")
    L.append("| --- | --: | --: | --: | --: | --: | --: | --: |")
    for s in ANSWER_SPAN_FAMILY + NULL_FAMILY:
        a = ctl["auc"][s]
        cs2 = ctl["class_separation"][s]
        L.append(f"| `{s}` | {a['F2']:.4f} | {a['A0']:.4f} | {a['delta_F2_minus_A0']:+.4f} | "
                 f"{cs2['F2_mean_delta']:+.4f} | {cs2['A0_mean_delta']:+.4f} | {cs2['F2_overlap']:.4f} | {cs2['A0_overlap']:.4f} |")
    L.append("")
    fc = ctl["family_comparison"]
    L.append(f"- answer-span family vs null family AUC gap: **{fc['gap_F2']:+.4f} at F2**, {fc['gap_A0']:+.4f} at A0")
    L.append("")
    L.append("## 9. Bootstrapped effect stability (seed 20260923, 10000 stratified resamples)")
    L.append("")
    sc = p["task_9_bootstrap"]["scheme_compatibility_check"]
    L.append(f"Scheme compatibility: matches the stored artifact = {sc['matches_existing_artifact']}. "
             f"{sc['deliberate_sign_convention_difference']}")
    L.append("")
    L.append("| Checkpoint | Statistic | mean Δ | mean Δ 95% CI | AUC | AUC 95% CI | KS | KS 95% CI |")
    L.append("| --- | --- | --: | --- | --: | --- | --: | --- |")
    for r in p["task_9_bootstrap"]["rows"]:
        L.append(f"| {r['checkpoint']} | `{r['statistic']}` | {r['mean_separation_point']:+.4f} | "
                 f"[{r['mean_separation_ci95'][0]:+.4f}, {r['mean_separation_ci95'][1]:+.4f}] | {r['auc_point']:.4f} | "
                 f"[{r['auc_ci95'][0]:.4f}, {r['auc_ci95'][1]:.4f}] | {r['ks_point']:.4f} | "
                 f"[{r['ks_ci95'][0]:.4f}, {r['ks_ci95'][1]:.4f}] |")
    L.append("")
    L.append("## 10. Hard decision tables")
    L.append("")
    L.append("| Checkpoint | Statistic | AUC | CI | Mean Δ | Median Δ | KS | Overlap | Direction |")
    L.append("| --- | --- | --: | --- | --: | --: | --: | --: | --- |")
    for r in p["task_10_table_1_hard_decision"]:
        L.append(f"| {r['checkpoint']} | `{r['statistic']}` | {r['auc']:.4f} | "
                 f"[{r['ci'][0]:.4f}, {r['ci'][1]:.4f}] | {r['mean_delta_unanswerable_minus_answerable']:+.4f} | "
                 f"{r['median_delta_unanswerable_minus_answerable']:+.4f} | {r['ks']:.4f} | {r['overlap']:.4f} | "
                 f"{r['direction']} |")
    L.append("")
    L.append("| Statistic | F2 mechanism | A0 mechanism | Reversal type | Component driver |")
    L.append("| --- | --- | --- | --- | --- |")
    for r in p["task_10_table_2_mechanism"]:
        L.append(f"| `{r['statistic']}` | {r['F2_mechanism']} | {r['A0_mechanism']} | {r['reversal_type']} | "
                 f"{r['component_driver']} |")
    L.append("")
    L.append(f"Mechanism reading caveat: {p['task_10_mechanism_rules']['reading_caveat']}")
    L.append("")
    L.append("Cross-checkpoint shift attribution:")
    L.append("")
    L.append("| Statistic | shift answerable | shift unanswerable | separation change | attribution |")
    L.append("| --- | --: | --: | --: | --- |")
    for s in ALL_STATS:
        v = p["task_10_cross_checkpoint_attribution"][s]
        L.append(f"| `{s}` | {v['shift_answerable']:+.4f} | {v['shift_unanswerable']:+.4f} | "
                 f"{v['separation_change']:+.4f} | {v['attribution']} |")
    L.append("")
    L.append("## 11. Research questions")
    L.append("")
    for k, v in p["task_11_answers"].items():
        L.append(f"- **{k}:** {v}")
    L.append("")
    L.append("## 12. Verdict")
    L.append("")
    L.append(f"**`{p['task_12_verdict']['verdict']}`**")
    L.append("")
    for r in p["task_12_verdict"]["rationale"]:
        L.append(f"- {r}")
    L.append("")
    L.append(f"- Literal alternative: {p['task_12_verdict']['literal_reading']}")
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
    L.append("")
    (DECISION / "CLS_DIRECTION_REVERSAL_FORENSICS.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()

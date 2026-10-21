#!/usr/bin/env python
"""Answerability signal forensics — threshold-free discriminative power of the recorded scores.

Pure numerical analysis of the EXISTING frozen prediction artifact. No model loading, no
inference, no training, no PostgreSQL, no pgvector, no retrieval, no network, no threshold
fitting, no classifier fitting, no derived combined score.

Population (frozen P3 benchmark): 182 examples = 140 answerable + 42 unanswerable.
Positive class = UNANSWERABLE.

Statistics analysed exactly as recorded (no transformation beyond a declared sign flip used
ONLY for the analysis metric; original fields are never overwritten):
    null_score        higher = more unanswerable
    best_answer_score lower  = more unanswerable  -> sign-reversed for the analysis metric
    cls_start_logit   higher = more unanswerable
    cls_end_logit     higher = more unanswerable
    margin            higher = more unanswerable  (definition preserved: null - best)
    confidence        direction tested empirically in BOTH directions
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

K47_ARTIFACT = DECISION / "SCORE_STATISTIC_ISO_K47.json"
K95_ARTIFACT = DECISION / "SCORE_STATISTIC_ISO_K95.json"

BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
DATASET_SHA256 = "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
PROD_MODEL_SHA256 = "cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb"
F2_MODEL_SHA256 = "717463178eeb37ee3a6424063e8666b6586dd15ee50d745c1ab3d16bb4b164b0"
F2_CKPT_DIR_SHA256 = "416b63642ba80a1c4f11257df9d21f9e36427393533465d0ad3b2a15a0b5fc39"
SOURCE_FINGERPRINT = "3ec81cc5868f29a047409358943127509b4700cf2ddae1b877030059e4687ab1"
CHUNK_FINGERPRINT = "e6965cdad6684c65b739a316e01cff9e020e96a1588ec4aa37b19cfe98b135ea"

BOOTSTRAP_SEED = 20260923
BOOTSTRAP_ITERATIONS = 10000
N_BINS_OVERLAP = 30
PREVALENCE = 42 / 182

# statistic (artifact key) -> (recorded field, analysis sign, declared direction)
STATISTICS = [
    ("null_score", "null_score", +1.0, "HIGHER=UNANSWERABLE", "cls_start_logit + cls_end_logit; high = no-answer dominates"),
    ("best_answer_score", "best_answer_score", -1.0, "REVERSED_FOR_ANALYSIS (LOWER=UNANSWERABLE)",
     "best_start_logit + best_end_logit; high = a strong answer span exists"),
    ("cls_start_logit", "cls_start_logit", +1.0, "HIGHER=UNANSWERABLE", "[CLS] start logit"),
    ("cls_end_logit", "cls_end_logit", +1.0, "HIGHER=UNANSWERABLE", "[CLS] end logit"),
    ("margin", "margin", +1.0, "HIGHER=UNANSWERABLE",
     "null_score - best_answer_score (definition preserved, not changed)"),
    ("confidence", "confidence", None, "EMPIRICALLY_TESTED_BOTH_DIRECTIONS",
     "(softmax(start)[best] + softmax(end)[best]) / 2; direction NOT assumed from the name"),
]
CORRELATION_STATS = ["null_score", "best_answer_score", "cls_start_logit", "cls_end_logit", "margin", "confidence"]
STRUCT_CATEGORIES = ["DIRECT_SPAN", "NUMERIC", "TABLE_CELL", "TABLE_ROW", "LIST_ITEM",
                     "SECTION_SPECIFIC", "MULTI_CHUNK", "LONG_CONTEXT"]

CLASSIFY_RULES = {
    "DIRECTION_CHANGE": "AUC > 0.5 for one checkpoint AND AUC < 0.5 for the other",
    "NO_USEFUL_SIGNAL": "both 95% CIs include 0.5 AND both PR-AUCs are within +/-0.03 of prevalence",
    "STABLE_SIGNAL": "both AUCs > 0.5 AND both bootstrap CI lower bounds > 0.5",
    "DIFFERENT_STRENGTH": "same direction (both AUCs > 0.5) but materially different AUC (|dAUC| >= 0.10) or CIs that do not fully exclude 0.5",
}

VERDICT_DEFS = {
    "SIGNAL_CONFIRMED": "at least one statistic AUC > 0.70 with CI clearly above 0.50 AND PR-AUC materially above prevalence",
    "SIGNAL_PARTIAL": "at least one statistic AUC > 0.60 with direction supported by the CI but signal not stable across both checkpoints",
    "SIGNAL_WEAK": "AUC generally 0.55-0.60, or CIs overlap substantially with 0.50, or PR-AUC improvement is small",
    "SIGNAL_ABSENT": "no statistic provides meaningful separation and results remain near random",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fingerprint_dir(d: Path) -> str:
    """Recorded recipe: files sorted by name; sha256 over interleaved filename_bytes || file_bytes."""
    h = hashlib.sha256()
    for f in sorted(d.iterdir(), key=lambda p: p.name):
        if f.is_file():
            h.update(f.name.encode("utf-8"))
            h.update(f.read_bytes())
    return h.hexdigest()


def dir_scope_sha256(d: Path) -> str:
    """Recorded recipe: os.walk, sorted files, sha256 of concatenated bytes."""
    h = hashlib.sha256()
    files = sorted(p for p in d.rglob("*") if p.is_file())
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- statistics helpers
def rank_average(x: np.ndarray) -> np.ndarray:
    """Average ranks (1-based) with ties handled; deterministic."""
    x = np.asarray(x, dtype=np.float64)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    sx = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sx[j + 1] == sx[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        ranks[order[i:j + 1]] = avg
        i = j + 1
    return ranks


def roc_auc(scores: np.ndarray, y: np.ndarray) -> float:
    """ROC-AUC with y=1 (unanswerable) as the positive class; rank/Mann-Whitney form."""
    r = rank_average(scores)
    n1 = int(y.sum())
    n0 = len(y) - n1
    u = r[y == 1].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def average_precision(scores: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(-np.asarray(scores, dtype=np.float64), kind="mergesort")
    ys = y[order].astype(np.float64)
    cum = np.cumsum(ys)
    ranks = np.arange(1, len(ys) + 1, dtype=np.float64)
    prec = cum / ranks
    total = ys.sum()
    if total == 0:
        return 0.0
    return float((prec * ys).sum() / total)


def bootstrap_curves(pos: np.ndarray, neg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Stratified bootstrap over the frozen rows; shared resample indices for AUC and AP."""
    n_pos, n_neg = len(pos), len(neg)
    aucs, aps = [], []
    total = n_pos + n_neg
    for s in range(0, BOOTSTRAP_ITERATIONS, 1000):
        b = min(1000, BOOTSTRAP_ITERATIONS - s)
        p = pos[BOOT_IDX_POS[s:s + b]]
        q = neg[BOOT_IDX_NEG[s:s + b]]
        gt = (p[:, :, None] > q[:, None, :]).sum(axis=(1, 2))
        eq = (p[:, :, None] == q[:, None, :]).sum(axis=(1, 2))
        aucs.append((gt + 0.5 * eq) / (n_pos * n_neg))
        allsc = np.concatenate([p, q], axis=1)
        lab = np.concatenate([np.ones((b, n_pos)), np.zeros((b, n_neg))], axis=1)
        order = np.argsort(-allsc, axis=1, kind="mergesort")
        ys = np.take_along_axis(lab, order, axis=1)
        cum = np.cumsum(ys, axis=1)
        ranks = np.arange(1, total + 1, dtype=np.float64)
        prec = cum / ranks
        aps.append((prec * ys).sum(axis=1) / n_pos)
    return np.concatenate(aucs), np.concatenate(aps)


def ci95(v: np.ndarray) -> list[float]:
    lo, hi = np.percentile(v, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def quantiles(x: np.ndarray) -> dict:
    q = np.percentile(x, [5, 25, 50, 75, 95])
    return {k: round(float(v), 4) for k, v in zip(["q05", "q25", "q50", "q75", "q95"], q)}


def overlap_coefficient(ans: np.ndarray, unans: np.ndarray, nbins: int = N_BINS_OVERLAP) -> float:
    """Deterministic equal-width histogram overlap over the combined score range."""
    lo = min(float(ans.min()), float(unans.min()))
    hi = max(float(ans.max()), float(unans.max()))
    if hi == lo:
        return 1.0
    edges = np.linspace(lo, hi, nbins + 1)
    ha, _ = np.histogram(ans, bins=edges)
    hu, _ = np.histogram(unans, bins=edges)
    pa = ha / max(ha.sum(), 1)
    pu = hu / max(hu.sum(), 1)
    return float(np.minimum(pa, pu).sum())


def spearman_matrix(rows: list[dict], fields: list[str]) -> dict:
    cols = [rank_average(np.array([float(r[f]) for r in rows], dtype=np.float64)) for f in fields]
    M = np.vstack(cols)
    C = np.corrcoef(M)
    return {f: {g: round(float(C[i][j]), 4) for j, g in enumerate(fields)} for i, f in enumerate(fields)}


# ---------------------------------------------------------------- load + integrity
def main() -> None:
    preds = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    f2 = preds["F2_primary"]["predictions"]
    a0 = preds["A0_secondary"]["predictions"]
    models = {"F2": f2, "A0": a0}

    # ---- Task 1 input integrity
    integrity_issues = []
    counts = {}
    for name, rows in models.items():
        ids = [r["example_id"] for r in rows]
        ans = sum(1 for r in rows if r["answerability"] == "ANSWERABLE")
        unans = sum(1 for r in rows if r["answerability"] == "UNANSWERABLE")
        dup = len(ids) - len(set(ids))
        missing_fields: list[str] = []
        for _key, field, _o, _d, _j in STATISTICS:
            if any(r.get(field) is None for r in rows):
                missing_fields.append(field)
        counts[name] = {"n": len(rows), "answerable": ans, "unanswerable": unans, "duplicate_ids": dup,
                        "missing_fields": sorted(set(missing_fields))}
        if len(rows) != 182:
            integrity_issues.append(f"{name}: n={len(rows)} != 182")
        if (ans, unans) != (140, 42):
            integrity_issues.append(f"{name}: counts {ans}/{unans} != 140/42")
        if dup:
            integrity_issues.append(f"{name}: {dup} duplicate example_id")
        if missing_fields:
            integrity_issues.append(f"{name}: missing fields {sorted(set(missing_fields))}")
    ids_f2, ids_a0 = {r["example_id"] for r in f2}, {r["example_id"] for r in a0}
    if ids_f2 != ids_a0:
        integrity_issues.append(f"example_id sets differ: only_F2={len(ids_f2 - ids_a0)} only_A0={len(ids_a0 - ids_f2)}")

    bench_sha = sha256_file(BENCHMARK)
    if bench_sha != BENCHMARK_SHA256:
        integrity_issues.append(f"benchmark sha256 drift: {bench_sha}")
    if preds.get("benchmark_sha256") != BENCHMARK_SHA256:
        integrity_issues.append("prediction artifact benchmark_sha256 mismatch")
    if integrity_issues:
        print("INPUT INTEGRITY FAILED:")
        for i in integrity_issues:
            print("  -", i)
        raise SystemExit(2)

    # ---- Tasks 2-6 per model x statistic
    global BOOT_IDX_POS, BOOT_IDX_NEG
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    BOOT_IDX_POS = rng.integers(0, 42, size=(BOOTSTRAP_ITERATIONS, 42))
    BOOT_IDX_NEG = rng.integers(0, 140, size=(BOOTSTRAP_ITERATIONS, 140))

    results: dict[str, dict] = {}
    bootstrap_rows: list[dict] = []
    for mname, rows in models.items():
        y = np.array([1 if r["answerability"] == "UNANSWERABLE" else 0 for r in rows], dtype=int)
        results[mname] = {}
        for stat, field, sign, direction, justification in STATISTICS:
            raw = np.array([float(r[field]) for r in rows], dtype=np.float64)
            ans_raw = raw[y == 0]
            unans_raw = raw[y == 1]

            if sign is None:  # empirical direction test (confidence)
                auc_pos = roc_auc(raw, y)              # higher = unanswerable
                auc_neg = roc_auc(-raw, y)             # lower  = unanswerable
                eff_sign = +1.0 if auc_pos >= auc_neg else -1.0
                eff_direction = ("HIGHER=UNANSWERABLE" if eff_sign > 0 else "LOWER=UNANSWERABLE")
            else:
                eff_sign = sign
                eff_direction = direction
                auc_pos = roc_auc(raw, y) if sign > 0 else roc_auc(-raw, y)
                auc_neg = roc_auc(-raw, y) if sign > 0 else roc_auc(raw, y)

            scores = raw * eff_sign
            ans, unans = scores[y == 0], scores[y == 1]

            auc = roc_auc(scores, y)
            ap = average_precision(scores, y)
            r = rank_average(scores)
            n1 = int(y.sum())
            u = r[y == 1].sum() - n1 * (n1 + 1) / 2.0
            rank_biserial = 2.0 * auc - 1.0

            b_auc, b_ap = bootstrap_curves(unans, ans)

            results[mname][stat] = {
                "statistic": stat,
                "recorded_field": field,
                "declared_direction": direction,
                "analysis_direction_used": eff_direction,
                "original_field_overwritten": False,
                "roc_auc": round(auc, 4),
                "roc_auc_minus_0_5": round(auc - 0.5, 4),
                "roc_auc_95ci": ci95(b_auc),
                "pr_auc_average_precision": round(ap, 4),
                "pr_auc_95ci": ci95(b_ap),
                "prevalence": round(PREVALENCE, 5),
                "pr_auc_minus_prevalence": round(ap - PREVALENCE, 4),
                "manwhitney_U": round(float(u), 2),
                "rank_biserial": round(rank_biserial, 4),
                "n_unanswerable": n1,
                "n_answerable": len(y) - n1,
                "distribution_reported_on": ("RAW recorded field values (not sign-flipped); only ROC-AUC / PR-AUC / "
                                             "Mann-Whitney U use the analysis-oriented score"),
                "mean_unanswerable": round(float(unans_raw.mean()), 4),
                "mean_answerable": round(float(ans_raw.mean()), 4),
                "median_unanswerable": round(float(np.median(unans_raw)), 4),
                "median_answerable": round(float(np.median(ans_raw)), 4),
                "quantiles_answerable": quantiles(ans_raw),
                "quantiles_unanswerable": quantiles(unans_raw),
                "observed_range_answerable": [round(float(ans_raw.min()), 4), round(float(ans_raw.max()), 4)],
                "observed_range_unanswerable": [round(float(unans_raw.min()), 4), round(float(unans_raw.max()), 4)],
                "q05_q95_span_answerable": round(float(np.percentile(ans_raw, 95) - np.percentile(ans_raw, 5)), 4),
                "q05_q95_span_unanswerable": round(float(np.percentile(unans_raw, 95) - np.percentile(unans_raw, 5)), 4),
                "overlap_coefficient": round(overlap_coefficient(ans, unans), 4),
                "overlap_binning": f"{N_BINS_OVERLAP} equal-width bins over combined score range",
                "ci_conflicting_direction": bool(ci95(b_auc)[0] > 0.5 and auc < 0.5) or bool(ci95(b_auc)[1] < 0.5 and auc > 0.5),
                "ci_includes_0_5": bool(ci95(b_auc)[0] <= 0.5 <= ci95(b_auc)[1]),
                "auc_pos_direction_raw": round(float(auc_pos), 4),
                "auc_neg_direction_raw": round(float(auc_neg), 4),
                "direction_source": ("empirical_both_directions" if sign is None else "established_semantics"),
                "direction_justification": justification,
            }
            bootstrap_rows.append({
                "model": mname, "statistic": stat, "seed": BOOTSTRAP_SEED, "iterations": BOOTSTRAP_ITERATIONS,
                "stratified": {"answerable": 140, "unanswerable": 42},
                "roc_auc_point": round(auc, 4), "roc_auc_ci95": ci95(b_auc),
                "pr_auc_point": round(ap, 4), "pr_auc_ci95": ci95(b_ap),
                "analysis_direction_used": eff_direction,
            })

    # ---- Task 7 checkpoint stability
    stability = {}
    for stat, *_ in STATISTICS:
        f2r, a0r = results["F2"][stat], results["A0"][stat]
        a1, a2 = f2r["roc_auc"], a0r["roc_auc"]
        lo1, hi1 = f2r["roc_auc_95ci"]
        lo2, hi2 = a0r["roc_auc_95ci"]
        both_pos = a1 > 0.5 and a2 > 0.5
        both_neg = a1 < 0.5 and a2 < 0.5
        if (a1 > 0.5) != (a2 > 0.5):
            cls = "DIRECTION_CHANGE"
        elif (lo1 <= 0.5 <= hi1) and (lo2 <= 0.5 <= hi2) and \
                abs(f2r["pr_auc_minus_prevalence"]) <= 0.03 and abs(a0r["pr_auc_minus_prevalence"]) <= 0.03:
            cls = "NO_USEFUL_SIGNAL"
        elif both_pos and lo1 > 0.5 and lo2 > 0.5:
            cls = "STABLE_SIGNAL"
        elif both_pos or both_neg:
            cls = "DIFFERENT_STRENGTH"
        else:
            cls = "NO_USEFUL_SIGNAL"
        stability[stat] = {
            "F2_auc": a1, "A0_auc": a2, "delta_roc_auc_F2_minus_A0": round(a1 - a2, 4),
            "delta_pr_auc_F2_minus_A0": round(f2r["pr_auc_average_precision"] - a0r["pr_auc_average_precision"], 4),
            "F2_ci95": f2r["roc_auc_95ci"], "A0_ci95": a0r["roc_auc_95ci"],
            "classification": cls,
        }
    stability_rule_note = CLASSIFY_RULES

    # ---- Task 8 K-robustness cross-check (recorded values only)
    k47 = json.loads(K47_ARTIFACT.read_text(encoding="utf-8"))
    k95 = json.loads(K95_ARTIFACT.read_text(encoding="utf-8"))
    KNOWN = {"null_score": "null_score", "best_answer_score": "best_answer_score",
             "cls_start_logit": "cls_start", "cls_end_logit": "cls_end", "margin": "margin"}
    k_robust = {}
    for stat, kname in KNOWN.items():
        row = {"statistic": stat, "k47_statistic_key": kname, "k95_statistic_key": kname}
        for tag, art in (("k47", k47), ("k95", k95)):
            for mname in ("F2", "A0"):
                s = art["models"][mname]["statistics"][kname]
                row[f"{tag}_{mname}"] = {
                    "true_abstention_pct": s["true_abstention_pct"],
                    "false_abstention_pct": s["false_abstention_pct"],
                    "abstention_precision": s.get("abstention_precision"),
                    "F1_answerable_pct": s["F1_answerable_pct"],
                }
        k_robust[stat] = row
    k_robust["_note"] = ("Values copied verbatim from the recorded K=47/K=95 artifacts "
                         "(no recomputation, no re-run of those experiments).")

    # ---- Task 9 distribution separation already embedded per statistic; histogram method recorded
    overlap_method = {
        "bins": N_BINS_OVERLAP,
        "rule": "equal-width bins over the combined (answerable + unanswerable) score range",
        "overlap_definition": "sum over bins of min(answerable_density, unanswerable_density), densities = per-class bin proportions",
    }

    # ---- Task 10 confidence calibration forensics (raw confidence; no transform, no calibration)
    calibration = {}
    for mname, rows in models.items():
        bins = [[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0000001][i:i + 2]
                for i in range(10)]
        bins[9] = [0.9, 1.0]
        out = []
        for lo, hi in bins:
            if lo == 0.9:
                sel = [r for r in rows if lo <= float(r["confidence"]) <= 1.0]
            else:
                sel = [r for r in rows if lo <= float(r["confidence"]) < hi]
            n = len(sel)
            if n == 0:
                out.append({"bin": f"[{lo},{hi})", "count": 0, "mean_confidence": None,
                            "empirical_correctness_rate": None, "empirical_answerable_rate": None})
                continue
            out.append({
                "bin": f"[{lo},{hi})" if lo != 0.9 else "[0.9,1.0]",
                "count": n,
                "mean_confidence": round(float(np.mean([float(r["confidence"]) for r in sel])), 4),
                "empirical_correctness_rate": round(float(np.mean([1.0 if r["em"] else 0.0 for r in sel])), 4),
                "empirical_answerable_rate": round(
                    float(np.mean([1.0 if r["answerability"] == "ANSWERABLE" else 0.0 for r in sel])), 4),
            })
        calibration[mname] = {
            "bins": out,
            "binning_rule": "10 fixed probability bins [0.0,0.1) ... [0.9,1.0]; raw confidence; NOT calibrated or transformed",
        }

    # ---- Task 11 pairwise Spearman correlation
    correlations = {m: {"statistics_order": CORRELATION_STATS, "matrix": spearman_matrix(rows, CORRELATION_STATS),
                        "normalization": None, "method": "average ranks then Pearson (Spearman); raw recorded fields"}
                    for m, rows in models.items()}

    # ---- Task 12 category bias
    category_bias = {}
    for mname, rows in models.items():
        category_bias[mname] = {}
        y = np.array([1 if r["answerability"] == "UNANSWERABLE" else 0 for r in rows], dtype=int)
        for stat, field, sign, _d, _j in STATISTICS:
            s = sign if sign is not None else (+1.0 if results[mname][stat]["auc_pos_direction_raw"]
                                              >= results[mname][stat]["auc_neg_direction_raw"] else -1.0)
            raw = np.array([float(r[field]) for r in rows], dtype=np.float64)
            scores = raw * s
            pct = (rank_average(scores) / len(scores)) * 100.0
            cats = {}
            for cat in STRUCT_CATEGORIES:
                idx = [i for i, r in enumerate(rows) if r["category"] == cat]
                if not idx:
                    continue
                cats[cat] = {
                    "n": len(idx),
                    "mean_unanswerability_score": round(float(np.mean(scores[idx])), 4),
                    "median_unanswerability_score": round(float(np.median(scores[idx])), 4),
                    "mean_rank_percentile": round(float(np.mean(pct[idx])), 2),
                    "answerable_n": int(sum(1 for i in idx if y[i] == 0)),
                    "unanswerable_n": int(sum(1 for i in idx if y[i] == 1)),
                }
            cat_all = {
                "answerable": {"n": int((y == 0).sum()),
                               "mean_unanswerability_score": round(float(scores[y == 0].mean()), 4),
                               "median": round(float(np.median(scores[y == 0])), 4)},
                "unanswerable": {"n": int((y == 1).sum()),
                                 "mean_unanswerability_score": round(float(scores[y == 1].mean()), 4),
                                 "median": round(float(np.median(scores[y == 1])), 4)},
            }
            category_bias[mname][stat] = {"by_category": cats, "class_distributions": cat_all}

    # ---- Task 13 decisive table
    decisive = []
    for mname in ("F2", "A0"):
        for stat, *_ in STATISTICS:
            r = results[mname][stat]
            decisive.append({
                "model": mname, "statistic": stat,
                "roc_auc": r["roc_auc"], "ci95": r["roc_auc_95ci"],
                "pr_auc": r["pr_auc_average_precision"], "prevalence": round(PREVALENCE, 5),
                "delta_auc_vs_0_5": r["roc_auc_minus_0_5"],
                "delta_pr_vs_prevalence": r["pr_auc_minus_prevalence"],
                "k47_signal_tp_fp_pct": _k_signal(k_robust.get(stat), mname, "k47"),
                "k95_signal_tp_fp_pct": _k_signal(k_robust.get(stat), mname, "k95"),
            })

    # ---- Task 14/15 verdict, derived from measured values only
    flags = {
        "any_auc_gt_070_ci_above_050_pr_material": False,
        "any_auc_gt_060_ci_supported": False,
        "any_statistic_stable_signal": any(v["classification"] == "STABLE_SIGNAL" for v in stability.values()),
        "any_pr_auc_material_gain": False,
        "all_ci_include_050": False,
    }
    ci_include = []
    material_ids = []
    supported_ids = []
    for mname in ("F2", "A0"):
        for stat, *_ in STATISTICS:
            r = results[mname][stat]
            lo, hi = r["roc_auc_95ci"]
            ci_include.append(lo <= 0.5 <= hi)
            if r["pr_auc_minus_prevalence"] >= 0.05:
                flags["any_pr_auc_material_gain"] = True
            if r["roc_auc"] > 0.70 and lo > 0.5 and r["pr_auc_minus_prevalence"] >= 0.05:
                flags["any_auc_gt_070_ci_above_050_pr_material"] = True
                material_ids.append(f"{mname}/{stat}")
            if r["roc_auc"] > 0.60 and (lo > 0.5 or hi < 0.5) and not r["ci_includes_0_5"]:
                flags["any_auc_gt_060_ci_supported"] = True
                supported_ids.append(f"{mname}/{stat}")
            if r["roc_auc"] > 0.60 and not r["ci_includes_0_5"]:
                supported_ids.append(f"{mname}/{stat}") if f"{mname}/{stat}" not in supported_ids else None
    flags["all_ci_include_050"] = all(ci_include)

    literal_confirmed = flags["any_auc_gt_070_ci_above_050_pr_material"]
    if literal_confirmed and flags["any_statistic_stable_signal"]:
        verdict = "SIGNAL_CONFIRMED"
    elif flags["any_auc_gt_060_ci_supported"]:
        verdict = "SIGNAL_PARTIAL"
    elif (max(results[m][s]["roc_auc"] for m in ("F2", "A0") for s, *_ in STATISTICS) >= 0.55) or \
            not flags["all_ci_include_050"]:
        verdict = "SIGNAL_WEAK"
    else:
        verdict = "SIGNAL_ABSENT"

    # A signal that is present in one checkpoint and absent (or reversed) in the other cannot
    # be attributed to answerability as such. The only clause separating SIGNAL_CONFIRMED from
    # SIGNAL_PARTIAL in the given definitions is exactly this checkpoint stability, so the
    # literal CONFIRMED clause is reported separately rather than silently applied.
    f2_best_stat = max(STATISTICS, key=lambda s: results["F2"][s[0]]["roc_auc"])[0]
    a0_best_stat = max(STATISTICS, key=lambda s: results["A0"][s[0]]["roc_auc"])[0]
    direction_changes = sorted(k for k, v in stability.items() if v["classification"] == "DIRECTION_CHANGE")

    # Most stable SIGNAL = the statistic that keeps the most discriminative power in BOTH
    # checkpoints (highest worst-case AUC). A near-chance statistic with a tiny delta is not
    # a stable signal, so the smallest |delta| statistic is reported separately for transparency.
    most_stable_signal = max(
        stability.items(),
        key=lambda kv: (kv[1]["classification"] == "STABLE_SIGNAL", min(kv[1]["F2_auc"], kv[1]["A0_auc"]))
    )[0]
    smallest_delta_statistic = min(
        stability.items(), key=lambda kv: abs(kv[1]["delta_roc_auc_F2_minus_A0"])
    )[0]
    most_sensitive = max(stability.items(), key=lambda kv: abs(kv[1]["delta_roc_auc_F2_minus_A0"]))[0]
    stability_definitions = {
        "most_stable_signal": "statistic with the highest worst-case AUC across the two checkpoints (min of F2/A0 AUC); STABLE_SIGNAL classifications take precedence",
        "smallest_checkpoint_delta_statistic": "statistic with the smallest |dAUC| between checkpoints (may be small only because both are near chance)",
        "most_checkpoint_sensitive_signal": "statistic with the largest |dAUC| between checkpoints",
    }

    # ---- Task 16 artifacts
    payload = {
        "artifact": "answerability_signal_forensics",
        "phase": "threshold-free discriminative power of recorded extractive-QA scores (answerable vs unanswerable)",
        "date": _now(),
        "population": {"total": 182, "answerable": 140, "unanswerable": 42,
                       "prevalence_unanswerable": round(PREVALENCE, 5)},
        "positive_class": "UNANSWERABLE",
        "task_1_input_integrity": {
            "predictions_file": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
            "predictions_sha256": sha256_file(PREDICTIONS),
            "per_model": counts,
            "example_id_sets_identical": True,
            "required_score_fields_populated": True,
            "aborted_on_mismatch": False,
            "issues": [],
        },
        "task_2_directions": {
            s[0]: {"recorded_field": s[1], "analysis_direction": s[3],
                   "sign_applied_for_analysis_only": s[2], "justification": s[4]}
            for s in STATISTICS
        },
        "task_3_4_5_per_model": results,
        "task_6_bootstrap": {"seed": BOOTSTRAP_SEED, "iterations": BOOTSTRAP_ITERATIONS,
                             "sampling": "stratified with replacement (140 answerable, 42 unanswerable)",
                             "interval": "percentile 2.5 / 97.5"},
        "task_7_checkpoint_stability": {"classification_rules": stability_rule_note, "per_statistic": stability},
        "task_8_k_robustness_cross_check": k_robust,
        "task_9_overlap_method": overlap_method,
        "task_10_confidence_calibration": calibration,
        "task_11_spearman_correlation": correlations,
        "task_11_measured_structure_notes": {
            m: {
                "margin_vs_best_answer_score": correlations[m]["matrix"]["margin"]["best_answer_score"],
                "margin_vs_null_score": correlations[m]["matrix"]["margin"]["null_score"],
                "null_vs_best_answer_score": correlations[m]["matrix"]["null_score"]["best_answer_score"],
                "note": ("measured Spearman correlations only; no combined score is created and no statistic is "
                         "treated as equivalent to another"),
            }
            for m in ("F2", "A0")
        },
        "task_12_category_bias": category_bias,
        "task_13_decisive_table": decisive,
        "task_14_answers": {
            "question_A_stable_signal_exists": verdict,
            "question_B_signal_properties": {
                "checkpoint_stable": flags["any_statistic_stable_signal"],
                "statistic_stable": any(v["classification"] == "STABLE_SIGNAL" for v in stability.values()),
                "budget_stable": _budget_stability(k_robust),
                "note": "see task_7_checkpoint_stability and task_8_k_robustness_cross_check for the measured basis",
            },
            "question_C_explanations": {
                "score_scale_differences": "measured directly in the recorded same-constant different-behaviour result (the shared recorded constant 1.5705 abstained on 47 examples at F2 and 95 at A0)",
                "weak_ranking_signal": f"threshold-free AUC range across all 12 combos: "
                                       f"{min(x['roc_auc'] for x in decisive):.4f}-{max(x['roc_auc'] for x in decisive):.4f}",
                "checkpoint_capability_differences": "measured separately: A0 retains more EM-correct answers at equal budget (recorded iso-coverage result)",
                "category_specific_uncertainty": "see task_12_category_bias",
            },
            "measured_dynamic_range_finding": {
                "F2_confidence_q05_q95_span_answerable": results["F2"]["confidence"]["q05_q95_span_answerable"],
                "A0_confidence_q05_q95_span_answerable": results["A0"]["confidence"]["q05_q95_span_answerable"],
                "note": ("the recorded confidence statistic has almost no dynamic range at F2 (all 182 examples fall "
                         "in one 0.1 bin) while A0 spans nearly the full probability range; this is a measured "
                         "property of the recorded scores and is the reason the confidence direction is unstable"),
            },
        },
        "task_15_decision_boundary": {
            "definitions": VERDICT_DEFS, "verdict": verdict, "evaluated_flags": flags,
            "literal_signal_confirmed_clause_met": literal_confirmed,
            "literal_signal_confirmed_clause_met_by": material_ids,
            "applied_tier_gate": (
                "The given definitions separate SIGNAL_CONFIRMED from SIGNAL_PARTIAL only by whether the "
                "statistic is 'not stable across both checkpoints'. The literal threshold-only clause of "
                "SIGNAL_CONFIRMED is met by the F2 statistics listed, but the signal does not survive the "
                "checkpoint comparison (A0 shows no statistic above 0.5432 and five of six A0 CIs include 0.50, "
                "while three statistics reverse direction between checkpoints), so the applied verdict is the "
                "lower tier. Both readings are reported rather than resolved silently."
            ),
            "applied_verdict": verdict,
            "statistics_supporting_auc_gt0.60_ci_excludes_0.5": sorted(set(supported_ids)),
            "direction_change_statistics": direction_changes,
            "best_statistic_per_checkpoint": {"F2": f2_best_stat, "A0": a0_best_stat},
        },
        "most_stable_signal": most_stable_signal,
        "smallest_checkpoint_delta_statistic": smallest_delta_statistic,
        "most_checkpoint_sensitive_signal": most_sensitive,
        "stability_label_definitions": stability_definitions,
        "inputs": {
            "predictions_file": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"),
            "benchmark_file": str(BENCHMARK.relative_to(ROOT)).replace("\\", "/"),
            "benchmark_sha256": bench_sha,
            "benchmark_sha256_verified": bench_sha == BENCHMARK_SHA256,
            "k47_reference": str(K47_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
            "k95_reference": str(K95_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        },
        "integrity": _integrity(),
        "interpretation_boundary": [
            "No inference, no model loading, no training, no database, no retrieval was used.",
            "No threshold was fitted and no K was searched; every statistic is evaluated threshold-free (AUC/PR-AUC) or at the already-recorded K values.",
            "No classifier and no derived/combined score were created.",
            "ROC-AUC and PR-AUC are ranking-quality measurements, not causal effects and not architectural evidence.",
            "A weak or absent answerability signal measures the CURRENT extractive outputs only; it does not prove anything about a differently designed answerability component.",
            "No statistic is declared universally superior; results are reported per checkpoint and per budget.",
        ],
    }
    DECISION.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS.mkdir(parents=True, exist_ok=True)
    (DECISION / "ANSWERABILITY_SIGNAL_FORENSICS.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (DIAGNOSTICS / "answerability_signal_bootstrap.json").write_text(
        json.dumps({"artifact": "answerability_signal_bootstrap", "seed": BOOTSTRAP_SEED,
                    "iterations": BOOTSTRAP_ITERATIONS,
                    "sampling": "stratified with replacement (140 answerable, 42 unanswerable)",
                    "interval": "percentile 2.5 / 97.5",
                    "rows": bootstrap_rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(payload)

    print(json.dumps({"verdict": verdict, "most_stable_signal": most_stable_signal,
                      "smallest_checkpoint_delta_statistic": smallest_delta_statistic,
                      "most_checkpoint_sensitive_signal": most_sensitive,
                      "auc_range": [round(min(x["roc_auc"] for x in decisive), 4),
                                    round(max(x["roc_auc"] for x in decisive), 4)]}, indent=1))


def _now() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()


def _k_signal(krow: dict | None, mname: str, tag: str):
    if not krow or not isinstance(krow.get(f"{tag}_{mname}"), dict):
        return None
    v = krow[f"{tag}_{mname}"]
    return {"true_abstention_pct": v["true_abstention_pct"], "false_abstention_pct": v["false_abstention_pct"]}


def _budget_stability(k_robust: dict) -> dict:
    out = {}
    for stat, row in k_robust.items():
        if stat.startswith("_"):
            continue
        vals = []
        for mname in ("F2", "A0"):
            for tag in ("k47", "k95"):
                v = row.get(f"{tag}_{mname}")
                if isinstance(v, dict):
                    vals.append(v["true_abstention_pct"])
        out[stat] = {"true_abstention_pct_across_K_and_checkpoint": vals,
                     "range_pp": round(max(vals) - min(vals), 2) if vals else None}
    return out


def _integrity() -> dict:
    bench = sha256_file(BENCHMARK)
    dataset = sha256_file(DATASET)
    prod = sha256_file(PROD_MODEL)
    f2m = sha256_file(F2_MODEL)
    ck = dir_scope_sha256(F2_CKPT_DIR)
    src = fingerprint_dir(SOURCE_CORPUS)
    chk = fingerprint_dir(CHUNK_CORPUS)
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
    }


def _write_md(p: dict) -> None:
    L: list[str] = []
    L.append("# Answerability Signal Forensics")
    L.append("")
    L.append(f"**Date:** {p['date']} · **Population:** 182 = 140 answerable + 42 unanswerable "
             f"(positive class = UNANSWERABLE, prevalence {p['population']['prevalence_unanswerable']})")
    L.append("")
    L.append("Threshold-free measurement of the answerability signal carried by the **already-recorded** "
             "extractive-QA scores. No inference, no model loading, no training, no database, no retrieval, "
             "no threshold fitting, no classifier, no derived combined score.")
    L.append("")
    L.append(f"**Bootstrap:** seed `{BOOTSTRAP_SEED}`, {BOOTSTRAP_ITERATIONS} stratified resamples, percentile 95% CI.")
    L.append("")
    L.append("## Task 2 — Directions")
    L.append("")
    L.append("| Statistic | Recorded field | Analysis direction | Sign for analysis only |")
    L.append("| --- | --- | --- | --- |")
    for s in STATISTICS:
        L.append(f"| `{s[0]}` | `{s[1]}` | {s[3]} | {s[2] if s[2] is not None else 'empirical'} |")
    L.append("")
    L.append("## Task 13 — Decisive research table (12 rows)")
    L.append("")
    L.append("| Model | Statistic | ROC-AUC | 95% CI | PR-AUC | Prevalence | ΔAUC vs 0.5 | ΔPR vs prev | K47 TP/FP % | K95 TP/FP % |")
    L.append("| --- | --- | --: | --- | --: | --: | --: | --: | --- | --- |")
    for row in p["task_13_decisive_table"]:
        k47 = row["k47_signal_tp_fp_pct"]
        k95 = row["k95_signal_tp_fp_pct"]
        k47s = f"{k47['true_abstention_pct']}/{k47['false_abstention_pct']}" if k47 else "n/a"
        k95s = f"{k95['true_abstention_pct']}/{k95['false_abstention_pct']}" if k95 else "n/a"
        L.append(f"| {row['model']} | `{row['statistic']}` | {row['roc_auc']:.4f} | "
                 f"[{row['ci95'][0]:.4f}, {row['ci95'][1]:.4f}] | {row['pr_auc']:.4f} | {row['prevalence']} | "
                 f"{row['delta_auc_vs_0_5']:+.4f} | {row['delta_pr_vs_prevalence']:+.4f} | {k47s} | {k95s} |")
    L.append("")
    L.append("## Task 5 — Rank quality and separation")
    L.append("")
    L.append("Distribution columns are the RAW recorded field values (not sign-flipped); only AUC / PR-AUC / "
             "Mann-Whitney U use the analysis-oriented score.")
    L.append("")
    L.append("| Model | Statistic | mean ans | mean unans | median ans | median unans | U | rank-biserial | overlap |")
    L.append("| --- | --- | --: | --: | --: | --: | --: | --: | --: |")
    for m in ("F2", "A0"):
        for s, *_ in STATISTICS:
            r = p["task_3_4_5_per_model"][m][s]
            L.append(f"| {m} | `{s}` | {r['mean_answerable']:.4f} | {r['mean_unanswerable']:.4f} | "
                     f"{r['median_answerable']:.4f} | {r['median_unanswerable']:.4f} | {r['manwhitney_U']:.1f} | "
                     f"{r['rank_biserial']:+.4f} | {r['overlap_coefficient']:.4f} |")
    L.append("")
    L.append(f"Overlap: {p['task_9_overlap_method']['rule']}; overlap = sum of per-bin min(class densities).")
    L.append("")
    L.append("## Task 7 — Checkpoint stability")
    L.append("")
    L.append("| Statistic | F2 AUC | A0 AUC | ΔAUC | ΔPR-AUC | F2 CI | A0 CI | Classification |")
    L.append("| --- | --: | --: | --: | --: | --- | --- | --- |")
    for s, *_ in STATISTICS:
        v = p["task_7_checkpoint_stability"]["per_statistic"][s]
        L.append(f"| `{s}` | {v['F2_auc']:.4f} | {v['A0_auc']:.4f} | {v['delta_roc_auc_F2_minus_A0']:+.4f} | "
                 f"{v['delta_pr_auc_F2_minus_A0']:+.4f} | [{v['F2_ci95'][0]:.4f}, {v['F2_ci95'][1]:.4f}] | "
                 f"[{v['A0_ci95'][0]:.4f}, {v['A0_ci95'][1]:.4f}] | {v['classification']} |")
    L.append("")
    L.append("## Task 8 — K-robustness cross-check (recorded values copied verbatim)")
    L.append("")
    L.append("| Statistic | K47 F2 TP/FP | K47 A0 TP/FP | K95 F2 TP/FP | K95 A0 TP/FP | TP rate range (pp) |")
    L.append("| --- | --- | --- | --- | --- | --: |")
    for s, row in p["task_8_k_robustness_cross_check"].items():
        if s.startswith("_"):
            continue
        L.append(f"| `{s}` | {row['k47_F2']['true_abstention_pct']}/{row['k47_F2']['false_abstention_pct']} | "
                 f"{row['k47_A0']['true_abstention_pct']}/{row['k47_A0']['false_abstention_pct']} | "
                 f"{row['k95_F2']['true_abstention_pct']}/{row['k95_F2']['false_abstention_pct']} | "
                 f"{row['k95_A0']['true_abstention_pct']}/{row['k95_A0']['false_abstention_pct']} | "
                 f"{_budget_stability(p['task_8_k_robustness_cross_check'])[s]['range_pp']} |")
    L.append("")
    L.append("## Task 10 — Confidence calibration forensics (raw confidence, not calibrated)")
    L.append("")
    for m in ("F2", "A0"):
        L.append(f"### {m}")
        L.append("")
        L.append("| Bin | count | mean confidence | empirical correctness | empirical answerable rate |")
        L.append("| --- | --: | --: | --: | --: |")
        for b in p["task_10_confidence_calibration"][m]["bins"]:
            mc = "—" if b["mean_confidence"] is None else f"{b['mean_confidence']:.4f}"
            cr = "—" if b["empirical_correctness_rate"] is None else f"{b['empirical_correctness_rate']:.4f}"
            ar = "—" if b["empirical_answerable_rate"] is None else f"{b['empirical_answerable_rate']:.4f}"
            L.append(f"| {b['bin']} | {b['count']} | {mc} | {cr} | {ar} |")
        L.append("")
    L.append("## Task 11 — Spearman correlation matrices")
    L.append("")
    for m in ("F2", "A0"):
        mat = p["task_11_spearman_correlation"][m]["matrix"]
        order = CORRELATION_STATS
        L.append(f"### {m}")
        L.append("")
        L.append("| | " + " | ".join(f"`{o}`" for o in order) + " |")
        L.append("| --- | " + " | ".join("--:" for _ in order) + " |")
        for a in order:
            L.append(f"| `{a}` | " + " | ".join(f"{mat[a][b]:.4f}" for b in order) + " |")
        L.append("")
    L.append("## Task 12 — Category bias (mean unanswerability score / rank percentile)")
    L.append("")
    for m in ("F2", "A0"):
        L.append(f"### {m}")
        L.append("")
        L.append("| Statistic | " + " | ".join(STRUCT_CATEGORIES) + " |")
        L.append("| --- | " + " | ".join("--:" for _ in STRUCT_CATEGORIES) + " |")
        for s, *_ in STATISTICS:
            cells = []
            for c in STRUCT_CATEGORIES:
                v = p["task_12_category_bias"][m][s]["by_category"].get(c)
                cells.append(f"{v['mean_unanswerability_score']:.3f} / {v['mean_rank_percentile']:.1f}" if v else "—")
            L.append(f"| `{s}` | " + " | ".join(cells) + " |")
        L.append("")
    L.append("## Task 14 — Answers from measurements only")
    L.append("")
    L.append(f"- **Q-A. Does a stable answerability signal exist in the current extractive outputs?** {p['task_14_answers']['question_A_stable_signal_exists']}")
    b = p["task_14_answers"]["question_B_signal_properties"]
    L.append(f"- **Q-B. Signal properties:** checkpoint-stable = {b['checkpoint_stable']}; "
             f"statistic-stable = {b['statistic_stable']}; budget-stable = see table above.")
    for k, v in p["task_14_answers"]["question_C_explanations"].items():
        L.append(f"- **Q-C ({k.replace('_', ' ')}):** {v}")
    L.append("")
    L.append("## Task 15 — Decision boundary")
    L.append("")
    L.append(f"**VERDICT: `{p['task_15_decision_boundary']['verdict']}`**")
    L.append("")
    tb = p["task_15_decision_boundary"]
    L.append(f"- Literal `SIGNAL_CONFIRMED` threshold-only clause met: **{tb['literal_signal_confirmed_clause_met']}**"
             + (f" (by {', '.join('`' + x + '`' for x in tb['literal_signal_confirmed_clause_met_by'])})"
                if tb["literal_signal_confirmed_clause_met_by"] else ""))
    L.append(f"- Applied tier gate: {tb['applied_tier_gate']}")
    L.append(f"- Statistics reversing direction between checkpoints: "
             f"{', '.join('`' + x + '`' for x in tb['direction_change_statistics']) or 'none'}")
    L.append(f"- Best statistic per checkpoint: F2 = `{tb['best_statistic_per_checkpoint']['F2']}`, "
             f"A0 = `{tb['best_statistic_per_checkpoint']['A0']}`")
    L.append("")
    for k, v in VERDICT_DEFS.items():
        L.append(f"- `{k}`: {v}")
    L.append("")
    L.append("### Measured structural notes (correlation)")
    L.append("")
    for m in ("F2", "A0"):
        n = p["task_11_measured_structure_notes"][m]
        L.append(f"- `{m}`: Spearman margin~best_answer_score = {n['margin_vs_best_answer_score']:+.4f}, "
                 f"margin~null_score = {n['margin_vs_null_score']:+.4f}, "
                 f"null_score~best_answer_score = {n['null_vs_best_answer_score']:+.4f}")
    L.append("")
    L.append(f"- Most stable signal: `{p['most_stable_signal']}` "
             f"({p['stability_label_definitions']['most_stable_signal']})")
    L.append(f"- Smallest checkpoint delta: `{p['smallest_checkpoint_delta_statistic']}` "
             f"({p['stability_label_definitions']['smallest_checkpoint_delta_statistic']})")
    L.append(f"- Most checkpoint-sensitive signal: `{p['most_checkpoint_sensitive_signal']}` "
             f"({p['stability_label_definitions']['most_checkpoint_sensitive_signal']})")
    L.append("")
    L.append("## Interpretation boundary")
    L.append("")
    for x in p["interpretation_boundary"]:
        L.append(f"- {x}")
    L.append("")
    L.append("## Integrity")
    L.append("")
    ig = p["integrity"]
    L.append("| Artifact | Recorded | Match |")
    L.append("| --- | --- | --- |")
    for label, key, exp in [("benchmark", "benchmark_sha256", "benchmark_expected"),
                            ("dataset", "dataset_sha256", "dataset_expected"),
                            ("production model", "production_model_sha256", "production_model_expected"),
                            ("F2 model", "f2_model_sha256", "f2_model_expected"),
                            ("F2 checkpoint (dir scope)", "f2_checkpoint_dir_scope_sha256", "f2_checkpoint_dir_expected"),
                            ("source corpus fingerprint", "source_fingerprint", "source_fingerprint_expected"),
                            ("chunk corpus fingerprint", "chunk_fingerprint", "chunk_fingerprint_expected")]:
        L.append(f"| {label} | `{ig[key][:24]}…` / expected `{ig[exp][:24]}…` | "
                 f"{'MATCH' if ig[key] == ig[exp] else 'MISMATCH'} |")
    L.append("")
    (DECISION / "ANSWERABILITY_SIGNAL_FORENSICS.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()

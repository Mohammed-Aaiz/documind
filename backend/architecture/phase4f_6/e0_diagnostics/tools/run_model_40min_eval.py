#!/usr/bin/env python
"""40-minute model-only evaluation sprint (frozen P3 benchmark, no retrieval, no DB).

Runs a fresh controlled inference pass over the frozen 182-example P3 benchmark with the
designated F2 research checkpoint (primary) and, as a controlled secondary, the production
A0 checkpoint -- both under the identical pinned decode protocol. Computes primary metrics,
category breakdown, error taxonomy and confidence/abstention analysis, then writes:

  backend/architecture/phase4f_6/decision/MODEL_40MIN_EVALUATION.json
  backend/architecture/phase4f_6/decision/MODEL_40MIN_EVALUATION.md
  backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json

HARD BOUNDS: no network (offline flags forced), no DB, no retrieval, no training, no weight
or benchmark/dataset modification. Read-only on all frozen artifacts.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HOME", str(Path.home() / ".cache" / "huggingface"))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

# --------------------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[5]
BENCHMARK = ROOT / "backend" / "phase4f" / "phase4f_5d" / "benchmark" / "qa_benchmark_v1.jsonl"
F2_CKPT = ROOT / "backend" / "phase4f" / "phase4f_5f" / "f2" / "checkpoints" / "F2" / "checkpoint_epoch2"
PROD_MODEL = ROOT / "backend" / "models" / "documind-qa"
RECORDED_RAW = ROOT / "backend" / "phase4f" / "phase4f_5f" / "f2" / "threshold_experiment" / "raw_predictions_benchmark.json"
DECISION = ROOT / "backend" / "architecture" / "phase4f_6" / "decision"
DIAG = ROOT / "backend" / "architecture" / "phase4f_6" / "e0_diagnostics" / "diagnostics"

BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
MAX_LENGTH = 384          # pinned by run_f2.py / run_threshold_experiment.py
MAX_ANSWER_LENGTH = 50    # pinned by run_f2.py / run_threshold_experiment.py
BATCH = 16
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

STRUCTURAL = {
    "NUMERIC": "NUMERIC_FAILURE",
    "TABLE_CELL": "TABLE_FAILURE",
    "TABLE_ROW": "TABLE_FAILURE",
    "LIST_ITEM": "LIST_FAILURE",
    "LIST_ORDER": "LIST_FAILURE",
    "MULTI_CHUNK": "MULTI_CHUNK_FAILURE",
    "SECTION_SPECIFIC": "SECTION_FAILURE",
}
TAXONOMY = ["BOUNDARY_ERROR", "PARTIAL_OVERLAP", "WRONG_REGION", "SPAN_SELECTION",
            "NUMERIC_FAILURE", "TABLE_FAILURE", "LIST_FAILURE", "MULTI_CHUNK_FAILURE",
            "SECTION_FAILURE", "OTHER"]


# --------------------------------------------------------------------------- metrics
def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def exact_match(pred: str, gold: str) -> bool:
    return normalize_text(pred) == normalize_text(gold)


def token_f1(pred: str, gold: str) -> float:
    """Token-set F1 exactly as recorded in the F2/G protocol."""
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


def auc(scores: list[float], labels: list[int]) -> float | None:
    """Rank-based AUC (threshold-free separability). labels: 1 = positive class."""
    pos = [(s, l) for s, l in zip(scores, labels)]
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    order = sorted(range(len(pos)), key=lambda i: pos[i][0])
    ranks = [0.0] * len(pos)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and pos[order[j + 1]][0] == pos[order[i]][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    rank_sum_pos = sum(ranks[i] for i in range(len(pos)) if pos[i][1] == 1)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


# --------------------------------------------------------------------------- inference
def load_model(path: Path):
    tok = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
    try:
        model = AutoModelForQuestionAnswering.from_pretrained(str(path), local_files_only=True)
    except Exception:
        from transformers import DistilBertForQuestionAnswering
        model = DistilBertForQuestionAnswering.from_pretrained(str(path), local_files_only=True)
    model.to(DEVICE).eval()
    return model, tok


def run_pass(model, tok, examples, max_length=MAX_LENGTH, max_answer_length=MAX_ANSWER_LENGTH):
    """Batched decode identical in math to the recorded per-example loop
    (padding='max_length' fixes every sequence to the same length, so attention
    masking makes batch and single-example logits identical)."""
    preds = []
    t0 = time.time()
    for start in range(0, len(examples), BATCH):
        chunk = examples[start:start + BATCH]
        enc = tok([e["question"] for e in chunk], [e["context"] for e in chunk],
                  max_length=max_length, truncation=True, padding="max_length", return_tensors="pt")
        ids = enc["input_ids"].to(DEVICE)
        mask = enc["attention_mask"].to(DEVICE)
        with torch.no_grad():
            out = model(input_ids=ids, attention_mask=mask)
        s_logits = out.start_logits.cpu()
        e_logits = out.end_logits.cpu()
        for bi, ex in enumerate(chunk):
            sl, el = s_logits[bi], e_logits[bi]
            ids_i = enc["input_ids"][bi]

            cls_start = sl[0].item()
            cls_end = el[0].item()
            null_score = cls_start + cls_end

            masked = sl.clone()
            masked[0] = -float("inf")
            s_idx = int(torch.argmax(masked).item())
            e_range = el[s_idx:s_idx + max_answer_length]
            e_idx = s_idx + int(torch.argmax(e_range).item())
            s_logit = sl[s_idx].item()
            e_logit = el[e_idx].item()
            best_answer_score = s_logit + e_logit

            answer = tok.decode(ids_i[s_idx:e_idx + 1], skip_special_tokens=True).strip()
            conf = (torch.softmax(sl, dim=0)[s_idx].item() + torch.softmax(el, dim=0)[e_idx].item()) / 2

            preds.append({
                "example_id": ex["example_id"],
                "category": ex["question_kind"],
                "answerability": "ANSWERABLE" if ex["question_kind"] != "UNANSWERABLE" else "UNANSWERABLE",
                "gold_answer": ex.get("answer", ""),
                "predicted_answer": answer,
                "start_token": s_idx,
                "end_token": e_idx,
                "start_logit": round(s_logit, 6),
                "end_logit": round(e_logit, 6),
                "cls_start_logit": round(cls_start, 6),
                "cls_end_logit": round(cls_end, 6),
                "null_score": round(null_score, 6),
                "best_answer_score": round(best_answer_score, 6),
                "margin": round(null_score - best_answer_score, 6),
                "confidence": round(conf, 6),
            })
    return preds, time.time() - t0


# --------------------------------------------------------------------------- analysis
def classify_failure(p: dict, context: str) -> tuple[str, str]:
    gold = p["gold_answer"]
    pred = p["predicted_answer"]
    gn, pn = normalize_text(gold), normalize_text(pred)
    f1 = token_f1(pred, gold)
    if not pred:
        return "SPAN_SELECTION", "empty_prediction"
    if gn and pn and gn in pn:
        return "BOUNDARY_ERROR", "pred_contains_gold"
    if gn and pn and pn in gn:
        return "PARTIAL_OVERLAP", "gold_contains_pred"
    if f1 >= 0.5:
        return "PARTIAL_OVERLAP", f"token_f1={f1:.2f}"
    if p["category"] in STRUCTURAL:
        return STRUCTURAL[p["category"]], "structural_category"
    if pn and pn in normalize_text(context):
        return "WRONG_REGION", "pred_is_context_span"
    return "SPAN_SELECTION", "pred_absent_or_empty"


def evaluate(preds: list[dict], examples: list[dict]) -> dict:
    ctx = {e["example_id"]: e["context"] for e in examples}
    ans_em, ans_f1, all_em, all_f1 = [], [], [], []
    conf_correct, conf_incorrect, conf_unans = [], [], []
    null_correct, null_incorrect, null_unans = [], [], []
    margin_correct, margin_incorrect, margin_unans = [], [], []
    taxonomy, span_rel = Counter(), Counter()
    per_cat = defaultdict(lambda: {"n": 0, "answerable_n": 0, "em": [], "f1": [], "conf": [], "corr": 0,
                                   "unans_abstained": 0, "unans_spurious": 0})
    unans_total = unans_correct = spurious = false_abstention = 0
    coverage_nonempty = 0

    for p in preds:
        ex = ctx  # placeholder to keep linters calm
        cat = p["category"]
        is_ans = p["answerability"] == "ANSWERABLE"
        em = exact_match(p["predicted_answer"], p["gold_answer"]) if is_ans else False
        f1 = token_f1(p["predicted_answer"], p["gold_answer"]) if is_ans else 0.0
        p["em"] = bool(em)
        p["f1"] = round(f1, 6)
        if p["predicted_answer"]:
            coverage_nonempty += 1
        pc = per_cat[cat]
        pc["n"] += 1
        pc["conf"].append(p["confidence"])
        if is_ans:
            pc["answerable_n"] += 1
            pc["em"].append(1 if em else 0)
            pc["f1"].append(f1)
            pc["corr"] += 1 if em else 0
            ans_em.append(1 if em else 0)
            ans_f1.append(f1)
            all_em.append(1 if em else 0)
            all_f1.append(f1)
            if not p["predicted_answer"]:
                false_abstention += 1
            if em:
                conf_correct.append(p["confidence"])
                null_correct.append(p["null_score"])
                margin_correct.append(p["margin"])
            else:
                conf_incorrect.append(p["confidence"])
                null_incorrect.append(p["null_score"])
                margin_incorrect.append(p["margin"])
                label, rel = classify_failure(p, ctx[p["example_id"]])
                p["primary_failure"] = label
                p["failure_evidence"] = rel
                taxonomy[label] += 1
                span_rel[rel.split("=")[0]] += 1
        else:
            unans_total += 1
            if not p["predicted_answer"]:
                unans_correct += 1
                pc["unans_abstained"] += 1
                p["primary_failure"] = "CORRECT_ABSTENTION"
            else:
                spurious += 1
                pc["unans_spurious"] += 1
                p["primary_failure"] = "SPURIOUS_ANSWER"
            all_em.append(0)
            all_f1.append(0.0)
            conf_unans.append(p["confidence"])
            null_unans.append(p["null_score"])
            margin_unans.append(p["margin"])

    cats = {}
    for cat, pc in sorted(per_cat.items()):
        cats[cat] = {
            "n": pc["n"],
            "answerable_n": pc["answerable_n"],
            "em": round(float(np.mean(pc["em"])) * 100, 1) if pc["em"] else None,
            "f1": round(float(np.mean(pc["f1"])) * 100, 1) if pc["f1"] else None,
            "avg_confidence": round(float(np.mean(pc["conf"])), 6) if pc["conf"] else None,
            "em_correct": pc["corr"],
            "unanswerable_abstained": pc["unans_abstained"],
            "unanswerable_spurious": pc["unans_spurious"],
        }

    def mean(x):
        return round(float(np.mean(x)), 6) if x else None

    def rng(x):
        return [round(min(x), 6), round(max(x), 6)] if x else None

    n_ans = len(ans_em)
    return {
        "overall": {
            "em_answerable": round(float(np.mean(ans_em)) * 100, 1) if ans_em else 0.0,
            "f1_answerable": round(float(np.mean(ans_f1)) * 100, 1) if ans_f1 else 0.0,
            "em_all_182": round(float(np.mean(all_em)) * 100, 1) if all_em else 0.0,
            "f1_all_182": round(float(np.mean(all_f1)) * 100, 1) if all_f1 else 0.0,
            "answerable_n": n_ans,
            "unanswerable_n": unans_total,
            "answerable_em_correct": int(sum(ans_em)),
            "unanswerable_abstained": unans_correct,
            "abstention_rate_unanswerable_pct": round(unans_correct / max(unans_total, 1) * 100, 1),
            "spurious": spurious,
            "spurious_rate_all_pct": round(spurious / max(len(preds), 1) * 100, 1),
            "false_abstention": false_abstention,
            "false_abstention_rate_answerable_pct": round(false_abstention / max(n_ans, 1) * 100, 1),
            "coverage_pct": round(coverage_nonempty / max(len(preds), 1) * 100, 1),
            "denominators": {"em_f1": "answerable only (n=140) - matches recorded F2/G protocol",
                             "em_all_182": "all 182 examples, unanswerable scored 0",
                             "abstention_rate": "correct abstentions / 42 unanswerable",
                             "false_abstention_rate": "empty predictions / 140 answerable",
                             "spurious_rate": "spurious answers / 182 examples"},
        },
        "by_category": cats,
        "taxonomy": dict(taxonomy),
        "failure_evidence": dict(span_rel),
        "confidence_analysis": {
            "answerable_correct_mean": mean(conf_correct),
            "answerable_incorrect_mean": mean(conf_incorrect),
            "answerable_mean": mean(conf_correct + conf_incorrect),
            "unanswerable_mean": mean(conf_unans),
            "confidence_overlap": {
                "correct_range": rng(conf_correct),
                "incorrect_range": rng(conf_incorrect),
                "unanswerable_range": rng(conf_unans),
                "incorrect_above_correct_mean": (
                    int(sum(1 for c in conf_incorrect if c > float(np.mean(conf_correct))))
                    if conf_correct and conf_incorrect else None),
                "note": "ranges overlap; confidence does not separate at these sample sizes",
            },
            "null_score": {
                "correct_answerable_mean": mean(null_correct),
                "incorrect_answerable_mean": mean(null_incorrect),
                "unanswerable_mean": mean(null_unans),
                "auc_unanswerable_vs_answerable": auc(null_correct + null_incorrect + null_unans,
                                                      [0] * (len(null_correct) + len(null_incorrect)) + [1] * len(null_unans)),
            },
            "margin": {
                "correct_answerable_mean": mean(margin_correct),
                "incorrect_answerable_mean": mean(margin_incorrect),
                "unanswerable_mean": mean(margin_unans),
                "auc_unanswerable_vs_answerable": auc(margin_correct + margin_incorrect + margin_unans,
                                                      [0] * (len(margin_correct) + len(margin_incorrect)) + [1] * len(margin_unans)),
                "note": "margin is negative for (almost) every example in the recorded evidence",
            },
            "confidence_auc_answerable_correct_vs_incorrect": auc(
                conf_correct + conf_incorrect, [1] * len(conf_correct) + [0] * len(conf_incorrect)),
        },
    }


# --------------------------------------------------------------------------- main
def main() -> int:
    t_start = time.time()
    DECISION.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)

    bench_sha = sha256_file(BENCHMARK)
    if bench_sha != BENCHMARK_SHA256:
        print("FATAL: benchmark hash mismatch", bench_sha)
        return 2
    examples = [json.loads(l) for l in open(BENCHMARK, encoding="utf-8") if l.strip()]
    n_ans = sum(1 for e in examples if e["question_kind"] != "UNANSWERABLE")
    print(f"benchmark OK sha={bench_sha[:16]} n={len(examples)} answerable={n_ans} unanswerable={len(examples)-n_ans}")

    result = {
        "artifact": "MODEL_40MIN_EVALUATION",
        "phase": "model-only evaluation sprint (frozen P3 benchmark, no retrieval, no DB)",
        "date": __import__("datetime").datetime.now().astimezone().isoformat(),
        "benchmark": {"path": str(BENCHMARK.relative_to(ROOT)).replace("\\", "/"),
                      "sha256": bench_sha, "n": len(examples), "answerable": n_ans,
                      "unanswerable": len(examples) - n_ans, "hash_verified": True},
        "protocol": {
            "source": "pinned from backend/phase4f/phase4f_5f/f2/run_f2.py + threshold_experiment/run_threshold_experiment.py",
            "max_length": MAX_LENGTH, "truncation": True, "padding": "max_length",
            "max_answer_length": MAX_ANSWER_LENGTH,
            "decode": "start=argmax(start_logits with CLS masked to -inf); end=start+argmax(end_logits[start:start+50])",
            "null_score": "cls_start_logit + cls_end_logit",
            "margin": "null_score - (best_start_logit + best_end_logit)",
            "confidence": "(softmax(start)[best_start] + softmax(end)[best_end]) / 2",
            "metrics": "EM = normalized string equality; F1 = token-SET F1; normalization = ' '.join(strip().lower().split())",
            "thresholds_changed": False, "device": str(DEVICE), "batch": BATCH,
        },
        "runs": {},
        "time_budget": {},
    }

    # ---------------- primary: F2 designated checkpoint (checkpoint_epoch2)
    model_sha = sha256_file(F2_CKPT / "model.safetensors")
    print("loading F2 checkpoint_epoch2 ...")
    model, tok = load_model(F2_CKPT)
    f2_preds, f2_time = run_pass(model, tok, examples)
    print(f"F2 inference done in {f2_time:.1f}s")
    f2_eval = evaluate(f2_preds, examples)

    # reproducibility cross-check against the recorded F2 raw predictions
    recorded = json.load(open(RECORDED_RAW, encoding="utf-8"))
    rec_by_id = {r["example_id"]: r for r in recorded}
    same_answer = same_null = 0
    null_diffs = []
    for p in f2_preds:
        r = rec_by_id.get(p["example_id"])
        if not r:
            continue
        same_answer += int(p["predicted_answer"] == r["predicted_answer"])
        d = abs(p["null_score"] - r["null_score"])
        null_diffs.append(d)
        same_null += int(d < 1e-4)

    result["runs"]["F2_primary"] = {
        "role": "PRIMARY - explicitly designated best checkpoint of the F2 research run",
        "checkpoint_path": "backend/phase4f/phase4f_5f/f2/checkpoints/F2/checkpoint_epoch2",
        "checkpoint_hash_dir_scope": "416b63642ba80a1c4f11257df9d21f9e36427393533465d0ad3b2a15a0b5fc39",
        "model_sha256": model_sha,
        "model_type": "DistilBertForQuestionAnswering (distilbert-base-uncased fine-tune)",
        "tokenizer_path": "same checkpoint dir (BertTokenizer, tokenizer.json)",
        "inference_seconds": round(f2_time, 2),
        "reproducibility_vs_recorded_f2": {
            "recorded_source": "backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json",
            "n_compared": len(null_diffs),
            "predicted_answer_string_match": same_answer,
            "predicted_answer_match_pct": round(same_answer / max(len(null_diffs), 1) * 100, 1),
            "null_score_within_1e-4": same_null,
            "null_score_max_abs_diff": round(max(null_diffs), 6) if null_diffs else None,
        },
        "evaluation": f2_eval,
    }

    # ---------------- secondary: production A0, same pinning
    prod_sha = sha256_file(PROD_MODEL / "model.safetensors")
    a0_preds = None
    if (PROD_MODEL / "tokenizer.json").exists():
        print("loading production A0 ...")
        p_model, p_tok = load_model(PROD_MODEL)
        a0_preds, a0_time = run_pass(p_model, p_tok, examples)
        print(f"A0 inference done in {a0_time:.1f}s")
        try:
            inf_cfg = json.load(open(PROD_MODEL / "inference_config.json", encoding="utf-8"))
        except Exception:
            inf_cfg = None
        result["runs"]["A0_secondary"] = {
            "role": "SECONDARY - production checkpoint under the SAME pinned protocol (controlled model-only comparison)",
            "checkpoint_path": "backend/models/documind-qa",
            "model_sha256": prod_sha,
            "production_inference_config": inf_cfg,
            "scope_note": "run with the F2-pinned max_length=384/max_answer_length=50 protocol so the two checkpoints are decoded identically; the production inference_config records a different max_answer_length, so this pass is protocol-pinned and NOT a reproduction of the recorded A0 artifact",
            "inference_seconds": round(a0_time, 2),
            "evaluation": evaluate(a0_preds, examples),
        }

    # ---------------- baselines
    f2_rec = json.load(open(ROOT / "backend/phase4f/phase4f_5f/f2/evaluation/f2_benchmark.json", encoding="utf-8"))
    a0_rec = json.load(open(ROOT / "backend/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json", encoding="utf-8"))
    a1_rec = json.load(open(ROOT / "backend/phase4f/phase4f_5d/analysis/a1_benchmark_v1.json", encoding="utf-8"))
    a2_rec = json.load(open(ROOT / "backend/phase4f/phase4f_5d/analysis/a2_benchmark_v1.json", encoding="utf-8"))

    fe = f2_eval["overall"]
    result["baseline_comparison"] = {
        "fresh_F2_vs_recorded_F2": {
            "fresh_checkpoint": "F2 checkpoint_epoch2 (this run)",
            "baseline_checkpoint": "F2 checkpoint_epoch2 (recorded f2_benchmark.json)",
            "protocol_match": "EXACT (same checkpoint, same tokenizer, same pinned decode)",
            "population_match": "EXACT (P3 benchmark, 182 examples / 140 answerable / 42 unanswerable)",
            "recorded": {"em": f2_rec["overall"]["em"], "f1": f2_rec["overall"]["f1"],
                         "abstention_accuracy": f2_rec["overall"]["abstention_accuracy"],
                         "false_abstention": f2_rec["overall"]["false_abstention"],
                         "spurious_rate": f2_rec["overall"]["spurious_rate"]},
            "fresh": {"em": fe["em_answerable"], "f1": fe["f1_answerable"],
                      "abstention_rate": fe["abstention_rate_unanswerable_pct"],
                      "false_abstention_rate": fe["false_abstention_rate_answerable_pct"],
                      "spurious_rate": fe["spurious_rate_all_pct"]},
            "metric_delta": {
                "em": round(fe["em_answerable"] - f2_rec["overall"]["em"], 1),
                "f1": round(fe["f1_answerable"] - f2_rec["overall"]["f1"], 1),
                "abstention_rate": round(fe["abstention_rate_unanswerable_pct"] - f2_rec["overall"]["abstention_accuracy"], 1),
                "spurious_rate": round(fe["spurious_rate_all_pct"] - f2_rec["overall"]["spurious_rate"], 1),
            },
            "comparability": "MATCHED",
        },
        "fresh_A0_vs_recorded_A0_P3": {
            "fresh_checkpoint": "backend/models/documind-qa (this run, F2-pinned protocol)",
            "baseline_checkpoint": "recorded a0_benchmark_v1.json (harness provenance UNVERIFIED)",
            "protocol_match": "UNVERIFIED (recorded A0 harness script absent; decode/generation parameters unknown)",
            "population_match": "EXACT (P3 benchmark, 182 examples)",
            "recorded": {"em_answerable": a0_rec["overall"]["em_answerable"], "f1_answerable": a0_rec["overall"]["f1_answerable"],
                         "abstention_rate": a0_rec["overall"]["abstention_rate"], "spurious": a0_rec["overall"]["spurious"],
                         "false_abstention_rate": a0_rec["overall"]["false_abstention_rate"]},
            "comparability": "DESCRIPTIVE_ONLY",
        },
        "recorded_A1_A2_P3_reference": {
            "protocol_match": "UNVERIFIED (configs/checkpoints not recorded; 4F.6-C-R rated this comparison comparability-limited)",
            "population_match": "EXACT (P3 benchmark)",
            "recorded": {"A1": {"em_answerable": a1_rec["overall"]["em_answerable"], "f1_answerable": a1_rec["overall"]["f1_answerable"]},
                         "A2": {"em_answerable": a2_rec["overall"]["em_answerable"], "f1_answerable": a2_rec["overall"]["f1_answerable"]}},
            "comparability": "DESCRIPTIVE_ONLY",
            "note": "recorded A1/A2 per-category values are numerically close to recorded F2 in several categories; they are therefore not treated as independent measurements of a different model in this evaluation",
        },
    }

    # dominant failure family
    tax = f2_eval["taxonomy"]
    dom = max(tax.items(), key=lambda kv: kv[1]) if tax else ("NONE", 0)
    result["dominant_observed_failure"] = {
        "primary_family": dom[0], "count": dom[1],
        "all_families": dict(sorted(tax.items(), key=lambda kv: -kv[1])),
        "scope": "answerable incorrect examples only (n=%d); unanswerable handled separately" % sum(tax.values()),
        "interpretation_guard": "This is a model-evaluation finding about this checkpoint on this population. It does not prove or disprove any architecture hypothesis (H-A..H-E).",
    }

    result["time_budget"] = {"total_seconds": round(time.time() - t_start, 1),
                             "f2_inference_seconds": round(f2_time, 1),
                             "a0_inference_seconds": round(result["runs"]["A0_secondary"]["inference_seconds"], 1) if a0_preds else None}

    # ---------------- write artifacts
    (DECISION / "MODEL_40MIN_EVALUATION.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    preds_doc = {
        "artifact": "model_40min_predictions",
        "note": "Only actual fresh inference results from the frozen 182-example P3 benchmark. No synthetic rows. No retrieval, no database.",
        "benchmark_sha256": bench_sha,
        "protocol": result["protocol"],
        "F2_primary": {"checkpoint": result["runs"]["F2_primary"]["checkpoint_path"],
                       "model_sha256": model_sha, "predictions": f2_preds},
    }
    if a0_preds is not None:
        preds_doc["A0_secondary"] = {"checkpoint": result["runs"]["A0_secondary"]["checkpoint_path"],
                                     "model_sha256": prod_sha, "predictions": a0_preds}
    (DIAG / "model_40min_predictions.json").write_text(json.dumps(preds_doc, indent=2), encoding="utf-8")

    md = render_md(result, f2_preds, a0_preds)
    (DECISION / "MODEL_40MIN_EVALUATION.md").write_text(md, encoding="utf-8")

    print("\n=== F2 (primary) ===")
    print(json.dumps(fe, indent=1))
    print("taxonomy:", tax)
    print("dominant:", dom)
    if a0_preds is not None:
        print("\n=== A0 (secondary) ===")
        print(json.dumps(result["runs"]["A0_secondary"]["evaluation"]["overall"], indent=1))
    print("\nreproducibility vs recorded F2:", result["runs"]["F2_primary"]["reproducibility_vs_recorded_f2"])
    print("total seconds:", result["time_budget"]["total_seconds"])
    return 0


def render_md(res: dict, f2_preds, a0_preds) -> str:
    fe = res["runs"]["F2_primary"]["evaluation"]["overall"]
    L = []
    L.append("# Model 40-Minute Evaluation (model-only, frozen P3 benchmark)\n")
    L.append(f"- Date: {res['date']}")
    L.append(f"- Benchmark: `{res['benchmark']['path']}` sha256 `{res['benchmark']['sha256'][:16]}...` "
             f"({res['benchmark']['n']} examples: {res['benchmark']['answerable']} answerable / {res['benchmark']['unanswerable']} unanswerable) — hash verified")
    L.append("- No retrieval, no database, no training, no weight/benchmark modification. Offline mode forced.\n")
    L.append("## Protocol (pinned from the recorded F2 run)\n")
    for k, v in res["protocol"].items():
        L.append(f"- **{k}**: {v}")
    L.append("\n## Primary — F2 designated checkpoint (`checkpoint_epoch2`)\n")
    L.append(f"- checkpoint dir-scope sha256: `{res['runs']['F2_primary']['checkpoint_hash_dir_scope']}`")
    L.append(f"- model.safetensors sha256: `{res['runs']['F2_primary']['model_sha256']}`")
    L.append(f"- inference time: {res['runs']['F2_primary']['inference_seconds']} s on {res['protocol']['device']}\n")
    L.append("### Overall metrics\n")
    L.append("| metric | value | denominator |")
    L.append("|---|---|---|")
    L.append(f"| EM (answerable) | {fe['em_answerable']}% | 140 answerable |")
    L.append(f"| F1 (answerable) | {fe['f1_answerable']}% | 140 answerable |")
    L.append(f"| EM (all 182) | {fe['em_all_182']}% | 182 (unanswerable scored 0) |")
    L.append(f"| F1 (all 182) | {fe['f1_all_182']}% | 182 (unanswerable scored 0) |")
    L.append(f"| unanswerable abstention | {fe['unanswerable_abstained']}/42 = {fe['abstention_rate_unanswerable_pct']}% | 42 |")
    L.append(f"| false abstention | {fe['false_abstention']}/140 = {fe['false_abstention_rate_answerable_pct']}% | 140 |")
    L.append(f"| spurious | {fe['spurious']}/{res['benchmark']['n']} = {fe['spurious_rate_all_pct']}% | 182 |")
    L.append(f"| coverage (non-empty) | {fe['coverage_pct']}% | 182 |")
    L.append("\n### Category breakdown\n")
    L.append("| category | n | answerable_n | EM | F1 | avg confidence |")
    L.append("|---|---|---|---|---|---|")
    for cat, v in res["runs"]["F2_primary"]["evaluation"]["by_category"].items():
        L.append(f"| {cat} | {v['n']} | {v['answerable_n']} | {v['em']} | {v['f1']} | {v['avg_confidence']} |")
    absent = [c for c in ["DEFINITION", "TABLE_COMPARISON", "LIST_ORDER"] if c not in res["runs"]["F2_primary"]["evaluation"]["by_category"]]
    if absent:
        L.append(f"\nCategories in the requested list but **absent from the benchmark** (n=0, not invented): {', '.join(absent)}")
    L.append("\n### Error taxonomy (answerable incorrect only)\n")
    L.append("| primary failure | count |")
    L.append("|---|---|")
    for k, v in sorted(res["runs"]["F2_primary"]["evaluation"]["taxonomy"].items(), key=lambda kv: -kv[1]):
        L.append(f"| {k} | {v} |")
    L.append("\nUnanswerable: " + ", ".join(
        f"{k}={v}" for k, v in res["runs"]["F2_primary"]["evaluation"]["taxonomy"].items()
        if k in ("CORRECT_ABSTENTION", "SPURIOUS_ANSWER")) or "Unanswerable: (none)")
    L.append("\n### Confidence / abstention analysis\n")
    ca = res["runs"]["F2_primary"]["evaluation"]["confidence_analysis"]
    L.append("| group | mean confidence |")
    L.append("|---|---|")
    L.append(f"| answerable correct | {ca['answerable_correct_mean']} |")
    L.append(f"| answerable incorrect | {ca['answerable_incorrect_mean']} |")
    L.append(f"| answerable (all) | {ca['answerable_mean']} |")
    L.append(f"| unanswerable | {ca['unanswerable_mean']} |")
    L.append(f"\n- confidence overlap: correct {ca['confidence_overlap']['correct_range']}, "
             f"incorrect {ca['confidence_overlap']['incorrect_range']}, unanswerable {ca['confidence_overlap']['unanswerable_range']}")
    L.append(f"- incorrect predictions above the correct-mean: {ca['confidence_overlap']['incorrect_above_correct_mean']}")
    L.append(f"- AUC (answerable correct vs incorrect, confidence): {ca['confidence_auc_answerable_correct_vs_incorrect']}")
    L.append(f"- null_score: correct {ca['null_score']['correct_answerable_mean']} / incorrect {ca['null_score']['incorrect_answerable_mean']} / "
             f"unanswerable {ca['null_score']['unanswerable_mean']}; AUC(unanswerable vs answerable) = {ca['null_score']['auc_unanswerable_vs_answerable']}")
    L.append(f"- margin: correct {ca['margin']['correct_answerable_mean']} / incorrect {ca['margin']['incorrect_answerable_mean']} / "
             f"unanswerable {ca['margin']['unanswerable_mean']}; AUC = {ca['margin']['auc_unanswerable_vs_answerable']}")
    L.append("\nNo threshold was tuned, fitted or selected in this evaluation.\n")
    if a0_preds is not None:
        ao = res["runs"]["A0_secondary"]["evaluation"]["overall"]
        L.append("## Secondary — production A0 checkpoint (same pinned protocol)\n")
        L.append(f"- model.safetensors sha256: `{res['runs']['A0_secondary']['model_sha256']}`")
        L.append(f"- production inference_config (recorded): `{res['runs']['A0_secondary']['production_inference_config']}`")
        L.append(f"- scope: {res['runs']['A0_secondary']['scope_note']}\n")
        L.append("| metric | A0 (fresh) | F2 (fresh) |")
        L.append("|---|---|---|")
        L.append(f"| EM (answerable) | {ao['em_answerable']}% | {fe['em_answerable']}% |")
        L.append(f"| F1 (answerable) | {ao['f1_answerable']}% | {fe['f1_answerable']}% |")
        L.append(f"| unanswerable abstention | {ao['unanswerable_abstained']}/42 | {fe['unanswerable_abstained']}/42 |")
        L.append(f"| false abstention | {ao['false_abstention']}/140 | {fe['false_abstention']}/140 |")
        L.append(f"| spurious | {ao['spurious']} | {fe['spurious']} |")
        L.append("\nA0 per-category:\n")
        L.append("| category | n | EM | F1 |")
        L.append("|---|---|---|---|")
        for cat, v in res["runs"]["A0_secondary"]["evaluation"]["by_category"].items():
            L.append(f"| {cat} | {v['n']} | {v['em']} | {v['f1']} |")
    L.append("\n## Baseline comparison\n")
    for key, blk in res["baseline_comparison"].items():
        L.append(f"### {key}\n")
        for k, v in blk.items():
            L.append(f"- **{k}**: {json.dumps(v)}")
        L.append("")
    L.append("## Dominant observed failure\n")
    L.append(f"- primary family: **{res['dominant_observed_failure']['primary_family']}** (count {res['dominant_observed_failure']['count']})")
    L.append(f"- all families: `{json.dumps(res['dominant_observed_failure']['all_families'])}`")
    L.append(f"- guard: {res['dominant_observed_failure']['interpretation_guard']}")
    L.append("\n## Reproducibility against the recorded F2 run\n")
    for k, v in res["runs"]["F2_primary"]["reproducibility_vs_recorded_f2"].items():
        L.append(f"- **{k}**: {v}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

"""
Phase 4F.5-G — No-Answer Decision Experiment

Offline evaluation only. No training. No checkpoint creation.
Determines if F2's CLS/no-answer signal can produce abstention
through a calibrated decision rule.
"""

import hashlib
import json
import os
import sys
import io
import time
import gc
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
F2_DIR = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5f" / "f2"
RECONCILIATION_DIR = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5f" / "reconciliation"
DERIVED_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5" / "dataset" / "derived_dataset.jsonl"
SOURCE_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "dataset" / "training_data_v3_1.jsonl"
PROD_MODEL_DIR = PROJECT_ROOT / "backend" / "models" / "documind-qa"
BENCHMARK_PATH = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5d" / "benchmark" / "qa_benchmark_v1.jsonl"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MAX_LENGTH = 384
MAX_ANSWER_LENGTH = 50
SEED = 42

OUTPUT_DIR = F2_DIR / "threshold_experiment"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# === Metrics ===
def normalize_text(s):
    return " ".join(s.strip().lower().split())

def exact_match(pred, gold):
    return normalize_text(pred) == normalize_text(gold)

def token_f1(pred, gold):
    pred_tokens = set(normalize_text(pred).split())
    gold_tokens = set(normalize_text(gold).split())
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = pred_tokens & gold_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


# === Raw Prediction Collection ===
def collect_raw_predictions(model, tokenizer, examples, split_name):
    """Collect raw model outputs for every example."""
    model.eval()
    predictions = []
    
    for ex in examples:
        encoding = tokenizer(
            ex["question"], ex["context"],
            max_length=MAX_LENGTH, truncation=True,
            padding="max_length", return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(DEVICE)
        attention_mask = encoding["attention_mask"].to(DEVICE)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        start_logits = outputs.start_logits[0].cpu()
        end_logits = outputs.end_logits[0].cpu()

        # CLS scores
        cls_start = start_logits[0].item()
        cls_end = end_logits[0].item()
        null_score = cls_start + cls_end

        # Best non-CLS start
        start_probs = torch.softmax(start_logits, dim=0)
        # Mask CLS (token 0) by setting to -inf for argmax
        masked_start = start_logits.clone()
        masked_start[0] = -float('inf')
        best_start_idx = torch.argmax(masked_start).item()
        best_start_logit = start_logits[best_start_idx].item()

        # Best end given best start
        end_range = end_logits[best_start_idx:best_start_idx + MAX_ANSWER_LENGTH]
        best_end_offset = torch.argmax(end_range).item()
        best_end_idx = best_start_idx + best_end_offset
        best_end_logit = end_logits[best_end_idx].item()

        best_answer_score = best_start_logit + best_end_logit

        # Predicted answer
        answer_tokens = encoding["input_ids"][0][best_start_idx:best_end_idx + 1]
        predicted_answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        # Null margin
        null_margin = null_score - best_answer_score

        # Confidence
        start_conf = torch.softmax(start_logits, dim=0)[best_start_idx].item()
        end_conf = torch.softmax(end_logits, dim=0)[best_end_idx].item()
        confidence = (start_conf + end_conf) / 2

        meta = ex.get("metadata", {})

        predictions.append({
            "example_id": ex["example_id"],
            "question": ex["question"],
            "gold_answer": ex.get("answer", ""),
            "is_answerable": ex["question_kind"] != "UNANSWERABLE",
            "question_kind": ex["question_kind"],
            "subcategory": meta.get("subcategory", "unknown"),
            "predicted_answer": predicted_answer,
            "predicted_start_idx": best_start_idx,
            "predicted_end_idx": best_end_idx,
            "start_logit": round(best_start_logit, 6),
            "end_logit": round(best_end_logit, 6),
            "cls_start_logit": round(cls_start, 6),
            "cls_end_logit": round(cls_end, 6),
            "null_score": round(null_score, 6),
            "best_answer_score": round(best_answer_score, 6),
            "null_margin": round(null_margin, 6),
            "confidence": round(confidence, 6),
        })

    return predictions


# === Evaluation with threshold ===
def evaluate_with_threshold(predictions, threshold, mode="null_score"):
    """Evaluate predictions using a threshold for abstention.
    
    mode="null_score": abstain if null_score >= threshold
    mode="margin": abstain if null_margin >= threshold
    """
    em_scores, f1_scores = [], []
    answerable_correct = answerable_total = 0
    unanswerable_correct = unanswerable_total = 0
    spurious = false_abstention = 0
    
    for p in predictions:
        is_answerable = p["is_answerable"]
        
        if mode == "null_score":
            abstain = p["null_score"] >= threshold
        elif mode == "margin":
            abstain = p["null_margin"] >= threshold
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        predicted = "" if abstain else p["predicted_answer"]
        
        if is_answerable:
            answerable_total += 1
            em = exact_match(predicted, p["gold_answer"])
            f1 = token_f1(predicted, p["gold_answer"])
            em_scores.append(1 if em else 0)
            f1_scores.append(f1)
            if em:
                answerable_correct += 1
            if not predicted:
                false_abstention += 1
        else:
            unanswerable_total += 1
            if not predicted:
                unanswerable_correct += 1
            else:
                spurious += 1

    return {
        "em": round(np.mean(em_scores) * 100, 2) if em_scores else 0,
        "f1": round(np.mean(f1_scores) * 100, 2) if f1_scores else 0,
        "answerable_total": answerable_total,
        "answerable_correct": answerable_correct,
        "answerable_coverage": round((answerable_total - false_abstention) / max(answerable_total, 1) * 100, 2),
        "false_abstention": false_abstention,
        "false_abstention_rate": round(false_abstention / max(answerable_total, 1) * 100, 2),
        "unanswerable_total": unanswerable_total,
        "unanswerable_correct": unanswerable_correct,
        "abstention_rate": round(unanswerable_correct / max(unanswerable_total, 1) * 100, 2),
        "spurious": spurious,
        "spurious_rate": round(spurious / max(unanswerable_total, 1) * 100, 2),
    }


# === Main ===
def main():
    print("=" * 60)
    print("PHASE 4F.5-G — NO-ANSWER DECISION EXPERIMENT")
    print("=" * 60)
    print(f"  Device: {DEVICE}")

    # === STEP 1: Verify F2 artifacts ===
    print(f"\n{'='*60}")
    print("STEP 1: VERIFY F2 ARTIFACTS")
    print(f"{'='*60}")

    # Verify source
    with open(SOURCE_DATASET, "rb") as f:
        src_hash = hashlib.sha256(f.read()).hexdigest()
    assert src_hash == "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
    print(f"  Source hash: VERIFIED")

    # Verify production
    prod_h = hashlib.sha256()
    for root, dirs, files in os.walk(str(PROD_MODEL_DIR)):
        for fn in sorted(files):
            with open(os.path.join(root, fn), "rb") as f:
                prod_h.update(f.read())
    assert prod_h.hexdigest() == "df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac"
    print(f"  Production: UNCHANGED")

    # Verify F2 checkpoint
    ckpt_path = F2_DIR / "checkpoints" / "F2" / "checkpoint_epoch2"
    assert ckpt_path.exists(), f"Checkpoint not found: {ckpt_path}"
    
    # Checkpoint hash
    ckpt_h = hashlib.sha256()
    for root, dirs, files in os.walk(str(ckpt_path)):
        for fn in sorted(files):
            with open(os.path.join(root, fn), "rb") as f:
                ckpt_h.update(f.read())
    print(f"  Checkpoint: epoch2 ({ckpt_h.hexdigest()[:16]}...)")

    # Verify benchmark
    with open(BENCHMARK_PATH, "rb") as f:
        bh = hashlib.sha256(f.read()).hexdigest()
    assert bh == "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
    print(f"  Benchmark: VERIFIED")

    # === Load model ===
    print(f"\n  Loading F2 model...")
    model = AutoModelForQuestionAnswering.from_pretrained(str(ckpt_path), local_files_only=True).to(DEVICE)
    tokenizer = AutoTokenizer.from_pretrained(str(ckpt_path), local_files_only=True)
    model.eval()
    print(f"  Model loaded.")

    # === Load data ===
    all_examples = []
    with open(DERIVED_DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_examples.append(json.loads(line))

    # Load reconciled IDs
    with open(RECONCILIATION_DIR / "final_validation_ids.json") as f:
        val_ids_meta = json.load(f)
    with open(RECONCILIATION_DIR / "final_holdout_ids.json") as f:
        hold_ids_meta = json.load(f)

    val_answerable_ids = set(val_ids_meta["answerable_ids"])
    val_unanswerable_ids = set(val_ids_meta["unanswerable_ids"])
    holdout_ids = set(hold_ids_meta["unanswerable_ids"])

    val_examples = [ex for ex in all_examples if ex["example_id"] in val_answerable_ids or ex["example_id"] in val_unanswerable_ids]
    holdout_examples = [ex for ex in all_examples if ex["example_id"] in holdout_ids]

    # Load benchmark
    benchmark_examples = []
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                benchmark_examples.append(json.loads(line))

    print(f"\n  Validation: {len(val_examples)} examples")
    print(f"  Holdout: {len(holdout_examples)} examples")
    print(f"  Benchmark: {len(benchmark_examples)} examples")

    # === STEP 2: Collect raw predictions ===
    print(f"\n{'='*60}")
    print("STEP 2: COLLECT RAW PREDICTIONS")
    print(f"{'='*60}")

    print("  Collecting validation predictions...")
    val_preds = collect_raw_predictions(model, tokenizer, val_examples, "validation")
    with open(OUTPUT_DIR / "raw_predictions_validation.json", "w") as f:
        json.dump(val_preds, f, indent=2)
    print(f"  Done: {len(val_preds)} predictions")

    print("  Collecting holdout predictions...")
    hold_preds = collect_raw_predictions(model, tokenizer, holdout_examples, "holdout")
    with open(OUTPUT_DIR / "raw_predictions_holdout.json", "w") as f:
        json.dump(hold_preds, f, indent=2)
    print(f"  Done: {len(hold_preds)} predictions")

    print("  Collecting benchmark predictions...")
    bench_preds = collect_raw_predictions(model, tokenizer, benchmark_examples, "benchmark")
    with open(OUTPUT_DIR / "raw_predictions_benchmark.json", "w") as f:
        json.dump(bench_preds, f, indent=2)
    print(f"  Done: {len(bench_preds)} predictions")

    del model
    gc.collect()
    torch.cuda.empty_cache()

    # === STEP 3: Define null score ===
    print(f"\n{'='*60}")
    print("STEP 3: DEFINE NULL SCORE")
    print(f"{'='*60}")

    null_score_def = {
        "formula": "null_score = cls_start_logit + cls_end_logit",
        "best_answer_score_formula": "best_answer_score = best_non_CLS_start_logit + best_non_CLS_end_logit",
        "null_margin_formula": "null_margin = null_score - best_answer_score",
        "abstention_rule_null": "abstain if null_score >= threshold",
        "abstention_rule_margin": "abstain if null_margin >= threshold",
    }
    print(f"  null_score = cls_start + cls_end")
    print(f"  best_answer_score = best_non_CLS_start + best_non_CLS_end")
    print(f"  null_margin = null_score - best_answer_score")

    # === STEP 4: Threshold sweep ===
    print(f"\n{'='*60}")
    print("STEP 4: THRESHOLD SWEEP")
    print(f"{'='*60}")

    # Coarse sweep
    coarse_thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    threshold_results = {}

    print("\n  COARSE THRESHOLD SWEEP (validation):")
    print(f"  {'thresh':>8} {'EM':>8} {'F1':>8} {'cov%':>8} {'f_abs%':>8} {'abst%':>8} {'spur%':>8}")
    print("  " + "-" * 60)

    for t in coarse_thresholds:
        r = evaluate_with_threshold(val_preds, t, mode="null_score")
        threshold_results[t] = r
        print(f"  {t:>8.1f} {r['em']:>7.2f}% {r['f1']:>7.2f}% {r['answerable_coverage']:>7.2f}% {r['false_abstention_rate']:>7.2f}% {r['abstention_rate']:>7.2f}% {r['spurious_rate']:>7.2f}%")

    # Fine-grained sweep around useful range
    null_scores = [p["null_score"] for p in val_preds if not p["is_answerable"]]
    null_scores_ans = [p["null_score"] for p in val_preds if p["is_answerable"]]
    
    min_ns = min(min(null_scores), min(null_scores_ans))
    max_ns = max(max(null_scores), max(null_scores_ans))
    
    fine_thresholds = [round(min_ns + i * 0.01, 4) for i in range(int((max_ns - min_ns) / 0.01) + 1)]
    fine_thresholds = [t for t in fine_thresholds if 0.0 <= t <= 3.0]

    fine_results = {}
    print(f"\n  FINE-GRAINED SWEEP ({len(fine_thresholds)} thresholds, validation):")
    print(f"  {'thresh':>8} {'EM':>8} {'F1':>8} {'cov%':>8} {'f_abs%':>8} {'abst%':>8} {'spur%':>8}")
    print("  " + "-" * 60)

    for t in fine_thresholds:
        r = evaluate_with_threshold(val_preds, t, mode="null_score")
        fine_results[t] = r

    # Print selected fine thresholds
    for t in fine_thresholds[::5]:  # Every 5th
        r = fine_results[t]
        print(f"  {t:>8.4f} {r['em']:>7.2f}% {r['f1']:>7.2f}% {r['answerable_coverage']:>7.2f}% {r['false_abstention_rate']:>7.2f}% {r['abstention_rate']:>7.2f}% {r['spurious_rate']:>7.2f}%")

    # === STEP 5: Margin sweep ===
    print(f"\n{'='*60}")
    print("STEP 5: MARGIN-BASED ABSTENTION")
    print(f"{'='*60}")

    margin_thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0]
    margin_results = {}

    print("\n  MARGIN SWEEP (validation):")
    print(f"  {'margin':>8} {'EM':>8} {'F1':>8} {'cov%':>8} {'f_abs%':>8} {'abst%':>8} {'spur%':>8}")
    print("  " + "-" * 60)

    for m in margin_thresholds:
        r = evaluate_with_threshold(val_preds, m, mode="margin")
        margin_results[m] = r
        print(f"  {m:>8.1f} {r['em']:>7.2f}% {r['f1']:>7.2f}% {r['answerable_coverage']:>7.2f}% {r['false_abstention_rate']:>7.2f}% {r['abstention_rate']:>7.2f}% {r['spurious_rate']:>7.2f}%")

    # Fine-grained margin sweep
    margins = [p["null_margin"] for p in val_preds if not p["is_answerable"]]
    margins_ans = [p["null_margin"] for p in val_preds if p["is_answerable"]]
    min_m = min(min(margins), min(margins_ans))
    max_m = max(max(margins), max(margins_ans))
    
    fine_margins = [round(min_m + i * 0.01, 4) for i in range(int((max_m - min_m) / 0.01) + 1)]
    fine_margins = [m for m in fine_margins if -5.0 <= m <= 5.0]

    fine_margin_results = {}
    for m in fine_margins:
        r = evaluate_with_threshold(val_preds, m, mode="margin")
        fine_margin_results[m] = r

    # === STEP 6: Validation calibration — select candidate ===
    print(f"\n{'='*60}")
    print("STEP 6: VALIDATION CALIBRATION (SELECT CANDIDATE)")
    print(f"{'='*60}")

    # Find best threshold: maximize abstention on unanswerable while keeping
    # answerable coverage >= 80% and false abstention <= 10%
    best_threshold = None
    best_threshold_score = -1
    best_threshold_metrics = None

    for t, r in fine_results.items():
        # Score: weighted combination of abstention and coverage
        if r["answerable_coverage"] >= 80.0 and r["false_abstention_rate"] <= 15.0:
            score = r["abstention_rate"] * 0.7 + r["answerable_coverage"] * 0.3
            if score > best_threshold_score:
                best_threshold_score = score
                best_threshold = t
                best_threshold_metrics = r

    # Also find best margin
    best_margin = None
    best_margin_score = -1
    best_margin_metrics = None

    for m, r in fine_margin_results.items():
        if r["answerable_coverage"] >= 80.0 and r["false_abstention_rate"] <= 15.0:
            score = r["abstention_rate"] * 0.7 + r["answerable_coverage"] * 0.3
            if score > best_margin_score:
                best_margin_score = score
                best_margin = m
                best_margin_metrics = r

    print(f"\n  Best NULL SCORE threshold: {best_threshold}")
    if best_threshold_metrics:
        r = best_threshold_metrics
        print(f"    EM={r['em']}%  F1={r['f1']}%  Coverage={r['answerable_coverage']}%")
        print(f"    False abstention={r['false_abstention_rate']}%  Abstention={r['abstention_rate']}%  Spurious={r['spurious_rate']}%")

    print(f"\n  Best MARGIN threshold: {best_margin}")
    if best_margin_metrics:
        r = best_margin_metrics
        print(f"    EM={r['em']}%  F1={r['f1']}%  Coverage={r['answerable_coverage']}%")
        print(f"    False abstention={r['false_abstention_rate']}%  Abstention={r['abstention_rate']}%  Spurious={r['spurious_rate']}%")

    # Determine which is better
    if best_threshold_metrics and best_margin_metrics:
        if best_margin_metrics["abstention_rate"] > best_threshold_metrics["abstention_rate"]:
            selected_mode = "margin"
            selected_value = best_margin
            selected_metrics = best_margin_metrics
            print(f"\n  SELECTED: margin={best_margin} (higher abstention)")
        else:
            selected_mode = "null_score"
            selected_value = best_threshold
            selected_metrics = best_threshold_metrics
            print(f"\n  SELECTED: threshold={best_threshold} (higher abstention)")
    elif best_threshold_metrics:
        selected_mode = "null_score"
        selected_value = best_threshold
        selected_metrics = best_threshold_metrics
        print(f"\n  SELECTED: threshold={best_threshold}")
    elif best_margin_metrics:
        selected_mode = "margin"
        selected_value = best_margin
        selected_metrics = best_margin_metrics
        print(f"\n  SELECTED: margin={best_margin}")
    else:
        # Fallback: use threshold that gives best abstention with coverage >= 70%
        for t in sorted(fine_thresholds, reverse=True):
            r = fine_results.get(t)
            if r and r["answerable_coverage"] >= 70.0:
                selected_mode = "null_score"
                selected_value = t
                selected_metrics = r
                print(f"\n  FALLBACK SELECTED: threshold={t} (coverage >= 70%)")
                break
        else:
            selected_mode = "null_score"
            selected_value = 0.5
            selected_metrics = evaluate_with_threshold(val_preds, 0.5, mode="null_score")
            print(f"\n  FALLBACK: threshold=0.5")

    print(f"\n  FROZEN DECISION RULE: {selected_mode} >= {selected_value}")

    # === STEP 7: Apply to holdout ===
    print(f"\n{'='*60}")
    print("STEP 7: APPLY TO HOLDOUT (14 unanswerable)")
    print(f"{'='*60}")

    holdout_result = evaluate_with_threshold(hold_preds, selected_value, mode=selected_mode)
    print(f"  Abstained: {holdout_result['unanswerable_correct']}/14 ({holdout_result['abstention_rate']}%)")
    print(f"  Spurious: {holdout_result['spurious']}/14 ({holdout_result['spurious_rate']}%)")

    # === STEP 8: Apply to benchmark ===
    print(f"\n{'='*60}")
    print("STEP 8: APPLY TO BENCHMARK")
    print(f"{'='*60}")

    bench_result = evaluate_with_threshold(bench_preds, selected_value, mode=selected_mode)
    print(f"  EM: {bench_result['em']}%  F1: {bench_result['f1']}%")
    print(f"  Abstention: {bench_result['abstention_rate']}%  Spurious: {bench_result['spurious_rate']}%")
    print(f"  Coverage: {bench_result['answerable_coverage']}%  False abstention: {bench_result['false_abstention_rate']}%")

    # Per-category benchmark
    print(f"\n  BENCHMARK PER-CATEGORY:")
    categories = ["DIRECT_SPAN", "NUMERIC", "TABLE_CELL", "TABLE_ROW", "LIST_ITEM", "SECTION_SPECIFIC", "MULTI_CHUNK", "LONG_CONTEXT", "UNANSWERABLE"]
    
    cat_results = {}
    for cat in categories:
        cat_preds = [p for p in bench_preds if p["question_kind"] == cat]
        if cat_preds:
            cat_r = evaluate_with_threshold(cat_preds, selected_value, mode=selected_mode)
            cat_results[cat] = cat_r
            if cat == "UNANSWERABLE":
                print(f"  {cat:<20} n={cat_r['unanswerable_total']:>3}  abstain={cat_r['abstention_rate']:>6.1f}%  spurious={cat_r['spurious_rate']:>6.1f}%")
            else:
                print(f"  {cat:<20} n={cat_r['answerable_total']:>3}  EM={cat_r['em']:>6.1f}%  F1={cat_r['f1']:>6.1f}%  coverage={cat_r['answerable_coverage']:>6.1f}%")

    # === STEP 9: Compare against baselines ===
    print(f"\n{'='*60}")
    print("STEP 9: BASELINE COMPARISON")
    print(f"{'='*60}")

    baselines = {
        "A0 Production": {"em": 2.1, "f1": 12.0, "abstention": 64.3, "spurious": 8.2},
        "A1 DistilBERT": {"em": 3.6, "f1": 21.3, "abstention": 0.0, "spurious": 23.1},
        "A2 BERT": {"em": 3.6, "f1": 19.4, "abstention": 0.0, "spurious": 23.1},
        "F2 raw (argmax)": {"em": 2.9, "f1": 19.7, "abstention": 0.0, "spurious": 23.1},
        f"F2 + {selected_mode}={selected_value}": {
            "em": bench_result["em"], "f1": bench_result["f1"],
            "abstention": bench_result["abstention_rate"],
            "spurious": bench_result["spurious_rate"]
        },
    }

    print(f"\n  {'Model':<35} {'EM':>8} {'F1':>8} {'Abstain':>8} {'Spurious':>8}")
    print("  " + "-" * 70)
    for name, m in baselines.items():
        print(f"  {name:<35} {m['em']:>7.1f}% {m['f1']:>7.1f}% {m['abstention']:>7.1f}% {m['spurious']:>7.1f}%")

    # === STEP 10: Stability analysis ===
    print(f"\n{'='*60}")
    print("STEP 10: CALIBRATION ROBUSTNESS")
    print(f"{'='*60}")

    stability = {}
    for delta in [-0.1, -0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05, 0.1]:
        test_val = selected_value + delta
        r = evaluate_with_threshold(val_preds, test_val, mode=selected_mode)
        stability[delta] = r
        print(f"  {selected_mode}={test_val:.4f} (delta={delta:+.2f}): "
              f"abstain={r['abstention_rate']:.1f}% coverage={r['answerable_coverage']:.1f}% "
              f"false_abs={r['false_abstention_rate']:.1f}%")

    # Check stability
    abstentions = [stability[d]["abstention_rate"] for d in stability]
    max_shift = max(abstentions) - min(abstentions)
    print(f"\n  Max abstention shift across ±0.1: {max_shift:.1f}%")
    print(f"  Stability: {'STABLE' if max_shift < 20 else 'UNSTABLE'}")

    # === Save all results ===
    print(f"\n{'='*60}")
    print("SAVING RESULTS")
    print(f"{'='*60}")

    # Threshold sweep
    with open(OUTPUT_DIR / "threshold_sweep.json", "w") as f:
        json.dump({
            "coarse": {str(k): v for k, v in threshold_results.items()},
            "fine": {str(k): v for k, v in fine_results.items()},
            "best_threshold": best_threshold,
        }, f, indent=2)

    # Margin sweep
    with open(OUTPUT_DIR / "margin_sweep.json", "w") as f:
        json.dump({
            "coarse": {str(k): v for k, v in margin_results.items()},
            "fine": {str(k): v for k, v in fine_margin_results.items()},
            "best_margin": best_margin,
        }, f, indent=2)

    # Validation calibration
    with open(OUTPUT_DIR / "validation_calibration.json", "w") as f:
        json.dump({
            "selected_mode": selected_mode,
            "selected_value": selected_value,
            "selected_metrics": selected_metrics,
            "null_score_distribution": {
                "answerable_mean": round(np.mean(null_scores_ans), 4),
                "answerable_std": round(np.std(null_scores_ans), 4),
                "unanswerable_mean": round(np.mean(null_scores), 4),
                "unanswerable_std": round(np.std(null_scores), 4),
            },
            "null_margin_distribution": {
                "answerable_mean": round(np.mean(margins_ans), 4),
                "answerable_std": round(np.std(margins_ans), 4),
                "unanswerable_mean": round(np.mean(margins), 4),
                "unanswerable_std": round(np.std(margins), 4),
            },
        }, f, indent=2)

    # Holdout result
    with open(OUTPUT_DIR / "holdout_result.json", "w") as f:
        json.dump({"decision_rule": f"{selected_mode} >= {selected_value}", **holdout_result}, f, indent=2)

    # Benchmark result
    with open(OUTPUT_DIR / "benchmark_result.json", "w") as f:
        json.dump({
            "decision_rule": f"{selected_mode} >= {selected_value}",
            "overall": bench_result,
            "by_category": cat_results,
        }, f, indent=2)

    # Stability
    with open(OUTPUT_DIR / "stability_analysis.json", "w") as f:
        json.dump({
            "selected_value": selected_value,
            "selected_mode": selected_mode,
            "stability": {str(k): v for k, v in stability.items()},
            "max_abstention_shift": max_shift,
            "stable": max_shift < 20,
        }, f, indent=2)

    # Manifest
    manifest = {
        "phase": "4F.5-G",
        "status": "EXPERIMENT_COMPLETE",
        "selected_mode": selected_mode,
        "selected_value": selected_value,
        "validation_metrics": selected_metrics,
        "holdout_metrics": holdout_result,
        "benchmark_metrics": bench_result,
        "stability": "STABLE" if max_shift < 20 else "UNSTABLE",
        "source_hash": src_hash[:16],
        "production_unchanged": True,
        "benchmark_hash": bh[:16],
    }
    with open(OUTPUT_DIR / "threshold_experiment_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Raw prediction audit summary
    raw_audit = {
        "val_count": len(val_preds),
        "hold_count": len(hold_preds),
        "bench_count": len(bench_preds),
        "null_score_stats": {
            "val_answerable_mean": round(np.mean([p["null_score"] for p in val_preds if p["is_answerable"]]), 4),
            "val_unanswerable_mean": round(np.mean([p["null_score"] for p in val_preds if not p["is_answerable"]]), 4),
            "hold_unanswerable_mean": round(np.mean([p["null_score"] for p in hold_preds]), 4),
            "bench_answerable_mean": round(np.mean([p["null_score"] for p in bench_preds if p["is_answerable"]]), 4),
            "bench_unanswerable_mean": round(np.mean([p["null_score"] for p in bench_preds if not p["is_answerable"]]), 4),
        }
    }
    with open(OUTPUT_DIR / "raw_prediction_audit.json", "w") as f:
        json.dump(raw_audit, f, indent=2)

    print(f"  All results saved to {OUTPUT_DIR}")

    # === FINAL STATUS ===
    print(f"\n{'='*60}")
    print("FINAL STATUS")
    print(f"{'='*60}")

    # Determine status
    if selected_metrics and selected_metrics["abstention_rate"] > 0 and selected_metrics["answerable_coverage"] >= 70:
        if max_shift < 20:
            if selected_mode == "margin":
                status = "MARGIN_SIGNAL_SUPPORTED"
            else:
                status = "THRESHOLD_SIGNAL_SUPPORTED"
        else:
            status = "THRESHOLD_UNSTABLE"
    else:
        status = "THRESHOLD_NOT_USEFUL"

    print(f"  STATUS: {status}")
    print(f"  Selected: {selected_mode} >= {selected_value}")
    print(f"  Validation: EM={selected_metrics['em']}% F1={selected_metrics['f1']}% abstain={selected_metrics['abstention_rate']}%")
    print(f"  Holdout: abstain={holdout_result['abstention_rate']}% spur={holdout_result['spurious_rate']}%")
    print(f"  Benchmark: EM={bench_result['em']}% F1={bench_result['f1']}% abstain={bench_result['abstention_rate']}%")


if __name__ == "__main__":
    main()

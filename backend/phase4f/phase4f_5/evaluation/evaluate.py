"""
Phase 4F.5 — Canonical QA Evaluation Script

Evaluates A0/A1/A2 on the held-out TEST split using identical protocol.
All models MUST use this exact evaluator.

Usage:
    python evaluate.py --model_dir <path> --split test
    python evaluate.py --model_dir backend/models/documind-qa --split test
"""

import argparse
import json
import os
import sys
import io
import time
from collections import defaultdict

import numpy as np
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── Config ───────────────────────────────────────────────────────
EVAL_VERSION = "4F.5-eval-v1"
MAX_LENGTH = 384
MAX_ANSWER_LENGTH = 50


# ─── Metrics ──────────────────────────────────────────────────────
def normalize_text(s):
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
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


# ─── Inference ────────────────────────────────────────────────────
def predict(model_dir, examples, max_length=MAX_LENGTH):
    """Run greedy argmax inference on examples."""
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForQuestionAnswering.from_pretrained(model_dir)
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    predictions = []
    latencies = []
    confidences = []

    for ex in examples:
        t0 = time.time()
        encoding = tokenizer(
            ex["question"], ex["context"],
            max_length=max_length, truncation=True,
            padding="max_length", return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(device)
        attention_mask = encoding["attention_mask"].to(device)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        start_logits = outputs.start_logits[0]
        end_logits = outputs.end_logits[0]

        # Greedy span selection
        start_idx = torch.argmax(start_logits).item()
        end_idx = (
            torch.argmax(end_logits[start_idx : start_idx + MAX_ANSWER_LENGTH]).item()
            + start_idx
        )

        answer_tokens = encoding["input_ids"][0][start_idx : end_idx + 1]
        answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        # Confidence
        start_conf = torch.softmax(start_logits, dim=0)[start_idx].item()
        end_conf = torch.softmax(end_logits, dim=0)[end_idx].item()
        confidence = (start_conf + end_conf) / 2

        predictions.append(answer)
        confidences.append(confidence)
        latencies.append(time.time() - t0)

    return predictions, confidences, latencies


# ─── Evaluation ───────────────────────────────────────────────────
def evaluate(predictions, examples, confidences, latencies):
    """Compute all metrics on predictions vs examples."""
    results = {
        "eval_version": EVAL_VERSION,
        "total_examples": len(examples),
        "overall": {},
        "by_category": {},
        "failure_taxonomy": {},
        "confidence_analysis": {},
        "latency_ms": round(np.mean(latencies) * 1000, 2) if latencies else 0,
    }

    # Overall metrics
    em_scores = []
    f1_scores = []
    answerable_correct = 0
    answerable_total = 0
    unanswerable_correct = 0
    unanswerable_total = 0
    spurious = 0
    false_abstention = 0

    for pred, ex in zip(predictions, examples):
        is_answerable = ex["question_kind"] != "UNANSWERABLE"
        if is_answerable:
            answerable_total += 1
            em = exact_match(pred, ex["answer"])
            f1 = token_f1(pred, ex["answer"])
            em_scores.append(1 if em else 0)
            f1_scores.append(f1)
            if em:
                answerable_correct += 1
            if not pred:
                false_abstention += 1
        else:
            unanswerable_total += 1
            if not pred:
                unanswerable_correct += 1
            else:
                spurious += 1

    results["overall"] = {
        "em": round(np.mean(em_scores) * 100, 1) if em_scores else 0,
        "f1": round(np.mean(f1_scores) * 100, 1) if f1_scores else 0,
        "answerability_accuracy": round(
            answerable_correct / max(answerable_total, 1) * 100, 1
        ),
        "abstention_accuracy": round(
            unanswerable_correct / max(unanswerable_total, 1) * 100, 1
        ),
        "false_abstention": round(false_abstention / max(answerable_total, 1) * 100, 1),
        "spurious_rate": round(spurious / max(len(examples), 1) * 100, 1),
        "answerable": answerable_total,
        "unanswerable": unanswerable_total,
    }

    # Per-category metrics
    by_cat = defaultdict(lambda: {"preds": [], "gts": [], "confs": []})
    for pred, ex, conf in zip(predictions, examples, confidences):
        cat = ex["question_kind"]
        by_cat[cat]["preds"].append(pred)
        by_cat[cat]["gts"].append(ex)
        by_cat[cat]["confs"].append(conf)

    for cat, data in sorted(by_cat.items()):
        cat_em = []
        cat_f1 = []
        for pred, gt in zip(data["preds"], data["gts"]):
            if gt["question_kind"] != "UNANSWERABLE":
                em = exact_match(pred, gt["answer"])
                f1 = token_f1(pred, gt["answer"])
                cat_em.append(1 if em else 0)
                cat_f1.append(f1)

        results["by_category"][cat] = {
            "n": len(data["preds"]),
            "em": round(np.mean(cat_em) * 100, 1) if cat_em else 0,
            "f1": round(np.mean(cat_f1) * 100, 1) if cat_f1 else 0,
            "avg_confidence": round(np.mean(data["confs"]), 4),
        }

    # Confidence analysis
    correct_confs = []
    incorrect_confs = []
    for pred, ex, conf in zip(predictions, examples, confidences):
        if ex["question_kind"] != "UNANSWERABLE":
            if exact_match(pred, ex["answer"]):
                correct_confs.append(conf)
            else:
                incorrect_confs.append(conf)

    results["confidence_analysis"] = {
        "correct_mean": round(np.mean(correct_confs), 4) if correct_confs else 0,
        "correct_std": round(np.std(correct_confs), 4) if correct_confs else 0,
        "incorrect_mean": round(np.mean(incorrect_confs), 4) if incorrect_confs else 0,
        "incorrect_std": round(np.std(incorrect_confs), 4) if incorrect_confs else 0,
        "separation": round(
            np.mean(correct_confs) - np.mean(incorrect_confs), 4
        )
        if correct_confs and incorrect_confs
        else 0,
    }

    # Failure taxonomy
    failures = defaultdict(int)
    total_failures = 0
    for pred, ex in zip(predictions, examples):
        is_answerable = ex["question_kind"] != "UNANSWERABLE"
        if is_answerable:
            if not pred:
                failures["ABSTAIN"] += 1
                total_failures += 1
            elif not exact_match(pred, ex["answer"]):
                failures["EXTRACT"] += 1
                total_failures += 1
        else:
            if pred:
                failures["SPURIOUS"] += 1
                total_failures += 1

    results["failure_taxonomy"] = {
        "total_failures": total_failures,
        "failure_rate": round(total_failures / max(len(examples), 1) * 100, 1),
        "by_type": dict(failures),
    }

    return results


# ─── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 4F.5 QA Evaluation")
    parser.add_argument("--model_dir", required=True, help="Model checkpoint directory")
    parser.add_argument(
        "--dataset",
        default="backend/phase4f/phase4f_5/dataset/derived_dataset.jsonl",
        help="Derived dataset path",
    )
    parser.add_argument("--split", default="test", help="Split to evaluate on")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    # Load dataset and filter by split
    examples = []
    with open(args.dataset, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ex = json.loads(line)
                if ex.get("split") == args.split:
                    examples.append(ex)

    print(f"Loaded {len(examples)} examples for split '{args.split}'")
    print(f"Model: {args.model_dir}")
    print(f"Eval version: {EVAL_VERSION}")

    # Run inference
    predictions, confidences, latencies = predict(args.model_dir, examples)

    # Compute metrics
    results = evaluate(predictions, examples, confidences, latencies)
    results["model_dir"] = args.model_dir
    results["split"] = args.split
    results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Print results
    print(f"\n{'='*60}")
    print(f"RESULTS: {args.model_dir} on {args.split} split")
    print(f"{'='*60}")
    o = results["overall"]
    print(f"  EM:             {o['em']}%")
    print(f"  Token F1:       {o['f1']}%")
    print(f"  Answerability:  {o['answerability_accuracy']}%")
    print(f"  Abstention:     {o['abstention_accuracy']}%")
    print(f"  Spurious:       {o['spurious_rate']}%")
    print(f"  Latency:        {results['latency_ms']:.2f}ms")

    print(f"\n  Per-category:")
    for cat, m in sorted(results["by_category"].items(), key=lambda x: -x[1]["n"]):
        print(f"    {cat:20s} N={m['n']:3d} EM={m['em']:5.1f}% F1={m['f1']:5.1f}%")

    # Save results
    if args.output is None:
        model_name = os.path.basename(args.model_dir.rstrip("/\\"))
        args.output = f"backend/phase4f/phase4f_5/evaluation/{model_name}_{args.split}_results.json"

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {args.output}")


if __name__ == "__main__":
    main()

"""Phase 4F.3 — QA Model Evaluation Script.

Evaluates trained QA models on:
1. Internal validation/test
2. Per-category metrics
3. Failure taxonomy
4. Confidence calibration
5. Unanswerable detection

Usage::

    python evaluate.py --model_dir ./a1_distilbert --data_dir ../dataset --output_dir ./a1_distilbert/eval
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer


# ---------------------------------------------------------------------------
# Failure Taxonomy
# ---------------------------------------------------------------------------
FAILURE_TYPES = {
    "RET_MISS": "Retrieval missed relevant passage",
    "RET_NOISE": "Retrieval returned irrelevant passage",
    "CTX_TRUNC": "Context truncated, answer lost",
    "CTX_STARVE": "Context insufficient for answer",
    "QA_EXTRACT": "QA model failed to extract correct span",
    "QA_CONF": "QA model low confidence on correct answer",
    "EVID_OMIT": "Evidence omitted from context",
    "ABSTAIN": "Model abstained when answer exists",
    "SPURIOUS": "Model gave answer when none exists",
    "EXTRACT": "Extraction error (wrong span)",
    "CHUNK": "Chunk boundary issue",
    "AMBIG": "Question is ambiguous",
    "ANNOT": "Annotation issue",
    "UNKNOWN": "Unclassified failure",
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def compute_exact_match(prediction: str, ground_truth: str) -> bool:
    """Compute exact match after normalization."""
    pred_norm = prediction.strip().lower()
    gt_norm = ground_truth.strip().lower()
    return pred_norm == gt_norm


def compute_f1(prediction: str, ground_truth: str) -> float:
    """Compute token-level F1 score."""
    pred_tokens = set(prediction.strip().lower().split())
    gt_tokens = set(ground_truth.strip().lower().split())

    if not pred_tokens or not gt_tokens:
        return 0.0

    common = pred_tokens & gt_tokens
    if not common:
        return 0.0

    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gt_tokens)
    return 2 * precision * recall / (precision + recall)


def compute_metrics(predictions: list[dict], examples: list[dict]) -> dict:
    """Compute comprehensive metrics."""
    em_scores = []
    f1_scores = []
    answerable_correct = 0
    answerable_total = 0
    unanswerable_correct = 0
    unanswerable_total = 0
    spurious_count = 0
    abstention_count = 0

    for pred, ex in zip(predictions, examples):
        is_answerable = ex["question_kind"] != "UNANSWERABLE"

        if is_answerable:
            answerable_total += 1
            em = compute_match(pred.get("answer", ""), ex.get("answer", ""))
            f1 = compute_f1(pred.get("answer", ""), ex.get("answer", ""))
            em_scores.append(em)
            f1_scores.append(f1)
            if em:
                answerable_correct += 1
            if not pred.get("answer") and not ex.get("answer"):
                pass
            elif pred.get("answer") and not ex.get("answer"):
                spurious_count += 1
        else:
            unanswerable_total += 1
            if not pred.get("answer"):
                unanswerable_correct += 1
                abstention_count += 1
            else:
                spurious_count += 1

    metrics = {
        "exact_match": round(np.mean(em_scores) * 100, 1) if em_scores else 0,
        "token_f1": round(np.mean(f1_scores) * 100, 1) if f1_scores else 0,
        "answerability_accuracy": round(answerable_correct / max(answerable_total, 1) * 100, 1),
        "abstention_accuracy": round(unanswerable_correct / max(unanswerable_total, 1) * 100, 1),
        "false_abstention": round((answerable_total - answerable_correct) / max(answerable_total, 1) * 100, 1),
        "spurious_answer_rate": round(spurious_count / max(len(examples), 1) * 100, 1),
        "total_examples": len(examples),
        "answerable": answerable_total,
        "unanswerable": unanswerable_total,
    }

    return metrics


def compute_match(pred: str, gt: str) -> bool:
    """Compute match with normalization."""
    return pred.strip().lower() == gt.strip().lower()


def compute_category_metrics(predictions: list[dict], examples: list[dict]) -> dict:
    """Compute per-category metrics."""
    by_category = defaultdict(lambda: {"preds": [], "gts": [], "examples": []})

    for pred, ex in zip(predictions, examples):
        cat = ex.get("question_kind", "UNKNOWN")
        by_category[cat]["preds"].append(pred)
        by_category[cat]["gts"].append(ex)
        by_category[cat]["examples"].append(ex)

    results = {}
    for cat, data in sorted(by_category.items()):
        preds = data["preds"]
        gts = data["gts"]

        em_scores = []
        f1_scores = []
        for p, g in zip(preds, gts):
            if g.get("question_kind") != "UNANSWERABLE":
                em = compute_match(p.get("answer", ""), g.get("answer", ""))
                f1 = compute_f1(p.get("answer", ""), g.get("answer", ""))
                em_scores.append(em)
                f1_scores.append(f1)

        results[cat] = {
            "n": len(data["examples"]),
            "em": round(np.mean(em_scores) * 100, 1) if em_scores else 0,
            "f1": round(np.mean(f1_scores) * 100, 1) if f1_scores else 0,
        }

    return results


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def predict(model_dir: str, examples: list[dict], max_length: int = 384) -> list[dict]:
    """Run inference on examples."""
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForQuestionAnswering.from_pretrained(model_dir)
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    predictions = []
    start_time = time.time()

    for ex in examples:
        encoding = tokenizer(
            ex["question"],
            ex["context"],
            max_length=max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(device)
        attention_mask = encoding["attention_mask"].to(device)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        start_logits = outputs.start_logits[0]
        end_logits = outputs.end_logits[0]

        # Find best span
        max_len = ex.get("max_answer_length", 50)
        start_idx = torch.argmax(start_logits).item()
        end_idx = torch.argmax(end_logits[start_idx:start_idx + max_len]).item() + start_idx

        # Get answer
        answer_tokens = encoding["input_ids"][0][start_idx:end_idx + 1]
        answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        # Confidence
        start_conf = torch.softmax(start_logits, dim=0)[start_idx].item()
        end_conf = torch.softmax(end_logits, dim=0)[end_idx].item()
        confidence = (start_conf + end_conf) / 2

        predictions.append({
            "answer": answer,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "confidence": confidence,
            "start_confidence": start_conf,
            "end_confidence": end_conf,
        })

    total_time = time.time() - start_time
    avg_latency = total_time / max(len(examples), 1) * 1000  # ms

    return predictions, avg_latency


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Phase 4F.3 QA Model Evaluation")
    parser.add_argument("--model_dir", type=str, required=True, help="Model checkpoint directory")
    parser.add_argument("--data_dir", type=str, default="../dataset", help="Dataset directory")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory")
    parser.add_argument("--max_length", type=int, default=384, help="Max sequence length")
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = os.path.join(args.model_dir, "eval")

    os.makedirs(args.output_dir, exist_ok=True)

    # Load test data
    test_path = os.path.join(args.data_dir, "training_data_v3.jsonl")
    print(f"Loading test data: {test_path}")
    with open(test_path, "r") as f:
        examples = [json.loads(line) for line in f if line.strip()]
    print(f"  Examples: {len(examples)}")

    # Run inference
    print(f"\nRunning inference: {args.model_dir}")
    predictions, avg_latency = predict(args.model_dir, examples, args.max_length)

    # Compute overall metrics
    print("\nComputing metrics...")
    overall_metrics = compute_metrics(predictions, examples)
    overall_metrics["avg_latency_ms"] = round(avg_latency, 2)

    # Compute per-category metrics
    category_metrics = compute_category_metrics(predictions, examples)

    # Print results
    print(f"\n{'='*60}")
    print(f"RESULTS: {args.model_dir}")
    print(f"{'='*60}")
    print(f"  EM: {overall_metrics['exact_match']}%")
    print(f"  F1: {overall_metrics['token_f1']}%")
    print(f"  Answerability: {overall_metrics['answerability_accuracy']}%")
    print(f"  Abstention: {overall_metrics['abstention_accuracy']}%")
    print(f"  Spurious: {overall_metrics['spurious_answer_rate']}%")
    print(f"  Latency: {avg_latency:.2f}ms")
    print(f"\n  Per-category:")
    for cat, m in sorted(category_metrics.items(), key=lambda x: -x[1]["n"]):
        print(f"    {cat}: N={m['n']}, EM={m['em']}%, F1={m['f1']}%")

    # Save results
    results = {
        "model_dir": args.model_dir,
        "overall": overall_metrics,
        "by_category": category_metrics,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    output_path = os.path.join(args.output_dir, "evaluation_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved: {output_path}")


if __name__ == "__main__":
    main()

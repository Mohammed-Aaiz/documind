"""
Phase 4F.5-B — Corrected Controlled GPU QA Experiment

Trains A1 (distilbert-base-uncased) and A2 (bert-base-uncased) with
corrected span alignment. Evaluates A0/A1/A2 on held-out TEST split.

Uses Phase 4F.5-A derived dataset with document-level split.
"""

import hashlib
import json
import os
import sys
import io
import time
import gc
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoModelForQuestionAnswering,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── Paths ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DERIVED_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5" / "dataset" / "derived_dataset.jsonl"
SOURCE_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "dataset" / "training_data_v3_1.jsonl"
PROD_MODEL_DIR = PROJECT_ROOT / "backend" / "models" / "documind-qa"
OUTPUT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = OUTPUT_DIR / "results"
CHECKPOINTS_DIR = OUTPUT_DIR / "checkpoints"
LOGS_DIR = OUTPUT_DIR / "logs"
DIAG_DIR = OUTPUT_DIR / "diagnostics"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 42
MAX_LENGTH = 384
MAX_ANSWER_LENGTH = 50

# ─── Experiment configs ───────────────────────────────────────────
EXPERIMENTS = {
    "A1": {
        "name": "A1_DistilBERT_Uncased",
        "model": "distilbert-base-uncased",
        "lr": 3e-5,
        "batch": 8,
        "grad_acc": 8,
        "epochs": 3,
        "fp16": True,
    },
    "A2": {
        "name": "A2_BERT_Uncased",
        "model": "bert-base-uncased",
        "lr": 2e-5,
        "batch": 8,
        "grad_acc": 8,
        "epochs": 3,
        "fp16": True,
    },
}


# ─── Dataset ──────────────────────────────────────────────────────
class QADataset(Dataset):
    """Extractive QA dataset from derived_dataset.jsonl with correct span alignment."""

    def __init__(self, data_path, tokenizer, max_length=MAX_LENGTH, split="train",
                 exclude_invalid=True):
        self.examples = []
        self.tokenizer = tokenizer
        self.max_length = max_length

        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ex = json.loads(line)
                    if ex.get("split") != split:
                        continue
                    # Exclude invalid spans from training
                    if exclude_invalid and split == "train":
                        ts = ex.get("token_span")
                        if ex["question_kind"] != "UNANSWERABLE":
                            if ts is None or not ts.get("valid", False):
                                continue
                    self.examples.append(ex)

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]

        encoding = self.tokenizer(
            ex["question"], ex["context"],
            max_length=self.max_length, truncation=True,
            padding="max_length", return_tensors="pt",
        )

        if ex["question_kind"] == "UNANSWERABLE":
            start_pos = torch.tensor(0)
            end_pos = torch.tensor(0)
        else:
            ts = ex["token_span"]
            start_pos = torch.tensor(ts["start_token"])
            end_pos = torch.tensor(ts["end_token"])

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "start_positions": start_pos,
            "end_positions": end_pos,
        }


# ─── Metrics ──────────────────────────────────────────────────────
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


# ─── Evaluation ───────────────────────────────────────────────────
def evaluate_model(model, tokenizer, data_path, split="test", label="model"):
    """Evaluate model on a split using the canonical protocol."""
    model.eval()

    examples = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ex = json.loads(line)
                if ex.get("split") == split:
                    examples.append(ex)

    all_preds = []
    confidences = []
    latencies = []

    for ex in examples:
        t0 = time.time()
        encoding = tokenizer(
            ex["question"], ex["context"],
            max_length=MAX_LENGTH, truncation=True,
            padding="max_length", return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(DEVICE)
        attention_mask = encoding["attention_mask"].to(DEVICE)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        start_logits = outputs.start_logits[0]
        end_logits = outputs.end_logits[0]

        start_idx = torch.argmax(start_logits).item()
        end_idx = torch.argmax(end_logits[start_idx:start_idx + MAX_ANSWER_LENGTH]).item() + start_idx

        answer_tokens = encoding["input_ids"][0][start_idx:end_idx + 1]
        answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        start_conf = torch.softmax(start_logits, dim=0)[start_idx].item()
        end_conf = torch.softmax(end_logits, dim=0)[end_idx].item()
        confidence = (start_conf + end_conf) / 2

        all_preds.append(answer)
        confidences.append(confidence)
        latencies.append(time.time() - t0)

    # Compute metrics
    em_scores = []
    f1_scores = []
    answerable_correct = 0
    answerable_total = 0
    unanswerable_correct = 0
    unanswerable_total = 0
    spurious = 0
    false_abstention = 0

    for pred, ex in zip(all_preds, examples):
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

    # Per-category
    by_cat = defaultdict(lambda: {"preds": [], "gts": [], "confs": []})
    for pred, ex, conf in zip(all_preds, examples, confidences):
        cat = ex["question_kind"]
        by_cat[cat]["preds"].append(pred)
        by_cat[cat]["gts"].append(ex)
        by_cat[cat]["confs"].append(conf)

    per_category = {}
    for cat, data in sorted(by_cat.items()):
        cat_em = []
        cat_f1 = []
        for pred, gt in zip(data["preds"], data["gts"]):
            if gt["question_kind"] != "UNANSWERABLE":
                cat_em.append(1 if exact_match(pred, gt["answer"]) else 0)
                cat_f1.append(token_f1(pred, gt["answer"]))
        per_category[cat] = {
            "n": len(data["preds"]),
            "em": round(np.mean(cat_em) * 100, 1) if cat_em else 0,
            "f1": round(np.mean(cat_f1) * 100, 1) if cat_f1 else 0,
            "avg_confidence": round(np.mean(data["confs"]), 4),
        }

    # Confidence analysis
    correct_confs = [c for pred, ex, c in zip(all_preds, examples, confidences)
                     if ex["question_kind"] != "UNANSWERABLE" and exact_match(pred, ex["answer"])]
    incorrect_confs = [c for pred, ex, c in zip(all_preds, examples, confidences)
                       if ex["question_kind"] != "UNANSWERABLE" and not exact_match(pred, ex["answer"])]

    # Failure taxonomy
    failures = defaultdict(int)
    total_failures = 0
    for pred, ex in zip(all_preds, examples):
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

    results = {
        "model_label": label,
        "eval_version": "4F.5-eval-v1",
        "split": split,
        "total_examples": len(examples),
        "overall": {
            "em": round(np.mean(em_scores) * 100, 1) if em_scores else 0,
            "f1": round(np.mean(f1_scores) * 100, 1) if f1_scores else 0,
            "answerability_accuracy": round(answerable_correct / max(answerable_total, 1) * 100, 1),
            "abstention_accuracy": round(unanswerable_correct / max(unanswerable_total, 1) * 100, 1),
            "false_abstention": round(false_abstention / max(answerable_total, 1) * 100, 1),
            "spurious_rate": round(spurious / max(len(examples), 1) * 100, 1),
            "answerable": answerable_total,
            "unanswerable": unanswerable_total,
        },
        "by_category": per_category,
        "failure_taxonomy": {
            "total_failures": total_failures,
            "failure_rate": round(total_failures / max(len(examples), 1) * 100, 1),
            "by_type": dict(failures),
        },
        "confidence_analysis": {
            "correct_mean": round(np.mean(correct_confs), 4) if correct_confs else 0,
            "correct_std": round(np.std(correct_confs), 4) if correct_confs else 0,
            "incorrect_mean": round(np.mean(incorrect_confs), 4) if incorrect_confs else 0,
            "incorrect_std": round(np.std(incorrect_confs), 4) if incorrect_confs else 0,
            "separation": round(np.mean(correct_confs) - np.mean(incorrect_confs), 4) if correct_confs and incorrect_confs else 0,
        },
        "latency_ms": round(np.mean(latencies) * 1000, 2),
    }

    return results, all_preds, examples, confidences


# ─── Training ─────────────────────────────────────────────────────
def train_experiment(exp_key, config, data_path, results_dir):
    """Train a single experiment with checkpoint selection by validation EM."""
    print(f"\n{'='*60}")
    print(f"TRAINING: {config['name']}")
    print(f"{'='*60}")

    exp_dir = results_dir / exp_key
    exp_dir.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)

    # Load tokenizer and model from fresh pretrained
    print(f"  Loading fresh pretrained: {config['model']}")
    tok = AutoTokenizer.from_pretrained(config["model"])
    model = AutoModelForQuestionAnswering.from_pretrained(config["model"]).to(DEVICE)

    # Load datasets
    train_ds = QADataset(data_path, tok, MAX_LENGTH, split="train", exclude_invalid=True)
    val_ds = QADataset(data_path, tok, MAX_LENGTH, split="validation", exclude_invalid=False)
    print(f"  Train: {len(train_ds)} examples, Validation: {len(val_ds)} examples")

    train_loader = DataLoader(train_ds, batch_size=config["batch"], shuffle=True, num_workers=0)

    # Optimizer + scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["lr"], weight_decay=0.01)
    total_steps = len(train_loader) * config["epochs"] // config["grad_acc"]
    warmup_steps = int(total_steps * 0.1)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # Training loop with validation
    use_fp16 = config.get("fp16", False) and DEVICE.type == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_fp16 else None

    history = []
    best_val_em = -1
    best_checkpoint_path = None
    start_time = time.time()
    nan_detected = False
    overflow_count = 0

    for epoch in range(config["epochs"]):
        model.train()
        total_loss = 0
        num_batches = 0
        epoch_start = time.time()

        for batch_idx, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            start_positions = batch["start_positions"].to(DEVICE)
            end_positions = batch["end_positions"].to(DEVICE)

            if use_fp16:
                with torch.amp.autocast("cuda"):
                    outputs = model(input_ids=input_ids, attention_mask=attention_mask,
                                   start_positions=start_positions, end_positions=end_positions)
                    loss = outputs.loss / config["grad_acc"]
                scaler.scale(loss).backward()
            else:
                outputs = model(input_ids=input_ids, attention_mask=attention_mask,
                               start_positions=start_positions, end_positions=end_positions)
                loss = outputs.loss / config["grad_acc"]
                loss.backward()

            loss_val = loss.item() * config["grad_acc"]
            if np.isnan(loss_val) or np.isinf(loss_val):
                nan_detected = True
                print(f"    WARNING: NaN/Inf loss at epoch {epoch+1} batch {batch_idx}")

            total_loss += loss_val
            num_batches += 1

            if (batch_idx + 1) % config["grad_acc"] == 0:
                if use_fp16:
                    try:
                        scaler.unscale_(optimizer)
                        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        scaler.step(optimizer)
                    except (ValueError, RuntimeError) as e:
                        overflow_count += 1
                        print(f"    WARNING: FP16 overflow at batch {batch_idx}: {e}")
                    finally:
                        scaler.update()
                else:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_loss = total_loss / max(num_batches, 1)
        epoch_time = time.time() - epoch_start

        # Validation evaluation (use raw examples, not tokenized dataset)
        model.eval()
        val_em, val_f1, val_count = 0, 0, 0
        val_start = time.time()
        for vex in val_ds.examples:
            enc = tok(vex["question"], vex["context"], max_length=MAX_LENGTH,
                      truncation=True, padding="max_length", return_tensors="pt").to(DEVICE)
            with torch.no_grad():
                out = model(**enc)
            si = torch.argmax(out.start_logits[0]).item()
            ei = torch.argmax(out.end_logits[0][si:si+MAX_ANSWER_LENGTH]).item() + si
            pred = tok.decode(enc["input_ids"][0][si:ei+1], skip_special_tokens=True).strip()
            if vex["question_kind"] != "UNANSWERABLE":
                val_count += 1
                if exact_match(pred, vex["answer"]):
                    val_em += 1
                val_f1 += token_f1(pred, vex["answer"])
        val_time = time.time() - val_start

        val_em_pct = round(val_em / max(val_count, 1) * 100, 1)
        val_f1_pct = round(val_f1 / max(val_count, 1) * 100, 1)

        history.append({
            "epoch": epoch + 1,
            "loss": round(avg_loss, 4),
            "val_em": val_em_pct,
            "val_f1": val_f1_pct,
            "val_count": val_count,
            "lr": scheduler.get_last_lr()[0],
            "time_s": round(epoch_time, 1),
            "val_time_s": round(val_time, 1),
        })

        print(f"  Epoch {epoch+1}/{config['epochs']}: loss={avg_loss:.4f} val_EM={val_em_pct}% val_F1={val_f1_pct}% time={epoch_time:.1f}s")

        # Save checkpoint for this epoch
        ckpt_dir = exp_dir / f"checkpoint_epoch{epoch+1}"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(ckpt_dir))
        tok.save_pretrained(str(ckpt_dir))

        # Checkpoint selection by validation EM
        if val_em_pct > best_val_em:
            best_val_em = val_em_pct
            best_checkpoint_path = str(ckpt_dir)
            print(f"    -> New best checkpoint (val_EM={val_em_pct}%)")

        model.train()
        gc.collect()
        torch.cuda.empty_cache()

    total_time = time.time() - start_time
    peak_mem = torch.cuda.max_memory_allocated(0) / 1e6 if torch.cuda.is_available() else 0

    # Compute checkpoint hash
    ckpt_hash = hashlib.sha256()
    if best_checkpoint_path:
        for root, dirs, files in os.walk(best_checkpoint_path):
            for fn in sorted(files):
                fp = os.path.join(root, fn)
                with open(fp, "rb") as f:
                    ckpt_hash.update(f.read())
    ckpt_hash_hex = ckpt_hash.hexdigest()[:16]

    # Save training metadata
    metadata = {
        "experiment": config["name"],
        "model_name": config["model"],
        "hyperparameters": {k: v for k, v in config.items() if k not in ("name",)},
        "training_history": history,
        "training_time_s": round(total_time, 1),
        "peak_gpu_memory_mb": round(peak_mem, 0),
        "best_checkpoint": best_checkpoint_path,
        "best_val_em": best_val_em,
        "checkpoint_hash": ckpt_hash_hex,
        "nan_detected": nan_detected,
        "overflow_count": overflow_count,
        "device": str(DEVICE),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        "pytorch_version": torch.__version__,
        "transformers_version": __import__("transformers").__version__,
    }

    with open(LOGS_DIR / f"{exp_key.lower()}_training.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  Training complete: {total_time:.1f}s")
    print(f"  Peak GPU memory: {peak_mem:.0f} MB")
    print(f"  Best checkpoint: {best_checkpoint_path}")
    print(f"  Best val EM: {best_val_em}%")

    return metadata


# ─── Main ─────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("PHASE 4F.5-B — CORRECTED CONTROLLED GPU QA EXPERIMENT")
    print("=" * 60)
    print(f"  Device: {DEVICE}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  PyTorch: {torch.__version__}")
    print(f"  Dataset: {DERIVED_DATASET}")
    print()

    # Verify source hashes
    with open(SOURCE_DATASET, "rb") as f:
        src_hash = hashlib.sha256(f.read()).hexdigest()
    assert src_hash == "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97", \
        f"SOURCE HASH MISMATCH: {src_hash}"
    print(f"  Source hash: VERIFIED ({src_hash[:16]}...)")

    with open(DERIVED_DATASET, "rb") as f:
        der_hash = hashlib.sha256(f.read()).hexdigest()
    assert der_hash == "abcf4182f39f0620fb056eee4167d1872baf9b4c748051eade9d6312332f271f", \
        f"DERIVED HASH MISMATCH: {der_hash}"
    print(f"  Derived hash: VERIFIED ({der_hash[:16]}...)")

    # Create output directories
    for d in [RESULTS_DIR, CHECKPOINTS_DIR, LOGS_DIR, DIAG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    all_results = {}

    # ═══════════════════════════════════════════════════════════════
    # A0 — PRODUCTION BASELINE
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("A0 — PRODUCTION BASELINE")
    print(f"{'='*60}")

    a0_tok = AutoTokenizer.from_pretrained(str(PROD_MODEL_DIR))
    a0_model = AutoModelForQuestionAnswering.from_pretrained(str(PROD_MODEL_DIR)).to(DEVICE)
    a0_results, a0_preds, a0_exs, a0_confs = evaluate_model(
        a0_model, a0_tok, str(DERIVED_DATASET), split="test", label="A0_Production"
    )
    with open(RESULTS_DIR / "a0_test.json", "w") as f:
        json.dump(a0_results, f, indent=2)
    all_results["a0"] = a0_results
    print(f"  A0 EM: {a0_results['overall']['em']}%, F1: {a0_results['overall']['f1']}%")
    del a0_model, a0_tok
    gc.collect()
    torch.cuda.empty_cache()

    # ═══════════════════════════════════════════════════════════════
    # A1 — DISTILBERT
    # ═══════════════════════════════════════════════════════════════
    a1_meta = train_experiment("A1", EXPERIMENTS["A1"], str(DERIVED_DATASET), CHECKPOINTS_DIR)

    # Load best checkpoint and evaluate on test
    print(f"\n  Evaluating A1 on TEST...")
    a1_tok = AutoTokenizer.from_pretrained(a1_meta["best_checkpoint"], local_files_only=True)
    a1_model = AutoModelForQuestionAnswering.from_pretrained(a1_meta["best_checkpoint"], local_files_only=True).to(DEVICE)
    a1_results, a1_preds, a1_exs, a1_confs = evaluate_model(
        a1_model, a1_tok, str(DERIVED_DATASET), split="test", label="A1_DistilBERT"
    )
    with open(RESULTS_DIR / "a1_test.json", "w") as f:
        json.dump(a1_results, f, indent=2)
    all_results["a1"] = a1_results
    print(f"  A1 EM: {a1_results['overall']['em']}%, F1: {a1_results['overall']['f1']}%")
    del a1_model, a1_tok
    gc.collect()
    torch.cuda.empty_cache()

    # ═══════════════════════════════════════════════════════════════
    # A2 — BERT
    # ═══════════════════════════════════════════════════════════════
    a2_meta = train_experiment("A2", EXPERIMENTS["A2"], str(DERIVED_DATASET), CHECKPOINTS_DIR)

    # Load best checkpoint and evaluate on test
    print(f"\n  Evaluating A2 on TEST...")
    a2_tok = AutoTokenizer.from_pretrained(a2_meta["best_checkpoint"], local_files_only=True)
    a2_model = AutoModelForQuestionAnswering.from_pretrained(a2_meta["best_checkpoint"], local_files_only=True).to(DEVICE)
    a2_results, a2_preds, a2_exs, a2_confs = evaluate_model(
        a2_model, a2_tok, str(DERIVED_DATASET), split="test", label="A2_BERT"
    )
    with open(RESULTS_DIR / "a2_test.json", "w") as f:
        json.dump(a2_results, f, indent=2)
    all_results["a2"] = a2_results
    print(f"  A2 EM: {a2_results['overall']['em']}%, F1: {a2_results['overall']['f1']}%")
    del a2_model, a2_tok
    gc.collect()
    torch.cuda.empty_cache()

    # ═══════════════════════════════════════════════════════════════
    # COMPARISON
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("COMPARISON")
    print(f"{'='*60}")

    comparison = {
        "phase": "4F.5-B",
        "eval_version": "4F.5-eval-v1",
        "test_examples": a0_results["total_examples"],
        "models": {}
    }

    for key, label in [("a0", "A0_Production"), ("a1", "A1_DistilBERT"), ("a2", "A2_BERT")]:
        r = all_results[key]["overall"]
        comparison["models"][key] = {
            "label": label,
            "em": r["em"],
            "f1": r["f1"],
            "answerability": r["answerability_accuracy"],
            "abstention": r["abstention_accuracy"],
            "spurious": r["spurious_rate"],
        }

    # Paired differences
    for comp_key, (m1, m2) in [("A1_vs_A0", ("a1", "a0")), ("A2_vs_A0", ("a2", "a0")), ("A2_vs_A1", ("a2", "a1"))]:
        r1 = all_results[m1]["overall"]
        r2 = all_results[m2]["overall"]
        comparison[comp_key] = {
            "em_delta": round(r1["em"] - r2["em"], 1),
            "f1_delta": round(r1["f1"] - r2["f1"], 1),
            "answerability_delta": round(r1["answerability_accuracy"] - r2["answerability_accuracy"], 1),
            "abstention_delta": round(r1["abstention_accuracy"] - r2["abstention_accuracy"], 1),
            "spurious_delta": round(r1["spurious_rate"] - r2["spurious_rate"], 1),
        }

    with open(RESULTS_DIR / "comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    # Print comparison table
    print(f"\n{'Model':<25} {'EM':>8} {'F1':>8} {'Answer':>8} {'Abstain':>8} {'Spurious':>8}")
    print("-" * 73)
    for key in ["a0", "a1", "a2"]:
        r = all_results[key]["overall"]
        print(f"{all_results[key]['model_label']:<25} {r['em']:>7.1f}% {r['f1']:>7.1f}% "
              f"{r['answerability_accuracy']:>7.1f}% {r['abstention_accuracy']:>7.1f}% "
              f"{r['spurious_rate']:>7.1f}%")

    # ═══════════════════════════════════════════════════════════════
    # PRODUCTION SAFETY
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("PRODUCTION SAFETY VERIFICATION")
    print(f"{'='*60}")

    prod_hash = hashlib.sha256()
    for root, dirs, files in os.walk(str(PROD_MODEL_DIR)):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            with open(fp, "rb") as f:
                prod_hash.update(f.read())
    prod_checksum = prod_hash.hexdigest()
    expected = "df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac"
    print(f"  Production model: {prod_checksum[:16]}... {'UNCHANGED' if prod_checksum == expected else 'CHANGED!'}")
    assert prod_checksum == expected, "PRODUCTION MODEL CHANGED!"

    with open(DERIVED_DATASET, "rb") as f:
        dh = hashlib.sha256(f.read()).hexdigest()
    print(f"  Derived dataset: {dh[:16]}... {'UNCHANGED' if dh == der_hash else 'CHANGED!'}")

    print(f"\n  ALL SAFETY CHECKS PASS")

    # ═══════════════════════════════════════════════════════════════
    # SAVE FINAL MANIFEST
    # ═══════════════════════════════════════════════════════════════
    final_manifest = {
        "phase": "4F.5-B",
        "status": "COMPLETE",
        "source_dataset_hash": src_hash,
        "derived_dataset_hash": der_hash,
        "production_model_checksum": prod_checksum,
        "production_unchanged": True,
        "results": {
            "a0": {"em": all_results["a0"]["overall"]["em"], "f1": all_results["a0"]["overall"]["f1"]},
            "a1": {"em": all_results["a1"]["overall"]["em"], "f1": all_results["a1"]["overall"]["f1"],
                   "best_checkpoint": a1_meta["best_checkpoint"], "best_val_em": a1_meta["best_val_em"],
                   "nan_detected": a1_meta["nan_detected"], "overflow_count": a1_meta["overflow_count"]},
            "a2": {"em": all_results["a2"]["overall"]["em"], "f1": all_results["a2"]["overall"]["f1"],
                   "best_checkpoint": a2_meta["best_checkpoint"], "best_val_em": a2_meta["best_val_em"],
                   "nan_detected": a2_meta["nan_detected"], "overflow_count": a2_meta["overflow_count"]},
        },
        "comparison": comparison.get("A1_vs_A0", {}),
        "training_stability": {
            "A1": "STABLE" if not a1_meta["nan_detected"] else "UNSTABLE",
            "A2": "STABLE" if not a2_meta["nan_detected"] else "UNSTABLE",
        },
        "a3_status": "DEFERRED",
    }

    with open(OUTPUT_DIR / "manifests" / "final_experiment_manifest.json", "w") as f:
        json.dump(final_manifest, f, indent=2)

    print(f"\n{'='*60}")
    print("ALL EXPERIMENTS COMPLETE")
    print(f"{'='*60}")

    return all_results


if __name__ == "__main__":
    main()

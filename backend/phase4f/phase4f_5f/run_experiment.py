"""
Phase 4F.5-F — Targeted Unanswerable Training Experiment

Trains F1 (natural ratio 571:28) and F2 (class-balanced ~3:1)
on distilbert-base-uncased with corrected span alignment and
unanswerable examples in training.

Evaluates A0, A1, F1, F2 on the Phase 4F.5-D benchmark.
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DERIVED_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5" / "dataset" / "derived_dataset.jsonl"
SOURCE_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "dataset" / "training_data_v3_1.jsonl"
PROD_MODEL_DIR = PROJECT_ROOT / "backend" / "models" / "documind-qa"
BENCHMARK_PATH = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5d" / "benchmark" / "qa_benchmark_v1.jsonl"

OUTPUT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = OUTPUT_DIR / "results"
CHECKPOINTS_DIR = OUTPUT_DIR / "checkpoints"
LOGS_DIR = OUTPUT_DIR / "logs"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 42
MAX_LENGTH = 384
MAX_ANSWER_LENGTH = 50
TRAIN_UNANSWERABLE_COUNT = 28


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


# === Dataset for F1/F2 training ===
class FDataset(Dataset):
    """QA dataset with unanswerable examples included in training."""

    def __init__(self, examples, tokenizer, max_length=MAX_LENGTH):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

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
            ts = ex.get("token_span")
            if ts and ts.get("valid", False):
                start_pos = torch.tensor(ts["start_token"])
                end_pos = torch.tensor(ts["end_token"])
            else:
                start_pos = torch.tensor(0)
                end_pos = torch.tensor(0)

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "start_positions": start_pos,
            "end_positions": end_pos,
        }


# === Load derived dataset ===
def load_derived():
    examples = []
    with open(DERIVED_DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


# === Create F1 training set (move 28 unanswerable to train) ===
def create_f1_training_data(all_examples):
    """Move 28 unanswerable from validation to training."""
    train_exs = []
    val_exs = []
    unanswerable_in_val = []

    for ex in all_examples:
        if ex["split"] == "train":
            train_exs.append(ex)
        elif ex["split"] == "validation":
            val_exs.append(ex)

    # Separate unanswerable from validation
    for ex in val_exs:
        if ex["question_kind"] == "UNANSWERABLE":
            unanswerable_in_val.append(ex)

    # Deterministic split
    unanswerable_sorted = sorted(unanswerable_in_val, key=lambda x: x["example_id"])
    train_unans = unanswerable_sorted[:TRAIN_UNANSWERABLE_COUNT]
    held_unans = unanswerable_sorted[TRAIN_UNANSWERABLE_COUNT:]

    # Add training unanswerable to train
    for ex in train_unans:
        new_ex = dict(ex)
        new_ex["split"] = "train"
        new_ex["is_resampled"] = False
        train_exs.append(new_ex)

    # Keep held-out unanswerable in validation
    for ex in held_unans:
        val_exs.append(ex)

    # Keep answerable validation
    for ex in val_exs:
        if ex["question_kind"] != "UNANSWERABLE":
            pass  # already in val_exs

    # Filter valid answerable for training
    train_valid = []
    for ex in train_exs:
        if ex["question_kind"] == "UNANSWERABLE":
            train_valid.append(ex)
        else:
            ts = ex.get("token_span")
            if ts and ts.get("valid", False):
                train_valid.append(ex)

    return train_valid, val_exs


# === Create F2 training set (class-balanced ~3:1) ===
def create_f2_training_data(train_f1_examples, all_unanswerable_val):
    """Add ~190 resampled unanswerable examples."""
    train_exs = list(train_f1_examples)

    # Get unanswerable examples from F1 training
    unans_train = [ex for ex in train_exs if ex["question_kind"] == "UNANSWERABLE"]

    # Target: ~190 unanswerable (3:1 ratio with 571 answerable)
    target_unans = 190
    current_unans = len(unans_train)

    if current_unans < target_unans:
        needed = target_unans - current_unans
        # Resample from existing unanswerable training examples
        random.seed(SEED)
        for i in range(needed):
            src = unans_train[i % len(unans_train)]
            new_ex = dict(src)
            new_ex["example_id"] = f"{src['example_id']}_r{i}"
            new_ex["is_resampled"] = True
            new_ex["resample_index"] = i
            train_exs.append(new_ex)

    return train_exs


# === Inference ===
def predict(model, tokenizer, examples):
    """Run inference on examples."""
    model.eval()
    predictions = []
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
        end_idx = (
            torch.argmax(end_logits[start_idx:start_idx + MAX_ANSWER_LENGTH]).item()
            + start_idx
        )

        answer_tokens = encoding["input_ids"][0][start_idx:end_idx + 1]
        answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        start_conf = torch.softmax(start_logits, dim=0)[start_idx].item()
        end_conf = torch.softmax(end_logits, dim=0)[end_idx].item()
        confidence = (start_conf + end_conf) / 2

        predictions.append(answer)
        confidences.append(confidence)
        latencies.append(time.time() - t0)

    return predictions, confidences, latencies


# === Evaluation ===
def evaluate(predictions, examples, confidences, latencies):
    """Compute all metrics."""
    results = {
        "eval_version": "4F.5-F-eval-v1",
        "total_examples": len(examples),
    }

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

    # Per-category
    by_cat = defaultdict(lambda: {"preds": [], "gts": [], "confs": []})
    for pred, ex, conf in zip(predictions, examples, confidences):
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

    results["by_category"] = per_category

    # Confidence analysis
    correct_confs = []
    incorrect_confs = []
    abstained_confs = []
    spurious_confs = []
    for pred, ex, conf in zip(predictions, examples, confidences):
        if ex["question_kind"] != "UNANSWERABLE":
            if exact_match(pred, ex["answer"]):
                correct_confs.append(conf)
            else:
                incorrect_confs.append(conf)
        else:
            if not pred:
                abstained_confs.append(conf)
            else:
                spurious_confs.append(conf)

    results["confidence_analysis"] = {
        "answerable_correct_mean": round(np.mean(correct_confs), 4) if correct_confs else 0,
        "answerable_incorrect_mean": round(np.mean(incorrect_confs), 4) if incorrect_confs else 0,
        "unanswerable_abstained_mean": round(np.mean(abstained_confs), 4) if abstained_confs else 0,
        "unanswerable_spurious_mean": round(np.mean(spurious_confs), 4) if spurious_confs else 0,
        "separation": round(
            np.mean(correct_confs) - np.mean(spurious_confs), 4
        ) if correct_confs and spurious_confs else 0,
    }

    # Failure taxonomy
    failures = defaultdict(int)
    for pred, ex in zip(predictions, examples):
        is_answerable = ex["question_kind"] != "UNANSWERABLE"
        if is_answerable:
            if not pred:
                failures["ABSTAIN"] += 1
            elif not exact_match(pred, ex["answer"]):
                failures["EXTRACT"] += 1
        else:
            if pred:
                failures["SPURIOUS"] += 1

    results["failure_taxonomy"] = {"by_type": dict(failures)}

    return results


# === Threshold sweep ===
def threshold_sweep(predictions, examples, confidences):
    """Diagnostic threshold sweep."""
    thresholds = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80, 0.90]
    sweep = []

    answerable_indices = [i for i, ex in enumerate(examples) if ex["question_kind"] != "UNANSWERABLE"]
    unanswerable_indices = [i for i, ex in enumerate(examples) if ex["question_kind"] == "UNANSWERABLE"]

    for thresh in thresholds:
        # For answerable: correct if pred matches gold and confidence > threshold
        # For unanswerable: correct if abstained (pred empty or confidence < threshold)
        abstained_unans = 0
        spurious_after_thresh = 0
        correct_answerable = 0
        total_answerable = len(answerable_indices)
        false_abstention_count = 0

        for i in answerable_indices:
            pred = predictions[i]
            conf = confidences[i]
            gold = examples[i]["answer"]
            if exact_match(pred, gold) and conf >= thresh:
                correct_answerable += 1
            elif not pred or conf < thresh:
                false_abstention_count += 1

        for i in unanswerable_indices:
            conf = confidences[i]
            if conf < thresh:
                abstained_unans += 1
            else:
                spurious_after_thresh += 1

        total_unans = len(unanswerable_indices)
        sweep.append({
            "threshold": thresh,
            "answerable_correct": correct_answerable,
            "answerable_total": total_answerable,
            "answerable_em": round(correct_answerable / max(total_answerable, 1) * 100, 1),
            "false_abstention": round(false_abstention_count / max(total_answerable, 1) * 100, 1),
            "unanswerable_abstained": abstained_unans,
            "unanswerable_total": total_unans,
            "abstention_rate": round(abstained_unans / max(total_unans, 1) * 100, 1),
            "spurious_rate": round(spurious_after_thresh / max(total_unans, 1) * 100, 1),
        })

    return sweep


# === Training ===
def train_model(train_examples, val_examples, config, exp_name, data_desc):
    """Train a single model."""
    print(f"\n{'='*60}")
    print(f"TRAINING: {exp_name}")
    print(f"  {data_desc}")
    print(f"{'='*60}")

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)

    tok = AutoTokenizer.from_pretrained(config["model"])
    model = AutoModelForQuestionAnswering.from_pretrained(config["model"]).to(DEVICE)

    train_ds = FDataset(train_examples, tok, MAX_LENGTH)
    val_ds = FDataset(val_examples, tok, MAX_LENGTH)

    print(f"  Train: {len(train_ds)} examples")
    print(f"  Validation: {len(val_ds)} examples")

    train_loader = DataLoader(train_ds, batch_size=config["batch"], shuffle=True, num_workers=0)

    optimizer = torch.optim.AdamW(model.parameters(), lr=config["lr"], weight_decay=0.01)
    total_steps = len(train_loader) * config["epochs"] // config["grad_acc"]
    warmup_steps = int(total_steps * 0.1)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    use_fp16 = config.get("fp16", False) and DEVICE.type == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_fp16 else None

    history = []
    best_val_em = -1
    best_checkpoint_path = None
    start_time = time.time()
    nan_detected = False
    overflow_count = 0

    ckpt_dir = CHECKPOINTS_DIR / exp_name
    ckpt_dir.mkdir(parents=True, exist_ok=True)

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
                        print(f"    WARNING: FP16 overflow: {e}")
                    finally:
                        scaler.update()
                else:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_loss = total_loss / max(num_batches, 1)
        epoch_time = time.time() - epoch_start

        # Validation
        model.eval()
        val_em, val_f1, val_count = 0, 0, 0
        val_abstained, val_spurious = 0, 0
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
            else:
                if not pred:
                    val_abstained += 1
                else:
                    val_spurious += 1

        val_em_pct = round(val_em / max(val_count, 1) * 100, 1)
        val_f1_pct = round(val_f1 / max(val_count, 1) * 100, 1)
        val_abstention_pct = round(val_abstained / max(val_abstained + val_spurious, 1) * 100, 1)

        history.append({
            "epoch": epoch + 1,
            "loss": round(avg_loss, 4),
            "val_em": val_em_pct,
            "val_f1": val_f1_pct,
            "val_count": val_count,
            "val_abstention": val_abstention_pct,
            "val_spurious": val_spurious,
            "lr": scheduler.get_last_lr()[0],
            "time_s": round(epoch_time, 1),
        })

        print(f"  Epoch {epoch+1}: loss={avg_loss:.4f} val_EM={val_em_pct}% val_F1={val_f1_pct}% "
              f"val_abstain={val_abstention_pct}% time={epoch_time:.1f}s")

        # Save checkpoint
        epoch_ckpt = ckpt_dir / f"checkpoint_epoch{epoch+1}"
        epoch_ckpt.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(epoch_ckpt))
        tok.save_pretrained(str(epoch_ckpt))

        # Best checkpoint by val EM (with abstention as tiebreak)
        combined_score = val_em_pct + val_abstention_pct * 0.01
        best_combined = best_val_em + 0.01 if best_val_em >= 0 else -1
        if combined_score > best_combined:
            best_val_em = val_em_pct
            best_checkpoint_path = str(epoch_ckpt)
            print(f"    -> New best checkpoint (val_EM={val_em_pct}%, val_abstain={val_abstention_pct}%)")

        model.train()
        gc.collect()
        torch.cuda.empty_cache()

    total_time = time.time() - start_time
    peak_mem = torch.cuda.max_memory_allocated(0) / 1e6 if torch.cuda.is_available() else 0

    # Checkpoint hash
    ckpt_hash = hashlib.sha256()
    if best_checkpoint_path:
        for root, dirs, files in os.walk(best_checkpoint_path):
            for fn in sorted(files):
                fp = os.path.join(root, fn)
                with open(fp, "rb") as f:
                    ckpt_hash.update(f.read())

    metadata = {
        "experiment": exp_name,
        "data_description": data_desc,
        "model_name": config["model"],
        "hyperparameters": {k: v for k, v in config.items() if k != "name"},
        "training_history": history,
        "training_time_s": round(total_time, 1),
        "peak_gpu_memory_mb": round(peak_mem, 0),
        "best_checkpoint": best_checkpoint_path,
        "best_val_em": best_val_em,
        "checkpoint_hash": ckpt_hash.hexdigest()[:16],
        "nan_detected": nan_detected,
        "overflow_count": overflow_count,
        "device": str(DEVICE),
    }

    print(f"\n  Training complete: {total_time:.1f}s, Peak: {peak_mem:.0f}MB")
    print(f"  Best checkpoint: {best_checkpoint_path}")
    print(f"  Best val EM: {best_val_em}%")

    return metadata


# === Main ===
def main():
    print("=" * 60)
    print("PHASE 4F.5-F — TARGETED UNANSWERABLE TRAINING EXPERIMENT")
    print("=" * 60)
    print(f"  Device: {DEVICE}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")

    # Verify source hashes
    with open(SOURCE_DATASET, "rb") as f:
        src_hash = hashlib.sha256(f.read()).hexdigest()
    assert src_hash == "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
    print(f"  Source hash: VERIFIED ({src_hash[:16]}...)")

    for d in [RESULTS_DIR, CHECKPOINTS_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # === Load data ===
    all_examples = load_derived()
    print(f"\n  Loaded {len(all_examples)} examples from derived dataset")

    # Split distribution
    split_counts = Counter(ex["split"] for ex in all_examples)
    print(f"  Split distribution: {dict(split_counts)}")

    unans_by_split = Counter(
        ex["split"] for ex in all_examples if ex["question_kind"] == "UNANSWERABLE"
    )
    print(f"  Unanswerable by split: {dict(unans_by_split)}")

    # === Create F1 training data ===
    print(f"\n{'='*60}")
    print("CREATING F1 DATASET (natural ratio)")
    print(f"{'='*60}")

    train_f1, val_f1 = create_f1_training_data(all_examples)
    train_f1_answerable = [ex for ex in train_f1 if ex["question_kind"] != "UNANSWERABLE"]
    train_f1_unanswerable = [ex for ex in train_f1 if ex["question_kind"] == "UNANSWERABLE"]
    val_f1_answerable = [ex for ex in val_f1 if ex["question_kind"] != "UNANSWERABLE"]
    val_f1_unanswerable = [ex for ex in val_f1 if ex["question_kind"] == "UNANSWERABLE"]

    print(f"  F1 Training: {len(train_f1)} total ({len(train_f1_answerable)} answerable + {len(train_f1_unanswerable)} unanswerable)")
    print(f"  F1 Validation: {len(val_f1)} total ({len(val_f1_answerable)} answerable + {len(val_f1_unanswerable)} unanswerable)")

    # === Create F2 training data (class-balanced) ===
    print(f"\n{'='*60}")
    print("CREATING F2 DATASET (class-balanced ~3:1)")
    print(f"{'='*60}")

    train_f2 = create_f2_training_data(train_f1, val_f1_unanswerable)
    train_f2_answerable = [ex for ex in train_f2 if ex["question_kind"] != "UNANSWERABLE"]
    train_f2_unanswerable = [ex for ex in train_f2 if ex["question_kind"] == "UNANSWERABLE"]
    resampled = [ex for ex in train_f2 if ex.get("is_resampled", False)]

    print(f"  F2 Training: {len(train_f2)} total ({len(train_f2_answerable)} answerable + {len(train_f2_unanswerable)} unanswerable)")
    print(f"  F2 Resampled unanswerable: {len(resampled)}")
    print(f"  F2 Answerable:Unanswerable ratio = {len(train_f2_answerable)}:{len(train_f2_unanswerable)}")

    # === Save dataset manifests ===
    f1_manifest = {
        "experiment": "F1",
        "train_total": len(train_f1),
        "train_answerable": len(train_f1_answerable),
        "train_unanswerable": len(train_f1_unanswerable),
        "val_total": len(val_f1),
        "val_answerable": len(val_f1_answerable),
        "val_unanswerable": len(val_f1_unanswerable),
        "train_unanswerable_ids": sorted([ex["example_id"] for ex in train_f1_unanswerable]),
        "held_out_unanswerable_ids": sorted([ex["example_id"] for ex in val_f1_unanswerable]),
    }
    with open(RESULTS_DIR / "f1_dataset_manifest.json", "w") as f:
        json.dump(f1_manifest, f, indent=2)

    f2_manifest = {
        "experiment": "F2",
        "train_total": len(train_f2),
        "train_answerable": len(train_f2_answerable),
        "train_unanswerable": len(train_f2_unanswerable),
        "resampled_count": len(resampled),
        "ratio": f"{len(train_f2_answerable)}:{len(train_f2_unanswerable)}",
        "val_total": len(val_f1),
        "val_answerable": len(val_f1_answerable),
        "val_unanswerable": len(val_f1_unanswerable),
    }
    with open(RESULTS_DIR / "f2_dataset_manifest.json", "w") as f:
        json.dump(f2_manifest, f, indent=2)

    # === Load benchmark for evaluation ===
    print(f"\n{'='*60}")
    print("LOADING BENCHMARK")
    print(f"{'='*60}")

    benchmark_examples = []
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                benchmark_examples.append(json.loads(line))

    bench_cats = Counter(ex["question_kind"] for ex in benchmark_examples)
    print(f"  Benchmark: {len(benchmark_examples)} examples")
    print(f"  Categories: {dict(bench_cats)}")

    all_results = {}

    # === A0 — Production Baseline ===
    print(f"\n{'='*60}")
    print("A0 — PRODUCTION BASELINE (on benchmark)")
    print(f"{'='*60}")

    a0_tok = AutoTokenizer.from_pretrained(str(PROD_MODEL_DIR))
    a0_model = AutoModelForQuestionAnswering.from_pretrained(str(PROD_MODEL_DIR)).to(DEVICE)
    a0_preds, a0_confs, a0_lats = predict(a0_model, a0_tok, benchmark_examples)
    a0_results = evaluate(a0_preds, benchmark_examples, a0_confs, a0_lats)
    a0_results["model_label"] = "A0_Production"
    with open(RESULTS_DIR / "a0_benchmark.json", "w") as f:
        json.dump(a0_results, f, indent=2)
    all_results["A0"] = a0_results
    print(f"  A0 EM: {a0_results['overall']['em']}%, F1: {a0_results['overall']['f1']}%")
    print(f"  A0 Abstention: {a0_results['overall']['abstention_accuracy']}%, Spurious: {a0_results['overall']['spurious_rate']}%")
    del a0_model, a0_tok
    gc.collect()
    torch.cuda.empty_cache()

    # === A1 — Previous best (no unanswerable training) ===
    print(f"\n{'='*60}")
    print("A1 — PREVIOUS BEST (no unanswerable training)")
    print(f"{'='*60}")

    a1_config = {
        "model": "distilbert-base-uncased",
        "lr": 3e-5, "batch": 8, "grad_acc": 8, "epochs": 3, "fp16": True,
    }

    # Load A1 best checkpoint from Phase 4F.5-B
    a1_best_ckpt = None
    a1_base = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5" / "checkpoints" / "A1"
    if a1_base.exists():
        # Find best checkpoint
        ckpt_dirs = sorted([d for d in a1_base.iterdir() if d.is_dir() and d.name.startswith("checkpoint_")])
        if not ckpt_dirs:
            ckpt_dirs = sorted([d for d in a1_base.iterdir() if d.is_dir() and d.name.startswith("checkpoint")])
        if ckpt_dirs:
            a1_best_ckpt = str(ckpt_dirs[-1])  # Last checkpoint (or best)
            # Try to load training metadata to find best
            meta_path = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5" / "logs" / "a1_training.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    a1_meta = json.load(f)
                if a1_meta.get("best_checkpoint"):
                    a1_best_ckpt = a1_meta["best_checkpoint"]

    if a1_best_ckpt and Path(a1_best_ckpt).exists():
        print(f"  Loading A1 from: {a1_best_ckpt}")
        a1_tok = AutoTokenizer.from_pretrained(a1_best_ckpt, local_files_only=True)
        a1_model = AutoModelForQuestionAnswering.from_pretrained(a1_best_ckpt, local_files_only=True).to(DEVICE)
        a1_preds, a1_confs, a1_lats = predict(a1_model, a1_tok, benchmark_examples)
        a1_results = evaluate(a1_preds, benchmark_examples, a1_confs, a1_lats)
        a1_results["model_label"] = "A1_DistilBERT"
        with open(RESULTS_DIR / "a1_benchmark.json", "w") as f:
            json.dump(a1_results, f, indent=2)
        all_results["A1"] = a1_results
        print(f"  A1 EM: {a1_results['overall']['em']}%, F1: {a1_results['overall']['f1']}%")
        print(f"  A1 Abstention: {a1_results['overall']['abstention_accuracy']}%, Spurious: {a1_results['overall']['spurious_rate']}%")
        del a1_model, a1_tok
        gc.collect()
        torch.cuda.empty_cache()
    else:
        print("  WARNING: A1 checkpoint not found, skipping A1 evaluation")

    # === F1 — Unanswerable training (natural ratio) ===
    f1_meta = train_model(
        train_f1, val_f1, a1_config, "F1",
        f"{len(train_f1_answerable)} answerable + {len(train_f1_unanswerable)} unanswerable"
    )

    with open(LOGS_DIR / "f1_training.json", "w") as f:
        json.dump(f1_meta, f, indent=2)

    # Evaluate F1 on benchmark
    print(f"\n  Evaluating F1 on benchmark...")
    f1_tok = AutoTokenizer.from_pretrained(f1_meta["best_checkpoint"], local_files_only=True)
    f1_model = AutoModelForQuestionAnswering.from_pretrained(f1_meta["best_checkpoint"], local_files_only=True).to(DEVICE)
    f1_preds, f1_confs, f1_lats = predict(f1_model, f1_tok, benchmark_examples)
    f1_results = evaluate(f1_preds, benchmark_examples, f1_confs, f1_lats)
    f1_results["model_label"] = "F1_UnanswerableTraining"
    with open(RESULTS_DIR / "f1_benchmark.json", "w") as f:
        json.dump(f1_results, f, indent=2)
    all_results["F1"] = f1_results
    print(f"  F1 EM: {f1_results['overall']['em']}%, F1: {f1_results['overall']['f1']}%")
    print(f"  F1 Abstention: {f1_results['overall']['abstention_accuracy']}%, Spurious: {f1_results['overall']['spurious_rate']}%")

    # Threshold sweep for F1
    f1_sweep = threshold_sweep(f1_preds, benchmark_examples, f1_confs)
    with open(RESULTS_DIR / "f1_threshold_sweep.json", "w") as f:
        json.dump(f1_sweep, f, indent=2)

    del f1_model, f1_tok
    gc.collect()
    torch.cuda.empty_cache()

    # === F2 — Class-balanced (~3:1) ===
    f2_meta = train_model(
        train_f2, val_f1, a1_config, "F2",
        f"{len(train_f2_answerable)} answerable + {len(train_f2_unanswerable)} unanswerable (3:1 balanced)"
    )

    with open(LOGS_DIR / "f2_training.json", "w") as f:
        json.dump(f2_meta, f, indent=2)

    # Evaluate F2 on benchmark
    print(f"\n  Evaluating F2 on benchmark...")
    f2_tok = AutoTokenizer.from_pretrained(f2_meta["best_checkpoint"], local_files_only=True)
    f2_model = AutoModelForQuestionAnswering.from_pretrained(f2_meta["best_checkpoint"], local_files_only=True).to(DEVICE)
    f2_preds, f2_confs, f2_lats = predict(f2_model, f2_tok, benchmark_examples)
    f2_results = evaluate(f2_preds, benchmark_examples, f2_confs, f2_lats)
    f2_results["model_label"] = "F2_ClassBalanced"
    with open(RESULTS_DIR / "f2_benchmark.json", "w") as f:
        json.dump(f2_results, f, indent=2)
    all_results["F2"] = f2_results
    print(f"  F2 EM: {f2_results['overall']['em']}%, F1: {f2_results['overall']['f1']}%")
    print(f"  F2 Abstention: {f2_results['overall']['abstention_accuracy']}%, Spurious: {f2_results['overall']['spurious_rate']}%")

    # Threshold sweep for F2
    f2_sweep = threshold_sweep(f2_preds, benchmark_examples, f2_confs)
    with open(RESULTS_DIR / "f2_threshold_sweep.json", "w") as f:
        json.dump(f2_sweep, f, indent=2)

    del f2_model, f2_tok
    gc.collect()
    torch.cuda.empty_cache()

    # === Comparison ===
    print(f"\n{'='*60}")
    print("COMPARISON")
    print(f"{'='*60}")

    comparison = {"phase": "4F.5-F", "models": {}}
    for key in ["A0", "A1", "F1", "F2"]:
        if key in all_results:
            r = all_results[key]["overall"]
            comparison["models"][key] = {
                "label": all_results[key].get("model_label", key),
                "em": r["em"],
                "f1": r["f1"],
                "abstention": r["abstention_accuracy"],
                "spurious": r["spurious_rate"],
                "false_abstention": r["false_abstention"],
            }

    # Paired differences vs A1
    if "A1" in all_results:
        for comp_key, model_key in [("F1_vs_A1", "F1"), ("F2_vs_A1", "F2")]:
            if model_key in all_results:
                r1 = all_results[model_key]["overall"]
                ra = all_results["A1"]["overall"]
                comparison[comp_key] = {
                    "em_delta": round(r1["em"] - ra["em"], 1),
                    "f1_delta": round(r1["f1"] - ra["f1"], 1),
                    "abstention_delta": round(r1["abstention_accuracy"] - ra["abstention_accuracy"], 1),
                    "spurious_delta": round(r1["spurious_rate"] - ra["spurious_rate"], 1),
                }

    with open(RESULTS_DIR / "comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    # Print comparison table
    print(f"\n{'Model':<30} {'EM':>8} {'F1':>8} {'Abstain':>8} {'Spurious':>8}")
    print("-" * 70)
    for key in ["A0", "A1", "F1", "F2"]:
        if key in all_results:
            r = all_results[key]["overall"]
            label = all_results[key].get("model_label", key)
            print(f"{label:<30} {r['em']:>7.1f}% {r['f1']:>7.1f}% "
                  f"{r['abstention_accuracy']:>7.1f}% {r['spurious_rate']:>7.1f}%")

    # === Unanswerable analysis ===
    print(f"\n{'='*60}")
    print("UNANSWERABLE ANALYSIS")
    print(f"{'='*60}")

    unans_analysis = {}
    unans_examples = [ex for ex in benchmark_examples if ex["question_kind"] == "UNANSWERABLE"]
    for key in ["A0", "A1", "F1", "F2"]:
        if key in all_results:
            preds = a0_preds if key == "A0" else (a1_preds if key == "A1" else (f1_preds if key == "F1" else f2_preds))
            confs = a0_confs if key == "A0" else (a1_confs if key == "A1" else (f1_confs if key == "F1" else f2_confs))
            analysis = {"by_example": []}
            for i, ex in enumerate(unans_examples):
                # Find index in benchmark
                bench_idx = benchmark_examples.index(ex)
                pred = preds[bench_idx]
                conf = confs[bench_idx]
                analysis["by_example"].append({
                    "example_id": ex["example_id"],
                    "question": ex["question"],
                    "prediction": pred,
                    "confidence": round(conf, 4),
                    "abstained": not pred,
                    "subcategory": ex.get("metadata", {}).get("subcategory", "unknown"),
                })
            unans_analysis[key] = analysis
            abstained = sum(1 for e in analysis["by_example"] if e["abstained"])
            print(f"  {key}: {abstained}/{len(unans_examples)} abstained ({round(abstained/len(unans_examples)*100, 1)}%)")

    with open(RESULTS_DIR / "unanswerable_analysis.json", "w") as f:
        json.dump(unans_analysis, f, indent=2)

    # === Production safety verification ===
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
    status = "UNCHANGED" if prod_checksum == expected else "CHANGED!"
    print(f"  Production model: {prod_checksum[:16]}... {status}")
    assert prod_checksum == expected, "PRODUCTION MODEL CHANGED!"

    with open(DERIVED_DATASET, "rb") as f:
        dh = hashlib.sha256(f.read()).hexdigest()
    print(f"  Derived dataset: {dh[:16]}... UNCHANGED")
    assert dh == "abcf4182f39f0620fb056eee4167d1872baf9b4c748051eade9d6312332f271f"

    print("\n  ALL SAFETY CHECKS PASS")

    # === Save final manifest ===
    manifest = {
        "phase": "4F.5-F",
        "status": "EXPERIMENT_COMPLETE",
        "source_dataset_hash": src_hash,
        "production_model_checksum": prod_checksum,
        "production_unchanged": True,
        "derived_dataset_hash": dh,
        "f1_manifest": f1_manifest,
        "f2_manifest": f2_manifest,
        "results": {},
        "training_stability": {},
    }

    for key in ["A0", "A1", "F1", "F2"]:
        if key in all_results:
            manifest["results"][key] = {
                "em": all_results[key]["overall"]["em"],
                "f1": all_results[key]["overall"]["f1"],
                "abstention": all_results[key]["overall"]["abstention_accuracy"],
                "spurious": all_results[key]["overall"]["spurious_rate"],
            }

    manifest["training_stability"]["F1"] = "STABLE" if not f1_meta["nan_detected"] else "UNSTABLE"
    manifest["training_stability"]["F2"] = "STABLE" if not f2_meta["nan_detected"] else "UNSTABLE"

    with open(OUTPUT_DIR / "phase4f_5f_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print("ALL EXPERIMENTS COMPLETE")
    print(f"{'='*60}")

    return all_results


if __name__ == "__main__":
    main()

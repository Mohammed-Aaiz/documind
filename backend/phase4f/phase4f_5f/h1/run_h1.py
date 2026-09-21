#!/usr/bin/env python3
"""
Phase 4F.5-H1 - Document-Grounded Negative Training Experiment

Trains a fresh DistilBERT QA model using:
- F1 reconciled answerable training set (486 examples)
- H20 document-grounded unanswerable pool (114 examples)
- Total: 600 training examples

Evaluates on validation, holdout, and frozen benchmark.
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
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent.parent
DERIVED_DATASET = PROJECT_ROOT / "phase4f" / "phase4f_5" / "dataset" / "derived_dataset.jsonl"
SOURCE_DATASET = PROJECT_ROOT / "phase4f" / "dataset" / "training_data_v3_1.jsonl"
BENCHMARK_PATH = PROJECT_ROOT / "phase4f" / "phase4f_5d" / "benchmark" / "qa_benchmark_v1.jsonl"
H20_POOL_PATH = PROJECT_ROOT / "phase4f" / "phase4f_5f" / "h" / "pools" / "h20.jsonl"
PROD_MODEL_DIR = PROJECT_ROOT / "models" / "documind-qa"

CHECKPOINTS_DIR = BASE_DIR / "checkpoints"
LOGS_DIR = BASE_DIR / "logs"
EVAL_DIR = BASE_DIR / "evaluation"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 42
MAX_LENGTH = 384
MAX_ANSWER_LENGTH = 50

# Expected hashes
EXPECTED_SOURCE_HASH = "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
EXPECTED_DERIVED_HASH = "abcf4182f39f0620fb056eee4167d1872baf9b4c748051eade9d6312332f271f"
EXPECTED_BENCHMARK_HASH = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
EXPECTED_H20_HASH = "49defabe24affe40c0a849a8ec451659e9a200adb933643cab1bc01581d0305f"
EXPECTED_PROD_HASH = "df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac"


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


def compute_file_hash(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# === Dataset ===
class H1Dataset(Dataset):
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

        is_unanswerable = (
            ex.get("is_unanswerable", False)
            or ex.get("question_kind") == "UNANSWERABLE"
            or ex.get("is_impossible", False)
        )

        if is_unanswerable:
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


def load_derived_dataset():
    examples = []
    with open(DERIVED_DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def load_h20_pool():
    examples = []
    with open(H20_POOL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def convert_h20_to_training_format(h20_examples):
    """Convert H20 candidates to the same format as derived dataset examples."""
    converted = []
    for ex in h20_examples:
        converted.append({
            "example_id": ex["candidate_id"],
            "source": "phase4f_h20_grounding",
            "document_id": ex["source_document_id"],
            "question": ex["question"],
            "context": ex["context"],
            "answer": "",
            "answer_start": 0,
            "answer_end": 0,
            "question_kind": "UNANSWERABLE",
            "metadata": {
                "category": ex.get("category", ""),
                "subcategory": ex.get("subcategory", ""),
                "rationale": ex.get("rationale", ""),
                "is_impossible": True,
            },
            "split": "train",
            "token_span": None,
            "is_unanswerable": True,
        })
    return converted


def build_h1_training_set(derived_examples, h20_converted):
    """Build H1 training set: 486 F1-reconciled answerable + 114 H20 unanswerable."""
    excluded_ids = {"li_4fa4a839", "li_8770780b", "li_8bc7889f", "tc_3b383990"}

    # Load F1 reconciled IDs (486 train, 85 val from valid answerable train-split examples)
    f1_ids_path = BASE_DIR / "config" / "f1_reconciled_ids.json"
    with open(f1_ids_path) as f:
        f1_ids = json.load(f)
    train_answerable_ids = set(f1_ids["train_answerable_ids"])
    val_answerable_ids = set(f1_ids["val_answerable_ids"])

    train_answerable = []
    val_answerable = []
    val_unanswerable = []

    for ex in derived_examples:
        eid = ex["example_id"]
        if eid in excluded_ids:
            continue
        is_impossible = ex.get("metadata", {}).get("is_impossible", False)

        # Use F1 reconciled split for answerable examples
        if not is_impossible and eid in train_answerable_ids:
            train_answerable.append(ex)
        elif not is_impossible and eid in val_answerable_ids:
            val_answerable.append(ex)
        elif is_impossible or ex.get("question_kind") == "UNANSWERABLE":
            val_unanswerable.append(ex)

    # Validation = 85 answerable + 8 unanswerable (F1 convention: last 8 from sorted unanswerable)
    val_unanswerable_sorted = sorted(val_unanswerable, key=lambda x: x["example_id"])
    val_unanswerable_holdback = val_unanswerable_sorted[:8]  # 8 for validation
    holdout_unanswerable = val_unanswerable_sorted[8:]  # 14 for holdout

    validation = val_answerable + val_unanswerable_holdback

    # H1 training = 486 answerable + 114 H20 negatives
    h1_train = list(train_answerable) + h20_converted

    return h1_train, validation, train_answerable, h20_converted, holdout_unanswerable


def load_benchmark():
    examples = []
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def get_holdout_examples(derived_examples, val_unanswerable_count=20):
    """Get the 14-example holdout (last 14 unanswerable from validation)."""
    excluded_ids = {"li_4fa4a839", "li_8770780b", "li_8bc7889f", "tc_3b383990"}
    val_unanswerable = []
    for ex in derived_examples:
        if ex["example_id"] in excluded_ids:
            continue
        if ex.get("split") == "validation":
            is_impossible = ex.get("metadata", {}).get("is_impossible", False)
            if is_impossible or ex.get("question_kind") == "UNANSWERABLE":
                val_unanswerable.append(ex)
    val_unanswerable_sorted = sorted(val_unanswerable, key=lambda x: x["example_id"])
    return val_unanswerable_sorted[val_unanswerable_count:]


def predict(model, tokenizer, examples, max_length=MAX_LENGTH, max_answer_length=MAX_ANSWER_LENGTH):
    """Run inference and return predictions, confidences, and detailed logits."""
    model.eval()
    predictions = []
    confidences = []
    details = []

    for ex in examples:
        encoding = tokenizer(
            ex["question"], ex["context"],
            max_length=max_length, truncation=True,
            padding="max_length", return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(DEVICE)
        attention_mask = encoding["attention_mask"].to(DEVICE)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        start_logits = outputs.start_logits[0]
        end_logits = outputs.end_logits[0]

        # CLS/null scores
        cls_start_score = torch.softmax(start_logits, dim=0)[0].item()
        cls_end_score = torch.softmax(end_logits, dim=0)[0].item()
        null_score = (cls_start_score + cls_end_score) / 2

        # Best answer
        start_idx = torch.argmax(start_logits).item()
        end_idx = (
            torch.argmax(end_logits[start_idx:start_idx + max_answer_length]).item()
            + start_idx
        )
        answer_tokens = encoding["input_ids"][0][start_idx:end_idx + 1]
        answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        start_conf = torch.softmax(start_logits, dim=0)[start_idx].item()
        end_conf = torch.softmax(end_logits, dim=0)[end_idx].item()
        confidence = (start_conf + end_conf) / 2

        best_answer_score = confidence
        null_margin = null_score - best_answer_score

        predictions.append(answer)
        confidences.append(confidence)
        details.append({
            "null_score": round(null_score, 6),
            "best_answer_score": round(best_answer_score, 6),
            "null_margin": round(null_margin, 6),
            "start_idx": start_idx,
            "end_idx": end_idx,
        })

    return predictions, confidences, details


def evaluate(predictions, examples, confidences, details=None):
    results = {"total_examples": len(examples)}

    em_scores = []
    f1_scores = []
    answerable_correct = 0
    answerable_total = 0
    unanswerable_correct = 0
    unanswerable_total = 0
    spurious = 0
    false_abstention = 0

    for i, (pred, ex) in enumerate(zip(predictions, examples)):
        is_answerable = (
            ex.get("question_kind") != "UNANSWERABLE"
            and not ex.get("is_unanswerable", False)
            and not ex.get("is_impossible", False)
        )
        if is_answerable:
            answerable_total += 1
            em = exact_match(pred, ex.get("answer", ""))
            f1 = token_f1(pred, ex.get("answer", ""))
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
        "answerable_correct": answerable_correct,
        "answerable_total": answerable_total,
        "answerability_accuracy": round(answerable_correct / max(answerable_total, 1) * 100, 1),
        "abstention_accuracy": round(unanswerable_correct / max(unanswerable_total, 1) * 100, 1),
        "false_abstention": round(false_abstention / max(answerable_total, 1) * 100, 1),
        "spurious_rate": round(spurious / max(unanswerable_total, 1) * 100, 1),
        "answerable": answerable_total,
        "unanswerable": unanswerable_total,
    }

    by_cat = defaultdict(lambda: {"preds": [], "gts": [], "confs": []})
    for pred, ex, conf in zip(predictions, examples, confidences):
        cat = ex.get("question_kind", "UNKNOWN")
        by_cat[cat]["preds"].append(pred)
        by_cat[cat]["gts"].append(ex)
        by_cat[cat]["confs"].append(conf)

    per_category = {}
    for cat, data in sorted(by_cat.items()):
        cat_em = []
        cat_f1 = []
        for pred, gt in zip(data["preds"], data["gts"]):
            is_ans = (
                gt.get("question_kind") != "UNANSWERABLE"
                and not gt.get("is_unanswerable", False)
                and not gt.get("is_impossible", False)
            )
            if is_ans:
                cat_em.append(1 if exact_match(pred, gt.get("answer", "")) else 0)
                cat_f1.append(token_f1(pred, gt.get("answer", "")))
        per_category[cat] = {
            "n": len(data["preds"]),
            "em": round(np.mean(cat_em) * 100, 1) if cat_em else 0,
            "f1": round(np.mean(cat_f1) * 100, 1) if cat_f1 else 0,
        }
    results["by_category"] = per_category

    if details:
        unans_details = []
        for i, (ex, det) in enumerate(zip(examples, details)):
            is_ans = (
                ex.get("question_kind") != "UNANSWERABLE"
                and not ex.get("is_unanswerable", False)
                and not ex.get("is_impossible", False)
            )
            if not is_ans:
                unans_details.append({
                    "example_id": ex.get("example_id", ""),
                    "question": ex.get("question", "")[:80],
                    "prediction": predictions[i],
                    "null_score": det["null_score"],
                    "best_answer_score": det["best_answer_score"],
                    "null_margin": det["null_margin"],
                    "abstained": not predictions[i],
                })
        results["unanswerable_details"] = unans_details

    return results


def train_h1(train_examples, val_examples, config):
    """Train the H1 model."""
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)

    tok = AutoTokenizer.from_pretrained(config["model"])
    model = AutoModelForQuestionAnswering.from_pretrained(config["model"]).to(DEVICE)

    train_ds = H1Dataset(train_examples, tok, MAX_LENGTH)

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["lr"],
        weight_decay=config.get("weight_decay", 0.01),
    )
    total_steps = len(train_examples) // config["batch"] * config["epochs"]
    warmup_steps = int(total_steps * config.get("warmup_ratio", 0.1))
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    use_fp16 = config.get("fp16", False) and DEVICE.type == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_fp16 else None

    history = []
    best_val_score = -1
    best_checkpoint_path = None
    start_time = time.time()
    nan_detected = False

    ckpt_dir = CHECKPOINTS_DIR / "H1"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(config["epochs"]):
        model.train()
        total_loss = 0
        num_batches = 0
        epoch_start = time.time()
        train_loader = DataLoader(
            train_ds, batch_size=config["batch"],
            shuffle=True, num_workers=0,
        )

        for batch_idx, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            start_positions = batch["start_positions"].to(DEVICE)
            end_positions = batch["end_positions"].to(DEVICE)

            if use_fp16:
                with torch.amp.autocast("cuda"):
                    outputs = model(
                        input_ids=input_ids, attention_mask=attention_mask,
                        start_positions=start_positions, end_positions=end_positions,
                    )
                    loss = outputs.loss / config["grad_acc"]
                scaler.scale(loss).backward()
            else:
                outputs = model(
                    input_ids=input_ids, attention_mask=attention_mask,
                    start_positions=start_positions, end_positions=end_positions,
                )
                loss = outputs.loss / config["grad_acc"]
                loss.backward()

            loss_val = loss.item() * config["grad_acc"]
            if np.isnan(loss_val) or np.isinf(loss_val):
                nan_detected = True
            total_loss += loss_val
            num_batches += 1

            if (batch_idx + 1) % config["grad_acc"] == 0:
                if use_fp16:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_loss = total_loss / max(num_batches, 1)
        epoch_time = time.time() - epoch_start

        # Validation evaluation
        model.eval()
        val_preds = []
        val_confs = []
        for vex in val_examples:
            enc = tok(vex["question"], vex["context"], max_length=MAX_LENGTH,
                      truncation=True, padding="max_length", return_tensors="pt").to(DEVICE)
            with torch.no_grad():
                out = model(**enc)
            si = torch.argmax(out.start_logits[0]).item()
            ei = torch.argmax(out.end_logits[0][si:si+MAX_ANSWER_LENGTH]).item() + si
            pred = tok.decode(enc["input_ids"][0][si:ei+1], skip_special_tokens=True).strip()
            val_preds.append(pred)
            val_confs.append(0.0)

        val_results = evaluate(val_preds, val_examples, val_confs)
        val_em = val_results["overall"]["em"]
        val_f1 = val_results["overall"]["f1"]
        val_abstention = val_results["overall"]["abstention_accuracy"]
        val_spurious = val_results["overall"]["spurious_rate"]

        history.append({
            "epoch": epoch + 1,
            "loss": round(avg_loss, 4),
            "val_em": val_em,
            "val_f1": val_f1,
            "val_abstention": val_abstention,
            "val_spurious": val_spurious,
            "lr": scheduler.get_last_lr()[0],
            "time_s": round(epoch_time, 1),
        })

        print(f"  Epoch {epoch+1}: loss={avg_loss:.4f} val_EM={val_em}% val_F1={val_f1}% "
              f"val_abstain={val_abstention}% val_spurious={val_spurious}% time={epoch_time:.1f}s")

        # Save checkpoint
        epoch_ckpt = ckpt_dir / f"checkpoint_epoch{epoch+1}"
        epoch_ckpt.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(epoch_ckpt))
        tok.save_pretrained(str(epoch_ckpt))

        # Best by val EM
        if val_em > best_val_score:
            best_val_score = val_em
            best_checkpoint_path = str(epoch_ckpt)
            print(f"    -> New best checkpoint (val_EM={val_em}%)")

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
        "experiment": "H1",
        "model_name": config["model"],
        "config": config,
        "training_history": history,
        "training_time_s": round(total_time, 1),
        "peak_gpu_memory_mb": round(peak_mem, 0),
        "best_checkpoint": best_checkpoint_path,
        "best_val_em": best_val_score,
        "checkpoint_hash": ckpt_hash.hexdigest()[:16],
        "nan_detected": nan_detected,
        "device": str(DEVICE),
    }

    print(f"\n  Training complete: {total_time:.1f}s, Peak: {peak_mem:.0f}MB")
    print(f"  Best checkpoint: {best_checkpoint_path}")

    return metadata


def main():
    print("=" * 70)
    print("PHASE 4F.5-H1: DOCUMENT-GROUNDED NEGATIVE TRAINING")
    print("=" * 70)
    print(f"  Device: {DEVICE}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")

    # === STEP 1: Verify frozen artifacts ===
    print("\nSTEP 1: Verifying frozen artifacts...")
    for d in [CHECKPOINTS_DIR, LOGS_DIR, EVAL_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    src_hash = compute_file_hash(str(SOURCE_DATASET))
    assert src_hash == EXPECTED_SOURCE_HASH, f"SOURCE HASH MISMATCH: {src_hash}"
    print(f"  Source dataset: VERIFIED ({src_hash[:16]}...)")

    derived_hash = compute_file_hash(str(DERIVED_DATASET))
    assert derived_hash == EXPECTED_DERIVED_HASH, f"DERIVED HASH MISMATCH: {derived_hash}"
    print(f"  Derived dataset: VERIFIED ({derived_hash[:16]}...)")

    bench_hash = compute_file_hash(str(BENCHMARK_PATH))
    assert bench_hash == EXPECTED_BENCHMARK_HASH, f"BENCHMARK HASH MISMATCH: {bench_hash}"
    print(f"  Benchmark: VERIFIED ({bench_hash[:16]}...)")

    h20_hash = compute_file_hash(str(H20_POOL_PATH))
    assert h20_hash == EXPECTED_H20_HASH, f"H20 HASH MISMATCH: {h20_hash}"
    print(f"  H20 pool: VERIFIED ({h20_hash[:16]}...)")

    # Production integrity
    prod_hash_val = hashlib.sha256()
    for root, dirs, files in os.walk(str(PROD_MODEL_DIR)):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            with open(fp, "rb") as f:
                prod_hash_val.update(f.read())
    prod_checksum = prod_hash_val.hexdigest()
    assert prod_checksum == EXPECTED_PROD_HASH, f"PRODUCTION CHANGED: {prod_checksum}"
    print(f"  Production model: VERIFIED ({prod_checksum[:16]}...)")

    # === STEP 2-3: Load data ===
    print("\nSTEP 2-3: Loading F1 answerable + H20 negatives...")
    derived = load_derived_dataset()
    h20_raw = load_h20_pool()
    h20_converted = convert_h20_to_training_format(h20_raw)

    h1_train, validation, train_answerable, h20_train, holdout_legacy = build_h1_training_set(derived, h20_converted)
    holdout = get_holdout_examples(derived)

    print(f"  H1 Training: {len(h1_train)} ({len(train_answerable)} answerable + {len(h20_train)} H20 unanswerable)")
    print(f"  Validation: {len(validation)} ({sum(1 for e in validation if e.get('question_kind') != 'UNANSWERABLE' and not e.get('is_unanswerable', False))} answerable + {sum(1 for e in validation if e.get('question_kind') == 'UNANSWERABLE' or e.get('is_unanswerable', False))} unanswerable)")
    print(f"  Holdout: {len(holdout)}")
    print(f"  Negative ratio: {len(h20_train)}/{len(h1_train)} = {len(h20_train)/len(h1_train)*100:.1f}%")

    # Category distribution of H20
    h20_cats = Counter(ex.get("metadata", {}).get("category", "unknown") for ex in h20_train)
    print(f"  H20 category distribution: {dict(h20_cats.most_common())}")

    # Document distribution of H20
    h20_docs = Counter(ex.get("document_id", "unknown") for ex in h20_train)
    print(f"  H20 document distribution: {len(h20_docs)} documents")

    # Verify no H20 in validation/holdout
    h20_ids = {ex["example_id"] for ex in h20_train}
    val_ids = {ex["example_id"] for ex in validation}
    holdout_ids = {ex["example_id"] for ex in holdout}
    assert h20_ids.isdisjoint(val_ids), "H20 OVERLAP WITH VALIDATION!"
    assert h20_ids.isdisjoint(holdout_ids), "H20 OVERLAP WITH HOLDOUT!"
    print("  Leakage check: PASS (H20 disjoint from val/holdout)")

    # === STEP 8: Training configuration ===
    config = {
        "model": "distilbert-base-uncased",
        "lr": 3e-5,
        "batch": 8,
        "grad_acc": 8,
        "epochs": 3,
        "fp16": True,
        "weight_decay": 0.01,
        "warmup_ratio": 0.1,
        "seed": SEED,
    }
    with open(BASE_DIR / "config" / "h1_config.json", "w") as f:
        json.dump(config, f, indent=2)

    # === STEP 11: Training ===
    print("\nSTEP 11: Training H1 model...")
    h1_meta = train_h1(h1_train, validation, config)

    with open(LOGS_DIR / "h1_training.json", "w") as f:
        json.dump(h1_meta, f, indent=2)

    # === STEP 14: Validation evaluation ===
    print("\nSTEP 14: Validation evaluation...")
    h1_tok = AutoTokenizer.from_pretrained(h1_meta["best_checkpoint"], local_files_only=True)
    h1_model = AutoModelForQuestionAnswering.from_pretrained(h1_meta["best_checkpoint"], local_files_only=True).to(DEVICE)

    val_preds, val_confs, val_details = predict(h1_model, h1_tok, validation)
    val_results = evaluate(val_preds, validation, val_confs, val_details)
    with open(EVAL_DIR / "h1_validation.json", "w") as f:
        json.dump(val_results, f, indent=2)
    print(f"  Val EM: {val_results['overall']['em']}%, F1: {val_results['overall']['f1']}%")
    print(f"  Val Abstention: {val_results['overall']['abstention_accuracy']}%, Spurious: {val_results['overall']['spurious_rate']}%")

    # === STEP 15: Holdout evaluation ===
    print("\nSTEP 15: Holdout evaluation...")
    hold_preds, hold_confs, hold_details = predict(h1_model, h1_tok, holdout)
    hold_results = evaluate(hold_preds, holdout, hold_confs, hold_details)
    with open(EVAL_DIR / "h1_holdout.json", "w") as f:
        json.dump(hold_results, f, indent=2)
    print(f"  Holdout abstention: {hold_results['overall']['abstention_accuracy']}%, spurious: {hold_results['overall']['spurious_rate']}%")

    del h1_model, h1_tok
    gc.collect()
    torch.cuda.empty_cache()

    # === STEP 16: Benchmark evaluation ===
    print("\nSTEP 16: Benchmark evaluation...")
    benchmark = load_benchmark()
    bench_tok = AutoTokenizer.from_pretrained(h1_meta["best_checkpoint"], local_files_only=True)
    bench_model = AutoModelForQuestionAnswering.from_pretrained(h1_meta["best_checkpoint"], local_files_only=True).to(DEVICE)

    bench_preds, bench_confs, bench_details = predict(bench_model, bench_tok, benchmark)
    bench_results = evaluate(bench_preds, benchmark, bench_confs, bench_details)
    with open(EVAL_DIR / "h1_benchmark.json", "w") as f:
        json.dump(bench_results, f, indent=2)
    print(f"  Benchmark EM: {bench_results['overall']['em']}%, F1: {bench_results['overall']['f1']}%")
    print(f"  Benchmark Abstention: {bench_results['overall']['abstention_accuracy']}%, Spurious: {bench_results['overall']['spurious_rate']}%")

    # Category breakdown
    print("\n  Category breakdown:")
    for cat, data in sorted(bench_results.get("by_category", {}).items()):
        print(f"    {cat}: n={data['n']} EM={data['em']}% F1={data['f1']}%")

    del bench_model, bench_tok
    gc.collect()
    torch.cuda.empty_cache()

    # === STEP 19: Null-score analysis ===
    print("\nSTEP 19: Null-score analysis...")
    null_analysis = {
        "unanswerable_examples": len([d for d in bench_details]),
        "null_scores": [d["null_score"] for d in bench_details],
        "best_answer_scores": [d["best_answer_score"] for d in bench_details],
        "null_margins": [d["null_margin"] for d in bench_details],
    }
    # Get null scores for unanswerable specifically
    unans_details = bench_results.get("unanswerable_details", [])
    if unans_details:
        null_analysis["unanswerable_null_scores"] = [d["null_score"] for d in unans_details]
        null_analysis["unanswerable_null_margins"] = [d["null_margin"] for d in unans_details]
        null_analysis["mean_null_score"] = round(np.mean([d["null_score"] for d in unans_details]), 6)
        null_analysis["mean_null_margin"] = round(np.mean([d["null_margin"] for d in unans_details]), 6)
        print(f"  Unanswerable mean null_score: {null_analysis['mean_null_score']}")
        print(f"  Unanswerable mean null_margin: {null_analysis['mean_null_margin']}")

    with open(EVAL_DIR / "h1_null_analysis.json", "w") as f:
        json.dump(null_analysis, f, indent=2)

    # === STEP 21: Production integrity ===
    print("\nSTEP 21: Production integrity...")
    prod_hash_final = hashlib.sha256()
    for root, dirs, files in os.walk(str(PROD_MODEL_DIR)):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            with open(fp, "rb") as f:
                prod_hash_final.update(f.read())
    prod_final = prod_hash_final.hexdigest()
    print(f"  Production: {prod_final[:16]}... {'UNCHANGED' if prod_final == EXPECTED_PROD_HASH else 'CHANGED!'}")
    assert prod_final == EXPECTED_PROD_HASH, "PRODUCTION INTEGRITY ERROR"

    # === STEP 22: Manifest and report ===
    print("\nSTEP 22: Creating manifest and report...")
    manifest = {
        "phase": "4F.5-H1",
        "status": "H1_COMPLETE",
        "dataset": {
            "train_total": len(h1_train),
            "train_answerable": len(train_answerable),
            "train_unanswerable": len(h20_train),
            "negative_ratio": round(len(h20_train) / len(h1_train) * 100, 1),
            "val_total": len(validation),
            "holdout_total": len(holdout),
            "h20_hash": h20_hash,
        },
        "config": config,
        "training": h1_meta,
        "validation_results": val_results["overall"],
        "holdout_results": hold_results["overall"],
        "benchmark_results": bench_results["overall"],
        "benchmark_categories": bench_results.get("by_category", {}),
        "null_analysis": {k: v for k, v in null_analysis.items() if k != "null_scores" and k != "best_answer_scores" and k != "null_margins"},
        "production_checksum": prod_final,
        "production_unchanged": prod_final == EXPECTED_PROD_HASH,
        "source_dataset_hash": src_hash,
        "derived_dataset_hash": derived_hash,
        "benchmark_hash": bench_hash,
    }
    with open(BASE_DIR / "manifests" / "h1_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # === Comparison with baselines ===
    print("\n" + "=" * 70)
    print("COMPARISON WITH BASELINES")
    print("=" * 70)
    print(f"{'Model':<30} {'EM':>8} {'F1':>8} {'Abstain':>8} {'Spurious':>8}")
    print("-" * 70)
    print(f"{'A0 (Production)':<30} {'2.1%':>8} {'12.0%':>8} {'64.3%':>8} {'8.2%':>8}")
    print(f"{'A1 (DistilBERT)':<30} {'3.6%':>8} {'21.3%':>8} {'0.0%':>8} {'23.1%':>8}")
    print(f"{'F2 (20 synthetic)':<30} {'2.9%':>8} {'19.7%':>8} {'0.0%':>8} {'23.1%':>8}")
    br = bench_results["overall"]
    print(f"{'H1 (114 grounded)':<30} {br['em']:>7.1f}% {br['f1']:>7.1f}% {br['abstention_accuracy']:>7.1f}% {br['spurious_rate']:>7.1f}%")

    print(f"\n{'='*70}")
    print("H1 EXPERIMENT COMPLETE")
    print(f"{'='*70}")

    return manifest


if __name__ == "__main__":
    main()

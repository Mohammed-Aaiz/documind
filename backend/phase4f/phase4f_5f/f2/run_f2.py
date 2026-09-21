"""
Phase 4F.5-F2 — Targeted Unanswerable Training Experiment (Reconciled)

Uses exact reconciled IDs from Phase 4F.5-F1-R.
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
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
F2_DIR = Path(__file__).resolve().parent
RECONCILIATION_DIR = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5f" / "reconciliation"
DERIVED_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5" / "dataset" / "derived_dataset.jsonl"
SOURCE_DATASET = PROJECT_ROOT / "backend" / "phase4f" / "dataset" / "training_data_v3_1.jsonl"
PROD_MODEL_DIR = PROJECT_ROOT / "backend" / "models" / "documind-qa"
BENCHMARK_PATH = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5d" / "benchmark" / "qa_benchmark_v1.jsonl"

CHECKPOINTS_DIR = F2_DIR / "checkpoints"
LOGS_DIR = F2_DIR / "logs"
EVAL_DIR = F2_DIR / "evaluation"
MANIFESTS_DIR = F2_DIR / "manifests"
REPORTS_DIR = F2_DIR / "reports"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 42
MAX_LENGTH = 384
MAX_ANSWER_LENGTH = 50


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


# === Dataset — RECONCILED VERSION ===
class FDataset(Dataset):
    """QA dataset using reconciled IDs. Raises on invalid answerable spans."""

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
                # SAFETY: Never silently convert answerable to CLS
                raise ValueError(
                    f"Data integrity error: answerable example {ex['example_id']} "
                    f"has invalid token_span. This should not happen with reconciled IDs."
                )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "start_positions": start_pos,
            "end_positions": end_pos,
        }


# === Load data with reconciled IDs ===
def load_derived():
    examples = []
    with open(DERIVED_DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples

def load_reconciled_ids():
    with open(RECONCILIATION_DIR / "final_training_ids.json") as f:
        train_ids = json.load(f)
    with open(RECONCILIATION_DIR / "final_validation_ids.json") as f:
        val_ids = json.load(f)
    with open(RECONCILIATION_DIR / "final_holdout_ids.json") as f:
        hold_ids = json.load(f)
    return train_ids, val_ids, hold_ids

def filter_examples(all_examples, id_set):
    return [ex for ex in all_examples if ex["example_id"] in id_set]


# === Inference ===
def predict(model, tokenizer, examples):
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
        end_idx = torch.argmax(end_logits[start_idx:start_idx + MAX_ANSWER_LENGTH]).item() + start_idx
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
    results = {
        "eval_version": "4F.5-F2-eval-v1",
        "total_examples": len(examples),
    }
    em_scores, f1_scores = [], []
    answerable_correct = answerable_total = 0
    unanswerable_correct = unanswerable_total = 0
    spurious = false_abstention = 0

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
        "answerability_accuracy": round(answerable_correct / max(answerable_total, 1) * 100, 1),
        "abstention_accuracy": round(unanswerable_correct / max(unanswerable_total, 1) * 100, 1),
        "false_abstention": round(false_abstention / max(answerable_total, 1) * 100, 1),
        "spurious_rate": round(spurious / max(len(examples), 1) * 100, 1),
        "answerable": answerable_total,
        "unanswerable": unanswerable_total,
    }

    # Per-category
    by_cat = defaultdict(lambda: {"preds": [], "gts": [], "confs": []})
    for pred, ex, conf in zip(predictions, examples, confidences):
        by_cat[ex["question_kind"]]["preds"].append(pred)
        by_cat[ex["question_kind"]]["gts"].append(ex)
        by_cat[ex["question_kind"]]["confs"].append(conf)

    per_category = {}
    for cat, data in sorted(by_cat.items()):
        cat_em, cat_f1 = [], []
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
    correct_confs, incorrect_confs, abstained_confs, spurious_confs = [], [], [], []
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
        "separation": round(np.mean(correct_confs) - np.mean(spurious_confs), 4) if correct_confs and spurious_confs else 0,
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


# === Training ===
def train_model(train_examples, val_examples, config, exp_name, data_desc):
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
    best_val_score = -1
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
        val_em = val_f1 = val_count = 0
        val_abstained = val_spurious = 0
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

        # Combined score: val EM + abstention as tiebreak
        combined_score = val_em_pct + val_abstention_pct * 0.01

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

        if combined_score > best_val_score:
            best_val_score = combined_score
            best_checkpoint_path = str(epoch_ckpt)
            print(f"    -> New best checkpoint (val_EM={val_em_pct}%, val_abstain={val_abstention_pct}%)")

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
        "best_val_score": best_val_score,
        "checkpoint_hash": ckpt_hash.hexdigest()[:16],
        "nan_detected": nan_detected,
        "overflow_count": overflow_count,
        "device": str(DEVICE),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
    }

    print(f"\n  Training complete: {total_time:.1f}s, Peak: {peak_mem:.0f}MB")
    print(f"  Best checkpoint: {best_checkpoint_path}")

    return metadata


# === Main ===
def main():
    print("=" * 60)
    print("PHASE 4F.5-F2 — TARGETED UNANSWERABLE TRAINING")
    print("=" * 60)
    print(f"  Device: {DEVICE}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")

    # === Verify source hashes ===
    with open(SOURCE_DATASET, "rb") as f:
        src_hash = hashlib.sha256(f.read()).hexdigest()
    assert src_hash == "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
    print(f"  Source hash: VERIFIED ({src_hash[:16]}...)")

    for d in [CHECKPOINTS_DIR, LOGS_DIR, EVAL_DIR, MANIFESTS_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # === Load reconciled IDs ===
    print(f"\n{'='*60}")
    print("LOADING RECONCILED IDS")
    print(f"{'='*60}")

    train_ids_meta, val_ids_meta, hold_ids_meta = load_reconciled_ids()
    train_answerable_ids = set(train_ids_meta["answerable_ids"])
    train_unanswerable_ids = set(train_ids_meta["unanswerable_ids"])
    val_answerable_ids = set(val_ids_meta["answerable_ids"])
    val_unanswerable_ids = set(val_ids_meta["unanswerable_ids"])
    holdout_ids = set(hold_ids_meta["unanswerable_ids"])

    print(f"  Train answerable IDs: {len(train_answerable_ids)}")
    print(f"  Train unanswerable IDs: {len(train_unanswerable_ids)}")
    print(f"  Val answerable IDs: {len(val_answerable_ids)}")
    print(f"  Val unanswerable IDs: {len(val_unanswerable_ids)}")
    print(f"  Holdout IDs: {len(holdout_ids)}")

    # === Load derived dataset and filter ===
    all_examples = load_derived()
    print(f"\n  Loaded {len(all_examples)} examples from derived dataset")

    train_answerable = filter_examples(all_examples, train_answerable_ids)
    train_unanswerable = filter_examples(all_examples, train_unanswerable_ids)
    val_answerable = filter_examples(all_examples, val_answerable_ids)
    val_unanswerable = filter_examples(all_examples, val_unanswerable_ids)
    holdout_examples = filter_examples(all_examples, holdout_ids)

    train_examples = train_answerable + train_unanswerable
    val_examples = val_answerable + val_unanswerable

    print(f"\n  FINAL TRAIN: {len(train_examples)} ({len(train_answerable)} answerable + {len(train_unanswerable)} unanswerable)")
    print(f"  FINAL VAL:   {len(val_examples)} ({len(val_answerable)} answerable + {len(val_unanswerable)} unanswerable)")
    print(f"  HOLDOUT:     {len(holdout_examples)} unanswerable")

    # === Save training config ===
    config = {
        "model": "distilbert-base-uncased",
        "lr": 3e-5,
        "batch": 8,
        "grad_acc": 8,
        "epochs": 3,
        "fp16": True,
    }

    with open(F2_DIR / "config" / "f2_config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Save dataset hashes
    train_id_hash = hashlib.sha256(json.dumps(sorted(train_ids_meta["answerable_ids"] + train_ids_meta["unanswerable_ids"])).encode()).hexdigest()
    val_id_hash = hashlib.sha256(json.dumps(sorted(val_ids_meta["answerable_ids"] + val_ids_meta["unanswerable_ids"])).encode()).hexdigest()

    with open(MANIFESTS_DIR / "f2_dataset_ids.json", "w") as f:
        json.dump({
            "train_answerable_count": len(train_answerable_ids),
            "train_unanswerable_count": len(train_unanswerable_ids),
            "val_answerable_count": len(val_answerable_ids),
            "val_unanswerable_count": len(val_unanswerable_ids),
            "holdout_count": len(holdout_ids),
            "train_id_hash": train_id_hash[:16],
            "val_id_hash": val_id_hash[:16],
            "source_dataset_hash": src_hash[:16],
        }, f, indent=2)

    # === TRAIN F2 ===
    f2_meta = train_model(
        train_examples, val_examples, config, "F2",
        f"{len(train_answerable)} answerable + {len(train_unanswerable)} unanswerable (reconciled)"
    )

    with open(LOGS_DIR / "f2_training.json", "w") as f:
        json.dump(f2_meta, f, indent=2)

    # === Load best checkpoint for evaluation ===
    print(f"\n{'='*60}")
    print("LOADING BEST CHECKPOINT FOR EVALUATION")
    print(f"{'='*60}")

    best_ckpt = f2_meta["best_checkpoint"]
    print(f"  Checkpoint: {best_ckpt}")

    f2_tok = AutoTokenizer.from_pretrained(best_ckpt, local_files_only=True)
    f2_model = AutoModelForQuestionAnswering.from_pretrained(best_ckpt, local_files_only=True).to(DEVICE)

    # === VALIDATION EVALUATION ===
    print(f"\n{'='*60}")
    print("VALIDATION EVALUATION")
    print(f"{'='*60}")

    val_preds, val_confs, val_lats = predict(f2_model, f2_tok, val_examples)
    val_results = evaluate(val_preds, val_examples, val_confs, val_lats)
    val_results["model_label"] = "F2_Reconciled"

    with open(EVAL_DIR / "f2_validation.json", "w") as f:
        json.dump(val_results, f, indent=2)

    print(f"  Val EM: {val_results['overall']['em']}%, F1: {val_results['overall']['f1']}%")
    print(f"  Val Abstention: {val_results['overall']['abstention_accuracy']}%, Spurious: {val_results['overall']['spurious_rate']}%")

    # === HOLDOUT EVALUATION (14 unanswerable) ===
    print(f"\n{'='*60}")
    print("HOLDOUT EVALUATION (14 unanswerable)")
    print(f"{'='*60}")

    hold_preds, hold_confs, hold_lats = predict(f2_model, f2_tok, holdout_examples)
    hold_results = evaluate(hold_preds, holdout_examples, hold_confs, hold_lats)

    with open(EVAL_DIR / "f2_holdout.json", "w") as f:
        json.dump(hold_results, f, indent=2)

    hold_abstained = sum(1 for p in hold_preds if not p)
    hold_spurious = sum(1 for p in hold_preds if p)
    print(f"  Holdout abstained: {hold_abstained}/14 ({round(hold_abstained/14*100,1)}%)")
    print(f"  Holdout spurious:  {hold_spurious}/14 ({round(hold_spurious/14*100,1)}%)")

    # === BENCHMARK EVALUATION ===
    print(f"\n{'='*60}")
    print("BENCHMARK EVALUATION (Phase 4F.5-D)")
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

    bench_preds, bench_confs, bench_lats = predict(f2_model, f2_tok, benchmark_examples)
    bench_results = evaluate(bench_preds, benchmark_examples, bench_confs, bench_lats)
    bench_results["model_label"] = "F2_Reconciled"

    with open(EVAL_DIR / "f2_benchmark.json", "w") as f:
        json.dump(bench_results, f, indent=2)

    print(f"  Bench EM: {bench_results['overall']['em']}%, F1: {bench_results['overall']['f1']}%")
    print(f"  Bench Abstention: {bench_results['overall']['abstention_accuracy']}%, Spurious: {bench_results['overall']['spurious_rate']}%")

    # === BASELINE COMPARISON ===
    print(f"\n{'='*60}")
    print("BASELINE COMPARISON")
    print(f"{'='*60}")

    # Load A0/A1 results if they exist
    all_results = {"F2": bench_results}

    a0_path = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5f" / "results" / "a0_benchmark.json"
    if a0_path.exists():
        with open(a0_path) as f:
            a0 = json.load(f)
        all_results["A0"] = a0
        print(f"  A0 EM: {a0['overall']['em']}%, F1: {a0['overall']['f1']}%")

    a1_path = PROJECT_ROOT / "backend" / "phase4f" / "phase4f_5f" / "results" / "a1_benchmark.json"
    if a1_path.exists():
        with open(a1_path) as f:
            a1 = json.load(f)
        all_results["A1"] = a1
        print(f"  A1 EM: {a1['overall']['em']}%, F1: {a1['overall']['f1']}%")

    # Print comparison table
    print(f"\n{'Model':<30} {'EM':>8} {'F1':>8} {'Abstain':>8} {'Spurious':>8}")
    print("-" * 70)
    for key in ["A0", "A1", "F2"]:
        if key in all_results:
            r = all_results[key]["overall"]
            label = all_results[key].get("model_label", key)
            print(f"{label:<30} {r['em']:>7.1f}% {r['f1']:>7.1f}% "
                  f"{r['abstention_accuracy']:>7.1f}% {r['spurious_rate']:>7.1f}%")

    # === PRODUCTION SAFETY ===
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

    # Benchmark checksum
    with open(BENCHMARK_PATH, "rb") as f:
        bh = hashlib.sha256(f.read()).hexdigest()
    assert bh == "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
    print(f"  Benchmark: UNCHANGED")

    # Source dataset
    with open(DERIVED_DATASET, "rb") as f:
        dh = hashlib.sha256(f.read()).hexdigest()
    assert dh == "abcf4182f39f0620fb056eee4167d1872baf9b4c748051eade9d6312332f271f"
    print(f"  Derived dataset: UNCHANGED")

    print("\n  ALL SAFETY CHECKS PASS")

    # === SAVE FINAL MANIFEST ===
    manifest = {
        "phase": "4F.5-F2",
        "status": "EXPERIMENT_COMPLETE",
        "source_dataset_hash": src_hash[:16],
        "production_model_checksum": prod_checksum[:16],
        "production_unchanged": True,
        "benchmark_unchanged": True,
        "derived_dataset_unchanged": True,
        "training": {
            "train_answerable": len(train_answerable),
            "train_unanswerable": len(train_unanswerable),
            "train_total": len(train_examples),
            "val_answerable": len(val_answerable),
            "val_unanswerable": len(val_unanswerable),
            "val_total": len(val_examples),
            "holdout_count": len(holdout_examples),
            "config": config,
            "training_time_s": f2_meta["training_time_s"],
            "peak_gpu_memory_mb": f2_meta["peak_gpu_memory_mb"],
            "best_checkpoint": f2_meta["best_checkpoint"],
            "checkpoint_hash": f2_meta["checkpoint_hash"],
        },
        "validation_results": val_results["overall"],
        "holdout_results": hold_results["overall"],
        "benchmark_results": bench_results["overall"],
        "training_stability": "STABLE" if not f2_meta["nan_detected"] else "UNSTABLE",
    }

    with open(MANIFESTS_DIR / "f2_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # === UNANSWERABLE ANALYSIS ===
    print(f"\n{'='*60}")
    print("UNANSWERABLE ANALYSIS")
    print(f"{'='*60}")

    unans_bench = [ex for ex in benchmark_examples if ex["question_kind"] == "UNANSWERABLE"]
    bench_abstained = sum(1 for p, ex in zip(bench_preds, benchmark_examples) if ex["question_kind"] == "UNANSWERABLE" and not p)
    bench_spurious = sum(1 for p, ex in zip(bench_preds, benchmark_examples) if ex["question_kind"] == "UNANSWERABLE" and p)
    print(f"  Benchmark unanswerable: {len(unans_bench)}")
    print(f"  Abstained: {bench_abstained}/{len(unans_bench)} ({round(bench_abstained/len(unans_bench)*100,1)}%)")
    print(f"  Spurious: {bench_spurious}/{len(unans_bench)} ({round(bench_spurious/len(unans_bench)*100,1)}%)")

    print(f"\n{'='*60}")
    print("EXPERIMENT COMPLETE")
    print(f"{'='*60}")

    return all_results


if __name__ == "__main__":
    main()

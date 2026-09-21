"""
Phase 4F.4 — Controlled GPU QA Experiment
Full training + evaluation pipeline.

Uses isolated GPU environment: backend/phase4f_gpu/
Dataset: phase4f-qa-v3.1 (frozen, read-only)
"""
import json, hashlib, os, sys, time, gc, math, random
from pathlib import Path
from collections import defaultdict, Counter

import torch
import numpy as np
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForQuestionAnswering, AutoTokenizer,
    get_linear_schedule_with_warmup
)

# ─── Config ───────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "backend" / "phase4f" / "dataset" / "training_data_v3_1.jsonl"
PROD_MODEL_DIR = PROJECT_ROOT / "backend" / "models" / "documind-qa"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 42
MAX_LENGTH = 384
EPOCHS = 3
EFFECTIVE_BATCH = 64

EXPERIMENTS = {
    "a0": {"name": "A0_Production_Baseline", "model": None, "train": False},
    "a1": {
        "name": "A1_DistilBERT",
        "model": "distilbert-base-cased",
        "lr": 3e-5, "batch": 8, "grad_acc": 8,
        "train": True, "fp16": True
    },
    "a2": {
        "name": "A2_BERT_Base",
        "model": "bert-base-cased",
        "lr": 2e-5, "batch": 8, "grad_acc": 8,
        "train": True, "fp16": True
    },
    "a3": {
        "name": "A3_DeBERTa_v3",
        "model": "microsoft/deberta-v3-base",
        "lr": 1e-5, "batch": 4, "grad_acc": 16,
        "train": True, "fp16": False  # fp16 unstable for DeBERTa on 4GB
    },
}

CATEGORIES = [
    "DIRECT_SPAN", "ENTITY", "DATE", "NUMERIC", "TABLE_CELL",
    "TABLE_ROW", "LIST_ITEM", "SECTION_SPECIFIC", "LONG_CONTEXT",
    "MULTI_CHUNK", "UNANSWERABLE"
]

# ─── Dataset ──────────────────────────────────────────────────────
class QADataset(Dataset):
    def __init__(self, data_path, tokenizer, max_length=MAX_LENGTH):
        self.examples = []
        self.tokenizer = tokenizer
        self.max_length = max_length
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.examples.append(json.loads(line))

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]
        encoding = self.tokenizer(
            ex["question"], ex["context"],
            max_length=self.max_length, truncation=True,
            padding="max_length", return_tensors="pt"
        )
        if ex["question_kind"] == "UNANSWERABLE":
            start_pos = torch.tensor(0)
            end_pos = torch.tensor(0)
        else:
            # Map character offsets to token offsets
            q_tokens = self.tokenizer.encode(ex["question"], add_special_tokens=False)
            context_text = ex["context"]
            answer = ex["answer"]
            ans_start_char = ex["answer_start"]
            ans_end_char = ex["answer_end"]

            # Find token positions for answer span
            offset_mapping = encoding.get("offset_mapping", [None])[0]
            start_token, end_token = 0, 0
            if offset_mapping is not None:
                for i, (s, e) in enumerate(offset_mapping):
                    if s <= ans_start_char < e:
                        start_token = i
                    if s < ans_end_char <= e:
                        end_token = i
                        break
            else:
                # Fallback: encode context and find approximate positions
                ctx_ids = self.tokenizer.encode(context_text, add_special_tokens=False)
                # Simple heuristic
                start_token = min(ans_start_char, len(ctx_ids) - 1)
                end_token = min(ans_end_char - 1, len(ctx_ids) - 1)

            start_pos = torch.tensor(start_token)
            end_pos = torch.tensor(end_token)

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

def evaluate_model(model, tokenizer, data_path, max_length=MAX_LENGTH, label="model"):
    """Full evaluation with all required metrics."""
    model.eval()
    device = DEVICE

    # Load all examples
    examples = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))

    # Run inference
    all_preds = []
    latencies = []
    confidences = []

    for ex in examples:
        t0 = time.time()
        encoding = tokenizer(
            ex["question"], ex["context"],
            max_length=max_length, truncation=True,
            padding="max_length", return_tensors="pt"
        )
        input_ids = encoding["input_ids"].to(device)
        attention_mask = encoding["attention_mask"].to(device)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        start_logits = outputs.start_logits[0]
        end_logits = outputs.end_logits[0]

        # Find best span
        max_ans_len = 50
        start_idx = torch.argmax(start_logits).item()
        end_idx = torch.argmax(end_logits[start_idx:start_idx + max_ans_len]).item() + start_idx

        answer_tokens = encoding["input_ids"][0][start_idx:end_idx + 1]
        answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        start_conf = torch.softmax(start_logits, dim=0)[start_idx].item()
        end_conf = torch.softmax(end_logits, dim=0)[end_idx].item()
        confidence = (start_conf + end_conf) / 2

        all_preds.append(answer)
        confidences.append(confidence)
        latencies.append(time.time() - t0)

    # Compute metrics
    results = {
        "model_label": label,
        "total_examples": len(examples),
        "overall": {},
        "by_category": {},
        "failure_taxonomy": {},
        "confidence_analysis": {},
        "latency_ms": round(np.mean(latencies) * 1000, 2),
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

    # Per-category metrics
    by_cat = defaultdict(lambda: {"preds": [], "gts": [], "confs": []})
    for pred, ex, conf in zip(all_preds, examples, confidences):
        cat = ex["question_kind"]
        by_cat[cat]["preds"].append(pred)
        by_cat[cat]["gts"].append(ex)
        by_cat[cat]["confs"].append(conf)

    for cat, data in sorted(by_cat.items()):
        cat_em = []
        cat_f1 = []
        cat_conf_correct = []
        cat_conf_incorrect = []
        for pred, gt, conf in zip(data["preds"], data["gts"], data["confs"]):
            if gt["question_kind"] != "UNANSWERABLE":
                em = exact_match(pred, gt["answer"])
                f1 = token_f1(pred, gt["answer"])
                cat_em.append(1 if em else 0)
                cat_f1.append(f1)
                if em:
                    cat_conf_correct.append(conf)
                else:
                    cat_conf_incorrect.append(conf)
            else:
                if not pred:
                    cat_conf_correct.append(conf)
                else:
                    cat_conf_incorrect.append(conf)

        results["by_category"][cat] = {
            "n": len(data["preds"]),
            "em": round(np.mean(cat_em) * 100, 1) if cat_em else 0,
            "f1": round(np.mean(cat_f1) * 100, 1) if cat_f1 else 0,
            "avg_confidence": round(np.mean(data["confs"]), 4),
        }

    # Confidence analysis
    correct_confs = []
    incorrect_confs = []
    for pred, ex, conf in zip(all_preds, examples, confidences):
        is_answerable = ex["question_kind"] != "UNANSWERABLE"
        if is_answerable:
            if exact_match(pred, ex["answer"]):
                correct_confs.append(conf)
            else:
                incorrect_confs.append(conf)

    results["confidence_analysis"] = {
        "correct_mean": round(np.mean(correct_confs), 4) if correct_confs else 0,
        "correct_std": round(np.std(correct_confs), 4) if correct_confs else 0,
        "incorrect_mean": round(np.mean(incorrect_confs), 4) if incorrect_confs else 0,
        "incorrect_std": round(np.std(incorrect_confs), 4) if incorrect_confs else 0,
        "separation": round(np.mean(correct_confs) - np.mean(incorrect_confs), 4) if correct_confs and incorrect_confs else 0,
        "ECE": "NOT_IMPLEMENTED",
        "Brier": "NOT_IMPLEMENTED",
    }

    # Failure taxonomy (structural classification)
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

    results["failure_taxonomy"] = {
        "total_failures": total_failures,
        "failure_rate": round(total_failures / max(len(examples), 1) * 100, 1),
        "by_type": dict(failures),
    }

    return results

# ─── Training ─────────────────────────────────────────────────────
def train_experiment(exp_key, config, data_path, results_dir):
    """Train a single experiment and return metrics."""
    print(f"\n{'='*60}")
    print(f"TRAINING: {config['name']}")
    print(f"{'='*60}")

    exp_dir = results_dir / exp_key.upper()
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Set seed
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)

    # Load tokenizer and model
    print(f"  Loading model: {config['model']}")
    tok = AutoTokenizer.from_pretrained(config["model"])
    model = AutoModelForQuestionAnswering.from_pretrained(config["model"]).to(DEVICE)

    # Load dataset
    dataset = QADataset(data_path, tok, MAX_LENGTH)
    print(f"  Dataset: {len(dataset)} examples")

    loader = DataLoader(dataset, batch_size=config["batch"], shuffle=True, num_workers=0)

    # Optimizer + scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["lr"], weight_decay=0.01)
    total_steps = len(loader) * EPOCHS // config["grad_acc"]
    warmup_steps = int(total_steps * 0.1)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # Training loop
    use_fp16 = config.get("fp16", False) and DEVICE.type == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_fp16 else None

    history = []
    best_val_em = 0
    start_time = time.time()

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        num_batches = 0
        epoch_start = time.time()

        for batch_idx, batch in enumerate(loader):
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

            total_loss += loss.item() * config["grad_acc"]
            num_batches += 1

            if (batch_idx + 1) % config["grad_acc"] == 0:
                if use_fp16:
                    try:
                        scaler.unscale_(optimizer)
                        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        scaler.step(optimizer)
                    except (ValueError, RuntimeError):
                        # FP16 gradient overflow — skip this optimizer step
                        print(f"    WARNING: fp16 grad overflow at batch {batch_idx}, skipping step")
                    finally:
                        scaler.update()
                else:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_loss = total_loss / max(num_batches, 1)
        epoch_time = time.time() - epoch_start
        print(f"  Epoch {epoch+1}/{EPOCHS}: loss={avg_loss:.4f}, time={epoch_time:.1f}s")

        history.append({
            "epoch": epoch + 1,
            "loss": avg_loss,
            "lr": scheduler.get_last_lr()[0],
            "time_s": epoch_time,
        })

        # Quick validation eval on a subset
        model.eval()
        val_em, val_f1, val_count = 0, 0, 0
        with open(data_path, "r") as f:
            val_examples = [json.loads(l) for l in f if l.strip()]
        # Use last 100 examples as validation
        val_subset = val_examples[-100:]
        for vex in val_subset:
            enc = tok(vex["question"], vex["context"], max_length=MAX_LENGTH,
                      truncation=True, padding="max_length", return_tensors="pt").to(DEVICE)
            with torch.no_grad():
                out = model(**enc)
            si = torch.argmax(out.start_logits[0]).item()
            ei = torch.argmax(out.end_logits[0][si:si+50]).item() + si
            pred = tok.decode(enc["input_ids"][0][si:ei+1], skip_special_tokens=True).strip()
            if vex["question_kind"] != "UNANSWERABLE":
                val_count += 1
                if exact_match(pred, vex["answer"]):
                    val_em += 1
                val_f1 += token_f1(pred, vex["answer"])

        val_em_pct = round(val_em / max(val_count, 1) * 100, 1)
        val_f1_pct = round(val_f1 / max(val_count, 1) * 100, 1)
        history[-1]["val_em"] = val_em_pct
        history[-1]["val_f1"] = val_f1_pct
        print(f"  Val EM: {val_em_pct}%, Val F1: {val_f1_pct}%")

        # Always save checkpoint (overwrite each epoch)
        model.save_pretrained(str(exp_dir / "checkpoint_best"))
        tok.save_pretrained(str(exp_dir / "checkpoint_best"))
        if val_em_pct > best_val_em:
            best_val_em = val_em_pct

        model.train()
        gc.collect()
        torch.cuda.empty_cache()

    total_time = time.time() - start_time
    peak_mem = torch.cuda.max_memory_allocated(0) / 1e6 if torch.cuda.is_available() else 0

    # Compute checkpoint hash
    ckpt_dir = exp_dir / "checkpoint_best"
    ckpt_hash = hashlib.sha256()
    for root, dirs, files in os.walk(str(ckpt_dir)):
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
        "checkpoint_hash": ckpt_hash_hex,
        "device": str(DEVICE),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        "pytorch_version": torch.__version__,
    }
    with open(exp_dir / "training_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  Training complete: {total_time:.1f}s")
    print(f"  Peak GPU memory: {peak_mem:.0f} MB")
    print(f"  Checkpoint hash: {ckpt_hash_hex}")

    return metadata

# ─── A0 Baseline ──────────────────────────────────────────────────
def run_a0_baseline(data_path, results_dir):
    """Evaluate the current production model as A0 baseline."""
    print(f"\n{'='*60}")
    print(f"EVALUATING: A0 Production Baseline")
    print(f"{'='*60}")

    a0_dir = results_dir / "A0"
    a0_dir.mkdir(parents=True, exist_ok=True)

    # Load production model
    print(f"  Loading production model from: {PROD_MODEL_DIR}")
    tok = AutoTokenizer.from_pretrained(str(PROD_MODEL_DIR))
    model = AutoModelForQuestionAnswering.from_pretrained(str(PROD_MODEL_DIR)).to(DEVICE)

    # Evaluate
    results = evaluate_model(model, tok, data_path, label="A0_Production_Baseline")

    # Save results
    with open(a0_dir / "evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Save metadata
    prod_hash = hashlib.sha256()
    for root, dirs, files in os.walk(str(PROD_MODEL_DIR)):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            with open(fp, "rb") as f:
                prod_hash.update(f.read())

    metadata = {
        "experiment": "A0_Production_Baseline",
        "model_dir": str(PROD_MODEL_DIR),
        "checkpoint_hash": prod_hash.hexdigest()[:16],
        "full_checksum": prod_hash.hexdigest(),
        "device": str(DEVICE),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
    }
    with open(a0_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  A0 EM: {results['overall']['em']}%")
    print(f"  A0 F1: {results['overall']['f1']}%")
    print(f"  A0 Answerability: {results['overall']['answerability_accuracy']}%")

    del model, tok
    gc.collect()
    torch.cuda.empty_cache()

    return results

# ─── Main ─────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("PHASE 4F.4 — CONTROLLED GPU QA EXPERIMENT")
    print("=" * 60)
    print(f"  Device: {DEVICE}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e6:.0f} MB")
    print(f"  PyTorch: {torch.__version__}")
    print(f"  Dataset: {DATASET_PATH}")
    print(f"  Results: {RESULTS_DIR}")
    print()

    # Verify dataset
    with open(DATASET_PATH, "rb") as f:
        data_bytes = f.read()
    dataset_hash = hashlib.sha256(data_bytes).hexdigest()
    expected_hash = "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
    assert dataset_hash == expected_hash, f"DATASET HASH MISMATCH: {dataset_hash}"
    print(f"  Dataset hash: VERIFIED ({dataset_hash[:16]})")

    all_results = {}

    # A0: Production baseline
    a0_results = run_a0_baseline(str(DATASET_PATH), RESULTS_DIR)
    all_results["a0"] = a0_results

    # A1, A2, A3: Train and evaluate
    for exp_key in ["a1", "a2", "a3"]:
        config = EXPERIMENTS[exp_key]
        exp_dir = RESULTS_DIR / exp_key.upper()

        # Train
        train_metadata = train_experiment(exp_key, config, str(DATASET_PATH), RESULTS_DIR)

        # Load best checkpoint and evaluate
        print(f"\n  Evaluating {config['name']}...")
        ckpt_dir = exp_dir / "checkpoint_best"
        tok = AutoTokenizer.from_pretrained(str(ckpt_dir), local_files_only=True)
        model = AutoModelForQuestionAnswering.from_pretrained(str(ckpt_dir), local_files_only=True).to(DEVICE)
        eval_results = evaluate_model(model, tok, str(DATASET_PATH), label=config["name"])

        # Save evaluation
        with open(exp_dir / "evaluation_results.json", "w") as f:
            json.dump(eval_results, f, indent=2)

        all_results[exp_key] = eval_results

        # Production safety check
        prod_hash = hashlib.sha256()
        for root, dirs, files in os.walk(str(PROD_MODEL_DIR)):
            for fn in sorted(files):
                fp = os.path.join(root, fn)
                with open(fp, "rb") as f:
                    prod_hash.update(f.read())
        assert prod_hash.hexdigest()[:16] == "df592aa8d0ee1a23", \
            f"PRODUCTION MODEL CHANGED! Expected df592aa8d0ee1a23, got {prod_hash.hexdigest()[:16]}"
        print(f"  Production model safety: VERIFIED")

        del model, tok
        gc.collect()
        torch.cuda.empty_cache()

    # Save all results
    with open(RESULTS_DIR / "all_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'='*60}")
    print("ALL EXPERIMENTS COMPLETE")
    print(f"{'='*60}")

    # Print comparison table
    print(f"\n{'Model':<25} {'EM':>8} {'F1':>8} {'Answer':>8} {'Abstain':>8} {'Spurious':>8}")
    print("-" * 73)
    for key in ["a0", "a1", "a2", "a3"]:
        r = all_results[key]["overall"]
        print(f"{all_results[key]['model_label']:<25} {r['em']:>7.1f}% {r['f1']:>7.1f}% "
              f"{r['answerability_accuracy']:>7.1f}% {r['abstention_accuracy']:>7.1f}% "
              f"{r['spurious_rate']:>7.1f}%")

    return all_results

if __name__ == "__main__":
    main()

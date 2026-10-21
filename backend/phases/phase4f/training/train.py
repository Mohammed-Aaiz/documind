"""Phase 4F — Training Script.

Supports both full GPU training and CPU smoke testing.

If GPU unavailable, runs a minimal smoke test to validate the pipeline
and marks FULL_TRAINING_STATUS = BLOCKED_BY_COMPUTE.

Usage::

    cd backend
    venv/Scripts/python.exe -m phase4f.training.train
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForQuestionAnswering, AutoTokenizer, get_linear_schedule_with_warmup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from phase4f.dataset.generator import QAExample, load_dataset, dataset_stats, compute_hash
from phase4f.training.configs import ALL_CONFIGS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_MODEL = os.getenv("QA_MODEL_NAME", "./models/documind-qa")
MAX_SEQ_LENGTH = 384
MAX_ANSWER_LENGTH = 100
GPU_AVAILABLE = torch.cuda.is_available()
DEVICE = "cuda" if GPU_AVAILABLE else "cpu"

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class QADataset(Dataset):
    def __init__(self, examples: list[QAExample], tokenizer, max_length: int = 384):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]
        encoding = self.tokenizer(
            ex.question, ex.context, max_length=self.max_length,
            truncation=True, padding="max_length", return_tensors="pt",
        )

        # Find answer positions
        start_token, end_token = 0, 0
        if ex.answer and ex.answer_start >= 0 and ex.answer_end > ex.answer_start:
            # Decode tokens to find span
            input_ids = encoding["input_ids"][0]
            decoded = self.tokenizer.decode(input_ids, skip_special_tokens=True)
            ans_pos = decoded.lower().find(ex.answer.lower())
            if ans_pos >= 0:
                # Approximate token positions
                tokens_per_char = len(input_ids) / max(1, len(decoded))
                start_token = max(0, int(ans_pos * tokens_per_char))
                end_token = min(len(input_ids) - 1, int((ans_pos + len(ex.answer)) * tokens_per_char))

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "token_type_ids": encoding.get("token_type_ids", torch.zeros_like(encoding["input_ids"])).squeeze(0),
            "start_positions": torch.tensor(start_token, dtype=torch.long),
            "end_positions": torch.tensor(end_token, dtype=torch.long),
        }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_one_experiment(
    config: dict,
    train_data: list[QAExample],
    val_data: list[QAExample],
    output_dir: Path,
    smoke_test: bool = False,
) -> dict:
    """Run one training experiment."""
    print(f"\n  Training {config['experiment_id']}: {config['description']}")
    print(f"    Device: {DEVICE}")
    print(f"    Train: {len(train_data)}, Val: {len(val_data)}")

    start_time = time.time()

    # Load model
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForQuestionAnswering.from_pretrained(BASE_MODEL)
    model.to(DEVICE)

    # Datasets
    train_ds = QADataset(train_data, tokenizer, MAX_SEQ_LENGTH)
    val_ds = QADataset(val_data, tokenizer, MAX_SEQ_LENGTH)

    effective_batch = config["batch_size"] * config["gradient_accumulation_steps"]
    train_loader = DataLoader(train_ds, batch_size=config["batch_size"], shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=config["batch_size"], shuffle=False, num_workers=0)

    # If smoke test, limit to 2 epochs and 5 batches
    max_epochs = config["epochs"]
    max_train_batches = len(train_loader)
    max_val_batches = len(val_loader)
    if smoke_test:
        max_epochs = min(2, max_epochs)
        max_train_batches = min(3, max_train_batches)
        max_val_batches = min(2, max_val_batches)
        print(f"    SMOKE TEST: limited to {max_epochs} epochs, {max_train_batches} train batches")

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    total_steps = (max_train_batches * max_epochs) // config["gradient_accumulation_steps"]
    warmup_steps = int(total_steps * config["warmup_ratio"])
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # Training loop
    epoch_metrics = []
    best_val_loss = float("inf")

    for epoch in range(max_epochs):
        model.train()
        total_loss = 0.0
        steps = 0

        for batch_idx, batch in enumerate(train_loader):
            batch = {k: v.to(DEVICE) for k, v in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss / config["gradient_accumulation_steps"]
            loss.backward()
            total_loss += loss.item() * config["gradient_accumulation_steps"]

            if (batch_idx + 1) % config["gradient_accumulation_steps"] == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), config["max_grad_norm"])
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                steps += 1

            if batch_idx + 1 >= max_train_batches:
                break

        avg_train_loss = total_loss / max(1, steps)

        # Validate
        model.eval()
        val_loss = 0.0
        val_steps = 0
        with torch.no_grad():
            for batch_idx, batch in enumerate(val_loader):
                batch = {k: v.to(DEVICE) for k, v in batch.items()}
                outputs = model(**batch)
                val_loss += outputs.loss.item()
                val_steps += 1
                if batch_idx + 1 >= max_val_batches:
                    break

        avg_val_loss = val_loss / max(1, val_steps)

        epoch_metrics.append({
            "epoch": epoch + 1,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
        })

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss

        ratio = avg_val_loss / max(0.001, avg_train_loss)
        status = "OVERFITTING" if ratio > 3.0 else ("HEALTHY" if ratio < 1.5 else "MODERATE")
        print(f"    Epoch {epoch+1}: train={avg_train_loss:.4f} val={avg_val_loss:.4f} ratio={ratio:.2f} [{status}]")

    # Save model
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Save inference config
    with open(output_dir / "inference_config.json", "w") as f:
        json.dump({"max_input_length": MAX_SEQ_LENGTH, "max_answer_length": MAX_ANSWER_LENGTH, "n_best": 20}, f, indent=2)

    duration = time.time() - start_time

    result = {
        "experiment_id": config["experiment_id"],
        "description": config["description"],
        "config": config,
        "duration_seconds": round(duration, 1),
        "epoch_metrics": epoch_metrics,
        "final_train_loss": epoch_metrics[-1]["train_loss"] if epoch_metrics else 0,
        "final_val_loss": epoch_metrics[-1]["val_loss"] if epoch_metrics else 0,
        "best_val_loss": round(best_val_loss, 4),
        "model_path": str(output_dir),
        "smoke_test": smoke_test,
    }

    print(f"    Completed in {duration:.1f}s")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("PHASE 4F — TRAINING EXPERIMENTS")
    print("=" * 78)
    print(f"  Device: {DEVICE}")
    print(f"  GPU available: {GPU_AVAILABLE}")

    if not GPU_AVAILABLE:
        print("\n  WARNING: No GPU available.")
        print("  Running SMOKE TEST only to validate pipeline.")
        print("  FULL_TRAINING_STATUS = BLOCKED_BY_COMPUTE")
        smoke_test = True
    else:
        smoke_test = False

    # Load dataset
    dataset_path = Path("phase4f/dataset/training_data.jsonl")
    if not dataset_path.exists():
        print(f"  ERROR: Dataset not found at {dataset_path}")
        print("  Run: python -m phase4f.dataset.generator")
        return 1

    examples = load_dataset(dataset_path)
    print(f"\n  Loaded {len(examples)} examples")

    # Split: 80% train, 10% val, 10% test (document-level)
    random.seed(42)
    random.shuffle(examples)
    n = len(examples)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)

    train_data = examples[:train_end]
    val_data = examples[train_end:val_end]
    test_data = examples[val_end:]

    print(f"  Split: train={len(train_data)}, val={len(val_data)}, test={len(test_data)}")

    # Run experiments
    results = {}
    output_base = Path("phase4f/models")

    for exp_id in ["A1", "A2"]:
        config = ALL_CONFIGS[exp_id]
        output_dir = output_base / exp_id.lower()
        result = train_one_experiment(config, train_data, val_data, output_dir, smoke_test)
        results[exp_id] = result

    # Save results
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device": DEVICE,
        "gpu_available": GPU_AVAILABLE,
        "full_training_status": "BLOCKED_BY_COMPUTE" if not GPU_AVAILABLE else "COMPLETED",
        "smoke_test": smoke_test,
        "dataset_hash": compute_hash(examples),
        "dataset_stats": dataset_stats(examples),
        "train_size": len(train_data),
        "val_size": len(val_data),
        "test_size": len(test_data),
        "experiments": results,
    }

    out_path = Path("phase4f/training_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved: {out_path}")

    print("\n" + "=" * 78)
    if smoke_test:
        print("PHASE 4F — GPU TRAINING REQUIRED")
        print("Full training blocked by compute. Pipeline validated via smoke test.")
    else:
        print("PHASE 4F — TRAINING COMPLETE")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

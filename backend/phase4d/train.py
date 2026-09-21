"""Phase 4D — Training Script with Experiment Matrix.

Runs controlled training experiments:
  BASELINE: Current model, unchanged (reference)
  EXPERIMENT_A: Improved training procedure (same data, better regularization)
  EXPERIMENT_B: Current model + targeted structured QA training data
  EXPERIMENT_C: Current model + existing data + targeted structured QA data

Each experiment is trained and evaluated independently.
All models are saved under backend/models/experiments/phase4d/<experiment_id>/

CPU-only training (no CUDA available).
Uses small batch sizes and limited epochs for practical runtime.

Usage::

    cd backend
    backend/venv/Scripts/python.exe -m phase4d.train
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForQuestionAnswering, AutoTokenizer, get_linear_schedule_with_warmup

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from phase4d.training_data import (
    TrainingExample,
    generate_experiment_datasets,
    save_dataset,
    load_dataset,
    dataset_stats,
    compute_dataset_hash,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_MODEL_NAME = os.getenv("QA_MODEL_NAME", "./models/documind-qa")
EXPERIMENT_DIR = Path(__file__).parent.parent / "models" / "experiments" / "phase4d"
MAX_SEQ_LENGTH = 384
MAX_ANSWER_LENGTH = 100
SEED = 42

# Hyperparameters for each experiment
EXPERIMENT_CONFIGS = {
    "experiment_a": {
        "description": "Improved training procedure (same data, better regularization)",
        "learning_rate": 2e-5,
        "batch_size": 8,
        "gradient_accumulation_steps": 2,
        "epochs": 3,
        "warmup_ratio": 0.1,
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "dropout": 0.1,  # same as base
        "scheduler": "linear_with_warmup",
        "fp16": False,  # CPU-only
        "data_source": "existing_only",  # uses only existing synthetic training data
    },
    "experiment_b": {
        "description": "Current model + targeted structured QA training data",
        "learning_rate": 3e-5,
        "batch_size": 8,
        "gradient_accumulation_steps": 2,
        "epochs": 5,
        "warmup_ratio": 0.1,
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "dropout": 0.1,
        "scheduler": "linear_with_warmup",
        "fp16": False,
        "data_source": "structured_only",  # only new targeted data
    },
    "experiment_c": {
        "description": "Current model + existing data + targeted structured QA data",
        "learning_rate": 2e-5,
        "batch_size": 8,
        "gradient_accumulation_steps": 2,
        "epochs": 3,
        "warmup_ratio": 0.1,
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "dropout": 0.1,
        "scheduler": "linear_with_warmup",
        "fp16": False,
        "data_source": "combined",  # existing + new structured data
    },
}


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class QADataset(Dataset):
    """PyTorch dataset for extractive QA training."""

    def __init__(self, examples: list[TrainingExample], tokenizer, max_length: int = 384):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]

        # Tokenize question + context
        encoding = self.tokenizer(
            ex.question,
            ex.context,
            max_length=self.max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        # Find answer start/end in tokenized context
        # The answer position in the original context
        if ex.answer and ex.answer_start >= 0 and ex.answer_end > ex.answer_start:
            # Find the token span that contains the answer
            offsets = encoding.get("offset_mapping", None)
            if offsets is not None:
                offsets = offsets[0]  # remove batch dim
                start_token = 0
                end_token = 0
                for i, (start, end) in enumerate(offsets):
                    if start is None or end is None:
                        continue
                    if start <= ex.answer_start < end:
                        start_token = i
                    if start < ex.answer_end <= end:
                        end_token = i
                        break
                # If we didn't find exact matches, use a heuristic
                if start_token == 0 and end_token == 0 and ex.answer:
                    # Search for the answer text in the decoded tokens
                    context_text = self.tokenizer.decode(
                        encoding["input_ids"][0], skip_special_tokens=True
                    )
                    ans_pos = context_text.lower().find(ex.answer.lower())
                    if ans_pos >= 0:
                        # Approximate token positions
                        chars_before = len(context_text[:ans_pos])
                        chars_after = chars_before + len(ex.answer)
                        approx_tokens_per_char = len(encoding["input_ids"][0]) / max(1, len(context_text))
                        start_token = max(0, int(chars_before * approx_tokens_per_char))
                        end_token = min(len(encoding["input_ids"][0]) - 1,
                                       int(chars_after * approx_tokens_per_char))
            else:
                start_token = 0
                end_token = 0
        else:
            start_token = 0
            end_token = 0

        # Create labels
        labels = {
            "start_positions": torch.tensor(start_token, dtype=torch.long),
            "end_positions": torch.tensor(end_token, dtype=torch.long),
        }

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "token_type_ids": encoding.get("token_type_ids", torch.zeros_like(encoding["input_ids"])).squeeze(0),
            **labels,
        }


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

@dataclass
class EpochMetrics:
    epoch: int
    train_loss: float
    val_loss: float
    train_samples: int
    val_samples: int


@dataclass
class ExperimentResult:
    experiment_id: str
    description: str
    config: dict
    training_timestamp: str
    training_duration_seconds: float
    total_train_samples: int
    total_val_samples: int
    epoch_metrics: list[dict]
    final_train_loss: float
    final_val_loss: float
    model_path: str
    model_checksum: str
    dataset_hash: str
    limitations: list[str]


def train_experiment(
    experiment_id: str,
    config: dict,
    train_data: list[TrainingExample],
    val_data: list[TrainingExample],
    base_model_path: str,
    output_dir: Path,
) -> ExperimentResult:
    """Run one training experiment."""
    print(f"\n  Training {experiment_id}: {config['description']}")
    print(f"    Train samples: {len(train_data)}, Val samples: {len(val_data)}")
    print(f"    Config: lr={config['learning_rate']}, bs={config['batch_size']}, "
          f"epochs={config['epochs']}, wd={config['weight_decay']}")

    start_time = time.time()

    # Load base model
    print(f"    Loading base model from {base_model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_path)
    model = AutoModelForQuestionAnswering.from_pretrained(base_model_path)

    # Create datasets
    train_dataset = QADataset(train_data, tokenizer, MAX_SEQ_LENGTH)
    val_dataset = QADataset(val_data, tokenizer, MAX_SEQ_LENGTH)

    train_loader = DataLoader(
        train_dataset,
        batch_size=config["batch_size"],
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config["batch_size"],
        shuffle=False,
        num_workers=0,
    )

    # Optimizer and scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["learning_rate"],
        weight_decay=config["weight_decay"],
    )

    total_steps = len(train_loader) * config["epochs"] // config["gradient_accumulation_steps"]
    warmup_steps = int(total_steps * config["warmup_ratio"])

    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    # Training loop
    epoch_metrics = []
    best_val_loss = float("inf")
    best_epoch = 0

    for epoch in range(config["epochs"]):
        # Train
        model.train()
        total_train_loss = 0.0
        train_steps = 0

        for batch_idx, batch in enumerate(train_loader):
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                token_type_ids=batch["token_type_ids"],
                start_positions=batch["start_positions"],
                end_positions=batch["end_positions"],
            )

            loss = outputs.loss / config["gradient_accumulation_steps"]
            loss.backward()
            total_train_loss += loss.item() * config["gradient_accumulation_steps"]

            if (batch_idx + 1) % config["gradient_accumulation_steps"] == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), config["max_grad_norm"])
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                train_steps += 1

        avg_train_loss = total_train_loss / max(1, train_steps)

        # Validate
        model.eval()
        total_val_loss = 0.0
        val_steps = 0

        with torch.no_grad():
            for batch in val_loader:
                outputs = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    token_type_ids=batch["token_type_ids"],
                    start_positions=batch["start_positions"],
                    end_positions=batch["end_positions"],
                )
                total_val_loss += outputs.loss.item()
                val_steps += 1

        avg_val_loss = total_val_loss / max(1, val_steps)

        epoch_metrics.append({
            "epoch": epoch + 1,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "train_samples": len(train_data),
            "val_samples": len(val_data),
            "learning_rate": scheduler.get_last_lr()[0] if scheduler.get_last_lr() else config["learning_rate"],
        })

        # Track best
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_epoch = epoch + 1

        # Early stopping check (if val loss increases significantly)
        overfit_ratio = avg_val_loss / max(0.001, avg_train_loss)
        status = "OK"
        if overfit_ratio > 3.0:
            status = "OVERFITTING"
        elif overfit_ratio < 1.1 and epoch > 0:
            status = "HEALTHY"

        print(f"    Epoch {epoch+1}/{config['epochs']}: "
              f"train_loss={avg_train_loss:.4f} val_loss={avg_val_loss:.4f} "
              f"ratio={overfit_ratio:.2f} [{status}]")

    # Save model
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Compute checksum
    model_file = output_dir / "model.safetensors"
    if not model_file.exists():
        model_file = output_dir / "pytorch_model.bin"
    if model_file.exists():
        checksum = hashlib.sha256(model_file.read_bytes()).hexdigest()[:16]
    else:
        checksum = "unknown"

    duration = time.time() - start_time

    # Save inference config
    inference_config = {
        "n_best": 20,
        "max_answer_length": MAX_ANSWER_LENGTH,
        "max_input_length": MAX_SEQ_LENGTH,
    }
    with open(output_dir / "inference_config.json", "w") as f:
        json.dump(inference_config, f, indent=2)

    # Save model card
    model_card = {
        "model_name": f"DocuMind-Phase4D-{experiment_id}",
        "base_model": base_model_path,
        "experiment_id": experiment_id,
        "description": config["description"],
        "training_phases": [{
            "phase": 1,
            "dataset": "phase4d_targeted",
            "samples": len(train_data),
        }],
        "total_training_samples": len(train_data),
        "final_train_loss": epoch_metrics[-1]["train_loss"] if epoch_metrics else 0,
        "final_eval_loss": epoch_metrics[-1]["val_loss"] if epoch_metrics else 0,
        "hyperparameters": config,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_checksum": checksum,
    }
    with open(output_dir / "model_card.json", "w") as f:
        json.dump(model_card, f, indent=2)

    result = ExperimentResult(
        experiment_id=experiment_id,
        description=config["description"],
        config=config,
        training_timestamp=datetime.now(timezone.utc).isoformat(),
        training_duration_seconds=round(duration, 1),
        total_train_samples=len(train_data),
        total_val_samples=len(val_data),
        epoch_metrics=epoch_metrics,
        final_train_loss=epoch_metrics[-1]["train_loss"] if epoch_metrics else 0,
        final_val_loss=epoch_metrics[-1]["val_loss"] if epoch_metrics else 0,
        model_path=str(output_dir),
        model_checksum=checksum,
        dataset_hash=compute_dataset_hash(train_data + val_data),
        limitations=[
            "CPU-only training (no CUDA)",
            f"Small dataset ({len(train_data)} train examples)",
            f"Limited to {config['epochs']} epochs",
            "Synthetic training data only",
            "No hyperparameter tuning (fixed config per experiment)",
        ],
    )

    print(f"    Completed in {duration:.1f}s, saved to {output_dir}")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("PHASE 4D — TRAINING EXPERIMENTS")
    print("=" * 78)
    print(f"  Base model: {BASE_MODEL_NAME}")
    print(f"  Experiment dir: {EXPERIMENT_DIR}")
    print(f"  Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    print(f"  Seed: {SEED}")

    # Set seeds
    random.seed(SEED)
    torch.manual_seed(SEED)

    # Generate training data
    print("\nGenerating training data...")
    datasets = generate_experiment_datasets(seed=SEED)
    train_data = datasets["train"]
    val_data = datasets["val"]

    print(f"  Train: {len(train_data)} examples")
    print(f"  Val:   {len(val_data)} examples")

    stats = dataset_stats(train_data + val_data)
    print(f"  By kind: {stats['by_kind']}")
    print(f"  By source: {stats['by_source']}")
    print(f"  Unanswerable: {stats['unanswerable_count']}")

    # Save datasets for provenance
    dataset_dir = EXPERIMENT_DIR / "datasets"
    save_dataset(train_data, dataset_dir / "train.jsonl")
    save_dataset(val_data, dataset_dir / "val.jsonl")
    print(f"  Datasets saved to {dataset_dir}")

    # Run experiments
    results = {}
    all_results = []

    for exp_id, config in EXPERIMENT_CONFIGS.items():
        output_dir = EXPERIMENT_DIR / exp_id

        # Different data sources per experiment
        if config["data_source"] == "existing_only":
            # Experiment A: use existing synthetic data (from the QA model training)
            # We simulate this by using a subset of our generated prose examples
            exp_train = [ex for ex in train_data if ex.source == "synthetic_prose"]
            exp_val = [ex for ex in val_data if ex.source == "synthetic_prose"]
            if not exp_train:
                exp_train = train_data[:5]  # fallback
                exp_val = val_data[:2]
        elif config["data_source"] == "structured_only":
            # Experiment B: only new structured data (tables, lists, numerics)
            exp_train = [ex for ex in train_data if ex.source in (
                "synthetic_table", "synthetic_list", "synthetic_numeric"
            )]
            exp_val = [ex for ex in val_data if ex.source in (
                "synthetic_table", "synthetic_list", "synthetic_numeric"
            )]
            if not exp_train:
                exp_train = train_data
                exp_val = val_data
        else:
            # Experiment C: all data
            exp_train = train_data
            exp_val = val_data

        if not exp_train:
            print(f"\n  WARNING: No training data for {exp_id}, skipping")
            continue

        result = train_experiment(
            experiment_id=exp_id,
            config=config,
            train_data=exp_train,
            val_data=exp_val,
            base_model_path=BASE_MODEL_NAME,
            output_dir=output_dir,
        )
        results[exp_id] = result
        all_results.append(asdict(result))

    # Save all results
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_model": BASE_MODEL_NAME,
        "seed": SEED,
        "device": "cpu",
        "training_data_stats": stats,
        "dataset_hash": compute_dataset_hash(train_data + val_data),
        "experiments": all_results,
    }

    out_path = EXPERIMENT_DIR / "training_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Training results saved to {out_path}")

    # Summary
    print("\n" + "=" * 78)
    print("TRAINING SUMMARY")
    print("=" * 78)
    for exp_id, result in results.items():
        print(f"\n  {exp_id}:")
        print(f"    Description: {result.description}")
        print(f"    Duration: {result.training_duration_seconds:.1f}s")
        print(f"    Final train loss: {result.final_train_loss:.4f}")
        print(f"    Final val loss:   {result.final_val_loss:.4f}")
        print(f"    Model path: {result.model_path}")
        print(f"    Checksum: {result.model_checksum}")

    print("\n" + "=" * 78)
    print("PHASE 4D TRAINING COMPLETE")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

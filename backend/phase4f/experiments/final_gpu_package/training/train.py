"""Phase 4F.3 — QA Model Training Script.

Trains extractive QA models on the phase4f-qa-v3 dataset.
Supports A0 (baseline), A1 (DistilBERT), A2 (BERT-base), A3 (DeBERTa-v3).

Usage::

    python train.py --experiment a1 --data_dir ../dataset --output_dir ./a1_distilbert
    python train.py --experiment a2 --data_dir ../dataset --output_dir ./a2_bert_base
    python train.py --experiment a3 --data_dir ../dataset --output_dir ./a3_deberta_v3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForQuestionAnswering,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXPERIMENT_CONFIGS = {
    "a0": {
        "name": "A0_Current_Production_Baseline",
        "model_name": "distilbert-base-cased",
        "description": "Current production model (frozen baseline, no training)",
        "train": False,
    },
    "a1": {
        "name": "A1_DistilBERT_Targeted_FineTune",
        "model_name": "distilbert-base-cased",
        "learning_rate": 3e-5,
        "effective_batch_size": 64,
        "actual_batch_size": 16,
        "gradient_accumulation": 4,
        "epochs": 3,
        "warmup_ratio": 0.1,
        "weight_decay": 0.01,
        "max_length": 384,
        "max_answer_length": 50,
        "seed": 42,
        "fp16": True,
        "train": True,
    },
    "a2": {
        "name": "A2_BERT_Base_Targeted_FineTune",
        "model_name": "bert-base-cased",
        "learning_rate": 2e-5,
        "effective_batch_size": 64,
        "actual_batch_size": 8,
        "gradient_accumulation": 8,
        "epochs": 3,
        "warmup_ratio": 0.1,
        "weight_decay": 0.01,
        "max_length": 384,
        "max_answer_length": 50,
        "seed": 42,
        "fp16": True,
        "train": True,
    },
    "a3": {
        "name": "A3_DeBERTa_v3_Targeted_FineTune",
        "model_name": "microsoft/deberta-v3-base",
        "learning_rate": 1e-5,
        "effective_batch_size": 64,
        "actual_batch_size": 8,
        "gradient_accumulation": 8,
        "epochs": 3,
        "warmup_ratio": 0.1,
        "weight_decay": 0.01,
        "max_length": 384,
        "max_answer_length": 50,
        "seed": 42,
        "fp16": True,
        "train": True,
    },
}


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class QADataset(Dataset):
    """Extractive QA dataset from JSONL."""

    def __init__(self, data_path: str, tokenizer, max_length: int = 384):
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

        # Tokenize
        encoding = self.tokenizer(
            ex["question"],
            ex["context"],
            max_length=self.max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        # Find answer span in tokenized space
        if ex["question_kind"] == "UNANSWERABLE":
            start_positions = torch.tensor(0)
            end_positions = torch.tensor(0)
            is_impossible = torch.tensor(1)
        else:
            # Map character offsets to token offsets
            context_start = len(self.tokenizer.encode(ex["question"], add_special_tokens=False)) + 2  # [SEP] + [CLS]
            char_to_token = {}
            offset = 0
            for i, token_id in enumerate(encoding["input_ids"][0]):
                if token_id == self.tokenizer.sep_token_id:
                    break
                if token_id not in [self.tokenizer.cls_token_id, self.tokenizer.sep_token_id]:
                    char_to_token[offset] = i
                    offset += 1

            # Find start and end token positions
            ans_start = ex["answer_start"]
            ans_end = ex["answer_end"]

            # Map to token positions
            start_token = char_to_token.get(ans_start, 0)
            end_token = char_to_token.get(ans_end - 1, 0)

            start_positions = torch.tensor(start_token)
            end_positions = torch.tensor(end_token)
            is_impossible = torch.tensor(0)

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "start_positions": start_positions,
            "end_positions": end_positions,
            "is_impossible": is_impossible,
        }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train_model(config: dict, data_path: str, output_dir: str, split_info: dict):
    """Train a QA model with the given configuration."""
    print(f"\n{'='*60}")
    print(f"Training: {config['name']}")
    print(f"{'='*60}")

    # Set seed
    seed = config.get("seed", 42)
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Load tokenizer and model
    print(f"Loading model: {config['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    model = AutoModelForQuestionAnswering.from_pretrained(config["model_name"])

    # Load datasets
    train_path = data_path
    train_dataset = QADataset(train_path, tokenizer, config.get("max_length", 384))
    print(f"Training examples: {len(train_dataset)}")

    # Create data loader
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.get("actual_batch_size", 16),
        shuffle=True,
        num_workers=0,
    )

    # Optimizer and scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["learning_rate"],
        weight_decay=config.get("weight_decay", 0.01),
    )

    total_steps = len(train_loader) * config["epochs"]
    warmup_steps = int(total_steps * config.get("warmup_ratio", 0.1))
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    # Training loop
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    use_fp16 = config.get("fp16", True) and device.type == "cuda"
    scaler = torch.cuda.amp.GradScaler() if use_fp16 else None

    training_history = []
    start_time = time.time()

    for epoch in range(config["epochs"]):
        model.train()
        total_loss = 0
        num_batches = 0

        for batch_idx, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            start_positions = batch["start_positions"].to(device)
            end_positions = batch["end_positions"].to(device)

            if use_fp16:
                with torch.cuda.amp.autocast():
                    outputs = model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        start_positions=start_positions,
                        end_positions=end_positions,
                    )
                    loss = outputs.loss / config.get("gradient_accumulation", 1)
                scaler.scale(loss).backward()
            else:
                outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    start_positions=start_positions,
                    end_positions=end_positions,
                )
                loss = outputs.loss / config.get("gradient_accumulation", 1)
                loss.backward()

            total_loss += loss.item() * config.get("gradient_accumulation", 1)
            num_batches += 1

            if (batch_idx + 1) % config.get("gradient_accumulation", 1) == 0:
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
        epoch_time = time.time() - start_time
        print(f"  Epoch {epoch+1}/{config['epochs']}: loss={avg_loss:.4f}, time={epoch_time:.1f}s")

        training_history.append({
            "epoch": epoch + 1,
            "loss": avg_loss,
            "lr": scheduler.get_last_lr()[0],
            "time": epoch_time,
        })

    # Save checkpoint
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Compute checkpoint hash
    checkpoint_hash = _compute_dir_hash(output_dir)

    # Save training metadata
    training_time = time.time() - start_time
    metadata = {
        "experiment": config["name"],
        "model_name": config["model_name"],
        "hyperparameters": {k: v for k, v in config.items() if k not in ("name", "train")},
        "training_history": training_history,
        "training_duration_seconds": training_time,
        "checkpoint_hash": checkpoint_hash,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        "pytorch_version": torch.__version__,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(os.path.join(output_dir, "training_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  Training complete: {training_time:.1f}s")
    print(f"  Checkpoint saved: {output_dir}")
    print(f"  Checkpoint hash: {checkpoint_hash}")

    return metadata


def _compute_dir_hash(directory: str) -> str:
    """Compute hash of all files in a directory."""
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(directory):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            with open(fp, "rb") as f:
                hasher.update(f.read())
    return hasher.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Baseline (no training)
# ---------------------------------------------------------------------------
def run_baseline(config: dict, output_dir: str):
    """Run baseline - just record the existing model info."""
    print(f"\n{'='*60}")
    print(f"Baseline: {config['name']}")
    print(f"{'='*60}")

    # Check if production model exists
    prod_model_dir = Path(__file__).parent.parent.parent / "models" / "documind-qa"
    if prod_model_dir.exists():
        print(f"  Production model found: {prod_model_dir}")
        # Copy to experiment dir for evaluation
        os.makedirs(output_dir, exist_ok=True)
        import shutil
        for fn in os.listdir(prod_model_dir):
            src = prod_model_dir / fn
            dst = os.path.join(output_dir, fn)
            if src.is_file():
                shutil.copy2(src, dst)
        print(f"  Copied to: {output_dir}")
    else:
        print(f"  Production model not found at {prod_model_dir}")
        print(f"  Using HuggingFace baseline: {config['model_name']}")
        tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
        model = AutoModelForQuestionAnswering.from_pretrained(config["model_name"])
        os.makedirs(output_dir, exist_ok=True)
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

    metadata = {
        "experiment": config["name"],
        "model_name": config["model_name"],
        "description": config["description"],
        "train": False,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(os.path.join(output_dir, "training_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Phase 4F.3 QA Model Training")
    parser.add_argument("--experiment", type=str, required=True,
                       choices=["a0", "a1", "a2", "a3"],
                       help="Experiment to run")
    parser.add_argument("--data_dir", type=str, default="../dataset",
                       help="Directory containing training_data_v3.jsonl")
    parser.add_argument("--output_dir", type=str, default=None,
                       help="Output directory for checkpoints")
    parser.add_argument("--split_info", type=str, default=None,
                       help="Path to split info JSON")
    args = parser.parse_args()

    config = EXPERIMENT_CONFIGS[args.experiment]
    data_path = os.path.join(args.data_dir, "training_data_v3.jsonl")

    if args.output_dir is None:
        args.output_dir = f"./{args.experiment}_{config['name'].split('_')[1].lower()}"

    # Verify dataset hash
    print("Verifying dataset...")
    with open(data_path, "r") as f:
        examples = [json.loads(line) for line in f if line.strip()]
    dataset_hash = hashlib.sha256(
        json.dumps(examples, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    print(f"  Dataset hash: {dataset_hash}")
    print(f"  Examples: {len(examples)}")

    # Record GPU info
    print(f"\nGPU Info:")
    print(f"  PyTorch: {torch.__version__}")
    print(f"  CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
        print(f"  CUDA version: {torch.version.cuda}")
    else:
        print("  WARNING: No GPU available. Training will be slow on CPU.")

    # Run experiment
    if config.get("train", True):
        metadata = train_model(config, data_path, args.output_dir, None)
    else:
        metadata = run_baseline(config, args.output_dir)

    print(f"\n{'='*60}")
    print(f"Experiment complete: {config['name']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

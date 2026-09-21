"""Phase 4F — Training Configurations.

Three controlled experiment configurations for 4F-A.
"""

A1_CONSERVATIVE = {
    "experiment_id": "4F_A1",
    "description": "Conservative learning rate, standard regularization",
    "learning_rate": 3e-5,
    "batch_size": 16,
    "gradient_accumulation_steps": 1,
    "epochs": 10,
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    "max_grad_norm": 1.0,
    "scheduler": "linear_with_warmup",
    "seed": 42,
}

A2_LOW_LR_REGULARIZED = {
    "experiment_id": "4F_A2",
    "description": "Lower learning rate with stronger regularization",
    "learning_rate": 1e-5,
    "batch_size": 16,
    "gradient_accumulation_steps": 1,
    "epochs": 15,
    "warmup_ratio": 0.15,
    "weight_decay": 0.05,
    "max_grad_norm": 1.0,
    "scheduler": "linear_with_warmup",
    "seed": 42,
}

A3_BEST_SELECTED = {
    "experiment_id": "4F_A3",
    "description": "Best configuration from validation (placeholder)",
    "learning_rate": None,  # Set from validation selection
    "batch_size": 16,
    "gradient_accumulation_steps": 1,
    "epochs": None,  # Set from validation selection
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    "max_grad_norm": 1.0,
    "scheduler": "linear_with_warmup",
    "seed": 42,
    "note": "This config is populated after A1/A2 validation comparison",
}

ALL_CONFIGS = {
    "A1": A1_CONSERVATIVE,
    "A2": A2_LOW_LR_REGULARIZED,
    "A3": A3_BEST_SELECTED,
}

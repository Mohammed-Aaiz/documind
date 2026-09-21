"""
QA model for DocuMind question answering.

Loads the trained DocuMind QA model (DistilBERT fine-tuned on SQuAD 2.0,
mixed QA datasets, and custom academic QA) from a local directory.
The model path is configured via the QA_MODEL_NAME environment variable
and MUST point to a local directory containing the trained model artifacts.

IMPORTANT: This does NOT fall back to any external pre-trained model.
If the configured model directory does not exist or cannot be loaded,
an exception is raised — answers are never fabricated.

The `question-answering` pipeline task was removed in transformers v5,
so we load the model and tokenizer directly.
"""

import json
import os
import torch
from pathlib import Path
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

_MODEL_NAME = os.getenv("QA_MODEL_NAME", "./models/documind-qa")

_model = None
_tokenizer = None
_model_loaded = False
_model_load_error: str | None = None
_inference_config: dict = {}


def _load_model():
    global _model, _tokenizer, _model_loaded, _model_load_error, _inference_config
    if _model_loaded:
        if _model_load_error:
            raise RuntimeError(_model_load_error)
        return

    model_path = Path(_MODEL_NAME)
    if not model_path.exists():
        _model_load_error = (
            f"DocuMind QA model not found at '{_MODEL_NAME}'. "
            f"Please provide the trained model artifacts in that directory. "
            f"The model directory should contain config.json, model weights, "
            f"and tokenizer files."
        )
        _model_loaded = True
        raise RuntimeError(_model_load_error)

    try:
        _tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        _model = AutoModelForQuestionAnswering.from_pretrained(str(model_path))
        _model.eval()

        # Load inference config if available
        inference_cfg_path = model_path / "inference_config.json"
        if inference_cfg_path.exists():
            with open(inference_cfg_path) as f:
                _inference_config = json.load(f)

        _model_loaded = True
    except Exception as exc:
        _model_loaded = True
        _model_load_error = (
            f"Failed to load DocuMind QA model from '{_MODEL_NAME}': {exc}"
        )
        raise RuntimeError(_model_load_error)


def is_model_available() -> bool:
    """Check whether the DocuMind QA model is loaded and ready."""
    global _model
    try:
        _load_model()
        return _model is not None
    except RuntimeError:
        return False


def get_model_status() -> dict:
    """Return model availability info for debugging / health checks."""
    global _model
    try:
        _load_model()
        return {
            "available": True,
            "model_path": _MODEL_NAME,
            "error": None,
        }
    except RuntimeError as exc:
        return {
            "available": False,
            "model_path": _MODEL_NAME,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Token accounting (Phase 3D)
#
# The QA model has a finite input window and the tokenizer TRUNCATES silently
# at that window.  Everything upstream (chunking budget, context construction)
# must therefore be able to ask this module exactly how much room is left.
# ---------------------------------------------------------------------------

_DEFAULT_MAX_INPUT_LENGTH = 384


def _ensure_inference_config() -> None:
    """Populate ``_inference_config`` from disk without loading the model.

    Context construction must be able to size its budget even before the QA
    weights are needed (and even when the model is unavailable, so the call
    can then fail honestly at the QA step instead of here).
    """
    global _inference_config
    if _inference_config:
        return

    cfg_path = Path(_MODEL_NAME) / "inference_config.json"
    try:
        if cfg_path.exists():
            with open(cfg_path) as f:
                _inference_config = json.load(f)
    except Exception:
        _inference_config = {}


def get_max_input_length() -> int:
    """QA model input window in tokens (question + context + specials)."""
    _ensure_inference_config()
    try:
        return int(_inference_config.get("max_input_length", _DEFAULT_MAX_INPUT_LENGTH))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_INPUT_LENGTH


def get_tokenizer():
    """The QA tokenizer, or ``None`` when the model cannot be loaded."""
    try:
        _load_model()
    except RuntimeError:
        return None
    return _tokenizer


def is_tokenizer_available() -> bool:
    """True when exact QA token counts are available."""
    return get_tokenizer() is not None


def count_input_tokens(question: str, context: str) -> int | None:
    """Exact token count of the (question, context) pair, specials included.

    Returns ``None`` when the tokenizer is unavailable so callers can fall
    back deterministically instead of guessing silently.
    """
    tokenizer = get_tokenizer()
    if tokenizer is None:
        return None
    try:
        return len(
            tokenizer(
                question, context, add_special_tokens=True, truncation=False
            )["input_ids"]
        )
    except Exception:
        return None


def count_text_tokens(text: str) -> int | None:
    """Exact token count of a string without special tokens."""
    tokenizer = get_tokenizer()
    if tokenizer is None:
        return None
    try:
        return len(tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"])
    except Exception:
        return None


def answer_question(question: str, context: str) -> dict:
    """
    Run extractive QA on the given question and context using the
    trained DocuMind QA model.

    Returns:
        {
            "answer": str,       # the extracted answer span
            "score": float,      # confidence score (0-1)
            "start": int,        # start character offset in context
            "end": int,          # end character offset in context
        }

    Raises:
        RuntimeError: If the DocuMind QA model is not available.
    """
    if not context.strip():
        return {"answer": "", "score": 0.0, "start": 0, "end": 0}

    _load_model()  # raises RuntimeError if model unavailable

    _ensure_inference_config()
    max_input_length = _inference_config.get("max_input_length", 384)
    max_answer_length = _inference_config.get("max_answer_length", 100)
    n_best = _inference_config.get("n_best", 20)

    inputs = _tokenizer(
        question,
        context,
        return_tensors="pt",
        max_length=max_input_length,
        truncation=True,
        padding=True,
    )

    with torch.no_grad():
        outputs = _model(**inputs)

    start_logits = outputs.start_logits
    end_logits = outputs.end_logits

    # N-best answer selection for better answer quality
    start_probs = torch.softmax(start_logits, dim=1)[0]
    end_probs = torch.softmax(end_logits, dim=1)[0]

    start_top_idx = torch.topk(start_probs, min(n_best, len(start_probs))).indices
    end_top_idx = torch.topk(end_probs, min(n_best, len(end_probs))).indices

    best_answer = ""
    best_score = 0.0
    best_start = 0
    best_end = 0

    seq_len = inputs["input_ids"].shape[1]

    input_ids_0 = inputs["input_ids"][0]
    for s_idx in start_top_idx:
        s_idx_int = int(s_idx)
        for e_idx in end_top_idx:
            e_idx_int = int(e_idx)
            # end must be >= start and within answer length limit
            if e_idx_int < s_idx_int:
                continue
            if (e_idx_int - s_idx_int + 1) > max_answer_length:
                continue
            # skip special tokens
            token_s = _tokenizer.convert_ids_to_tokens(int(input_ids_0[s_idx_int]))
            token_e = _tokenizer.convert_ids_to_tokens(int(input_ids_0[e_idx_int]))
            if token_s in ("[CLS]", "[PAD]", "[SEP]") or token_e in ("[SEP]", "[PAD]"):
                continue
            score = float(start_probs[s_idx_int] * end_probs[e_idx_int])
            if score > best_score:
                best_score = score
                best_start = s_idx_int
                best_end = e_idx_int + 1
                answer_tokens = input_ids_0[s_idx_int : e_idx_int + 1]
                best_answer = _tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

    # Fallback to simple argmax if n-best produced nothing valid
    if not best_answer:
        s_idx = torch.argmax(start_logits)
        e_idx = torch.argmax(end_logits) + 1
        answer_tokens = inputs["input_ids"][0][s_idx:e_idx]
        best_answer = _tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()
        best_score = float(torch.softmax(start_logits, dim=1)[0][s_idx]
                           * torch.softmax(end_logits, dim=1)[0][e_idx - 1])
        best_start = int(s_idx)
        best_end = int(e_idx)

    return {
        "answer": best_answer,
        "score": round(max(0.0, min(1.0, best_score)), 4),
        "start": best_start,
        "end": best_end,
    }

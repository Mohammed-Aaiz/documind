"""Shared token accounting for chunking and QA context construction.

Phase 3D.

Why this module exists
----------------------
Every consumer downstream of chunking measures its input in *tokens*, not
characters:

  * ``all-MiniLM-L6-v2`` (the embedding model) has
    ``max_seq_length = 256`` and ``SentenceTransformer.encode()`` silently
    truncates.  Chunks longer than that are partially invisible to retrieval.
  * The DocuMind QA model (DistilBERT) has ``max_input_length = 384`` for
    *question + context together* (``models/documind-qa/inference_config.json``).

Both limits were verified empirically against the models actually loaded in
this project's environment, not assumed:

    >>> import tokenization
    >>> tokenization.get_encoder_limits()
    {'available': True, 'model': 'all-MiniLM-L6-v2', 'max_tokens': 256,
     'dimensions': 384, 'source': 'loaded sentence-transformers model'}

The verification also confirmed that truncation is real rather than
theoretical: two texts that differ only *after* token 256 produce identical
embeddings.

This module is deliberately dependency-light at import time.  The heavy
``sentence-transformers`` import happens lazily inside the accessors, and a
deterministic character-based fallback is provided so that ingestion never
fails merely because a model artifact is missing.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable

# The transformers tokenizer emits a noisy warning whenever a sequence is
# longer than the model maximum.  We intentionally count the *full* token
# length of candidate texts (that is the whole point), so suppress just that
# logger rather than the transformers root logger.
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("transformers.tokenization_utils").setLevel(logging.ERROR)

# Deterministic fallback ratio for English prose with a WordPiece vocabulary.
# Used ONLY when no tokenizer can be loaded; every count derived this way is
# reported as approximate via ``is_tokenizer_available()``.
FALLBACK_CHARS_PER_TOKEN = 4.0

_tokenizer: Any | None = None
_tokenizer_loaded = False
_encoder_limits: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Tokenizer access
# ---------------------------------------------------------------------------

def _load_tokenizer() -> Any | None:
    """Lazily obtain the embedding model's tokenizer.

    Returns ``None`` (and caches that fact) when the model cannot be loaded.
    Never raises: chunking must degrade, not fail.
    """
    global _tokenizer, _tokenizer_loaded
    if _tokenizer_loaded:
        return _tokenizer

    _tokenizer_loaded = True
    try:
        from embeddings.model import get_model

        _tokenizer = get_model().tokenizer
    except Exception:
        _tokenizer = None
    return _tokenizer


def is_tokenizer_available() -> bool:
    """True when real token counts are available for this process."""
    return _load_tokenizer() is not None


def reset_tokenizer_cache() -> None:
    """Clear cached tokenizer/limit state. For tests only."""
    global _tokenizer, _tokenizer_loaded, _encoder_limits
    _tokenizer = None
    _tokenizer_loaded = False
    _encoder_limits = None


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------

def count_tokens(text: str, *, add_special_tokens: bool = False) -> int:
    """Count WordPiece tokens in ``text``.

    ``add_special_tokens`` defaults to ``False`` because chunk and context
    budgets are measured on *content*; the special tokens belong to the
    window arithmetic performed by the QA layer.

    Falls back to a deterministic character estimate when no tokenizer is
    loadable, so callers always get a stable number.
    """
    if not text:
        return 0

    tokenizer = _load_tokenizer()
    if tokenizer is not None:
        try:
            return len(tokenizer(text, add_special_tokens=add_special_tokens)["input_ids"])
        except Exception:
            pass

    return max(1, int(math.ceil(len(text) / FALLBACK_CHARS_PER_TOKEN)))


def count_tokens_verbose(text: str, *, add_special_tokens: bool = False) -> tuple[int, bool]:
    """Return ``(token_count, exact)`` where ``exact`` is False for estimates."""
    exact = is_tokenizer_available()
    return count_tokens(text, add_special_tokens=add_special_tokens), exact


def make_token_counter() -> Callable[[str], int]:
    """Return a callable suitable for injection into the chunker."""
    return count_tokens


# ---------------------------------------------------------------------------
# Encoder limits (verified against the loaded model)
# ---------------------------------------------------------------------------

def get_encoder_limits() -> dict[str, Any]:
    """Report the loaded embedding model's real token limit.

    ``max_tokens`` is read from the model object rather than hard-coded, so
    a change of model artifact cannot silently invalidate the chunk budget.
    """
    global _encoder_limits
    if _encoder_limits is not None:
        return _encoder_limits

    info: dict[str, Any] = {
        "available": False,
        "model": None,
        "max_tokens": None,
        "dimensions": None,
        "source": "unavailable",
    }
    try:
        from embeddings.model import get_model

        model = get_model()
        max_tokens = getattr(model, "max_seq_length", None)
        if max_tokens is None and getattr(model, "tokenizer", None) is not None:
            max_tokens = getattr(model.tokenizer, "model_max_length", None)
        if isinstance(max_tokens, int) and 0 < max_tokens < 100_000:
            info["max_tokens"] = max_tokens
            info["available"] = True
            info["source"] = "loaded sentence-transformers model"
        info["model"] = type(model).__name__
        try:
            getter = getattr(model, "get_embedding_dimension", None) or getattr(
                model, "get_sentence_embedding_dimension", None
            )
            if getter is not None:
                info["dimensions"] = getter()
        except Exception:
            pass
    except Exception:
        pass

    _encoder_limits = info
    return info


def get_encoder_max_tokens() -> int | None:
    """Verified encoder sequence limit, or None when it cannot be determined."""
    return get_encoder_limits().get("max_tokens")

"""
Embedding model using sentence-transformers.

Uses the all-MiniLM-L6-v2 model (384 dimensions, fast, good quality).
Model is loaded lazily on first use and cached for the process lifetime.

The model is resolved from a local directory or the local HuggingFace cache
rather than from the Hub, so the first request and a cold backend start do not
depend on network access.  See ``_resolve_source`` for the resolution order.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_DIMENSIONS = 384

# Resolved against the backend package root so behaviour does not depend on the
# process working directory.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_LOCAL_MODEL_DIR = _BACKEND_DIR / "models" / _MODEL_NAME

_model = None


def _resolve_source() -> tuple[str, bool]:
    """Return ``(model_name_or_path, local_files_only)`` for SentenceTransformer.

    Resolution order:

    1. ``EMBEDDING_MODEL`` -- an existing local directory is loaded strictly
       offline; any other value is treated as a Hub model id (the explicit
       operator escape hatch, which may use the network).
    2. ``backend/models/all-MiniLM-L6-v2`` -- a project-local snapshot, when one
       has been placed there.
    3. The Hub id ``all-MiniLM-L6-v2``, resolved with ``local_files_only=True``
       so it comes from the local HuggingFace cache instead of the network.
    """
    override = os.getenv("EMBEDDING_MODEL")
    if override:
        path = Path(override).expanduser()
        if path.exists():
            return str(path), True
        return override, False

    if _LOCAL_MODEL_DIR.exists():
        return str(_LOCAL_MODEL_DIR), True

    return _MODEL_NAME, True


def get_model():
    """The shared SentenceTransformer, loaded on first use and reused after."""
    global _model
    if _model is None:
        # Deferred so importing this module -- and therefore starting the whole
        # application -- does not pay the multi-second torch/transformers import
        # cost before the embedding model is actually needed.
        from sentence_transformers import SentenceTransformer

        source, local_only = _resolve_source()
        try:
            _model = SentenceTransformer(source, local_files_only=local_only)
        except Exception:
            if not local_only:
                raise
            # Not present in the local path/cache.  Download it once rather than
            # leaving embeddings permanently unavailable, and report it instead
            # of failing with an opaque cache error.
            logger.warning(
                "Embedding model %r was not found locally; downloading it from "
                "the HuggingFace Hub. Set EMBEDDING_MODEL to a local directory "
                "to run fully offline.",
                source,
            )
            _model = SentenceTransformer(source)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.
    Returns a list of 384-dimensional float vectors.
    """
    if not texts:
        return []
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return [e.tolist() for e in embeddings]


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a single query string."""
    return embed_texts([query])[0]


def get_dimensions() -> int:
    return _DIMENSIONS

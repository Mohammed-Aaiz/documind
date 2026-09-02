"""
Embedding model using sentence-transformers.

Uses the all-MiniLM-L6-v2 model (384 dimensions, fast, good quality).
Model is loaded lazily on first use and cached.
"""

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_DIMENSIONS = 384

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
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

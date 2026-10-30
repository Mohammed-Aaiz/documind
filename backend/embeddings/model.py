"""Pinned offline MiniLM encoder and the identity of its vector space."""
from __future__ import annotations

import hashlib
import math
import os
import threading
from pathlib import Path

REPOSITORY = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
WEIGHTS_SHA256 = "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db"
IDENTITY_KEY = f"{REPOSITORY}@{REVISION}:d384:t256:l2"
_MODEL_NAME = "all-MiniLM-L6-v2"
_DIMENSIONS = 384
_LOCAL_MODEL_DIR = Path(__file__).resolve().parent / "assets" / "minilm"
# Inference-relevant Git blob hashes at the pinned revision.
_BLOB_HASHES = {
    "1_Pooling/config.json": "d1514c3162bbe87b343f565fadc62e6c06f04f03",
    "config.json": "72b987fd805cfa2b58c4c8c952b274a11bfd5a00",
    "modules.json": "952a9b81c0bfd99800fabf352f69c7ccd46c5e43",
    "sentence_bert_config.json": "59d594003bf59880a884c574bf88ef7555bb0202",
    "special_tokens_map.json": "e7b0375001f109a6b8873d756ad4f7bbb15fbaa5",
    "tokenizer.json": "cb202bfe2e3c98645018a6d12f182a434c9d3e02",
    "tokenizer_config.json": "c79f2b6a0cea6f4b564fed1938984bace9d30ff0",
}
_model = None
_model_lock = threading.Lock()
_loaded_override = None


def _resolve_source() -> tuple[str, bool]:
    """Resolve only local files; this function cannot download an encoder."""
    override = os.getenv("EMBEDDING_MODEL", "").strip()
    if override and override not in (_MODEL_NAME, REPOSITORY):
        candidate = Path(override).expanduser()
        if not candidate.is_dir():
            raise RuntimeError("Unsupported embedding model. Use the pinned MiniLM baseline or a verified local copy.")
        return str(candidate.resolve()), True
    if _LOCAL_MODEL_DIR.is_dir():
        return str(_LOCAL_MODEL_DIR), True
    from huggingface_hub import try_to_load_from_cache
    config = try_to_load_from_cache(REPOSITORY, "config.json", revision=REVISION)
    if isinstance(config, str):
        return str(Path(config).parent), True
    raise RuntimeError("Embedding assets are unavailable. Run python -m embeddings.provision_model before serving requests.")


def _verify_source(source: Path) -> None:
    """Verify weights, tokenizer, pooling and configuration before loading."""
    try:
        weights = hashlib.sha256()
        with (source / "model.safetensors").open("rb") as stream:
            for piece in iter(lambda: stream.read(1024 * 1024), b""):
                weights.update(piece)
        if weights.hexdigest() != WEIGHTS_SHA256:
            raise ValueError("Different model weights")
        for name, expected in _BLOB_HASHES.items():
            payload = (source / name).read_bytes()
            actual = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
            if actual != expected:
                raise ValueError("Different encoder configuration")
    except (OSError, ValueError) as exc:
        raise RuntimeError("Embedding assets do not match the pinned MiniLM vector space. Provision the baseline or create a separately versioned index.") from exc


def get_model():
    """Load a verified baseline once; never fetch weights during a request."""
    global _model, _loaded_override
    override = os.getenv("EMBEDDING_MODEL", "").strip()
    if _model is not None:
        if override != _loaded_override:
            raise RuntimeError("Embedding configuration changed after model loading. Restart with the pinned baseline.")
        return _model
    with _model_lock:
        if _model is None:
            source, _ = _resolve_source()
            _verify_source(Path(source))
            from sentence_transformers import SentenceTransformer
            candidate = SentenceTransformer(source, local_files_only=True, trust_remote_code=False, device="cpu")
            if candidate.get_sentence_embedding_dimension() != _DIMENSIONS or candidate.max_seq_length != 256:
                raise RuntimeError("The encoder dimensions or tokenizer window do not match the production index.")
            _model, _loaded_override = candidate, override
    return _model


def get_embedding_descriptor() -> dict:
    """Actual loaded encoder metadata; identityKey fits VARCHAR128."""
    get_model()
    return {"model": REPOSITORY, "revision": REVISION, "weightsSha256": WEIGHTS_SHA256,
            "dimensions": _DIMENSIONS, "maxSequenceLength": 256, "normalization": "l2",
            "identityKey": IDENTITY_KEY}


def compatible_embedding_labels() -> tuple[str, ...]:
    """The exact identity and explicitly known legacy baseline labels only."""
    get_model()
    return IDENTITY_KEY, _MODEL_NAME, REPOSITORY


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embeddings = get_model().encode(texts, show_progress_bar=False)
    vectors = [vector.tolist() for vector in embeddings]
    if len(vectors) != len(texts) or any(len(vector) != _DIMENSIONS or
            not all(math.isfinite(float(value)) for value in vector) for vector in vectors):
        raise RuntimeError("The encoder returned invalid vectors; nothing can be indexed.")
    return vectors


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]


def get_dimensions() -> int:
    return _DIMENSIONS

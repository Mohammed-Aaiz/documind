"""Optional, offline CLIP image/text embeddings for measured page regions.

Unlike OCR embeddings these encode the actual pixels of each region. Coordinates
and verbatim OCR/captions travel alongside the vector: CLIP similarity alone is
never evidence that a chart says something. No weights are downloaded at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import hashlib
from pathlib import Path
import threading
from typing import Any

DIMENSIONS = 512
MAX_REGIONS = 8
MAX_RENDER_PIXELS = 4_000_000
_INFERENCE_LOCK = threading.RLock()


class VisualModelUnavailable(RuntimeError):
    """The explicitly provisioned local visual encoder cannot be used."""


@dataclass(frozen=True)
class VisualPatch:
    page_number: int
    region_id: str
    kind: str
    bbox: list[float]
    ocr_text: str
    embedding: list[float]
    encoder_model: str


def _model_source(settings: Any) -> str:
    raw = getattr(settings, "visual_model_path", "")
    if not raw:
        raise VisualModelUnavailable("No local visual model path is configured.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return str(path.resolve())


def encoder_identity(settings: Any) -> str:
    """Version local artifacts so replacing a checkpoint cannot mix spaces.

    Hash small model/tokenizer configs plus weight file metadata, avoiding a
    several-hundred-MB weight read on every query. Operators must reindex after
    updating weights; preserving original file timestamps is unsupported.
    """
    path = Path(_model_source(settings))
    digest = hashlib.sha256(str(path).encode())
    if path.is_dir():
        for artifact in sorted(path.iterdir()):
            if artifact.is_file() and artifact.suffix in {".json", ".bin", ".safetensors", ".txt"}:
                stat = artifact.stat()
                digest.update(f"{artifact.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
                if artifact.suffix == ".json" and stat.st_size <= 1_000_000:
                    digest.update(artifact.read_bytes())
    return f"clip512:{digest.hexdigest()}"


def visual_model_status(settings: Any) -> dict:
    """Cheap artifact check; availability is not a successful inference claim."""
    if not getattr(settings, "visual_embeddings_enabled", False):
        return {"enabled": False, "available": False, "status": "disabled"}
    try:
        path = Path(_model_source(settings))
    except VisualModelUnavailable:
        return {"enabled": True, "available": False, "status": "not_configured"}
    files_present = (
        (path / "config.json").is_file()
        and (path / "preprocessor_config.json").is_file()
        and any((path / name).is_file() for name in (
            "model.safetensors", "pytorch_model.bin", "model.safetensors.index.json",
            "pytorch_model.bin.index.json"))
        and ((path / "tokenizer.json").is_file() or (
            (path / "vocab.json").is_file() and (path / "merges.txt").is_file()))
    )
    return {"enabled": True, "available": files_present,
            "status": "local_artifact_present" if files_present else "model_missing"}


@lru_cache(maxsize=1)
def _load_encoder(identity: str, source: str):
    # Cache only one CPU model, avoiding an unbounded resident model collection
    # on the 8 GB target machine. Serialize loading and inference below.
    if not Path(source).is_dir():
        raise VisualModelUnavailable("Local CLIP visual model is not provisioned.")
    try:
        from transformers import CLIPModel, CLIPProcessor
        model = CLIPModel.from_pretrained(source, local_files_only=True)
        processor = CLIPProcessor.from_pretrained(source, local_files_only=True)
        if model.config.projection_dim != DIMENSIONS:
            raise ValueError("Expected an aligned 512-dimensional CLIP checkpoint")
        model = model.to("cpu").eval()
        return model, processor
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        raise VisualModelUnavailable("Local CLIP visual encoder could not load.") from exc


def _unit_vectors(features) -> list[list[float]]:
    # A fixed unit norm makes the persisted pgvector cosine metric explicit.
    # Transformers 5 returns projected features in pooler_output; older
    # versions return the projected tensor directly. Never use hidden states:
    # those are not in the common image/text projection space.
    features = getattr(features, "pooler_output", features)
    features = features.float()
    norms = features.norm(dim=-1, keepdim=True)
    import torch
    if features.shape[-1] != DIMENSIONS or not torch.isfinite(features).all() or (norms <= 0).any():
        raise VisualModelUnavailable("Visual encoder returned invalid vectors.")
    return (features / norms).cpu().tolist()


def _box(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        box = [float(v) for v in value]
    except (ValueError, TypeError):
        return None
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in box):
        return None
    return box if box[0] < box[2] and box[1] < box[3] else None


def encode_page_regions(page: Any, regions: list[dict], settings: Any) -> list[VisualPatch]:
    """Render a PDF page once (<=144 DPI), then encode <=8 bounded crops.

    Figure/table crops are prioritized over paragraphs, preserving their spatial
    identity instead of flattening every object into a page-wide text vector.
    Captions linked by the measured layout stay verbatim alongside figure pixels.
    This does not interpret chart values or infer relations from their appearance.
    """
    if not getattr(settings, "visual_embeddings_enabled", False):
        return []
    identity = encoder_identity(settings)
    if not visual_model_status(settings)["available"]:
        raise VisualModelUnavailable("Local CLIP visual model is not provisioned.")
    candidates = [(r, _box(r.get("bbox"))) for r in regions if isinstance(r, dict)]
    candidates = [(r, b) for r, b in candidates if b is not None and r.get("id")]
    priority = {"figure": 0, "image": 0, "table": 1, "caption": 2}
    candidates.sort(key=lambda pair: priority.get(str(pair[0].get("kind")), 3))
    region_limit = max(1, min(MAX_REGIONS, int(getattr(settings, "visual_max_regions_per_page", 8))))
    candidates = candidates[:region_limit]
    if not candidates:
        return []
    width, height = float(page.rect.width), float(page.rect.height)
    if not math.isfinite(width * height) or width <= 0 or height <= 0:
        raise ValueError("Invalid PDF page dimensions")
    import fitz
    from PIL import Image
    # Pixel allocation is bounded before rendering; downscaling afterwards would
    # still allocate an unbounded native raster for a maliciously large page.
    dpi = max(36, min(144, int(getattr(settings, "visual_render_dpi", 96))))
    scale = min(dpi / 72.0, math.sqrt(MAX_RENDER_PIXELS / (width * height)))
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
    raster = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    crops = []
    try:
        for _, box in candidates:
            x0, y0, x1, y1 = box
            crops.append(raster.crop((max(0, math.floor(x0 * pix.width)),
                                      max(0, math.floor(y0 * pix.height)),
                                      min(pix.width, math.ceil(x1 * pix.width)),
                                      min(pix.height, math.ceil(y1 * pix.height)))))
        with _INFERENCE_LOCK:
            model, processor = _load_encoder(identity, _model_source(settings))
            import torch
            vectors = []
            with torch.inference_mode():
                batch_size = max(1, min(2, int(getattr(settings, "visual_embedding_batch_size", 2))))
                for offset in range(0, len(crops), batch_size):
                    inputs = processor(images=crops[offset:offset + batch_size], return_tensors="pt")
                    vectors.extend(_unit_vectors(model.get_image_features(**inputs)))
        patches = []
        for (region, box), vector in zip(candidates, vectors):
            exact_text = str(region.get("text") or "")
            captions = [str(r.get("text") or "") for r in regions
                        if isinstance(r, dict) and r.get("caption_for") == region["id"]]
            exact_text = "\n".join(t for t in [exact_text, *captions] if t)
            patches.append(VisualPatch(page.number + 1, str(region["id"])[:64],
                                       str(region.get("kind") or "region")[:32], box,
                                       exact_text, vector, identity))
        return patches
    finally:
        for crop in crops:
            crop.close()
        raster.close()


def encode_visual_query(question: str, settings: Any) -> list[float]:
    """Encode text in CLIP's image-aligned space, not MiniLM's OCR space."""
    if not question.strip():
        raise ValueError("A visual query must contain text")
    identity = encoder_identity(settings)
    with _INFERENCE_LOCK:
        model, processor = _load_encoder(identity, _model_source(settings))
        import torch
        inputs = processor(text=[question], return_tensors="pt", padding=True,
                           truncation=True, max_length=77)
        with torch.inference_mode():
            return _unit_vectors(model.get_text_features(**inputs))[0]

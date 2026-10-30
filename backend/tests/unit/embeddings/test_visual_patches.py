"""Real PDF crops and geometry, with deterministic fake local CLIP features.

These tests establish bounds and provenance, not learned visual quality.
"""
from types import SimpleNamespace
import math

import fitz
import pytest
import torch

from embeddings import visual


def settings(tmp_path, **kwargs):
    return SimpleNamespace(visual_model_path=str(tmp_path), visual_embeddings_enabled=True,
                           **kwargs)


def test_missing_local_artifact_never_loads_encoder_or_renders(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("A missing offline model must not load or render")

    monkeypatch.setattr(visual, "_load_encoder", forbidden)
    page = SimpleNamespace(get_pixmap=forbidden)
    assert visual.visual_model_status(settings(tmp_path))["status"] == "model_missing"
    with pytest.raises(visual.VisualModelUnavailable):
        visual.encode_page_regions(page, [{"id": "x", "bbox": [0, 0, 1, 1]}], settings(tmp_path))


@pytest.mark.parametrize("structured_features", [False, True])
def test_real_pdf_crops_preserve_pixels_caption_geometry_and_bounded_batches(tmp_path, monkeypatch, structured_features):
    captured = []

    class Processor:
        def __call__(self, *, images, return_tensors):
            captured.append([(image.size, image.getpixel((image.width // 2, image.height // 2))) for image in images])
            return {"count": len(images)}

    class Model:
        def get_image_features(self, count):
            features = torch.ones((count, 512))
            return SimpleNamespace(pooler_output=features) if structured_features else features

    monkeypatch.setattr(visual, "visual_model_status", lambda _: {"available": True})
    monkeypatch.setattr(visual, "_load_encoder", lambda *_: (Model(), Processor()))
    config = settings(tmp_path, visual_render_dpi=72, visual_max_regions_per_page=999,
                      visual_embedding_batch_size=999)
    with fitz.open() as pdf:
        page = pdf.new_page(width=200, height=100)
        page.draw_rect(fitz.Rect(0, 0, 100, 100), color=None, fill=(1, 0, 0))
        page.draw_rect(fitz.Rect(100, 0, 200, 100), color=None, fill=(0, 0, 1))
        regions = [{"id": "figure", "kind": "figure", "bbox": [0, 0, .5, 1], "text": ""},
                   {"id": "caption", "kind": "caption", "bbox": [.5, 0, 1, 1],
                    "text": "Figure 1. Exact observed caption.", "caption_for": "figure"}]
        regions.extend({"id": f"p{i}", "kind": "text", "bbox": [.5, 0, 1, 1], "text": f"Observed {i}"} for i in range(12))
        patches = visual.encode_page_regions(page, regions, config)
    assert len(patches) == 8
    assert [len(batch) for batch in captured] == [2, 2, 2, 2]
    assert captured[0][0] == ((100, 100), (255, 0, 0))
    assert captured[0][1] == ((100, 100), (0, 0, 255))
    assert patches[0].bbox == [0, 0, .5, 1]
    assert patches[0].page_number == 1
    assert patches[0].ocr_text == "Figure 1. Exact observed caption."
    assert patches[0].encoder_model.startswith("clip512:")
    assert all(len(p.embedding) == 512 for p in patches)
    assert all(math.isclose(sum(v*v for v in p.embedding), 1, abs_tol=1e-5) for p in patches)


@pytest.mark.parametrize("features", [torch.ones((1, 384)), torch.zeros((1, 512)), torch.full((1, 512), float("nan"))])
def test_invalid_encoder_vectors_are_never_accepted(features):
    with pytest.raises(visual.VisualModelUnavailable):
        visual._unit_vectors(features)


def test_encoder_identity_changes_when_checkpoint_config_changes(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"projection_dim":512}', encoding="utf-8")
    before = visual.encoder_identity(settings(tmp_path))
    config.write_text('{"projection_dim":256}', encoding="utf-8")
    assert visual.encoder_identity(settings(tmp_path)) != before


def test_query_encoding_uses_aligned_text_space_and_bounded_tokens(tmp_path, monkeypatch):
    calls = []

    class Processor:
        def __call__(self, **kwargs):
            calls.append(kwargs)
            return {"input_ids": torch.tensor([[1, 2]])}

    class Model:
        def get_text_features(self, **_kwargs):
            return SimpleNamespace(pooler_output=torch.ones((1, 512)))

    monkeypatch.setattr(visual, "_load_encoder", lambda *_: (Model(), Processor()))
    vector = visual.encode_visual_query("Which chart shows temperature?", settings(tmp_path))
    assert len(vector) == 512
    assert calls[0]["truncation"] is True and calls[0]["max_length"] == 77
    with pytest.raises(ValueError):
        visual.encode_visual_query(" ", settings(tmp_path))

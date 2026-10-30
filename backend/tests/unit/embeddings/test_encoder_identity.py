"""Offline encoder verification prevents silently mixing different vector spaces."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from embeddings import model


@pytest.fixture(autouse=True)
def isolated_encoder(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr(model, "_model", None)
    monkeypatch.setattr(model, "_loaded_override", None)


def test_model_id_override_cannot_silently_switch_to_same_dimension_bge(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    with pytest.raises(RuntimeError, match="Unsupported embedding model"):
        model.get_model()


def test_missing_local_assets_fail_without_any_snapshot_download(monkeypatch, tmp_path):
    import huggingface_hub
    monkeypatch.setattr(model, "_LOCAL_MODEL_DIR", tmp_path / "absent")
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a, **k: None)
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda *a, **k: pytest.fail("Runtime attempted a model download"))
    with pytest.raises(RuntimeError, match="provision_model"):
        model.get_model()


def test_existing_unverified_local_model_cannot_bypass_weight_identity(monkeypatch, tmp_path):
    (tmp_path / "model.safetensors").write_bytes(b"different384dimensionencoder")
    monkeypatch.setenv("EMBEDDING_MODEL", str(tmp_path))
    with pytest.raises(RuntimeError, match="separately versioned index"):
        model.get_model()


def test_matching_weights_still_require_the_expected_tokenizer_and_pooling(monkeypatch, tmp_path):
    weights, config = b"tiny-test-weights", b'{"pooling":"mean"}'
    (tmp_path / "model.safetensors").write_bytes(weights)
    (tmp_path / "config.json").write_bytes(config)
    monkeypatch.setattr(model, "WEIGHTS_SHA256", hashlib.sha256(weights).hexdigest())
    monkeypatch.setattr(model, "_BLOB_HASHES", {"config.json": hashlib.sha1(f"blob {len(config)}\0".encode() + config).hexdigest()})
    model._verify_source(tmp_path)
    (tmp_path / "config.json").write_text('{"pooling":"different"}')
    with pytest.raises(RuntimeError, match="pinned MiniLM vector space"):
        model._verify_source(tmp_path)


def test_loaded_encoder_configuration_change_requires_restart(monkeypatch, tmp_path):
    monkeypatch.setattr(model, "_model", object())
    monkeypatch.setattr(model, "_loaded_override", "")
    monkeypatch.setenv("EMBEDDING_MODEL", str(tmp_path))
    with pytest.raises(RuntimeError, match="changed after model loading"):
        model.get_model()


def test_descriptor_and_legacy_allowlist_are_consistent_and_fit_database_field(monkeypatch):
    monkeypatch.setattr(model, "_model", object())
    monkeypatch.setattr(model, "_loaded_override", "")
    descriptor = model.get_embedding_descriptor()
    assert descriptor["identityKey"] == model.IDENTITY_KEY
    assert len(descriptor["identityKey"]) <= 128
    assert descriptor["dimensions"] == 384 and descriptor["maxSequenceLength"] == 256
    assert descriptor["normalization"] == "l2"
    assert model.compatible_embedding_labels() == (model.IDENTITY_KEY, "all-MiniLM-L6-v2", model.REPOSITORY)
    assert "BAAI/bge-small-en-v1.5" not in model.compatible_embedding_labels()


@pytest.mark.parametrize("vectors", [[], [[0.] * 383], [[float("nan")] * 384]])
def test_invalid_vectors_are_rejected_before_they_can_be_indexed(monkeypatch, vectors):
    class Vector(list):
        def tolist(self):
            return list(self)
    monkeypatch.setattr(model, "_model", SimpleNamespace(encode=lambda *a, **k: [Vector(v) for v in vectors]))
    monkeypatch.setattr(model, "_loaded_override", "")
    with pytest.raises(RuntimeError, match="invalid vectors"):
        model.embed_texts(["one passage"])

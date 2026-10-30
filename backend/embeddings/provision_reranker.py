"""Explicit pinned model download: python -m embeddings.provision_reranker."""
from __future__ import annotations

import json

from generation.reranking import MODEL_PATH, REPOSITORY, REVISION


def main() -> None:
    from huggingface_hub import snapshot_download
    snapshot_download(REPOSITORY, revision=REVISION, local_dir=str(MODEL_PATH), max_workers=2,
        allow_patterns=["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                        "special_tokens_map.json", "vocab.txt"])
    (MODEL_PATH / "documind_manifest.json").write_text(json.dumps(
        {"repository": REPOSITORY, "revision": REVISION, "device": "cpu"}, indent=2), encoding="utf-8")
    print(f"Provisioned {REPOSITORY}@{REVISION} in {MODEL_PATH}")


if __name__ == "__main__":
    main()

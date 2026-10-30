"""Explicit download step; serving and ingestion never download model weights.

Run from backend: python -m embeddings.provision_visual
The checkpoint revision is pinned for reproducible indexing. Existing vectors
must be rebuilt when the configured checkpoint changes.
"""
from pathlib import Path

REPOSITORY = "openai/clip-vit-base-patch32"
REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"


def main() -> None:
    from huggingface_hub import snapshot_download
    target = Path(__file__).resolve().parent / "assets" / "clip"
    snapshot_download(
        REPOSITORY, revision=REVISION, local_dir=str(target), max_workers=2,
        allow_patterns=["config.json", "preprocessor_config.json", "pytorch_model.bin",
                        "merges.txt", "vocab.json", "tokenizer.json",
                        "tokenizer_config.json", "special_tokens_map.json"],
    )
    print(f"Provisioned {REPOSITORY}@{REVISION} in {target}")


if __name__ == "__main__":
    main()

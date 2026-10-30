"""Explicit baseline provisioning: python -m embeddings.provision_model."""
from embeddings.model import REPOSITORY, REVISION, _LOCAL_MODEL_DIR, _verify_source


def main() -> None:
    from huggingface_hub import snapshot_download
    snapshot_download(REPOSITORY, revision=REVISION, local_dir=str(_LOCAL_MODEL_DIR), max_workers=2,
        allow_patterns=["config.json", "model.safetensors", "modules.json", "sentence_bert_config.json",
                        "config_sentence_transformers.json", "1_Pooling/config.json", "tokenizer.json",
                        "tokenizer_config.json", "special_tokens_map.json", "vocab.txt"])
    _verify_source(_LOCAL_MODEL_DIR)
    print(f"Provisioned verified {REPOSITORY}@{REVISION}")


if __name__ == "__main__":
    main()

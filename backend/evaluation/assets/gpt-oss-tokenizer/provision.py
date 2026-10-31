"""Explicit research tokenizer provisioning; no model weights or auth tokens.

Run from backend: python evaluation/assets/gpt-oss-tokenizer/provision.py
An existing file is hash-checked, never overwritten. Inference stays offline.
"""
import hashlib
import json
import urllib.request
from pathlib import Path

REPOSITORY = "openai/gpt-oss-20b"
REVISION = "6cee5e81ee83917806bbde320786a8fb61efebee"
FILES = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "config.json")
ROOT = Path(__file__).resolve().parent


def main():
    manifest_path = ROOT / "documind_tokenizer_manifest.json"
    expected = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    hashes = {}
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            url = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}"
            with urllib.request.urlopen(url, timeout=90) as response:
                payload = response.read()
            if len(payload) > 64 * 1024 * 1024:
                raise ValueError("Unexpected tokenizer asset size")
            digest = hashlib.sha256(payload).hexdigest()
            if expected and expected["files_sha256"][name] != digest:
                raise ValueError("Downloaded asset differs from the committed research manifest")
            with path.open("xb") as stream:
                stream.write(payload)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected and hashes[name] != expected["files_sha256"][name]:
            raise ValueError("Existing asset differs from the committed research manifest")
    manifest = {"repository": REPOSITORY, "revision": REVISION, "license": "apache-2.0",
                "source": f"https://huggingface.co/{REPOSITORY}/tree/{REVISION}",
                "files_sha256": hashes, "role": "research_generation_context_tokenizer_only",
                "limitation": "Pinned official model tokenizer; hosted provider alias equivalence is not independently verified."}
    if not expected:
        with manifest_path.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
    print(json.dumps({"repository": REPOSITORY, "revision": REVISION, "files": len(hashes), "weights_downloaded": False}))


if __name__ == "__main__":
    main()

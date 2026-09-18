"""Explicit online build step; inference itself is offline. No AWS resources created."""

import argparse
import hashlib
import json
from pathlib import Path

from app.nlp.embeddings import MODEL_ID, MODEL_REVISION


def main():
    from huggingface_hub import snapshot_download

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    names = [
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
    ]
    snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=target, allow_patterns=names)
    manifest = {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "sha256": {
            name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in names
        },
    }
    (target / "artifact.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    from app.nlp.cpu_embedding import verify_artifact

    verify_artifact(target)
    print("Wrote pinned CPU model artifact and verified reviewed checksums.")


if __name__ == "__main__":
    main()

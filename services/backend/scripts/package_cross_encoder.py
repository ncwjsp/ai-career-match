"""Explicit download of the pinned public research model; never downloads at inference."""

import argparse
import json
from pathlib import Path

from app.modules.matching.cross_encoder import MODEL_ID, MODEL_REVISION


def main():
    from huggingface_hub import snapshot_download

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output)
    snapshot_download(
        MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=target,
        allow_patterns=[
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
        ],
    )
    (target / "identity.json").write_text(
        json.dumps({"model_id": MODEL_ID, "model_revision": MODEL_REVISION}), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

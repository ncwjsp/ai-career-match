"""A-04/A-07 bounded CPU encoder. Loads a verified local artifact, never the network."""

import hashlib
import json
import math
from pathlib import Path

from app.core.inference import EmbeddingBatch
from app.nlp.embeddings import DIMENSIONS, MODEL_ID, MODEL_REVISION
from app.nlp.text import normalize_text


def verify_artifact(directory: Path) -> None:
    manifest = json.loads((directory / "artifact.json").read_text(encoding="utf-8"))
    if (manifest["model_id"], manifest["model_revision"]) != (MODEL_ID, MODEL_REVISION):
        raise ValueError("Unexpected model artifact identity.")
    expected = json.loads(
        Path(__file__).with_name("model_manifest.json").read_text(encoding="utf-8")
    )
    if manifest != expected:
        raise ValueError("Model artifact does not match the reviewed checksum manifest.")
    required = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"}
    if not required <= manifest["sha256"].keys():
        raise ValueError("Incomplete model artifact manifest.")
    for name, expected in manifest["sha256"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Invalid artifact path.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Model artifact checksum mismatch.")


class CpuEmbeddingClient:
    def __init__(self, directory: str, *, batch_size: int = 16, threads: int = 2):
        if not 1 <= batch_size <= 32 or not 1 <= threads <= 8:
            raise ValueError("CPU batch/thread limit exceeded.")
        verify_artifact(Path(directory))
        import torch
        from transformers import AutoModel, AutoTokenizer

        torch.set_num_threads(threads)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
        self.model = (
            AutoModel.from_pretrained(directory, local_files_only=True, use_safetensors=True)
            .to("cpu")
            .eval()
        )
        self.batch_size = batch_size

    def embed(self, texts):
        if not 1 <= len(texts) <= 32:
            raise ValueError("Provide between 1 and 32 texts per batch.")
        chunks, owners, weights = [], [], []
        for owner, text in enumerate(texts):
            text = normalize_text(text).text
            if not text or len(text) > 200_000:
                raise ValueError("Embedding input exceeds text limits.")
            ids = self.tokenizer.encode(text, add_special_tokens=False, truncation=False)
            if not ids or math.ceil(len(ids) / 254) > 256:
                raise ValueError("Embedding input exceeds 256 chunks.")
            # 254 tokens plus CLS/SEP; no dropped tail and no overlapping double weight.
            for start in range(0, len(ids), 254):
                part = ids[start : start + 254]
                chunks.append(self.tokenizer.prepare_for_model(part, truncation=False))
                owners.append(owner)
                weights.append(len(part))
        torch = self.torch
        totals = torch.zeros((len(texts), DIMENSIONS))
        with torch.inference_mode():
            for start in range(0, len(chunks), self.batch_size):
                inputs = self.tokenizer.pad(
                    chunks[start : start + self.batch_size], padding=True, return_tensors="pt"
                )
                hidden = self.model(**inputs).last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
                for offset, vector in enumerate(pooled):
                    index = start + offset
                    totals[owners[index]] += vector * weights[index]
        vectors = torch.nn.functional.normalize(totals, p=2, dim=1).tolist()
        return EmbeddingBatch(vectors, MODEL_ID, MODEL_REVISION, DIMENSIONS)

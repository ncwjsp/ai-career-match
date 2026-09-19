"""Optional offline research ranker. Scores are relevance signals, not probabilities."""

import json
from pathlib import Path

from app.modules.matching.text import job_text, profile_text

MODEL_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
MODEL_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
CROSS_ENCODER_VERSION = "msmarco-233902d-pair512-sigmoid-v1"


class CrossEncoder:
    def __init__(self, model_dir: str):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        path = Path(model_dir)
        identity = json.loads((path / "identity.json").read_text(encoding="utf-8"))
        if identity != {"model_id": MODEL_ID, "model_revision": MODEL_REVISION}:
            raise ValueError("Cross-encoder artifact identity does not match the pinned model.")
        self.torch = torch
        torch.set_num_threads(2)
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            path, local_files_only=True, use_safetensors=True
        ).eval()

    def rank(self, profile, jobs):
        results = []
        text = profile_text(profile)
        with self.torch.inference_mode():
            for start in range(0, len(jobs), 8):
                batch = jobs[start : start + 8]
                inputs = self.tokenizer(
                    [text] * len(batch),
                    [job_text(job) for job in batch],
                    padding=True,
                    truncation="longest_first",
                    max_length=512,
                    return_tensors="pt",
                )
                scores = self.model(**inputs).logits.reshape(-1).sigmoid().tolist()
                results.extend(
                    (job.job_id, score) for job, score in zip(batch, scores, strict=True)
                )
        return sorted(results, key=lambda result: (-result[1], result[0]))

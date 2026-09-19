"""Run all five methods against a fully labeled, frozen JSON evaluation input."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from harness import from_pairwise, run_method
from rubric import EvaluationSplit, Label

from app.contracts.models import CandidateProfile, JobPosting
from app.modules.matching import bi_encoder, hybrid, keyword, tfidf
from app.modules.matching.cross_encoder import CROSS_ENCODER_VERSION, CrossEncoder
from app.modules.matching.text import job_text
from app.nlp.cpu_embedding import CpuEmbeddingClient
from app.nlp.embeddings import EMBEDDING_VERSION, BaselineEmbeddingClient


def load_input(payload):
    if payload.get("data_origin") not in ("synthetic", "human_labeled"):
        raise ValueError("Declare data_origin as synthetic or human_labeled.")
    profiles = {
        p.candidate_id: p for p in map(CandidateProfile.model_validate, payload["profiles"])
    }
    jobs = {j.job_id: j for j in map(JobPosting.model_validate, payload["jobs"])}
    labels = tuple(Label(**label) for label in payload["labels"])
    pairs = {(label.candidate_id, label.job_id) for label in labels}
    if len(pairs) != len(labels) or pairs != {(p, j) for p in profiles for j in jobs}:
        raise ValueError("Label every candidate/job pair exactly once before evaluation.")
    if any(type(label.relevant) is not bool or not label.labeled_by.strip() for label in labels):
        raise ValueError("Every label needs a boolean relevance and a labeler identity.")
    return (
        profiles,
        jobs,
        EvaluationSplit(payload["split_id"], tuple(profiles), tuple(jobs), labels),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--embedding-model", required=True)
    parser.add_argument("--cross-encoder-model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    raw = Path(args.input).read_bytes()
    payload = json.loads(raw)
    profiles, jobs, split = load_input(payload)
    encoder = BaselineEmbeddingClient(CpuEmbeddingClient(args.embedding_model))
    cross = CrossEncoder(args.cross_encoder_model)
    background = [job_text(job) for job in jobs.values()]
    methods = {
        "keyword": from_pairwise(keyword.score),
        "tfidf": from_pairwise(lambda p, j: tfidf.score(p, j, background=background)),
        "bi_encoder": from_pairwise(lambda p, j: bi_encoder.score(p, j, encoder)),
        "cross_encoder": lambda p, js: [job_id for job_id, _ in cross.rank(p, js)],
        "hybrid": lambda p, js: [
            r.job_id
            for r in hybrid.rerank(
                p, js, encoder, candidate_pool_size=len(js), background=background
            )
        ],
    }
    results = [
        asdict(run_method(name, rank, profiles, jobs, split, k=args.k))
        for name, rank in methods.items()
    ]
    report = {
        "data_origin": payload["data_origin"],
        "split_id": split.split_id,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "k": args.k,
        "embedding_version": EMBEDDING_VERSION,
        "cross_encoder_version": CROSS_ENCODER_VERSION,
        "results": results,
        "limitations": [
            "MS MARCO cross-encoder is not trained on this resume corpus.",
            "Cross-encoder truncates paired input to 512 tokens.",
            "Latency includes harness overhead; model loading is excluded.",
            "Synthetic labels do not establish real-world quality.",
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

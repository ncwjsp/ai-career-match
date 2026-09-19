"""Reproducible LDA over a frozen JSON corpus; never infers human relevance labels."""

import argparse
import hashlib
import json
from pathlib import Path


def analyze(documents, topics=3, seed=42):
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer

    if len(documents) < 2 or topics < 1:
        raise ValueError("Provide at least two documents and a positive topic count.")
    vectorizer = CountVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform(documents)
    model = LatentDirichletAllocation(
        n_components=topics, random_state=seed, learning_method="batch", max_iter=20
    )
    distribution = model.fit_transform(matrix)
    vocabulary = vectorizer.get_feature_names_out()
    return {
        "seed": seed,
        "topics": [
            [str(vocabulary[i]) for i in weights.argsort()[-10:][::-1]]
            for weights in model.components_
        ],
        "document_topic_probabilities": distribution.tolist(),
        "training_perplexity": float(model.perplexity(matrix)),
        "note": "Exploratory topics; training perplexity is not held-out matching quality.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", help="JSON with documents (strings) and data_origin")
    parser.add_argument("--output", required=True)
    parser.add_argument("--topics", type=int, default=3)
    args = parser.parse_args()
    raw = Path(args.corpus).read_bytes()
    corpus = json.loads(raw)
    result = analyze(corpus["documents"], args.topics)
    result.update(data_origin=corpus["data_origin"], corpus_sha256=hashlib.sha256(raw).hexdigest())
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

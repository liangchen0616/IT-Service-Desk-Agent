"""Rank-based fusion; raw cosine and BM25 scores are never mixed."""
from retrieval.contracts import RetrievedChunk, chunk_id, positive_int


def reciprocal_rank_fusion(rankings, top_k=3, rank_constant=60):
    positive_int(top_k, "top_k")
    positive_int(rank_constant, "rank_constant")
    scores, chunks = {}, {}
    for ranking in rankings:
        seen = set()
        rank = 0
        for result in ranking:
            key = chunk_id(result.chunk)
            if key in seen:
                continue
            seen.add(key)
            rank += 1
            chunks.setdefault(key, result.chunk)
            scores[key] = scores.get(key, 0.0) + 1 / (rank_constant + rank)
    keys = sorted(scores, key=lambda key: -scores[key])[:top_k]
    return [RetrievedChunk(chunks[key], scores[key], "rrf") for key in keys]

"""Compose interchangeable dense and sparse retrievers."""
from retrieval.contracts import positive_int
from retrieval.fusion import reciprocal_rank_fusion


class HybridRetriever:
    def __init__(self, dense, sparse, candidate_k=20, rank_constant=60):
        positive_int(candidate_k, "candidate_k")
        positive_int(rank_constant, "rank_constant")
        self.dense, self.sparse = dense, sparse
        self.candidate_k, self.rank_constant = candidate_k, rank_constant

    def retrieve(self, query, top_k=3, min_score=None):
        if min_score is not None:
            raise ValueError("Hybrid RRF scores cannot use a cosine threshold; set min_score=None")
        positive_int(top_k, "top_k")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be nonempty text")
        count = max(top_k, self.candidate_k)
        return reciprocal_rank_fusion([
            self.dense.retrieve(query, top_k=count),
            self.sparse.retrieve(query, top_k=count),
        ], top_k=top_k, rank_constant=self.rank_constant)

"""Exact cosine search using FAISS; JSON remains the portable cache format."""
from copy import deepcopy
import numpy as np
import faiss
from retrieval.contracts import RetrievedChunk, positive_int


class FaissVectorStore:
    def __init__(self):
        self._index = None
        self._chunks = []

    @staticmethod
    def _normalize(vectors):
        matrix = np.asarray(vectors, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] == 0 or not np.isfinite(matrix).all():
            raise ValueError("Vectors must be finite, rectangular and nonempty")
        scale = np.max(np.abs(matrix), axis=1, keepdims=True)
        if np.any(scale == 0):
            raise ValueError("Vectors must be nonzero")
        matrix = matrix / scale
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
        return np.ascontiguousarray(matrix, dtype=np.float32)

    def add(self, items):
        items = list(items)
        if not items:
            return
        matrix = self._normalize([item.vector for item in items])
        if self._index is not None and matrix.shape[1] != self._index.d:
            raise ValueError("Vector dimensions must match")
        chunks = deepcopy([item.chunk for item in items])
        index = faiss.IndexFlatIP(matrix.shape[1]) if self._index is None else faiss.clone_index(self._index)
        index.add(matrix)
        self._index = index
        self._chunks.extend(chunks)

    def count(self):
        return len(self._chunks)

    def search(self, query_vector, top_k=3):
        positive_int(top_k, "top_k")
        query = self._normalize([query_vector])
        if self._index is None:
            return []
        if query.shape[1] != self._index.d:
            raise ValueError("Query dimension must match index")
        scores, ids = self._index.search(query, min(top_k, self.count()))
        return [RetrievedChunk(deepcopy(self._chunks[int(i)]),
                max(-1.0, min(1.0, float(score))), "cosine")
                for score, i in zip(scores[0], ids[0]) if i >= 0]

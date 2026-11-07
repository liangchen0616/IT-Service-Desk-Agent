from dataclasses import dataclass
from math import isfinite
from embeddings.embedder import EmbeddedChunk
from ingestion.chunker import Chunk


@dataclass
class SearchResult:
    """A retrieved chunk and its similarity score."""

    chunk: Chunk
    score: float


class InMemoryVectorStore:
    """Store document embeddings in memory."""

    def __init__(self):
        self._items: list[EmbeddedChunk] = []

    def add(self, items: list[EmbeddedChunk]) -> None:
        """Append document embeddings with matching dimensions."""
        if not items:
            return

        if self._items:
            expected_dimension = len(self._items[0].vector)
        else:
            expected_dimension = len(items[0].vector)

        for item in items:
            if not item.vector:
                raise ValueError("Vector must not be empty.")

            if len(item.vector) != expected_dimension:
                raise ValueError("Vector dimensions must match.")

        self._items.extend(items)

    def export_items(self):
        """Return an isolated snapshot for alternative search indexes."""
        from copy import deepcopy
        return deepcopy(self._items)

    def count(self) -> int:
        """Return the number of stored embeddings."""
        return len(self._items)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two nonzero vectors."""
        if not a or not b:
            raise ValueError("Vectors must not be empty.")

        if len(a) != len(b):
            raise ValueError("Vector dimensions must match.")

        if not all(isfinite(value) for value in a + b):
            raise ValueError("Vector values must be finite.")

        norm_a = sum(value ** 2 for value in a) ** 0.5
        norm_b = sum(value ** 2 for value in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            raise ValueError("Vectors must have nonzero norms.")

        dot_product = sum(x * y for x, y in zip(a, b, strict=True))
        score = dot_product / (norm_a * norm_b)

        return max(-1.0, min(1.0, score))

    def search(
        self,
        query_vector: list[float],
        top_k: int = 3,
    ) -> list[SearchResult]:
        """Return the most similar document chunks."""
        if type(top_k) is not int:
            raise TypeError("top_k must be an integer.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")

        if not query_vector:
            raise ValueError("Query vector must not be empty.")

        if not all(isfinite(value) for value in query_vector):
            raise ValueError("Query vector values must be finite.")

        if all(value == 0 for value in query_vector):
            raise ValueError("Query vector must have a nonzero norm.")

        results = []

        for item in self._items:
            score = self._cosine_similarity(query_vector, item.vector)
            results.append(SearchResult(chunk=item.chunk, score=score))

        results.sort(key=lambda result: result.score, reverse=True)

        return results[:top_k]
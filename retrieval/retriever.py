from embeddings.embedder import LocalEmbedder
from vectorstore.memory_store import InMemoryVectorStore, SearchResult


class KnowledgeRetriever:
    """Search stored document chunks using a text question."""

    def __init__(
        self,
        embedder: LocalEmbedder,
        store: InMemoryVectorStore,
    ):
        self.embedder = embedder
        self.store = store


    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        query_vector = self.embedder.embed_query(query)
        results = self.store.search(query_vector, top_k=top_k)

        if min_score is None:
            return results

        return [
            result
            for result in results
            if result.score >= min_score
        ]
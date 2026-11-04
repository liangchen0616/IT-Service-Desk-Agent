from sentence_transformers import SentenceTransformer

from dataclasses import dataclass

from ingestion.chunker import Chunk


@dataclass
class EmbeddedChunk:
    """A text chunk paired with its embedding vector."""

    chunk: Chunk
    vector: list[float]

class LocalEmbedder:
    """Load a local embedding model."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
    ):
        self.model = SentenceTransformer(
            model_name,
            device="cpu",
        )

    def embed_chunk(self, chunk: Chunk) -> EmbeddedChunk:
        """Generate an embedding for one document chunk."""
        if not chunk.content.strip():
            raise ValueError("Chunk content must not be empty.")

        vector = self.model.encode(
            chunk.content,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return EmbeddedChunk(
            chunk=chunk,
            vector=vector.tolist(),
        )

    def embed_query(self, query: str) -> list[float]:
        """Generate an embedding for a search query."""
        if not query.strip():
            raise ValueError("Query must not be empty.")

        vector = self.model.encode(
            query,
            prompt_name="query",
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return vector.tolist()

    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Generate embeddings for a list of document chunks."""
        results = []

        for chunk in chunks:
            embedded_chunk = self.embed_chunk(chunk)
            results.append(embedded_chunk)

        return results
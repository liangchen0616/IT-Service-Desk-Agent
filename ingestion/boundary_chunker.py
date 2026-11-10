import re

from ingestion.chunker import Chunk, DocumentChunker
from ingestion.loader import Document


class BoundaryChunker(DocumentChunker):
    """Prefer punctuation and line boundaries within the size limit."""

    def _chunk_text(self, document: Document) -> list[Chunk]:
        text = document.content
        if not text.strip():
            return []

        boundaries = [
            match.end()
            for match in re.finditer(r"[。！？!?；;]|\n+|\.(?=\s|$)", text)
        ]
        boundaries = sorted(set(boundaries + [len(text)]))

        chunks = []
        start = 0

        while start < len(text):
            limit = min(start + self.chunk_size, len(text))
            end = self._choose_end(start, limit, len(text), boundaries)

            if text[start:end].strip():
                chunks.append(Chunk(
                    content=text[start:end],
                    metadata=document.metadata.copy(),
                    chunk_index=len(chunks),
                    start_index=start,
                    end_index=end,
                ))

            if end == len(text):
                break

            start = self._choose_start(start, end, boundaries)

        return chunks

    @staticmethod
    def _choose_end(start, limit, text_length, boundaries):
        if limit == text_length:
            return limit

        candidates = [
            point
            for point in boundaries
            if start < point <= limit
        ]
        return max(candidates) if candidates else limit

    def _choose_start(self, start, end, boundaries):
        candidates = [
            point
            for point in boundaries
            if max(start + 1, end - self.overlap) <= point < end
        ]
        return min(candidates) if candidates else end
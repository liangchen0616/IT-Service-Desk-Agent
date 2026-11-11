from dataclasses import dataclass
from ingestion.loader import Document

@dataclass
class Chunk:
    """A text chunk with document metadata and position."""

    content: str
    metadata: dict
    chunk_index: int
    start_index: int
    end_index: int


class DocumentChunker:
    """Configure character-based document chunking."""

    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        if type(chunk_size) is not int:
            raise TypeError("chunk_size must be an integer.")

        if type(overlap) is not int:
            raise TypeError("overlap must be an integer.")

        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0.")

        if overlap < 0 or overlap >= chunk_size:
            raise ValueError(
                "overlap must satisfy 0 <= overlap < chunk_size."
            )

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, document: Document) -> list[Chunk]:
        """Keep PDF chunks within one page and preserve document offsets."""
        if document.page_spans is None:
            return self._chunk_text(document)
        chunks = []
        for page, (start, end) in enumerate(document.page_spans, start=1):
            text = document.content[start:end]
            if not text.strip():
                continue
            metadata={**document.metadata, "page": page}
            if page in metadata.get("ocr_pages",[]): metadata["extraction_method"]="ocr"
            page_document = Document(text, metadata)
            for chunk in self._chunk_text(page_document):
                chunk.start_index += start
                chunk.end_index += start
                chunk.chunk_index = len(chunks)
                chunks.append(chunk)
        return chunks

    def _chunk_text(self, document: Document) -> list[Chunk]:
        """Split a document into overlapping character chunks."""
        chunks = []
        start = 0
        chunk_index = 0
        text = document.content

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk = Chunk(
                content=text[start:end],
                metadata=document.metadata.copy(),
                chunk_index=chunk_index,
                start_index=start,
                end_index=end,
            )
            chunks.append(chunk)
            chunk_index += 1

            if end == len(text):
                break

            start = end - self.overlap

        return chunks
"""Retrieval results retain the legacy chunk interface and explicit score semantics."""
from dataclasses import dataclass
import hashlib
import json
from ingestion.chunker import Chunk


def chunk_id(chunk: Chunk) -> str:
    payload = [chunk.metadata, chunk.chunk_index, chunk.start_index,
               chunk.end_index, chunk.content]
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                         ensure_ascii=False).encode()).hexdigest()


def positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float
    score_type: str

    @property
    def chunk_id(self):
        return chunk_id(self.chunk)

    @property
    def text(self):
        return self.chunk.content

    @property
    def source(self):
        return self.chunk.metadata.get("source", "")

    @property
    def page(self):
        return self.chunk.metadata.get("page")

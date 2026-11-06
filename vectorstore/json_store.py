import json
import os
import tempfile
from dataclasses import asdict
from math import isfinite
from pathlib import Path

from embeddings.embedder import EmbeddedChunk
from ingestion.chunker import Chunk
from vectorstore.memory_store import InMemoryVectorStore


class IndexMismatchError(ValueError):
    """The saved index belongs to a different model or document snapshot."""


class JsonVectorStore(InMemoryVectorStore):
    """Reuse in-memory search and save a small knowledge index as JSON."""

    FORMAT_VERSION = 1

    @staticmethod
    def _decode_item(record: dict) -> EmbeddedChunk:
        """Validate one JSON record and restore its Python data objects."""
        if not isinstance(record, dict):
            raise ValueError("Each index item must be an object.")
        chunk = record.get("chunk")
        vector = record.get("vector")
        if not isinstance(chunk, dict):
            raise ValueError("Missing chunk object.")
        content = chunk.get("content")
        metadata = chunk.get("metadata")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Chunk content must not be blank.")
        if not isinstance(metadata, dict):
            raise ValueError("Chunk metadata must be an object.")
        if not isinstance(metadata.get("source"), str) or not metadata["source"].strip():
            raise ValueError("Chunk metadata must contain a source.")
        positions = [chunk.get(name) for name in ("chunk_index", "start_index", "end_index")]
        if any(type(value) is not int or value < 0 for value in positions):
            raise ValueError("Chunk indices must be nonnegative integers.")
        chunk_index, start, end = positions
        if end - start != len(content):
            raise ValueError("Chunk positions must match its content length.")
        if not isinstance(vector, list) or not vector:
            raise ValueError("Vector must be a nonempty list.")
        if any(type(value) not in (int, float) or not isfinite(value) for value in vector):
            raise ValueError("Vector values must be finite numbers.")
        if not any(vector):
            raise ValueError("Vector must be nonzero.")
        return EmbeddedChunk(
            chunk=Chunk(content, metadata, chunk_index, start, end),
            vector=vector,
        )

    @classmethod
    def _from_payload(cls, payload: dict) -> "JsonVectorStore":
        """Validate the file structure before exposing a searchable store."""
        if not isinstance(payload, dict):
            raise ValueError("Index must be a JSON object.")
        if type(payload.get("format_version")) is not int or payload["format_version"] != cls.FORMAT_VERSION:
            raise ValueError("Unsupported index format. Rebuild the index.")
        for name in ("model_name", "signature"):
            if not isinstance(payload.get(name), str) or not payload[name].strip():
                raise ValueError(f"Index must contain {name}.")
        records = payload.get("items")
        if not isinstance(records, list) or not records:
            raise ValueError("Index must contain a nonempty items list.")
        store = cls()
        store.add([cls._decode_item(record) for record in records])
        return store

    def save(self, path: Path, model_name: str, signature: str) -> None:
        """Write a complete replacement first, then replace the previous index."""
        payload = {
            "format_version": self.FORMAT_VERSION,
            "model_name": model_name,
            "signature": signature,
            "items": [asdict(item) for item in self._items],
        }
        self._from_payload(payload)
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as output:
                temporary_path = Path(output.name)
                output.write(serialized)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: Path, model_name: str, signature: str) -> "JsonVectorStore":
        """Restore the index only when its model and document signature match."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            store = cls._from_payload(payload)
        except (ValueError, UnicodeError) as error:
            raise ValueError(
                "Saved index is invalid. Run: python -m ingestion.build_index"
            ) from error
        if payload["model_name"] != model_name or payload["signature"] != signature:
            raise IndexMismatchError("Documents or embedding settings have changed.")
        return store

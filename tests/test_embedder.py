import pytest

from embeddings.embedder import LocalEmbedder

from ingestion.chunker import Chunk

@pytest.mark.parametrize("query", ["", "   ", "\n"])
def test_embed_query_rejects_blank_text(query, monkeypatch):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, *args, **kwargs):
            raise AssertionError("Empty queries must not reach the model.")

    monkeypatch.setattr(
        "embeddings.embedder.SentenceTransformer",
        FakeModel,
    )

    embedder = LocalEmbedder()

    with pytest.raises(ValueError, match="Query"):
        embedder.embed_query(query)


def test_embed_query_uses_query_prompt(monkeypatch):
    calls = []

    class FakeVector:
        def tolist(self):
            return [0.6, 0.8]

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, text, **kwargs):
            calls.append((text, kwargs))
            return FakeVector()

    monkeypatch.setattr(
        "embeddings.embedder.SentenceTransformer",
        FakeModel,
    )

    embedder = LocalEmbedder()
    vector = embedder.embed_query("VPN 无法连接怎么办？")

    assert vector == [0.6, 0.8]
    assert len(calls) == 1

    text, options = calls[0]
    assert text == "VPN 无法连接怎么办？"
    assert options["prompt_name"] == "query"
    assert options["normalize_embeddings"] is True


def test_embed_chunk_preserves_chunk(monkeypatch):
    calls = []

    class FakeVector:
        def tolist(self):
            return [0.6, 0.8]

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, text, **kwargs):
            calls.append((text, kwargs))
            return FakeVector()

    monkeypatch.setattr(
        "embeddings.embedder.SentenceTransformer",
        FakeModel,
    )

    content = "VPN 连接失败时，请检查网络。"
    chunk = Chunk(
        content=content,
        metadata={"source": "vpn.txt"},
        chunk_index=2,
        start_index=100,
        end_index=100 + len(content),
    )

    embedder = LocalEmbedder()
    result = embedder.embed_chunk(chunk)

    assert result.chunk is chunk
    assert result.vector == [0.6, 0.8]
    assert len(calls) == 1

    text, options = calls[0]
    assert text == content
    assert options["normalize_embeddings"] is True
    assert "prompt_name" not in options
    assert "prompt" not in options


def test_embed_chunks_preserves_order(monkeypatch):
    expected_vectors = {
        "VPN": [1.0, 0.0],
        "食堂": [0.0, 1.0],
    }

    class FakeVector:
        def __init__(self, values):
            self.values = values

        def tolist(self):
            return self.values

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, text, **kwargs):
            return FakeVector(expected_vectors[text])

    monkeypatch.setattr(
        "embeddings.embedder.SentenceTransformer",
        FakeModel,
    )

    chunks = [
        Chunk(
            content=text,
            metadata={"source": f"document_{index}.txt"},
            chunk_index=0,
            start_index=0,
            end_index=len(text),
        )
        for index, text in enumerate(["VPN", "食堂"])
    ]

    embedder = LocalEmbedder()
    results = embedder.embed_chunks(chunks)

    assert len(results) == 2
    assert results[0].chunk is chunks[0]
    assert results[1].chunk is chunks[1]
    assert results[0].vector == [1.0, 0.0]
    assert results[1].vector == [0.0, 1.0]

@pytest.mark.parametrize("content", ["", "   ", "\n"])
def test_embed_chunk_rejects_blank_text(content, monkeypatch):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, *args, **kwargs):
            raise AssertionError("Blank chunks must not reach the model.")

    monkeypatch.setattr(
        "embeddings.embedder.SentenceTransformer",
        FakeModel,
    )

    chunk = Chunk(
        content=content,
        metadata={"source": "blank.txt"},
        chunk_index=0,
        start_index=0,
        end_index=len(content),
    )
    embedder = LocalEmbedder()

    with pytest.raises(ValueError, match="Chunk"):
        embedder.embed_chunk(chunk)        
        
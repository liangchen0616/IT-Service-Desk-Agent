import pytest
from embeddings.embedder import EmbeddedChunk
from ingestion.chunker import Chunk
from vectorstore.faiss_store import FaissVectorStore
from vectorstore.memory_store import InMemoryVectorStore
from retrieval.retriever import KnowledgeRetriever
from retrieval.factory import build_hybrid_retriever
from generation.rag import RagAssistant
from types import SimpleNamespace


def item(text, vector):
    return EmbeddedChunk(Chunk(text, {"source": "test.txt"}, 0, 0, len(text)), vector)


def test_faiss_matches_cosine_and_rejects_bad_batch():
    items = [item("vpn", [3, 4]), item("printer", [1, 0])]
    faiss, memory = FaissVectorStore(), InMemoryVectorStore()
    faiss.add(items)
    memory.add(items)
    actual, expected = faiss.search([2, 0]), memory.search([2, 0])
    assert [x.chunk.content for x in actual] == [x.chunk.content for x in expected]
    assert [x.score for x in actual] == pytest.approx([x.score for x in expected])
    with pytest.raises(ValueError): faiss.add([item("bad", [0, 0])])
    assert faiss.count() == 2


@pytest.mark.parametrize("vector", [[], [0, 0], [float("nan"), 1], [float("inf"), 1], [1, 2, 3]])
def test_invalid_query(vector):
    store = FaissVectorStore()
    store.add([item("vpn", [1, 0])])
    with pytest.raises(ValueError): store.search(vector)


def test_hybrid_reaches_citation_validation():
    class Embedder:
        def embed_query(self, query): return [1, 0]
    class Model:
        def generate(self, messages, schema):
            return {"answerable": True, "answer": "Check VPN.",
                    "evidence": [{"source_id": 1, "quote": "Check VPN"}]}
    store = InMemoryVectorStore()
    store.add([item("Check VPN", [1, 0])])
    kb = SimpleNamespace(retriever=KnowledgeRetriever(Embedder(), store))
    hybrid = build_hybrid_retriever(kb)
    answer = RagAssistant(hybrid, Model(), min_score=None).answer("VPN")
    assert answer.answered
    assert answer.citations[0].quote == "Check VPN"
    with pytest.raises(ValueError, match="cosine"):
        RagAssistant(hybrid, Model()).answer("VPN")

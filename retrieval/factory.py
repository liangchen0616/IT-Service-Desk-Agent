"""Build hybrid search from an existing knowledge base without re-embedding."""
from retrieval.retriever import KnowledgeRetriever
from retrieval.sparse import BM25Retriever
from retrieval.hybrid import HybridRetriever
from vectorstore.faiss_store import FaissVectorStore


def build_hybrid_retriever(knowledge_base, *, candidate_k=20, rank_constant=60):
    items = knowledge_base.retriever.store.export_items()
    store = FaissVectorStore()
    store.add(items)
    dense = KnowledgeRetriever(knowledge_base.retriever.embedder, store)
    sparse = BM25Retriever([item.chunk for item in items])
    return HybridRetriever(dense, sparse, candidate_k=candidate_k, rank_constant=rank_constant)

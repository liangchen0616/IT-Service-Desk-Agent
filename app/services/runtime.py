"""Single-process local runtime; immutable index replacement under a lock."""
from app.services.upload_catalog import published_uploads, tag_upload
from dataclasses import replace
from pathlib import Path
from threading import RLock
from memory.sessions import SessionStore
from types import SimpleNamespace
from agents.graph import AgentGraph
from embeddings.embedder import LocalEmbedder
from llm.factory import ModelFactory
from ingestion.knowledge_base import build_knowledge_base
from core.config import ProjectConfig, PROJECT_ROOT, load_config
from retrieval.factory import build_hybrid_retriever
from retrieval.retriever import KnowledgeRetriever
from vectorstore.memory_store import InMemoryVectorStore


class Runtime:
    def __init__(self, config=None, uploads=None, embedder=None, model=None):
        self.config = config if config is not None else load_config()
        self.uploads = Path(uploads) if uploads is not None else PROJECT_ROOT / "data" / "uploads"
        self.embedder, self.model = embedder, model
        self._model_injected = model is not None
        self.model_factory = ModelFactory(self.config)
        self.reports_dir = PROJECT_ROOT / "data" / "reports"
        self.lock = RLock()
        if self.config.session_backend == "sqlite":
            from memory.sqlite_sessions import SQLiteSessionStore
            self.sessions = SQLiteSessionStore(self.config.session_db_path,ttl=self.config.session_ttl)
        else:
            self.sessions = SessionStore(ttl=self.config.session_ttl)
        self.agent = None
        self.items = []
        self.reranker = None
        if self.config.reranker_enabled:
            from retrieval.reranker import CrossEncoderReranker
            self.reranker = CrossEncoderReranker(self.config.reranker_model, self.config.reranker_batch_size)

    def make_agent(self, items):
        store = InMemoryVectorStore()
        store.add(items)
        kb = SimpleNamespace(retriever=KnowledgeRetriever(self.embedder, store))
        retriever = build_hybrid_retriever(kb, candidate_k=self.config.candidate_k,
            rank_constant=self.config.rank_constant)
        if self.reranker is not None:
            from retrieval.reranker import RerankingRetriever
            retriever = RerankingRetriever(retriever, self.reranker, self.config.candidate_k)
        grade_model = self.model if self._model_injected else self.model_factory.get_model("grade")
        rewrite_model = self.model if self._model_injected else self.model_factory.get_model("rewrite")
        return AgentGraph(retriever, self.model, self.config,
                          grade_model=grade_model, rewrite_model=rewrite_model)

    def ensure_ready(self):
        if self.agent is not None: return
        if self.embedder is None: self.embedder = LocalEmbedder(self.config.model_name)
        if self.model is None: self.model = self.model_factory.get_model("generate")
        kb = build_knowledge_base(self.config, self.embedder, use_cache=True)
        items = kb.retriever.store.export_items()
        for folder, document in published_uploads(self.uploads):
            config = replace(self.config, documents_dir=folder / "documents",
                file_names=(document.name,), index_path=folder / "index.json")
            saved = build_knowledge_base(config, self.embedder, use_cache=True)
            items.extend(tag_upload(saved.retriever.store.export_items(), folder.name))
        agent = self.make_agent(items)
        self.items, self.agent = items, agent

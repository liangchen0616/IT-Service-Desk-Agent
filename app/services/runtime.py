"""Single-process local runtime; immutable index replacement under a lock."""
from dataclasses import replace
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from agents.graph import AgentGraph
from embeddings.embedder import LocalEmbedder
from generation.local_llm import OllamaChat
from ingestion.knowledge_base import build_knowledge_base
from project_config import ProjectConfig, PROJECT_ROOT
from retrieval.factory import build_hybrid_retriever
from retrieval.retriever import KnowledgeRetriever
from vectorstore.memory_store import InMemoryVectorStore


class Runtime:
    def __init__(self, config=None, uploads=None, embedder=None, model=None):
        self.config = config or ProjectConfig()
        self.uploads = Path(uploads) if uploads is not None else PROJECT_ROOT / "data" / "uploads"
        self.embedder, self.model = embedder, model
        self.lock = RLock()
        self.agent = None
        self.items = []

    def make_agent(self, items):
        store = InMemoryVectorStore()
        store.add(items)
        kb = SimpleNamespace(retriever=KnowledgeRetriever(self.embedder, store))
        return AgentGraph(build_hybrid_retriever(kb), self.model)

    def ensure_ready(self):
        if self.agent is not None: return
        if self.embedder is None: self.embedder = LocalEmbedder(self.config.model_name)
        if self.model is None: self.model = OllamaChat()
        kb = build_knowledge_base(self.config, self.embedder, use_cache=True)
        items = kb.retriever.store.export_items()
        if self.uploads.exists():
            for folder in sorted(self.uploads.iterdir()):
                if not folder.is_dir() or folder.name.startswith("."): continue
                docs = list((folder / "documents").glob("*"))
                if len(docs) != 1: raise ValueError("Invalid stored upload")
                config = replace(self.config, documents_dir=folder / "documents",
                    file_names=(docs[0].name,), index_path=folder / "index.json")
                saved = build_knowledge_base(config, self.embedder, use_cache=True)
                items.extend(saved.retriever.store.export_items())
        agent = self.make_agent(items)
        self.items, self.agent = items, agent

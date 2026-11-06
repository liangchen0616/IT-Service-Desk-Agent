from dataclasses import dataclass
import hashlib
import json

from embeddings.embedder import LocalEmbedder
from ingestion.boundary_chunker import BoundaryChunker
from ingestion.chunker import DocumentChunker
from ingestion.loader import Document, DocumentLoader
from project_config import ProjectConfig
from retrieval.retriever import KnowledgeRetriever
from vectorstore.memory_store import InMemoryVectorStore
from vectorstore.json_store import IndexMismatchError, JsonVectorStore


# Increase this when changing document extraction or embedding behavior.
PIPELINE_VERSION = 1


@dataclass
class KnowledgeBase:
    config: ProjectConfig
    retriever: KnowledgeRetriever
    document_count: int
    chunk_count: int
    loaded_from_cache: bool = False


def compute_signature(config: ProjectConfig) -> str:
    """Identify the selected file contents and settings that produce vectors."""
    files = []
    for filename in config.file_names:
        digest = hashlib.sha256()
        with (config.documents_dir / filename).open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        files.append({"name": filename, "sha256": digest.hexdigest()})
    snapshot = {
        "pipeline_version": PIPELINE_VERSION,
        "model_name": config.model_name,
        "chunk_mode": config.chunk_mode,
        "chunk_size": config.chunk_size,
        "overlap": config.overlap,
        "files": files,
    }
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_documents(config: ProjectConfig) -> list[Document]:
    loader = DocumentLoader()
    readers = {
        ".txt": loader.load_txt,
        ".md": loader.load_markdown,
        ".pdf": loader.load_pdf,
    }
    documents = []
    for filename in config.file_names:
        path = config.documents_dir / filename
        document = readers[path.suffix.lower()](path)
        documents.append(document)
    return documents


def build_knowledge_base(
    config: ProjectConfig | None = None,
    embedder: LocalEmbedder | None = None,
    *,
    use_cache: bool = False,
    force_rebuild: bool = False,
) -> KnowledgeBase:
    """Build in memory, or reuse a matching disk index when requested."""
    config = config if config is not None else ProjectConfig()
    if force_rebuild and not use_cache:
        raise ValueError("force_rebuild requires use_cache=True.")
    signature = compute_signature(config) if use_cache else None
    if use_cache and config.index_path.exists() and not force_rebuild:
        try:
            store = JsonVectorStore.load(config.index_path, config.model_name, signature)
        except IndexMismatchError:
            pass  # A valid but outdated index is rebuilt from the source files.
        else:
            if embedder is None:
                embedder = LocalEmbedder(model_name=config.model_name)
            retriever = KnowledgeRetriever(embedder=embedder, store=store)
            return KnowledgeBase(config, retriever, len(config.file_names), store.count(), True)

    documents = load_documents(config)
    chunker_type = BoundaryChunker if config.chunk_mode == "boundary" else DocumentChunker
    chunker = chunker_type(config.chunk_size, config.overlap)
    chunks = []
    for document in documents:
        chunks.extend(
            chunk for chunk in chunker.chunk_document(document)
            if chunk.content.strip()
        )
    if not chunks:
        raise ValueError("No usable text found in the selected documents.")

    if embedder is None:
        embedder = LocalEmbedder(model_name=config.model_name)
    items = embedder.embed_chunks(chunks)
    if len(items) != len(chunks):
        raise ValueError("The embedder must return one vector for every chunk.")
    store = JsonVectorStore() if use_cache else InMemoryVectorStore()
    store.add(items)
    if use_cache:
        if compute_signature(config) != signature:
            raise ValueError("Documents changed during indexing. Run the build again.")
        store.save(config.index_path, config.model_name, signature)
    retriever = KnowledgeRetriever(embedder=embedder, store=store)
    return KnowledgeBase(config, retriever, len(documents), len(chunks))

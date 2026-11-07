# Development specification — V2.1

Baseline: 开发文档, 2026-11-07. This supersedes the earlier V1.0 and V2.0 layouts.

## Boundaries
Agent decides; retrieval searches; services coordinate business workflows; infrastructure implements storage and model access.
Target packages: app/api, app/schemas, app/services; agents/nodes; ingestion; embeddings; retrieval; vectorstore; llm/prompts; core; ui; tools; evaluation; tests/unit; tests/integration; scripts; docs.
Do not replace existing working modules merely to match the directory names.

## Seven-day plan (November 8–14, 2026)
1. core, ingestion, embeddings, vectorstore: configuration, PDF/TXT/MD, metadata and FAISS.
2. retrieval: BM25, RRF and hybrid retrieval.
3. agents and llm: LangGraph state, routing, relevance grading, query rewrite and generation.
4. app: FastAPI routes, schemas, services, upload, chat, health and citations.
5. ui: Streamlit demo; optional web search.
6. tests and evaluation: unit/integration tests, at least 20 evaluation questions and measured latency.
7. docs and scripts: reproducible setup, CLI demo and delivery documentation.

## Contracts and acceptance
DocumentService -> IngestionPipeline -> Embedder -> FAISSStore/BM25Store.
ChatRoute -> ChatService -> AgentGraph -> RetrieveNode -> HybridRetriever.
GenerateNode -> LLMClient -> Answer + Sources + Trace.
Retrieved chunks carry chunk_id, text, source, optional page, score and score_type. Do not compare raw scores across retrieval methods.
Query rewriting is limited to two attempts. Citation correction is a separate bounded operation. Insufficient evidence must produce an explicit fallback rather than fabricated sources.
Record node paths, retry counts, sources and elapsed time. Keep API keys in environment variables.
P0: complete local knowledge workflow, citations, API, UI and evaluation.
P1: reranker, web search, model factory and RAGAs. P2: memory, containers and CI. Do not let P1/P2 block P0.

## Migration inspection (November 7)
The canonical repository is E:/Code/project/IT-Service-Desk-Agent. The ChatGPT workspace contains earlier day-by-day copies.
Existing README describes Qwen3 embeddings, boundary chunking, JSON cache validation and cosine retrieval. Preserve these working capabilities and existing model configuration during migration; E5 is the specification default, not grounds to discard local Qwen assets.
Existing generation code and three generation test files are untracked. Preserve them, including citation validation and correction.
Next implementation milestone: introduce shared retrieval contracts and FAISS/BM25/RRF adapters with compatibility tests before switching the current retriever.
This document records the target architecture; it does not claim the seven-day implementation is complete.

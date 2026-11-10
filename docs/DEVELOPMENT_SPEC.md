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

## Progress update — November 8, 2026

Hybrid retrieval, LangGraph, API and the initial evaluation are implemented (the migration notes above describe the initial inspection). Added core/config.py and .env.example. API Runtime and the full Agent CLI now load validated configuration with environment > project .env > defaults. Legacy project_config imports remain compatible. Retrieval and generation share configurable Top-K/context limits. Query rewrites remain capped at two. Unified logging/exceptions, other CLI entry points and broader evaluation remain pending; UI remains deferred.

### Logging and errors — November 8, 2026

Added core/logging.py and core/exceptions.py: JSON application logs, per-request IDs, consistent API errors, and distinct model vs internal workflow failures. API and full Agent CLI are integrated. Terminal output only; log rotation/central collection and remaining legacy entry points are not implemented.

### CLI integration — November 8, 2026

Added scripts/ingest.py and scripts/demo_query.py backed by the local API. Upload and query share the same live knowledge base/model; no automatic upload retries. Standalone generation.demo_agent now restores published uploads at startup; later changes require restart. Legacy demos and benchmark retain their original corpus. Packaging and clean-environment verification remain pending.

### Packaging — November 8, 2026

Added pyproject.toml, console entry points, packaged examples, non-overwriting initialization, and AGENT_HOME separation for installed runtime data. Wheel build/install validation is implemented; clean-machine dependency/model provisioning remains pending.

### Reranker — November 8, 2026

Added optional local Cross-Encoder reranking after hybrid candidate retrieval. API/full Agent runtime integration, explicit score type, lazy model reuse and logged RRF fallback are implemented. Default disabled; production weights and independent quality comparison remain unverified. Details: docs/reranking.md.

### PDF citations — November 8, 2026

PDF extraction now retains page spans. Both chunkers split each page separately, keeping global document offsets and sequential chunk IDs. Citation.page is derived from source metadata, not generated by the LLM. API and current CLI outputs expose physical page numbers (1-based, including blank pages); TXT/MD use null. Pipeline version 2 invalidates old caches for automatic rebuild. OCR and printed page-label recognition remain pending.

### Local model factory — November 8, 2026

Added llm/factory.py with per-runtime client reuse and optional grade/rewrite model overrides. API and full Agent CLI use the factory; all roles default to the existing local generation model. Existing injected test models remain supported. Graph node routing keeps citation validation, original questions and rewrite limits unchanged. Only Ollama is supported; other provider adapters and real multi-model quality/latency evaluation remain pending.

### Configured evaluation — November 8, 2026

Benchmark now loads shared configuration and role-based local models, accepts custom datasets and optional env files, respects Top-K/candidate/RRF settings, and compares optional reranking with its hybrid baseline. Reports include score types, pages and per-case reranking application/fallback status. Dataset/corpus mismatch is rejected before model initialization; corpus changes invalidate the run. Evaluation intentionally uses only configured source files, not API uploads. Metrics remain source-level, not factual correctness or independent generalization evidence.

### Uploaded document lifecycle — November 8, 2026

Added list/detail/delete API and CLI for uploaded documents. Published upload IDs tag runtime chunks, preventing same-name uploads from being removed together. List/detail require no model initialization. Deletion builds the replacement agent before archiving the directory, then swaps state under the shared lock. Hidden archives are excluded at restart; source files are retained (soft deletion), with no restore/purge API yet. Base configured documents remain outside upload management. Tests cover retrieval after removal, restart, cold deletion and failed replacement/rename.

### Controlled read-only tools — November 8, 2026

Added typed tool registration/execution and a knowledge_search adapter used by the retrieve node. Requests maintain their own call count (maximum three), strict search argument validation, structured failures and redacted tool traces. Cooperative deadlines discard late results but do not forcibly interrupt synchronous local inference. Only workflow-directed knowledge search is implemented; model-directed arbitrary tool selection and external search remain pending. Existing evidence grading, bounded rewrites and citation validation are preserved.

### Opt-in public search — November 8, 2026

Added Brave snippet search after exhausted local retrieval, enabled only by server configuration plus an explicit per-request public_web_query. The external request contains only that public query, not local chunks or rewritten queries. One web call is allowed in addition to the three local retrievals. Snippets are separately graded, cited by provider URL and marked web_snippet. Network failures remain workflow errors. Real-key connectivity and quality evaluation are pending; no full-page fetching or autonomous query disclosure is implemented.

### Bounded in-memory conversations — November 8, 2026

Added explicit session lifecycle and optional chat session_id. History is bounded by turns, characters, session count and idle expiry. A rewrite-model contextualizer resolves follow-up questions before normal retrieval; historical answers are not supplied as evidence. Every turn retrieves current knowledge and retains citation checks. Failed turns are not appended. Public search authorization remains per-request. Sessions are process-local and reset at restart; persistence, authentication and multi-instance storage remain pending.

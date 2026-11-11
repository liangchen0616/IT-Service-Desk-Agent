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

### Optional scanned PDF OCR — November 10, 2026

Added local Tesseract fallback for pages without extractable text, optional PDFium/Pillow dependencies, configurable language/command/page limit/process timeout, bounded rendering and temporary-file cleanup. OCR output retains physical page numbers and extraction provenance through citations. Parser settings participate in cache signatures. Real engine installation and multilingual scan quality remain unverified; pages with partial text layers do not trigger OCR.

### Evidence-aware quality reporting — November 10, 2026

Agent evaluation accepts optional expected_page and expected_quote labels, requiring all evidence constraints to match one citation. Reports distinguish refusals, unexpected answers/citations, source/page/evidence failures and execution errors, with explicit denominators. Individual invocation exceptions are recorded without exception payloads and do not stop subsequent cases. These are automatic label checks, not a factual-correctness guarantee or independent blind evaluation.

### Persistent conversation storage — November 10, 2026

Added optional SQLite session storage using short atomic transactions, with persistent expiry timestamps and the same history/count limits. Memory remains the default. Runtime selects storage from configuration; create/read/clear/delete APIs retain their existing contracts. Restart recovery and rollback are tested with real temporary databases. No automatic memory migration, user authentication, backup or multi-process whole-turn coordination is implemented.

### Archived document restoration — November 10, 2026

Added archive listing and restoration API/CLI. Restoration retains the original document ID, refuses destination conflicts, prepares the replacement index/agent before publication, and atomically renames the archive under the runtime lock. Tests cover live retrieval, cold restore/restart, failed rebuilding/rename and repeated restore. Permanent purge remains unimplemented.

### Evaluation summary endpoint and real validation — November 10, 2026

Added GET /metrics for bounded, validated summaries of the latest default benchmark report without model initialization. No case text, config or local paths are returned. Missing reports return 404; invalid newest reports return 503 without silent fallback. Report artifacts are ignored by Git. Full tests: 479 passed. Actual local qwen3:8b development-set run: 24/24 passed (18 supported answers, 6 correct refusals), mean 3536.57 ms and P95 7901.76 ms. This is not independent factual-quality validation. Real OCR, web search and reranking validation remain pending; CI is the next delivery milestone, followed by RAGAs and containers. UI remains deferred.

### CI configuration — November 10, 2026

Added GitHub Actions for push, pull requests and manual dispatch with Windows/Ubuntu Python 3.13 jobs. Checks dependency compatibility, full tests, wheel build/install and installed resources/CLI outside the source tree. Uses read-only repository permissions, offline model flags and seven-day JUnit artifacts; no model-quality claims or deployment. Local Windows: 479 tests passed, pip check passed, wheel and installed-package checks passed using existing dependencies. Remote Actions and clean Linux installation remain unverified until pushed. Next planned module: optional RAGAs evaluation; UI remains deferred.

### Optional local RAGAs judging — November 10, 2026

Added evaluation.ragas_eval with an explicit local Ollama adapter, citation-excerpt Faithfulness and custom binary AspectCritic relevance. Reads existing Agent reports; preserves input hash and context scope, skips refusals/Agent errors, reports per-metric failures and valid denominators, never overwrites output. No full retrieval-context or standard ResponseRelevancy claim. Optional dependencies are pinned after fixing a real import incompatibility. Main regression: 494 passed / 1 optional skip. Real-library focused tests: 16 passed in a temporary environment. One real qwen3:8b case scored faithfulness 0.2 and binary relevance 1 with no execution errors; full quality validation remains pending. Next planned delivery module: Docker/Compose; UI remains deferred.

### Container deployment support — November 10, 2026

Added wheel-based non-root Docker image, allowlisted build context, Compose API/Ollama services, named data/model volumes, loopback-only host API port, process health checks and non-overwriting initialization. Container-only entrypoint binds 0.0.0.0 with one worker; normal CLI remains loopback-only. AGENT_OLLAMA_ENDPOINT accepts only local/default and Compose service endpoints with existing no-proxy/no-redirect transport. Full tests: 501 passed, 1 optional RAGAs skip. Compose YAML parsed locally; Docker executable unavailable, so image build, runtime and volume persistence remain unverified. Tags are not digest-pinned; deployment guide records provisioning and acceptance gaps. UI remains deferred.

"""Optional local Cross-Encoder stage; never changes citation content."""
from math import isfinite
from threading import Lock
from time import perf_counter
import logging
from retrieval.contracts import RetrievedChunk, positive_int


class RerankerError(RuntimeError): pass


class CrossEncoderReranker:
    def __init__(self, model_name="BAAI/bge-reranker-base", batch_size=8, model=None):
        positive_int(batch_size, "batch_size")
        self.model_name, self.batch_size = model_name, batch_size
        self._model = model
        self._load_failed = False
        self._lock = Lock()

    def rerank(self, query, candidates, top_k):
        positive_int(top_k, "top_k")
        if not candidates: return []
        with self._lock:
            if self._load_failed: raise RerankerError("Model unavailable until restart")
            if self._model is None:
                try:
                    from sentence_transformers import CrossEncoder
                    self._model = CrossEncoder(self.model_name, device="cpu", max_length=512,
                        local_files_only=True, trust_remote_code=False)
                except Exception as exc:
                    self._load_failed = True
                    raise RerankerError("Cannot load local reranker") from exc
            try:
                scores = self._model.predict([(query,c.chunk.content) for c in candidates],
                    batch_size=self.batch_size, show_progress_bar=False)
                values = [float(score) for score in scores]
                if len(values) != len(candidates) or not all(isfinite(s) for s in values):
                    raise ValueError("Invalid reranker scores")
            except Exception as exc:
                raise RerankerError("Reranker prediction failed") from exc
        order = sorted(range(len(candidates)), key=lambda i: -values[i])[:top_k]
        return [RetrievedChunk(candidates[i].chunk, values[i], "cross_encoder") for i in order]


class RerankingRetriever:
    def __init__(self, retriever, reranker, candidate_k=20):
        positive_int(candidate_k, "candidate_k")
        self.retriever, self.reranker, self.candidate_k = retriever, reranker, candidate_k

    def retrieve(self, query, top_k=3, min_score=None):
        positive_int(top_k, "top_k")
        if not isinstance(query,str) or not query.strip(): raise ValueError("query must be nonempty")
        if min_score is not None: raise ValueError("Reranker scores cannot use a cosine threshold")
        candidates = self.retriever.retrieve(query, top_k=max(top_k,self.candidate_k))
        if not candidates: return []
        start = perf_counter()
        try:
            results = self.reranker.rerank(query, candidates, top_k)
        except RerankerError:
            logging.getLogger("it_agent").warning("rerank_fallback", extra={"node":"rerank",
                "elapsed_ms":(perf_counter()-start)*1000,"error_type":"RerankerError"})
            return candidates[:top_k]
        logging.getLogger("it_agent").info("rerank_completed",extra={"node":"rerank","elapsed_ms":(perf_counter()-start)*1000})
        return results

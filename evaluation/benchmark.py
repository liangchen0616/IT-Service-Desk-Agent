"""Reproducible retrieval comparison and optional real-model agent evaluation."""
import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from time import perf_counter
from agents.graph import AgentGraph
from llm.factory import ModelFactory
from retrieval.reranker import CrossEncoderReranker, RerankingRetriever
from core.logging import configure_logging
from ingestion.knowledge_base import build_knowledge_base, compute_signature
from core.config import PROJECT_ROOT, load_config
from retrieval.factory import build_hybrid_retriever
from retrieval.sparse import BM25Retriever
from retrieval.retriever import KnowledgeRetriever
from vectorstore.faiss_store import FaissVectorStore


def load_dataset(path):
    return parse_dataset(Path(path).read_bytes())


def parse_dataset(raw):
    cases = json.loads(raw)
    if not isinstance(cases, list) or not cases: raise ValueError("Dataset must be nonempty")
    seen = set()
    for case in cases:
        if not isinstance(case, dict): raise ValueError("Invalid case")
        if not isinstance(case.get("id"), str) or not case["id"] or case["id"] in seen: raise ValueError("Case IDs must be unique")
        seen.add(case["id"])
        if not isinstance(case.get("query"), str) or not case["query"].strip() or len(case["query"]) > 1000: raise ValueError("Invalid query")
        if type(case.get("answerable")) is not bool: raise ValueError("Missing answerability")
        source = case.get("expected_source")
        if case["answerable"] and (not isinstance(source, str) or not source.strip()): raise ValueError("Missing source")
        if not case["answerable"] and source is not None: raise ValueError("Negative case must not specify source")
        page=case.get("expected_page")
        quote=case.get("expected_quote")
        if page is not None and (type(page) is not int or page<=0): raise ValueError("Invalid expected_page")
        if quote is not None and (not isinstance(quote,str) or not quote.strip() or len(quote)>200): raise ValueError("Invalid expected_quote")
        if not case["answerable"] and (page is not None or quote is not None): raise ValueError("Negative case cannot require evidence")
    return cases


def evaluate_retrieval(cases, retrievers, top_k=3):
    reports = {}
    for name, retriever in retrievers.items():
        records = []
        for case in cases:
            start = perf_counter()
            hits = retriever.retrieve(case["query"], top_k=top_k)
            sources = [h.chunk.metadata["source"] for h in hits]
            rank = next((i for i, s in enumerate(sources, 1) if s == case["expected_source"]), None) if case["answerable"] else None
            records.append({**case, "sources": sources, "rank": rank,
                "elapsed_ms": (perf_counter()-start)*1000,
                "scores": [h.score for h in hits],
                "score_types": [getattr(h, "score_type", None) for h in hits],
                "pages": [h.chunk.metadata.get("page") for h in hits]})
        positive = [v for v in records if v["answerable"]]
        reports[name] = {"top_k": top_k, "positive_count": len(positive),
            "source_hit_at_k": sum(v["rank"] is not None for v in positive)/len(positive) if positive else None,
            "source_top1": sum(v["rank"] == 1 for v in positive)/len(positive) if positive else None,
            "source_mrr": sum(1/v["rank"] if v["rank"] else 0 for v in positive)/len(positive) if positive else None,
            "mean_ms": sum(v["elapsed_ms"] for v in records)/len(records), "cases": records}
    return reports


def classify_answer(case, answered, citations, error):
    if error: return "execution_error"
    if not case["answerable"]:
        return "unexpected_answer" if answered else "unexpected_citation" if citations else "correct_refusal"
    if not answered: return "false_refusal"
    matches=[c for c in citations if c["source"]==case["expected_source"]]
    if not matches: return "wrong_source"
    page=case.get("expected_page")
    if page is not None:
        matches=[c for c in matches if c["page"]==page]
        if not matches: return "wrong_page"
    quote=case.get("expected_quote")
    if quote is not None and not any(quote in (c["quote"] or "") for c in matches):
        return "missing_evidence"
    return "supported_answer"


def evaluate_agent(cases, agent, progress=None):
    if not cases: raise ValueError("Evaluation cases must not be empty")
    records=[]
    for case in cases:
        start=perf_counter()
        try:
            state=agent.invoke(case["query"])
            result=state["result"]
            citations=[{"source":c.source,"page":getattr(c,"page",None),
                        "quote":getattr(c,"quote",None)} for c in result.citations]
            answered,answer=result.answered,result.answer
            error=state.get("error")
            error_type=None
            trace,retries=state["trace"],state["retry_count"]
        except Exception as exc:
            # Preserve the rest of the evaluation without exposing exception payloads.
            citations,answered,answer=[],False,""
            error,error_type="Agent invocation failed",type(exc).__name__
            trace,retries=[],0
        outcome=classify_answer(case,answered,citations,error)
        record={**case,"answered":answered,"answer":answer,"citations":citations,
            "sources":[c["source"] for c in citations],"outcome":outcome,
            "passed":outcome in {"supported_answer","correct_refusal"},
            "error":error,"error_type":error_type,"trace":trace,"retry_count":retries,
            "elapsed_ms":(perf_counter()-start)*1000}
        records.append(record)
        if progress: progress(record)
    outcomes=("supported_answer","correct_refusal","false_refusal","unexpected_answer",
              "unexpected_citation","wrong_source","wrong_page","missing_evidence","execution_error")
    counts={name:sum(r["outcome"]==name for r in records) for name in outcomes}
    positives=sum(c["answerable"] for c in cases)
    negatives=len(cases)-positives
    latencies=sorted(r["elapsed_ms"] for r in records)
    return {"total":len(records),"passed":sum(r["passed"] for r in records),
        "positive_count":positives,"negative_count":negatives,"outcome_counts":counts,
        "false_refusal_rate":counts["false_refusal"]/positives if positives else None,
        "unexpected_answer_rate":counts["unexpected_answer"]/negatives if negatives else None,
        "execution_error_rate":counts["execution_error"]/len(records),
        "mean_ms":sum(latencies)/len(latencies),
        "p95_ms":latencies[ceil(.95*len(latencies))-1],"cases":records}


def run_benchmark(cases, config, *, include_agent=False, embedder=None,
                  model_factory=None, reranker=None, progress=None):
    """Evaluate only the explicitly configured corpus, not API upload folders."""
    missing = {c["expected_source"] for c in cases if c["answerable"]} - set(config.file_names)
    if missing:
        raise ValueError("Dataset sources absent from configured corpus: " + ", ".join(sorted(missing)))
    signature = compute_signature(config)
    kb = build_knowledge_base(config, embedder, use_cache=True)
    items = kb.retriever.store.export_items()
    store = FaissVectorStore()
    store.add(items)
    hybrid = build_hybrid_retriever(kb, candidate_k=config.candidate_k,
                                    rank_constant=config.rank_constant)
    retrievers = {"faiss": KnowledgeRetriever(kb.retriever.embedder, store),
                  "bm25": BM25Retriever([i.chunk for i in items]), "hybrid": hybrid}
    agent_retriever = hybrid
    if config.reranker_enabled:
        ranker = reranker if reranker is not None else CrossEncoderReranker(
            config.reranker_model, config.reranker_batch_size)
        agent_retriever = RerankingRetriever(hybrid, ranker, config.candidate_k)
        retrievers["hybrid_reranked"] = agent_retriever
    retrieval = evaluate_retrieval(cases, retrievers, top_k=config.top_k)
    if config.reranker_enabled:
        records = retrieval["hybrid_reranked"]["cases"]
        for record in records:
            kinds = set(record["score_types"])
            record["rerank_status"] = ("empty" if not kinds else
                "applied" if kinds == {"cross_encoder"} else "fallback")
        retrieval["hybrid_reranked"]["rerank_counts"] = {
            status: sum(r["rerank_status"] == status for r in records)
            for status in ("applied", "fallback", "empty")}
    report = {"created_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "config": config.to_report(),
        "corpus_signature": signature, "document_count": kb.document_count,
        "chunk_count": kb.chunk_count,
        "notes": "Source-level metrics, not chunk recall or factual-answer quality. Negative retrieval candidates are not hallucinations. Unthresholded top-k comparison. Timings exclude index startup but include query embedding and lazy reranker loading on first use. Corpus is configured files only, excluding API uploads.",
        "retrieval": retrieval}
    if include_agent:
        factory = model_factory if model_factory is not None else ModelFactory(config)
        agent = AgentGraph(agent_retriever, factory.get_model("generate"), config,
                           grade_model=factory.get_model("grade"),
                           rewrite_model=factory.get_model("rewrite"))
        report["agent_model"] = config.llm_model
        report["agent"] = evaluate_agent(cases, agent, progress)
    if compute_signature(config) != signature:
        raise ValueError("Corpus changed during evaluation; report was not saved")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate the configured local knowledge base")
    parser.add_argument("--agent", action="store_true", help="Also call configured local models")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("dataset.json"))
    parser.add_argument("--env-file", type=Path, help="Optional configuration file; environment still takes precedence")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or PROJECT_ROOT / "data" / "reports" / (datetime.now().strftime("benchmark-%Y%m%d-%H%M%S-%f")+'.json')
    if output.exists():
        parser.error("Output already exists; choose a new report path")
    configure_logging()
    raw = args.dataset.read_bytes()
    cases = parse_dataset(raw)
    config = load_config(args.env_file)
    report = run_benchmark(cases, config, include_agent=args.agent,
        progress=lambda record: print(record["id"], record["passed"], flush=True))
    report["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    report["dataset_path"] = str(args.dataset.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(output)
    for name, result in report["retrieval"].items():
        print(name, 'top1=', result['source_top1'], f"hit@{result['top_k']}=", result['source_hit_at_k'])
        if "rerank_counts" in result: print('Reranking:', result['rerank_counts'])
    if args.agent: print('Agent:', report['agent']['passed'], '/', report['agent']['total'])
    return 0


if __name__ == "__main__": main()

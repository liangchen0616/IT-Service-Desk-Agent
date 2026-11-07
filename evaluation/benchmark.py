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
from generation.local_llm import OllamaChat
from ingestion.knowledge_base import build_knowledge_base, compute_signature
from project_config import ProjectConfig
from retrieval.factory import build_hybrid_retriever
from retrieval.sparse import BM25Retriever
from retrieval.retriever import KnowledgeRetriever
from vectorstore.faiss_store import FaissVectorStore


def load_dataset(path):
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases: raise ValueError("Dataset must be nonempty")
    seen = set()
    for case in cases:
        if not isinstance(case, dict): raise ValueError("Invalid case")
        if not isinstance(case.get("id"), str) or not case["id"] or case["id"] in seen: raise ValueError("Case IDs must be unique")
        seen.add(case["id"])
        if not isinstance(case.get("query"), str) or not case["query"].strip(): raise ValueError("Invalid query")
        if type(case.get("answerable")) is not bool: raise ValueError("Missing answerability")
        source = case.get("expected_source")
        if case["answerable"] and (not isinstance(source, str) or not source.strip()): raise ValueError("Missing source")
        if not case["answerable"] and source is not None: raise ValueError("Negative case must not specify source")
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
                "scores": [h.score for h in hits]})
        positive = [v for v in records if v["answerable"]]
        reports[name] = {"top_k": top_k, "positive_count": len(positive),
            "source_hit_at_k": sum(v["rank"] is not None for v in positive)/len(positive) if positive else None,
            "source_top1": sum(v["rank"] == 1 for v in positive)/len(positive) if positive else None,
            "source_mrr": sum(1/v["rank"] if v["rank"] else 0 for v in positive)/len(positive) if positive else None,
            "mean_ms": sum(v["elapsed_ms"] for v in records)/len(records), "cases": records}
    return reports


def evaluate_agent(cases, agent, progress=None):
    records = []
    for case in cases:
        start = perf_counter()
        state = agent.invoke(case["query"])
        result = state["result"]
        sources = [c.source for c in result.citations]
        passed = not state.get("error") and result.answered == case["answerable"]
        if case["answerable"]: passed = passed and case["expected_source"] in sources
        else: passed = passed and not sources
        record = {**case, "answered": result.answered, "sources": sources,
            "answer": result.answer, "passed": bool(passed), "retry_count": state["retry_count"],
            "error": state.get("error"), "trace": state["trace"], "elapsed_ms": (perf_counter()-start)*1000}
        records.append(record)
        if progress: progress(record)
    latencies = sorted(v["elapsed_ms"] for v in records)
    return {"total": len(records), "passed": sum(v["passed"] for v in records),
        "p95_ms": latencies[ceil(.95*len(latencies))-1], "cases": records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="store_true", help="Also call the local model for all cases")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dataset = Path(__file__).with_name("dataset.json")
    cases = load_dataset(dataset)
    config = ProjectConfig()
    kb = build_knowledge_base(config, use_cache=True)
    items = kb.retriever.store.export_items()
    store = FaissVectorStore(); store.add(items)
    hybrid = build_hybrid_retriever(kb)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
        "config": config.to_report(), "corpus_signature": compute_signature(config),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "notes": "Source-level metrics on 2 documents; not chunk recall or factual-answer quality. Negative retrieval candidates are not hallucinations. Unthresholded top-k comparison. Timings include query embedding but exclude startup.",
        "retrieval": evaluate_retrieval(cases, {"faiss": KnowledgeRetriever(kb.retriever.embedder, store),
            "bm25": BM25Retriever([i.chunk for i in items]), "hybrid": hybrid})}
    if args.agent:
        report["agent_model"] = "qwen3:8b"
        report["agent"] = evaluate_agent(cases, AgentGraph(hybrid, OllamaChat()),
            lambda record: print(record["id"], record["passed"], flush=True))
    output = args.output or Path(__file__).parent / "reports" / (datetime.now().strftime("benchmark-%Y%m%d-%H%M%S-%f")+'.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle: json.dump(report, handle, ensure_ascii=False, indent=2)
    print(output)
    for name, result in report["retrieval"].items():
        print(name, 'top1=', result['source_top1'], 'hit@3=', result['source_hit_at_k'])
    if args.agent: print('Agent:', report['agent']['passed'], '/', report['agent']['total'])


if __name__ == "__main__": main()

"""Opt-in FAISS/BM25 question answering with existing citation checks."""
from generation.local_llm import OllamaChat
from generation.rag import RagAssistant
from ingestion.knowledge_base import build_knowledge_base
from retrieval.factory import build_hybrid_retriever


def main():
    kb = build_knowledge_base(use_cache=True)
    retriever = build_hybrid_retriever(kb)
    assistant = RagAssistant(retriever, OllamaChat(), min_score=None)
    while True:
        query = input("问题（q 退出）：").strip()
        if query.lower() in {"q", "quit", "exit"}:
            break
        if not query:
            continue
        result = assistant.answer(query)
        print(result.answer)
        for citation in result.citations:
            print(f"[{citation.source_id}] {citation.source}: {citation.quote}")


if __name__ == "__main__":
    main()

from core.config import load_config
from agents.graph import AgentGraph
from generation.local_llm import OllamaChat
from ingestion.knowledge_base import build_knowledge_base
from retrieval.factory import build_hybrid_retriever


def main():
    from core.logging import configure_logging
    configure_logging()
    from app.services.runtime import Runtime
    runtime = Runtime()
    with runtime.lock:
        runtime.ensure_ready()
    agent = runtime.agent
    while True:
        question = input("问题（q 退出）：").strip()
        if question.lower() in {"q", "quit", "exit"}: break
        if not question: continue
        state = agent.invoke(question)
        print(state["result"].answer)
        for citation in state["result"].citations:
            page = f"（第 {citation.page} 页）" if citation.page is not None else ""
            print(f"[{citation.source_id}] {citation.source}{page}: {citation.quote}")
        print("路径：", " -> ".join(t["node"] for t in state["trace"]), "重写次数：", state["retry_count"])


if __name__ == "__main__": main()

from agents.graph import AgentGraph
from generation.local_llm import OllamaChat
from ingestion.knowledge_base import build_knowledge_base
from retrieval.factory import build_hybrid_retriever


def main():
    agent = AgentGraph(build_hybrid_retriever(build_knowledge_base(use_cache=True)), OllamaChat())
    while True:
        question = input("问题（q 退出）：").strip()
        if question.lower() in {"q", "quit", "exit"}: break
        if not question: continue
        state = agent.invoke(question)
        print(state["result"].answer)
        for citation in state["result"].citations:
            print(f"[{citation.source_id}] {citation.source}: {citation.quote}")
        print("路径：", " -> ".join(t["node"] for t in state["trace"]), "重写次数：", state["retry_count"])


if __name__ == "__main__": main()

"""Bounded agent workflow with per-request state and local execution traces."""
from time import perf_counter
from langgraph.graph import StateGraph, START, END
from agents.state import AgentState
from agents.routing import after_grade, after_operation
from agents.nodes import retrieve, grade, rewrite, generate
from generation.local_llm import LocalModelError
from generation.rag import RagAnswer, INSUFFICIENT_ANSWER
from llm.client import DecisionClient


def observed(name, operation):
    def run(state):
        start = perf_counter()
        try:
            update = operation(state)
        except (LocalModelError, OSError, ValueError) as exc:
            update = {"error": str(exc), "sufficient": False}
        entry = {"node": name, "elapsed_ms": (perf_counter()-start)*1000,
                 "retry_count": update.get("retry_count", state["retry_count"]),
                 "status": "error" if update.get("error") else "ok"}
        if name == "retrieve":
            entry["sources"] = [d.chunk.metadata.get("source") for d in update.get("documents", [])]
        update["trace"] = state["trace"] + [entry]
        return update
    return run


def fallback(state):
    message = "处理请求时发生错误，请稍后重试。" if state.get("error") else INSUFFICIENT_ANSWER
    return {"result": RagAnswer(message, [], False)}


class AgentGraph:
    def __init__(self, retriever, model):
        client = DecisionClient(model)
        graph = StateGraph(AgentState)
        for name, node in [("retrieve", retrieve.make_node(retriever)),
                           ("grade", grade.make_node(client)),
                           ("rewrite", rewrite.make_node(client)),
                           ("generate", generate.make_node(model)), ("fallback", fallback)]:
            graph.add_node(name, observed(name, node))
        graph.add_edge(START, "retrieve")
        graph.add_conditional_edges("retrieve", after_operation("grade"), {"grade": "grade", "fallback": "fallback"})
        graph.add_conditional_edges("grade", after_grade, {n: n for n in ("generate", "rewrite", "fallback")})
        graph.add_conditional_edges("rewrite", after_operation("retrieve"), {"retrieve": "retrieve", "fallback": "fallback"})
        graph.add_conditional_edges("generate", after_operation("done"), {"done": END, "fallback": "fallback"})
        graph.add_edge("fallback", END)
        self.graph = graph.compile()

    def invoke(self, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 1000:
            raise ValueError("Question must contain 1–1000 characters")
        return self.graph.invoke({"question": question.strip(), "query": question.strip(),
            "documents": [], "retry_count": 0, "sufficient": False, "error": None,
            "trace": []}, config={"recursion_limit": 20})

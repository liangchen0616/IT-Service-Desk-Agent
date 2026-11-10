"""Bounded agent workflow with per-request state and local execution traces."""
from time import perf_counter
import logging
from core.logging import configure_logging
from core.config import ProjectConfig
from langgraph.graph import StateGraph, START, END
from agents.state import AgentState
from agents.routing import after_grade, after_operation
from agents.nodes import retrieve, grade, rewrite, generate, web_search
from generation.local_llm import LocalModelError
from generation.rag import RagAnswer, INSUFFICIENT_ANSWER
from llm.client import DecisionClient


def observed(name, operation):
    def run(state):
        start = perf_counter()
        try:
            update = operation(state)
        except (LocalModelError, OSError, ValueError) as exc:
            update = {"error": str(exc), "sufficient": False,
                      "error_code": "model_error" if isinstance(exc, LocalModelError) else "agent_error"}
            logging.getLogger("it_agent").warning("node_failed", extra={"node": name, "error_type": type(exc).__name__})
        entry = {"node": name, "elapsed_ms": (perf_counter()-start)*1000,
                 "retry_count": update.get("retry_count", state["retry_count"]),
                 "status": "error" if update.get("error") else "ok"}
        if name in {"retrieve", "web_search"} and "tool_result" in update:
            entry["tool"] = update["tool_result"]
        if name in {"retrieve", "web_search"}:
            entry["sources"] = [d.chunk.metadata.get("source") for d in update.get("documents", [])]
        logging.getLogger("it_agent").info("node_completed", extra={
            "node": name, "elapsed_ms": entry["elapsed_ms"], "retry_count": entry["retry_count"]})
        update["trace"] = state["trace"] + [entry]
        return update
    return run


def fallback(state):
    message = "处理请求时发生错误，请稍后重试。" if state.get("error") else INSUFFICIENT_ANSWER
    return {"result": RagAnswer(message, [], False)}


class AgentGraph:
    def __init__(self, retriever, model, config=None, *, grade_model=None, rewrite_model=None, web_tool=None):
        config = config if config is not None else ProjectConfig()
        self.web_search_enabled = config.web_search_enabled
        grading_client = DecisionClient(model if grade_model is None else grade_model, config.max_context_chars)
        rewriting_client = DecisionClient(model if rewrite_model is None else rewrite_model, config.max_context_chars)
        graph = StateGraph(AgentState)
        for name, node in [("retrieve", retrieve.make_node(retriever, config.top_k, config.tool_timeout)),
                           ("grade", grade.make_node(grading_client)),
                           ("rewrite", rewrite.make_node(rewriting_client)),
                           ("generate", generate.make_node(model, config.top_k, config.max_context_chars)), ("fallback", fallback)]:
            graph.add_node(name, observed(name, node))
        if config.web_search_enabled:
            graph.add_node("web_search", observed("web_search", web_search.make_node(config,web_tool)))
            graph.add_node("web_grade", observed("web_grade", grade.make_node(grading_client, public_web=True)))
            graph.add_conditional_edges("web_search", after_operation("web_grade"),
                {"web_grade":"web_grade","fallback":"fallback"})
            graph.add_conditional_edges("web_grade", lambda state: "generate" if state["sufficient"] and not state.get("error") else "fallback",
                {"generate":"generate","fallback":"fallback"})
        def route_grade(state):
            route=after_grade(state)
            if route=="fallback" and not state.get("error") and config.web_search_enabled and state.get("public_web_query"):
                return "web_search"
            return route
        graph.add_edge(START, "retrieve")
        graph.add_conditional_edges("retrieve", after_operation("grade"), {"grade": "grade", "fallback": "fallback"})
        graph.add_conditional_edges("grade", route_grade, {n:n for n in
            (("generate","rewrite","fallback","web_search") if config.web_search_enabled else ("generate","rewrite","fallback"))})
        graph.add_conditional_edges("rewrite", after_operation("retrieve"), {"retrieve": "retrieve", "fallback": "fallback"})
        graph.add_conditional_edges("generate", after_operation("done"), {"done": END, "fallback": "fallback"})
        graph.add_edge("fallback", END)
        self.graph = graph.compile()

    def invoke(self, question, *, public_web_query=None):
        if public_web_query is not None:
            from tools.web_search import WebArguments
            public_web_query=WebArguments(query=public_web_query).query
            if not self.web_search_enabled: raise ValueError("Web search is disabled")
        if not isinstance(question, str) or not question.strip() or len(question) > 1000:
            raise ValueError("Question must contain 1–1000 characters")
        return self.graph.invoke({"question": question.strip(), "query": question.strip(),
            "documents": [], "retry_count": 0, "sufficient": False, "error": None, "error_code": None,
            "public_web_query": public_web_query, "web_call_count": 0, "tool_call_count": 0, "tool_result": {}, "trace": []}, config={"recursion_limit": 20})

from tools.executor import ToolExecutor
from tools.knowledge_search import KnowledgeSearchTool


def make_node(retriever, top_k=3, timeout=180):
    executor = ToolExecutor([KnowledgeSearchTool(retriever, top_k)], timeout=timeout, max_calls=3)
    def retrieve(state):
        count = state.get("tool_call_count", 0) + 1
        result = executor.run("knowledge_search", {"query": state["query"], "top_k": top_k},
                              call_number=count)
        update = {"documents": result.data if result.status == "ok" else [],
                  "sufficient": False, "tool_call_count": count,
                  "tool_result": result.summary()}
        if result.status != "ok":
            update.update(error="Knowledge search failed: " + result.error_code,
                          error_code="model_error" if result.error_code == "model_error" else "agent_error")
        return update
    return retrieve

def make_node(client):
    def rewrite(state):
        return {"query": client.rewrite(state["question"], state["query"]),
                "retry_count": state["retry_count"] + 1, "documents": [], "sufficient": False}
    return rewrite

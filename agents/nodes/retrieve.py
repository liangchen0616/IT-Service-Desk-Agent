def make_node(retriever):
    def retrieve(state):
        return {"documents": retriever.retrieve(state["query"], top_k=3), "sufficient": False}
    return retrieve

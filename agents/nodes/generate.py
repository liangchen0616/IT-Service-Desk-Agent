from generation.rag import RagAssistant


class EvidenceSnapshot:
    """Ensure generation uses exactly the retrieved evidence that was graded."""
    def __init__(self, documents):
        self.documents = documents

    def retrieve(self, query, top_k=3, min_score=None):
        return self.documents[:top_k]


def make_node(model):
    def generate(state):
        assistant = RagAssistant(EvidenceSnapshot(state["documents"]), model, min_score=None)
        return {"result": assistant.answer(state["question"])}
    return generate

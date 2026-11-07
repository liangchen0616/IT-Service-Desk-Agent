import pytest
from agents.graph import AgentGraph
from generation.local_llm import LocalModelError
from ingestion.chunker import Chunk
from retrieval.contracts import RetrievedChunk


DOC = RetrievedChunk(Chunk("Check VPN", {"source": "guide.txt"}, 0, 0, 9), 1, "rrf")


class Retriever:
    def __init__(self): self.queries = []
    def retrieve(self, query, top_k=3):
        self.queries.append(query)
        return [DOC]


class Model:
    def __init__(self, grades): self.grades = iter(grades); self.calls = []
    def generate(self, messages, schema):
        self.calls.append(messages)
        if "sufficient" in schema["properties"]: return {"sufficient": next(self.grades)}
        if "query" in schema["properties"]: return {"query": "VPN rewritten"}
        return {"answerable": True, "answer": "Check VPN", "evidence": [{"source_id": 1, "quote": "Check VPN"}]}


def test_direct_answer_and_no_second_retrieval():
    r = Retriever()
    state = AgentGraph(r, Model([True])).invoke("VPN")
    assert state["result"].answered
    assert state["result"].citations[0].source == "guide.txt"
    assert r.queries == ["VPN"]
    assert [x["node"] for x in state["trace"]] == ["retrieve", "grade", "generate"]


def test_rewrite_preserves_original_question():
    r, m = Retriever(), Model([False, True])
    state = AgentGraph(r, m).invoke("original VPN")
    assert r.queries == ["original VPN", "VPN rewritten"]
    assert state["question"] == "original VPN"
    assert 'original VPN' in m.calls[-1][-1]["content"]
    assert state["retry_count"] == 1 and state["result"].answered


def test_limit_and_no_state_leak():
    r = Retriever()
    agent = AgentGraph(r, Model([False] * 6))
    for _ in range(2):
        state = agent.invoke("VPN")
        assert state["retry_count"] == 2
        assert not state["result"].answered
        assert state["result"].citations == []
        assert len(state["trace"]) == 9
    assert len(r.queries) == 6


def test_model_error_falls_back():
    class Broken:
        def generate(self, messages, schema): raise LocalModelError("unavailable")
    state = AgentGraph(Retriever(), Broken()).invoke("VPN")
    assert not state["result"].answered
    assert state["error"] == "unavailable"
    assert state["trace"][-1]["node"] == "fallback"


def test_invalid_grade_is_not_truthy():
    class Broken:
        def generate(self, messages, schema): return {"sufficient": "false"}
    assert not AgentGraph(Retriever(), Broken()).invoke("VPN")["result"].answered


@pytest.mark.parametrize("query", ["", " ", None, "x" * 1001])
def test_invalid_input(query):
    with pytest.raises(ValueError): AgentGraph(Retriever(), Model([])).invoke(query)

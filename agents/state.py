from typing import TypedDict
from generation.rag import RagAnswer


class AgentState(TypedDict):
    question: str
    query: str
    documents: list
    retry_count: int
    sufficient: bool
    error: str | None
    result: RagAnswer
    trace: list[dict]

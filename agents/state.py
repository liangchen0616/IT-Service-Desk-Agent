from typing import TypedDict
from generation.rag import RagAnswer


class AgentState(TypedDict):
    public_web_query: str | None
    web_call_count: int
    question: str
    query: str
    documents: list
    tool_call_count: int
    tool_result: dict
    retry_count: int
    sufficient: bool
    error: str | None
    error_code: str | None
    result: RagAnswer
    trace: list[dict]

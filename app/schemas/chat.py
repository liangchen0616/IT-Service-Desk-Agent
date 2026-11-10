from pydantic import BaseModel, Field, field_validator
from generation.rag import Citation


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    public_web_query: str | None = Field(default=None, min_length=1, max_length=600)
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("public_web_query")
    @classmethod
    def public_query(cls, value):
        if value is None: return None
        from tools.web_search import WebArguments
        return WebArguments(query=value).query

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError("问题不能为空")
        return value.strip()


class ChatResponse(BaseModel):
    session_id: str | None = None
    resolved_question: str | None = None
    answer: str
    answered: bool
    citations: list[Citation]
    retry_count: int
    trace: list[dict]

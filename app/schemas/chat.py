from pydantic import BaseModel, Field, field_validator
from generation.rag import Citation


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError("问题不能为空")
        return value.strip()


class ChatResponse(BaseModel):
    answer: str
    answered: bool
    citations: list[Citation]
    retry_count: int
    trace: list[dict]

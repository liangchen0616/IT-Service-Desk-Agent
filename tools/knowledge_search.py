"""Read-only adapter preserving retrieved chunks and citation metadata."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(gt=0)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError("query must not be blank")
        return value.strip()


class KnowledgeSearchTool:
    name = "knowledge_search"
    description = "Search the local knowledge base for evidence; does not modify documents."
    read_only = True
    input_model = SearchArguments

    def __init__(self, retriever, max_top_k):
        self.retriever, self.max_top_k = retriever, max_top_k

    def execute(self, arguments, context):
        if arguments.top_k > self.max_top_k:
            raise ValueError("Requested top_k exceeds configured limit")
        context.remaining_seconds()
        return self.retriever.retrieve(arguments.query, top_k=arguments.top_k)

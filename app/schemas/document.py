from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int

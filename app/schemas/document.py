from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    file_type: str
    size_bytes: int


class DocumentList(BaseModel):
    documents: list[DocumentInfo]
    total: int


class DocumentDetail(DocumentInfo):
    text_preview: str
    preview_truncated: bool
    page_count: int | None = None


class DocumentDeleted(BaseModel):
    document_id: str
    filename: str
    deleted: bool


class ArchiveInfo(DocumentInfo):
    archive_id: str


class ArchiveList(BaseModel):
    archives: list[ArchiveInfo]
    total: int

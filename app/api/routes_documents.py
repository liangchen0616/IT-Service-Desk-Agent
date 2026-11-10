from fastapi import APIRouter, Depends, UploadFile, HTTPException
from app.api.dependencies import get_runtime
from app.schemas.document import DocumentResponse, DocumentList, DocumentDetail, DocumentDeleted
from app.services.document_service import (
    ingest, validate_name, MAX_UPLOAD_BYTES, list_documents, get_document, delete_document,
)

router = APIRouter()


@router.post("/documents", response_model=DocumentResponse, status_code=201)
def upload(file: UploadFile, runtime=Depends(get_runtime)):
    try:
        validate_name(file.filename)
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES: raise HTTPException(413, "文件不能超过 5 MiB")
        return ingest(runtime, file.filename, data)
    finally:
        file.file.close()


@router.get("/documents", response_model=DocumentList)
def list_uploaded(runtime=Depends(get_runtime)):
    return list_documents(runtime)


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str, runtime=Depends(get_runtime)):
    return get_document(runtime, document_id)


@router.delete("/documents/{document_id}", response_model=DocumentDeleted)
def remove_document(document_id: str, runtime=Depends(get_runtime)):
    return delete_document(runtime, document_id)

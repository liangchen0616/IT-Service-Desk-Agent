from fastapi import APIRouter, Depends, UploadFile, HTTPException
from app.api.dependencies import get_runtime
from app.schemas.document import DocumentResponse
from app.services.document_service import ingest, validate_name, MAX_UPLOAD_BYTES

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

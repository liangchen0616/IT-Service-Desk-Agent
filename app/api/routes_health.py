from fastapi import APIRouter, Depends
from app.api.dependencies import get_runtime

router = APIRouter()


@router.get("/health")
def health(runtime=Depends(get_runtime)):
    return {"status": "ok", "knowledge_ready": runtime.agent is not None}

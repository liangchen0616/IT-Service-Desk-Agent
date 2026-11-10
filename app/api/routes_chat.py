from fastapi import APIRouter, Depends
from app.api.dependencies import get_runtime
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import answer

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, runtime=Depends(get_runtime)):
    return answer(runtime, request.question, public_web_query=request.public_web_query, session_id=request.session_id)

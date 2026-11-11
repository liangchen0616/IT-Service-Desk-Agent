from fastapi import APIRouter, Depends
from app.api.dependencies import get_runtime

router=APIRouter()


@router.get("/sessions")
def list_sessions(runtime=Depends(get_runtime)):
    with runtime.lock:
        sessions = runtime.sessions.list_sessions()
        return {"sessions": sessions, "total": len(sessions)}


@router.post("/sessions",status_code=201)
def create(runtime=Depends(get_runtime)):
    with runtime.lock: return {"session_id":runtime.sessions.create()}


@router.get("/sessions/{session_id}")
def history(session_id:str,runtime=Depends(get_runtime)):
    with runtime.lock:
        turns=runtime.sessions.history(session_id)
        return {"session_id":session_id,"turns":turns,"turn_count":len(turns)}


@router.delete("/sessions/{session_id}/history")
def clear(session_id:str,runtime=Depends(get_runtime)):
    with runtime.lock:
        runtime.sessions.clear(session_id)
        return {"session_id":session_id,"cleared":True}


@router.delete("/sessions/{session_id}")
def delete(session_id:str,runtime=Depends(get_runtime)):
    with runtime.lock:
        runtime.sessions.delete(session_id)
        return {"session_id":session_id,"deleted":True}

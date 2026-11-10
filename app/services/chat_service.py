from app.schemas.chat import ChatResponse
from llm.conversation import resolve_question
from time import perf_counter
from core.exceptions import LocalModelError, AgentExecutionError


def answer(runtime, question, *, public_web_query=None, session_id=None):
    if public_web_query is not None and not runtime.config.web_search_enabled:
        from fastapi import HTTPException
        raise HTTPException(400, "外部搜索未启用")
    with runtime.lock:
        history=runtime.sessions.history(session_id) if session_id is not None else []
        runtime.ensure_ready()
        resolved_question=question
        context_trace=[]
        if history:
            start=perf_counter()
            model=runtime.model if runtime._model_injected else runtime.model_factory.get_model("rewrite")
            resolved_question=resolve_question(model,question,history)
            context_trace=[{"node":"contextualize","elapsed_ms":(perf_counter()-start)*1000,
                            "retry_count":0,"status":"ok"}]
        state = runtime.agent.invoke(resolved_question, public_web_query=public_web_query) if public_web_query is not None else runtime.agent.invoke(resolved_question)
        if state.get("error"):
            if state.get("error_code") == "model_error": raise LocalModelError("Model execution failed")
            raise AgentExecutionError("Agent execution failed")
        result = state["result"]
        response=ChatResponse(session_id=session_id, resolved_question=resolved_question,
            answer=result.answer, answered=result.answered,
            citations=result.citations, retry_count=state["retry_count"], trace=context_trace+state["trace"])
        if session_id is not None:
            runtime.sessions.append(session_id,question,resolved_question,result.answer,result.answered)
        return response

from app.schemas.chat import ChatResponse
from generation.local_llm import LocalModelError


def answer(runtime, question):
    with runtime.lock:
        runtime.ensure_ready()
        state = runtime.agent.invoke(question)
        if state.get("error"): raise LocalModelError("Agent execution failed")
        result = state["result"]
        return ChatResponse(answer=result.answer, answered=result.answered,
            citations=result.citations, retry_count=state["retry_count"], trace=state["trace"])

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api import routes_chat, routes_documents, routes_health
from app.services.runtime import Runtime
from app.services.document_service import InvalidDocument
from generation.local_llm import LocalModelError


def create_app(runtime=None):
    app = FastAPI(title="Enterprise Knowledge Agent", version="2.1")
    app.state.runtime = runtime if runtime is not None else Runtime()
    for router in (routes_health.router, routes_chat.router, routes_documents.router):
        app.include_router(router)

    @app.exception_handler(InvalidDocument)
    async def invalid_document(request: Request, exc):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(LocalModelError)
    async def model_error(request: Request, exc):
        logging.getLogger(__name__).warning("Local model unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "模型服务暂不可用，请稍后重试"})

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc):
        logging.getLogger(__name__).exception("Request failed", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "请求处理失败，请检查服务日志"})
    return app


app = create_app()

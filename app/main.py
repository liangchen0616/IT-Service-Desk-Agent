from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from app.api import routes_chat, routes_documents, routes_health, routes_sessions, routes_metrics
from app.services.runtime import Runtime
from app.middleware import RequestLoggingMiddleware, error_response
from core.exceptions import OcrError, SessionNotFound, SessionCapacity, DocumentNotFound, InvalidDocument, LocalModelError, AgentExecutionError
from core.logging import configure_logging


def create_app(runtime=None):
    app = FastAPI(title="Enterprise Knowledge Agent", version="2.1")
    app.state.runtime = runtime if runtime is not None else Runtime()
    logger = configure_logging()
    app.add_middleware(RequestLoggingMiddleware)
    for router in (routes_health.router, routes_chat.router, routes_documents.router, routes_sessions.router, routes_metrics.router):
        app.include_router(router)

    @app.exception_handler(OcrError)
    async def ocr_error(request: Request, exc):
        return error_response(503,"ocr_unavailable",str(exc))

    @app.exception_handler(SessionNotFound)
    async def session_missing(request: Request, exc):
        return error_response(404,"session_not_found",str(exc))

    @app.exception_handler(SessionCapacity)
    async def session_capacity(request: Request, exc):
        return error_response(409,"session_capacity",str(exc))

    @app.exception_handler(DocumentNotFound)
    async def document_not_found(request: Request, exc):
        return error_response(404, "not_found", str(exc))

    @app.exception_handler(InvalidDocument)
    async def invalid_document(request: Request, exc):
        return error_response(400, "invalid_document", str(exc))

    @app.exception_handler(LocalModelError)
    async def model_error(request: Request, exc):
        logger.warning("model_failed", extra={"error_type": type(exc).__name__})
        return error_response(503, "model_unavailable", "模型调用失败，请检查本地模型服务")

    @app.exception_handler(AgentExecutionError)
    async def agent_error(request: Request, exc):
        logger.error("agent_failed", extra={"error_type": type(exc).__name__})
        return error_response(500, "agent_execution_failed", "工作流执行失败，请提供请求编号以便排查")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        return error_response(422, "invalid_request", "请求格式或参数不正确")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        codes = {404: "not_found", 405: "method_not_allowed", 413: "upload_too_large"}
        return error_response(exc.status_code, codes.get(exc.status_code, "http_error"), exc.detail)
    return app


app = create_app()

from time import perf_counter
from uuid import uuid4
from starlette.responses import JSONResponse
from core.logging import request_id, configure_logging


def error_response(status, code, detail):
    return JSONResponse(status_code=status, content={"detail": detail, "code": code,
                                                    "request_id": request_id.get()})


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app
        self.logger = configure_logging()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        identifier = uuid4().hex
        token = request_id.set(identifier)
        start = perf_counter()
        status = 500
        started = False

        async def send_response(message):
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                message = dict(message)
                message["headers"] = [(k,v) for k,v in message.get("headers", []) if k.lower() != b"x-request-id"] + [(b"x-request-id", identifier.encode())]
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_response)
            except Exception as exc:
                self.logger.error("request_failed", extra={"error_type": type(exc).__name__})
                if started: raise
                await error_response(500, "internal_error", "请求处理失败，请提供请求编号以便排查")(scope, receive, send_response)
        finally:
            route = scope.get("route")
            self.logger.info("request_completed", extra={"method": scope.get("method"),
                "route": getattr(route, "path", "unmatched"), "status_code": status,
                "elapsed_ms": round((perf_counter()-start)*1000, 3)})
            request_id.reset(token)

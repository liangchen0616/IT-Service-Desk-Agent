import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock

request_id = ContextVar("request_id", default="-")
_lock = Lock()


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"time": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                "event": record.getMessage(), "request_id": request_id.get()}
        for key in ("method", "route", "status_code", "elapsed_ms", "node", "retry_count", "error_type", "tool_name", "tool_status", "tool_error_code", "tool_call_number"):
            if hasattr(record, key): data[key] = getattr(record, key)
        return json.dumps(data, ensure_ascii=False)


def configure_logging():
    logger = logging.getLogger("it_agent")
    with _lock:
        if not any(getattr(h, "_agent_handler", False) for h in logger.handlers):
            handler = logging.StreamHandler()
            handler._agent_handler = True
            handler.setFormatter(JsonFormatter())
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger

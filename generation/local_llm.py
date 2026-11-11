import json
import os
from http.client import HTTPException
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


from core.exceptions import LocalModelError


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaChat:
    """Call an already installed local Ollama model; never download a model."""

    ENDPOINT = "http://127.0.0.1:11434/api/chat"

    def __init__(self, model_name: str = "qwen3:8b", timeout: float = 180):
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must not be empty.")
        if model_name.strip().endswith(("-cloud", ":cloud")):
            raise ValueError("Choose a local model, such as qwen3:8b.")
        if type(timeout) not in (int, float) or not isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a positive finite number.")
        endpoint = os.environ.get("AGENT_OLLAMA_ENDPOINT")
        if endpoint is not None:
            allowed = {"http://127.0.0.1:11434/api/chat", "http://ollama:11434/api/chat"}
            if endpoint not in allowed:
                raise ValueError("AGENT_OLLAMA_ENDPOINT must be the local or Compose Ollama endpoint")
            self.ENDPOINT = endpoint
        self.model_name = model_name.strip()
        self.timeout = timeout
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def generate(self, messages: list[dict], schema: dict) -> dict:
        """Request one complete JSON answer using the supplied output schema."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "format": schema,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1024},
        }
        request = Request(
            self.ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
        except HTTPError as error:
            if error.code == 404:
                message = f"请确认模型已下载：ollama pull {self.model_name}"
            else:
                message = "请检查 Ollama 窗口或日志中的具体错误。"
            raise LocalModelError(f"Ollama 返回 HTTP {error.code}。{message}") from error
        except (TimeoutError, URLError, OSError, HTTPException) as error:
            raise LocalModelError(
                "无法完成本地模型请求。请确认 Ollama 正在运行；"
                "若生成超时，可增加 timeout 或尝试较小的模型。"
            ) from error
        if len(raw) > 2_000_000:
            raise LocalModelError("本地模型响应过大，请缩短问题或资料。")
        try:
            envelope = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise LocalModelError("Ollama 返回的外层响应不是有效 JSON。") from error
        if not isinstance(envelope, dict):
            raise LocalModelError("Ollama 返回的响应结构不正确。")
        if envelope.get("error"):
            raise LocalModelError(f"Ollama 请求失败：{envelope['error']}")
        if envelope.get("done") is not True or envelope.get("done_reason") == "length":
            raise LocalModelError("模型输出尚未完成或达到长度限制，请缩短问题后重试。")
        message = envelope.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LocalModelError("模型没有返回可用的回答内容。")
        try:
            result = json.loads(content)
        except ValueError as error:
            raise LocalModelError("模型回答不是有效 JSON，本次回答未被采用。") from error
        if not isinstance(result, dict):
            raise LocalModelError("模型回答必须是一个 JSON 对象。")
        return result

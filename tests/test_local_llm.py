import io
import json
import threading
from contextlib import contextmanager
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from generation.local_llm import LocalModelError, OllamaChat


MESSAGES = [{"role": "user", "content": "公司 VPN 连接不上，应该怎么办？"}]
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}


@contextmanager
def local_server(body, status=200, headers=None):
    """Serve a predictable local response and record the actual HTTP request."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            calls.append({
                "path": self.path,
                "content_type": self.headers["Content-Type"],
                "raw": raw,
                "payload": json.loads(raw),
            })
            self.send_response(status)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/chat", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def envelope(content=None, **changes):
    result = {
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": content if content is not None else '{"answer": "检查网络。"}'},
    }
    result.update(changes)
    return result


def client_with_response(raw):
    client = OllamaChat()
    client._opener = SimpleNamespace(open=lambda request, timeout: io.BytesIO(raw))
    return client


def test_local_http_request_sends_chinese_schema_and_decodes_complete_answer(monkeypatch):
    expected = {"answer": "先检查网络，再检查 VPN 账号。"}
    response = json.dumps(envelope(json.dumps(expected, ensure_ascii=False)), ensure_ascii=False).encode("utf-8")
    with local_server(response) as (endpoint, calls):
        monkeypatch.setattr(OllamaChat, "ENDPOINT", endpoint)
        # A configured external proxy must not intercept this local request.
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("no_proxy", "")
        client = OllamaChat(model_name="qwen3:8b", timeout=5)
        assert client.generate(MESSAGES, SCHEMA) == expected

    assert len(calls) == 1
    request = calls[0]
    assert request["path"] == "/api/chat"
    assert request["content_type"] == "application/json"
    assert "公司 VPN".encode("utf-8") in request["raw"]
    assert request["payload"]["model"] == "qwen3:8b"
    assert request["payload"]["messages"] == MESSAGES
    assert request["payload"]["format"] == SCHEMA
    assert request["payload"]["stream"] is False
    assert request["payload"]["think"] is False


def test_missing_model_error_explains_how_to_download_selected_model(monkeypatch):
    with local_server(b'{"error":"model not found"}', status=404) as (endpoint, calls):
        monkeypatch.setattr(OllamaChat, "ENDPOINT", endpoint)
        with pytest.raises(LocalModelError, match="ollama pull qwen3:8b"):
            OllamaChat(timeout=5).generate(MESSAGES, SCHEMA)
    assert len(calls) == 1


def test_redirect_is_rejected_without_following_location(monkeypatch):
    with local_server(b"{}", status=307, headers={"Location": "http://127.0.0.1:1/outside"}) as (endpoint, calls):
        monkeypatch.setattr(OllamaChat, "ENDPOINT", endpoint)
        with pytest.raises(LocalModelError, match="HTTP 307"):
            OllamaChat(timeout=5).generate(MESSAGES, SCHEMA)
    assert len(calls) == 1


@pytest.mark.parametrize("error", [
    TimeoutError("slow model"),
    URLError("connection refused"),
    IncompleteRead(b"partial response", 100),
])
def test_transport_failures_become_actionable_local_model_errors(error):
    client = OllamaChat(timeout=7)
    def fail(request, timeout):
        assert timeout == 7
        raise error
    client._opener = SimpleNamespace(open=fail)
    with pytest.raises(LocalModelError, match="Ollama 正在运行") as captured:
        client.generate(MESSAGES, SCHEMA)
    assert captured.value.__cause__ is error


@pytest.mark.parametrize("raw", [b"{bad", b"\xff", b"[]"])
def test_invalid_outer_response_is_not_accepted(raw):
    with pytest.raises(LocalModelError):
        client_with_response(raw).generate(MESSAGES, SCHEMA)


@pytest.mark.parametrize("payload", [
    envelope(done=False),
    envelope(done=1),
    envelope(done_reason="length"),
    {"message": {"content": '{"answer":"部分回答"}'}},
])
def test_incomplete_or_truncated_model_answer_is_not_exposed(payload):
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(LocalModelError, match="尚未完成或达到长度限制"):
        client_with_response(raw).generate(MESSAGES, SCHEMA)


@pytest.mark.parametrize("payload", [
    envelope(message=None),
    envelope(message=[]),
    envelope(message={}),
    envelope(message={"content": "   "}),
    envelope(message={"content": 123}),
])
def test_missing_or_blank_message_is_not_exposed(payload):
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(LocalModelError, match="没有返回可用的回答内容"):
        client_with_response(raw).generate(MESSAGES, SCHEMA)


@pytest.mark.parametrize("content", ["普通回答", "```json\n{}\n```", "[]", "null"])
def test_invalid_structured_model_output_is_rejected(content):
    raw = json.dumps(envelope(content)).encode("utf-8")
    with pytest.raises(LocalModelError):
        client_with_response(raw).generate(MESSAGES, SCHEMA)


def test_service_error_inside_response_is_reported():
    raw = json.dumps({"error": "not enough memory"}).encode("utf-8")
    with pytest.raises(LocalModelError, match="not enough memory"):
        client_with_response(raw).generate(MESSAGES, SCHEMA)


def test_oversized_response_is_rejected():
    with pytest.raises(LocalModelError, match="响应过大"):
        client_with_response(b"x" * 2_000_001).generate(MESSAGES, SCHEMA)


@pytest.mark.parametrize("settings", [
    {"model_name": ""},
    {"model_name": "qwen3:8b-cloud"},
    {"timeout": 0},
    {"timeout": -1},
    {"timeout": float("inf")},
    {"timeout": float("nan")},
    {"timeout": True},
])
def test_unusable_or_nonlocal_model_settings_are_rejected(settings):
    with pytest.raises(ValueError):
        OllamaChat(**settings)

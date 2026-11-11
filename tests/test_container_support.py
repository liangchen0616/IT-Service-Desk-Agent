import pytest
from generation.local_llm import OllamaChat
from scripts import container_entrypoint


def test_compose_endpoint_uses_existing_transport(monkeypatch):
    monkeypatch.setenv("AGENT_OLLAMA_ENDPOINT", "http://ollama:11434/api/chat")
    assert OllamaChat().ENDPOINT == "http://ollama:11434/api/chat"


@pytest.mark.parametrize("endpoint", ["https://example.com/api/chat", "http://ollama:11434/api/chat?token=x", "http://user@ollama:11434/api/chat", ""])
def test_reject_unexpected_model_endpoint(monkeypatch, endpoint):
    monkeypatch.setenv("AGENT_OLLAMA_ENDPOINT", endpoint)
    with pytest.raises(ValueError): OllamaChat()


def test_normal_endpoint_is_unchanged(monkeypatch):
    monkeypatch.delenv("AGENT_OLLAMA_ENDPOINT", raising=False)
    assert OllamaChat().ENDPOINT == "http://127.0.0.1:11434/api/chat"


def test_container_start_initializes_without_overwriting(tmp_path,monkeypatch):
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))
    calls=[]
    monkeypatch.setattr("uvicorn.run", lambda *a,**kw:calls.append((a,kw)))
    container_entrypoint.main()
    file=tmp_path/"data/documents/vpn_guide_zh.txt"
    assert file.is_file()
    file.write_text("user text",encoding="utf-8")
    container_entrypoint.main()
    assert file.read_text(encoding="utf-8")=="user text"
    assert calls[0][1]==dict(host="0.0.0.0",port=8000,workers=1)

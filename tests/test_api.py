from dataclasses import replace
from fastapi.testclient import TestClient
import pytest
from app.main import create_app
from app.services.runtime import Runtime
from app.services.document_service import MAX_UPLOAD_BYTES
from embeddings.embedder import EmbeddedChunk
from project_config import ProjectConfig


class Embedder:
    def embed_chunks(self, chunks): return [EmbeddedChunk(c, [1., 0.]) for c in chunks]
    def embed_query(self, query): return [1., 0.]


class Model:
    def generate(self, messages, schema):
        if 'sufficient' in schema['properties']: return {'sufficient': False}
        return {'query': 'new query'}


@pytest.fixture
def runtime(tmp_path):
    docs = tmp_path / 'base'
    docs.mkdir()
    (docs / 'base.txt').write_text('VPN troubleshooting', encoding='utf-8')
    config = ProjectConfig(documents_dir=docs, file_names=('base.txt',), index_path=tmp_path/'base.json')
    return Runtime(config, tmp_path/'uploads', Embedder(), Model())


def test_health_is_lazy_and_chat_fallback(runtime):
    with TestClient(create_app(runtime)) as client:
        assert client.get('/health').json() == {'status': 'ok', 'knowledge_ready': False}
        result = client.post('/chat', json={'question': 'Unknown'} )
        assert result.status_code == 200
        assert result.json()['retry_count'] == 2
        assert result.json()['citations'] == []
        assert client.get('/health').json()['knowledge_ready']


@pytest.mark.parametrize('question', ['', ' ', 'x'*1001, 123])
def test_invalid_question(runtime, question):
    assert TestClient(create_app(runtime)).post('/chat', json={'question': question}).status_code == 422


def test_upload_and_restart(runtime):
    client = TestClient(create_app(runtime))
    result = client.post('/documents', files={'file': ('new.md', b'printer offline guide')})
    assert result.status_code == 201, result.text
    assert result.json()['chunk_count'] == 1
    assert len(runtime.items) == 2
    restored = Runtime(runtime.config, runtime.uploads, Embedder(), Model())
    with restored.lock: restored.ensure_ready()
    assert len(restored.items) == 2
    hits = restored.agent.invoke('printer')['documents']
    assert any(h.chunk.metadata['source'] == 'new.md' for h in hits)


@pytest.mark.parametrize('name,data', [('bad.exe',b'abc'), ('../bad.txt',b'abc'), ('empty.txt',b' '), ('bad.pdf', b'broken'), ('bad.txt', b'\xff')])
def test_invalid_upload_leaves_no_committed_document(runtime, name, data):
    result = TestClient(create_app(runtime)).post('/documents', files={'file': (name,data)})
    assert result.status_code == 400
    assert not runtime.uploads.exists() or list(runtime.uploads.iterdir()) == []


def test_large_upload(runtime):
    result = TestClient(create_app(runtime)).post('/documents', files={'file': ('big.txt',b'x'*(MAX_UPLOAD_BYTES+1))})
    assert result.status_code == 413


def test_failed_embedding_keeps_old_agent(runtime):
    with runtime.lock: runtime.ensure_ready()
    original = runtime.agent
    def fail(chunks): raise RuntimeError('embedding unavailable')
    runtime.embedder.embed_chunks = fail
    client = TestClient(create_app(runtime), raise_server_exceptions=False)
    assert client.post('/documents', files={'file': ('new.txt',b'new text')}).status_code == 500
    assert runtime.agent is original
    assert list(runtime.uploads.iterdir()) == []

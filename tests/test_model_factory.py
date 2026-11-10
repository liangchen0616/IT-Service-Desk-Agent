from dataclasses import replace
import json

import pytest
from fastapi.testclient import TestClient
from core.config import ProjectConfig, load_config
from core.exceptions import LocalModelError
from llm.factory import ModelFactory
from app.main import create_app
from app.services.runtime import Runtime
from embeddings.embedder import EmbeddedChunk


def test_default_roles_share_client_without_requests():
    factory = ModelFactory(ProjectConfig())
    model = factory.get_model('generate')
    assert factory.get_model('grade') is model
    assert factory.get_model('rewrite') is model
    assert model.model_name == 'qwen3:8b'
    with pytest.raises(ValueError): factory.get_model('unknown')


def test_role_settings_override_and_blank_inherits(tmp_path):
    env = tmp_path/'.env'
    env.write_text('AGENT_LLM_GRADE_MODEL=small:1b\nAGENT_LLM_REWRITE_MODEL=other:2b\n')
    config = load_config(env, {'AGENT_LLM_REWRITE_MODEL': ''})
    factory = ModelFactory(config)
    assert factory.get_model('grade').model_name == 'small:1b'
    assert factory.get_model('rewrite') is factory.get_model('generate')
    assert config.to_report()['llm_rewrite_model'] == config.llm_model


@pytest.mark.parametrize('field', ['llm_grade_model', 'llm_rewrite_model'])
@pytest.mark.parametrize('value', ['', '  ', 42, 'model-cloud', 'model:cloud'])
def test_invalid_role_models(field, value):
    with pytest.raises(ValueError): ProjectConfig(**{field: value})


class Embedder:
    def embed_chunks(self, chunks): return [EmbeddedChunk(c, [1., 0.]) for c in chunks]
    def embed_query(self, query): return [1., 0.]


def test_runtime_routes_roles_reuses_clients_and_preserves_citations(tmp_path, monkeypatch):
    calls, constructed = [], []
    class Model:
        def __init__(self, name, timeout):
            self.name = name
            self.grade_count = 0
            constructed.append(name)
        def generate(self, messages, schema):
            payload = json.loads(messages[1]['content'])
            calls.append((self.name, payload))
            if self.name == 'judge:1b':
                assert 'sufficient' in schema['properties']
                self.grade_count += 1
                return {'sufficient': self.grade_count > 1}
            if self.name == 'rewrite:1b':
                assert 'query' in schema['properties']
                return {'query': 'VPN restart'}
            assert 'answerable' in schema['properties']
            return {'answerable': True, 'answer': 'Restart VPN.',
                    'evidence': [{'source_id': 1, 'quote': 'Restart VPN.'}]}
    monkeypatch.setattr('llm.factory.OllamaChat', Model)
    (tmp_path/'guide.txt').write_text('Restart VPN.')
    config = ProjectConfig(documents_dir=tmp_path, file_names=('guide.txt',),
                           index_path=tmp_path/'index.json', llm_grade_model='judge:1b',
                           llm_rewrite_model='rewrite:1b')
    runtime = Runtime(config, tmp_path/'uploads', Embedder())
    assert constructed == []
    with TestClient(create_app(runtime)) as client:
        response = client.post('/chat', json={'question': 'Original question'})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['answered'] and result['retry_count'] == 1
        assert result['citations'][0]['quote'] == 'Restart VPN.'
        assert [name for name, _ in calls] == ['judge:1b', 'rewrite:1b', 'judge:1b', 'qwen3:8b']
        assert calls[-1][1]['question'] == 'Original question'
        assert client.post('/documents', files={'file': ('new.txt', b'Additional knowledge.')}).status_code == 201
        assert len(constructed) == 3


def test_configured_decision_failure_remains_503(tmp_path, monkeypatch):
    class Model:
        def __init__(self, name, timeout): self.name = name
        def generate(self, messages, schema):
            assert self.name == 'missing:1b'
            raise LocalModelError('not installed')
    monkeypatch.setattr('llm.factory.OllamaChat', Model)
    (tmp_path/'guide.txt').write_text('Restart VPN.')
    config = ProjectConfig(documents_dir=tmp_path, file_names=('guide.txt',),
                           index_path=tmp_path/'index.json', llm_grade_model='missing:1b')
    with TestClient(create_app(Runtime(config, tmp_path/'uploads', Embedder()))) as client:
        assert client.post('/chat', json={'question': 'VPN'}).status_code == 503

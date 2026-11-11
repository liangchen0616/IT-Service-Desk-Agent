import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.runtime import Runtime
from core.config import ProjectConfig
from embeddings.embedder import EmbeddedChunk
from scripts import documents
from scripts.api_client import ApiClient


class Embedder:
    def embed_chunks(self, chunks): return [EmbeddedChunk(c,[1.,0.]) for c in chunks]
    def embed_query(self, query): return [1.,0.]


class Model:
    def generate(self, messages, schema):
        payload = json.loads(messages[1]['content'])
        if 'sufficient' in schema['properties']:
            return {'sufficient': any('unique_secret' in text for text in payload['sources'])}
        if 'query' in schema['properties']: return {'query': 'unique_secret'}
        source = next(s for s in payload['sources'] if 'unique_secret' in s['content'])
        return {'answerable': True, 'answer': 'unique_secret',
                'evidence': [{'source_id': source['source_id'], 'quote': 'unique_secret'}]}


@pytest.fixture
def runtime(tmp_path):
    docs = tmp_path/'base'
    docs.mkdir()
    (docs/'same.txt').write_text('Base document remains.')
    config = ProjectConfig(documents_dir=docs, file_names=('same.txt',), index_path=tmp_path/'base.json')
    return Runtime(config, tmp_path/'uploads', Embedder(), Model())


def upload(client, text='unique_secret'):
    response = client.post('/documents', files={'file': ('same.txt', text.encode())})
    assert response.status_code == 201, response.text
    return response.json()['document_id']


def test_delete_only_selected_upload_then_restart(runtime):
    with TestClient(create_app(runtime)) as client:
        first = upload(client)
        second = upload(client, 'Another document remains.')
        assert client.post('/chat',json={'question':'unique_secret'}).json()['answered']
        listing = client.get('/documents').json()
        assert listing['total'] == 2
        assert {d['document_id'] for d in listing['documents']} == {first, second}
        detail = client.get('/documents/'+first).json()
        assert detail['text_preview'] == 'unique_secret'
        assert detail['size_bytes'] == len(b'unique_secret')
        response = client.delete('/documents/'+first)
        assert response.status_code == 200 and response.json()['deleted']
        result = client.post('/chat',json={'question':'unique_secret'}).json()
        assert not result['answered'] and result['citations'] == []
        assert client.get('/documents/'+first).status_code == 404
        assert client.delete('/documents/'+first).status_code == 404
        assert client.get('/documents').json()['total'] == 1
        assert client.get('/documents/'+second).status_code == 200
    restored = Runtime(runtime.config, runtime.uploads, Embedder(), Model())
    restored.ensure_ready()
    assert len(restored.items) == 2
    assert {i.chunk.metadata.get('document_id') for i in restored.items} == {None, second}
    assert not restored.agent.invoke('unique_secret')['result'].answered
    assert (runtime.config.documents_dir/'same.txt').read_text() == 'Base document remains.'
    archive = list(runtime.uploads.glob('.deleted-*'))
    assert len(archive) == 1 and (archive[0]/'documents'/'same.txt').read_text() == 'unique_secret'


def test_list_detail_and_cold_delete_do_not_load_models(runtime, monkeypatch):
    with TestClient(create_app(runtime)) as client: identifier = upload(client, 'x'*2100)
    cold = Runtime(runtime.config, runtime.uploads)
    def forbidden(*args, **kwargs): pytest.fail('Should not initialize models')
    monkeypatch.setattr(cold, 'ensure_ready', forbidden)
    monkeypatch.setattr(cold, 'make_agent', forbidden)
    with TestClient(create_app(cold)) as client:
        assert client.get('/documents').json()['total'] == 1
        detail = client.get('/documents/'+identifier).json()
        assert len(detail['text_preview']) == 2000 and detail['preview_truncated']
        assert client.delete('/documents/'+identifier).status_code == 200
        assert client.get('/health').json()['knowledge_ready'] is False
        assert client.get('/documents').json()['total'] == 0


@pytest.mark.parametrize('failure', ['rebuild', 'rename'])
def test_failed_delete_keeps_published_document_and_old_agent(runtime, monkeypatch, failure):
    with TestClient(create_app(runtime), raise_server_exceptions=False) as client:
        identifier = upload(client)
        old_agent, old_items = runtime.agent, runtime.items
        def fail(*args, **kwargs): raise OSError('simulated failure')
        if failure == 'rebuild': monkeypatch.setattr(runtime, 'make_agent', fail)
        else: monkeypatch.setattr(Path, 'rename', fail)
        response = client.delete('/documents/'+identifier)
        assert response.status_code == 500
        assert runtime.agent is old_agent and runtime.items is old_items
        assert client.get('/documents/'+identifier).status_code == 200
        assert (runtime.uploads/identifier).is_dir()
        assert not list(runtime.uploads.glob('.deleted-*'))


@pytest.mark.parametrize('identifier', ['not-an-id', 'a'*32, '.deleted-hidden', 'ABCDEF'*5+'AB'])
def test_unknown_and_invalid_ids_are_404(runtime, identifier):
    with TestClient(create_app(runtime)) as client:
        for method in [client.get, client.delete]:
            response = method('/documents/'+identifier)
            assert response.status_code == 404
            assert response.json()['code'] == 'not_found'
    assert runtime.agent is None


def test_hidden_pending_and_deleted_folders_are_not_listed(runtime):
    runtime.uploads.mkdir()
    (runtime.uploads/'.pending-test').mkdir()
    (runtime.uploads/'.deleted-test').mkdir()
    with TestClient(create_app(runtime)) as client:
        assert client.get('/documents').json() == {'documents': [], 'total': 0}


def test_document_cli_routes_requests_and_rejects_path_injection(monkeypatch, capsys):
    requests = []
    def handle(request):
        requests.append((request.method, request.url.path))
        return httpx.Response(200,json={'ok': True})
    monkeypatch.setattr(documents, 'ApiClient', lambda url: ApiClient(url,transport=httpx.MockTransport(handle)))
    identifier = 'a'*32
    assert documents.main(['list']) == 0
    assert documents.main(['show',identifier]) == 0
    assert documents.main(['delete',identifier]) == 0
    assert requests == [('GET','/documents'),('GET','/documents/'+identifier),('DELETE','/documents/'+identifier)]
    with pytest.raises(SystemExit): documents.main(['delete','../base'])
    assert len(requests) == 3


def test_archive_restore_roundtrip_and_restart(runtime):
    with TestClient(create_app(runtime)) as client:
        identifier=upload(client)
        client.delete('/documents/'+identifier)
        entries=client.get('/document-archives').json()
        assert entries['total']==1
        archive=entries['archives'][0]
        assert archive['document_id']==identifier and archive['filename']=='same.txt'
        result=client.post('/document-archives/'+archive['archive_id']+'/restore')
        assert result.status_code==200,result.text
        assert result.json()['document_id']==identifier
        assert client.get('/document-archives').json()['total']==0
        assert client.post('/chat',json={'question':'unique_secret'}).json()['answered']
        assert client.post('/document-archives/'+archive['archive_id']+'/restore').status_code==404
        client.delete('/documents/'+identifier)
    fresh=Runtime(runtime.config,runtime.uploads,Embedder(),Model())
    with TestClient(create_app(fresh)) as client:
        archives=client.get('/document-archives').json()['archives']
        assert fresh.agent is None
        assert client.post('/document-archives/'+archives[0]['archive_id']+'/restore').status_code==200
    restarted=Runtime(runtime.config,runtime.uploads,Embedder(),Model())
    restarted.ensure_ready()
    assert sum(i.chunk.metadata.get('document_id')==identifier for i in restarted.items)==1
    assert restarted.agent.invoke('unique_secret')['result'].answered


@pytest.mark.parametrize('failure',['rebuild','rename'])
def test_restore_failure_keeps_archive_and_active_knowledge(runtime,monkeypatch,failure):
    with TestClient(create_app(runtime),raise_server_exceptions=False) as client:
        identifier=upload(client)
        client.delete('/documents/'+identifier)
        archive=client.get('/document-archives').json()['archives'][0]['archive_id']
        agent,items=runtime.agent,runtime.items
        def fail(*args,**kwargs):raise OSError('simulated failure')
        if failure=='rebuild':monkeypatch.setattr(runtime,'make_agent',fail)
        else:monkeypatch.setattr(Path,'rename',fail)
        assert client.post('/document-archives/'+archive+'/restore').status_code==500
        assert runtime.agent is agent and runtime.items is items
        assert client.get('/document-archives').json()['total']==1
        assert client.get('/documents').json()['total']==0


def test_restore_does_not_overwrite_existing_id(runtime):
    with TestClient(create_app(runtime)) as client:
        identifier=upload(client)
        client.delete('/documents/'+identifier)
        archive=client.get('/document-archives').json()['archives'][0]['archive_id']
        destination=runtime.uploads/identifier
        destination.mkdir()
        (destination/'marker.txt').write_text('do not overwrite')
        assert client.post('/document-archives/'+archive+'/restore').status_code==400
        assert (destination/'marker.txt').read_text()=='do not overwrite'
        assert client.get('/document-archives').json()['total']==1


def test_archive_cli_and_unknown_id(runtime,monkeypatch):
    requests=[]
    def handle(request):
        requests.append((request.method,request.url.path))
        return httpx.Response(200,json={'ok':True})
    monkeypatch.setattr(documents,'ApiClient',lambda url:ApiClient(url,transport=httpx.MockTransport(handle)))
    archive='a'*32+'-'+'b'*32
    assert documents.main(['archives'])==0
    assert documents.main(['restore',archive])==0
    assert requests==[('GET','/document-archives'),('POST','/document-archives/'+archive+'/restore')]
    with pytest.raises(SystemExit):documents.main(['restore','../outside'])
    with TestClient(create_app(runtime)) as client:
        assert client.post('/document-archives/'+archive+'/restore').status_code==404
        assert runtime.agent is None

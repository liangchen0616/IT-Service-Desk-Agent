import json
import httpx
import pytest
from scripts.api_client import ApiClient, ClientError
from scripts import demo_query


def test_upload_then_query_same_backend(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.services.runtime import Runtime
    from core.config import ProjectConfig
    from embeddings.embedder import EmbeddedChunk
    class Embedder:
        def embed_chunks(self,chunks): return [EmbeddedChunk(c,[1,0]) for c in chunks]
        def embed_query(self,q): return [1,0]
    class Model:
        def generate(self,messages,schema):
            if 'sufficient' in schema['properties']: return {'sufficient':True}
            sources=json.loads(messages[-1]['content'])['sources']
            target=next(s for s in sources if 'unique_upload' in s['content'])
            return {'answerable':True,'answer':'unique_upload','evidence':[{'source_id':target['source_id'],'quote':'unique_upload'}]}
    base=tmp_path/'base'; base.mkdir(); (base/'base.txt').write_text('base guide')
    runtime=Runtime(ProjectConfig(documents_dir=base,file_names=('base.txt',),index_path=tmp_path/'index.json'),tmp_path/'uploads',Embedder(),Model())
    server=TestClient(create_app(runtime))
    def bridge(req):
        response=server.request(req.method,req.url.path,headers=dict(req.headers),content=req.read())
        return httpx.Response(response.status_code,headers=response.headers,content=response.content)
    uploaded=tmp_path/'new.txt'; uploaded.write_text('unique_upload')
    with ApiClient(transport=httpx.MockTransport(bridge)) as client:
        assert client.upload(uploaded)['filename']=='new.txt'
        result=client.ask('unique_upload')
        assert result['answered'] and result['citations'][0]['source']=='new.txt'


def test_error_includes_request_id():
    with ApiClient(transport=httpx.MockTransport(lambda req:httpx.Response(503,json={'detail':'模型不可用'},headers={'x-request-id':'abc'}))) as client:
        with pytest.raises(ClientError,match='abc'): client.ask('test')


def test_timeout_does_not_retry(tmp_path):
    calls=[]
    def timeout(req):
        calls.append(req)
        raise httpx.ReadTimeout('timeout')
    p=tmp_path/'file.txt'; p.write_text('text')
    with ApiClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(ClientError,match='重复上传'): client.upload(p)
    assert len(calls)==1


@pytest.mark.parametrize('url',['https://example.com','http://example.com','http://user:pass@localhost','http://localhost/chat'])
def test_remote_or_invalid_urls_rejected(url):
    with pytest.raises(ValueError): ApiClient(url)


def test_single_question_json(monkeypatch,capsys):
    class Fake:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def ask(self,q): return {'answer':q,'answered':False,'citations':[],'trace':[],'retry_count':2}
    monkeypatch.setattr(demo_query,'ApiClient',lambda *args:Fake())
    assert demo_query.main(['test','--json'])==0
    assert json.loads(capsys.readouterr().out)['answer']=='test'

import json
from time import perf_counter
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.runtime import Runtime
from agents.graph import AgentGraph
from core.config import ProjectConfig, load_config
from embeddings.embedder import EmbeddedChunk
from tools.web_search import BraveSearchTool, WebArguments
from tools.executor import ToolContext, ToolExecutor


def payload():
    return {'web':{'results':[{'url':'https://example.org/guide','title':'VPN guide',
        'description':'<b>Restart</b> the VPN client &amp; retry.'},
        {'url':'javascript:bad','description':'bad'},
        {'url':'https://example.org/guide','description':'duplicate'}]}}


def tool_with(handler):
    return BraveSearchTool('test-key',transport=httpx.MockTransport(handler))


def test_brave_request_normalizes_snippets_without_fetching_pages():
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.url.host=='api.search.brave.com'
        assert request.url.params['q']=='public VPN help'
        assert request.headers['x-subscription-token']=='test-key'
        return httpx.Response(200,json=payload())
    result=tool_with(handler).execute(WebArguments(query='public VPN help'),ToolContext(perf_counter()+10))
    assert len(calls)==1 and len(result)==1
    assert result[0].text=='Restart the VPN client & retry.'
    assert result[0].chunk.metadata['source_type']=='web_snippet'
    assert result[0].source=='https://example.org/guide'


@pytest.mark.parametrize('status',[301,401,429,500])
def test_http_failures_are_not_empty_search_success(status):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(status,headers={'location':'https://elsewhere.invalid'},json={'error':'secret'})
    result=ToolExecutor([tool_with(handler)]).run('web_search',{'query':'q'},call_number=1)
    assert result.status=='error' and result.data is None and len(calls)==1
    assert 'secret' not in json.dumps(result.summary())


@pytest.mark.parametrize('value',[[],{'web':{}},{'web':{'results':'bad'}}])
def test_malformed_response_is_failure(value):
    result=ToolExecutor([tool_with(lambda req:httpx.Response(200,json=value))]).run('web_search',{'query':'q'},call_number=1)
    assert result.error_code=='execution_failed'


def test_network_timeout_and_size_limit():
    def timeout(request): raise httpx.ReadTimeout('secret')
    result=ToolExecutor([tool_with(timeout)]).run('web_search',{'query':'q'},call_number=1)
    assert result.error_code=='timeout'
    result=ToolExecutor([tool_with(lambda req:httpx.Response(200,content=b'x'*1_000_001))]).run('web_search',{'query':'q'},call_number=1)
    assert result.error_code=='execution_failed'


class Retriever:
    def retrieve(self,*args,**kwargs): return []


class Model:
    def __init__(self, accept_web=True): self.accept_web=accept_web
    def generate(self,messages,schema):
        if 'query' in schema['properties']: return {'query':'PRIVATE rewritten query'}
        if 'sufficient' in schema['properties']:
            assert '公开网页搜索摘要' in messages[0]['content']
            return {'sufficient':self.accept_web}
        return {'answerable':True,'answer':'Restart the VPN client.',
                'evidence':[{'source_id':1,'quote':'Restart the VPN client'}]}


def enabled(): return ProjectConfig(web_search_enabled=True,web_search_api_key='test-key')


def test_graph_uses_only_explicit_public_query_and_preserves_url():
    queries=[]
    def handler(request):
        queries.append(request.url.params['q'])
        return httpx.Response(200,json=payload())
    graph=AgentGraph(Retriever(),Model(),enabled(),web_tool=tool_with(handler))
    result=graph.invoke('Original question',public_web_query='public VPN help')
    assert queries==['public VPN help']
    assert result['result'].answered
    citation=result['result'].citations[0]
    assert citation.url=='https://example.org/guide' and citation.source_type=='web_snippet'
    assert result['tool_call_count']==3 and result['web_call_count']==1
    assert [t['node'] for t in result['trace']][-3:]==['web_search','web_grade','generate']
    assert result['trace'][-3]['tool']['name']=='web_search'


def test_enabled_without_explicit_query_never_searches():
    def fail(request): pytest.fail('Unrequested external search')
    result=AgentGraph(Retriever(),Model(),enabled(),web_tool=tool_with(fail)).invoke('private question')
    assert not result['result'].answered and result['web_call_count']==0


@pytest.mark.parametrize('body,accept', [({},True),(payload(),False)])
def test_empty_or_insufficient_web_evidence_falls_back(body,accept):
    graph=AgentGraph(Retriever(),Model(accept),enabled(),web_tool=tool_with(lambda req:httpx.Response(200,json=body)))
    state=graph.invoke('company policy',public_web_query='public search')
    assert not state['result'].answered and not state['result'].citations
    assert state['error'] is None and state['web_call_count']==1


def test_configuration_secret_is_excluded_and_missing_key_rejected(tmp_path):
    with pytest.raises(ValueError): ProjectConfig(web_search_enabled=True)
    config=load_config(tmp_path/'missing',{'AGENT_WEB_SEARCH_ENABLED':'true','AGENT_WEB_SEARCH_API_KEY':'secret-credential'})
    assert 'secret-credential' not in repr(config)
    assert 'secret-credential' not in json.dumps(config.to_report())


@pytest.mark.parametrize('query',[' ', 'x'*601, 'word '*76])
def test_public_query_limits(query):
    with pytest.raises(ValueError): WebArguments(query=query)


def test_api_rejects_opt_in_when_disabled_before_loading_models():
    runtime=Runtime(ProjectConfig())
    with TestClient(create_app(runtime)) as client:
        response=client.post('/chat',json={'question':'VPN','public_web_query':'public VPN'})
        assert response.status_code==400 and runtime.agent is None


def test_api_serializes_web_citation(tmp_path, monkeypatch):
    from tools import web_search
    original=web_search.httpx.Client
    # Replace the tool construction only; the API test client's transport stays intact.
    import agents.nodes.web_search as node
    monkeypatch.setattr(node,'BraveSearchTool',lambda key,count:tool_with(lambda req:httpx.Response(200,json=payload())))
    (tmp_path/'base.txt').write_text('Unrelated local material.')
    class Embedder:
        def embed_chunks(self,chunks): return [EmbeddedChunk(c,[1.,0.]) for c in chunks]
        def embed_query(self,q): return [1.,0.]
    class ApiModel(Model):
        def generate(self,messages,schema):
            if 'sufficient' in schema['properties'] and '公开网页搜索摘要' not in messages[0]['content']:
                return {'sufficient':False}
            return super().generate(messages,schema)
    config=ProjectConfig(documents_dir=tmp_path,file_names=('base.txt',),index_path=tmp_path/'index.json',
                         web_search_enabled=True,web_search_api_key='test-key')
    with TestClient(create_app(Runtime(config,tmp_path/'uploads',Embedder(),ApiModel()))) as client:
        response=client.post('/chat',json={'question':'VPN help','public_web_query':'public VPN help'})
        assert response.status_code==200,response.text
        citation=response.json()['citations'][0]
        assert citation['url']=='https://example.org/guide' and citation['source_type']=='web_snippet'

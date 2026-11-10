import json
import pytest
from fastapi.testclient import TestClient
from core.config import ProjectConfig
from core.exceptions import SessionNotFound,SessionCapacity,LocalModelError
from memory.sessions import SessionStore
from llm.conversation import resolve_question
from app.main import create_app
from app.services.runtime import Runtime
from embeddings.embedder import EmbeddedChunk


def test_store_isolation_bounds_and_copy():
    store=SessionStore(max_turns=2,max_chars=100)
    a,b=store.create(),store.create()
    for i in range(3): store.append(a,str(i),'resolved','answer',True)
    assert [t['question'] for t in store.history(a)]==['1','2']
    history=store.history(a);history[0]['answer']='mutated'
    assert store.history(a)[0]['answer']=='answer' and store.history(b)==[]
    store.append(a,'long'*100,'resolved','answer',True)
    assert sum(len(t[k]) for t in store.history(a) for k in ['question','resolved_question','answer'])<=100


def test_expiry_capacity_clear_and_delete():
    now=[0]
    store=SessionStore(max_sessions=1,ttl=10,clock=lambda:now[0])
    identifier=store.create()
    with pytest.raises(SessionCapacity):store.create()
    store.append(identifier,'q','q','a',True)
    store.clear(identifier); assert store.history(identifier)==[]
    now[0]=11
    with pytest.raises(SessionNotFound):store.history(identifier)
    fresh=store.create();store.delete(fresh)
    with pytest.raises(SessionNotFound):store.history(fresh)


@pytest.mark.parametrize('response',[{},None,{'question':''},{'question':'x'*1001},{'question':42}])
def test_contextualizer_validates_output(response):
    class Model:
        def generate(self,*args):return response
    with pytest.raises(LocalModelError):resolve_question(Model(),'follow up',[{'question':'VPN'}])


class Embedder:
    def __init__(self):self.queries=[]
    def embed_chunks(self,chunks):return [EmbeddedChunk(c,[1.,0.]) for c in chunks]
    def embed_query(self,query):self.queries.append(query);return [1.,0.]


class Model:
    def __init__(self):self.histories=[];self.fail_context=False
    def generate(self,messages,schema):
        payload=json.loads(messages[1]['content'])
        if 'question' in schema['properties']:
            self.histories.append(payload['history'])
            if self.fail_context: return {'bad':'output'}
            return {'question':'VPN second step'}
        if 'sufficient' in schema['properties']:
            assert 'history' not in payload
            return {'sufficient':any('Restart VPN.' in text for text in payload['sources'])}
        if 'query' in schema['properties']:return {'query':'VPN'}
        assert 'history' not in payload
        source=next(s for s in payload['sources'] if 'Restart VPN.' in s['content'])
        assert all('HISTORY ONLY' not in s['content'] for s in payload['sources'])
        return {'answerable':True,'answer':'HISTORY ONLY: restart it.',
                'evidence':[{'source_id':source['source_id'],'quote':'Restart VPN.'}]}


@pytest.fixture
def runtime(tmp_path):
    (tmp_path/'base.txt').write_text('Unrelated base information.')
    config=ProjectConfig(documents_dir=tmp_path,file_names=('base.txt',),index_path=tmp_path/'index.json')
    return Runtime(config,tmp_path/'uploads',Embedder(),Model())


def test_api_followup_isolation_clear_and_no_old_answer_as_evidence(runtime):
    with TestClient(create_app(runtime)) as client:
        a=client.post('/sessions').json()['session_id']
        b=client.post('/sessions').json()['session_id']
        assert runtime.agent is None
        doc=client.post('/documents',files={'file':('vpn.txt',b'Restart VPN.')}).json()['document_id']
        first=client.post('/chat',json={'question':'VPN help','session_id':a})
        assert first.status_code==200 and first.json()['answered']
        second=client.post('/chat',json={'question':'second step?','session_id':a})
        assert second.status_code==200,second.text
        data=second.json()
        assert data['resolved_question']=='VPN second step'
        assert data['trace'][0]['node']=='contextualize'
        assert 'VPN second step' in runtime.embedder.queries
        assert runtime.model.histories[0][0]['question']=='VPN help'
        assert client.get('/sessions/'+b).json()['turns']==[]
        before=len(runtime.model.histories)
        client.post('/chat',json={'question':'different topic','session_id':b})
        assert len(runtime.model.histories)==before
        client.delete('/documents/'+doc)
        after_delete=client.post('/chat',json={'question':'repeat that','session_id':a}).json()
        assert not after_delete['answered'] and after_delete['citations']==[]
        assert client.delete('/sessions/'+a+'/history').json()['cleared']
        assert client.get('/sessions/'+a).json()['turn_count']==0
        assert client.delete('/sessions/'+a).json()['deleted']
        assert client.post('/chat',json={'question':'q','session_id':a}).status_code==404


def test_context_failure_does_not_append_history(runtime):
    with TestClient(create_app(runtime)) as client:
        identifier=client.post('/sessions').json()['session_id']
        client.post('/chat',json={'question':'VPN','session_id':identifier})
        before=client.get('/sessions/'+identifier).json()['turns']
        runtime.model.fail_context=True
        result=client.post('/chat',json={'question':'and then?','session_id':identifier})
        assert result.status_code==503
        assert client.get('/sessions/'+identifier).json()['turns']==before


def test_missing_session_and_invalid_id_do_not_load_models(runtime):
    with TestClient(create_app(runtime)) as client:
        assert client.post('/chat',json={'question':'q','session_id':'a'*32}).status_code==404
        assert client.post('/chat',json={'question':'q','session_id':'bad'}).status_code==422
        assert runtime.agent is None
        runtime.sessions=SessionStore(max_sessions=1)
        client.post('/sessions')
        assert client.post('/sessions').status_code==409


def test_new_runtime_has_no_history(runtime):
    identifier=runtime.sessions.create()
    fresh=Runtime(runtime.config,runtime.uploads,Embedder(),Model())
    with pytest.raises(SessionNotFound):fresh.sessions.history(identifier)

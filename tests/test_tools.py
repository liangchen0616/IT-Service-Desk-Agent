import json
from types import SimpleNamespace

import pytest
from agents.graph import AgentGraph
from core.config import ProjectConfig, load_config
from core.exceptions import LocalModelError
from ingestion.chunker import Chunk
from retrieval.contracts import RetrievedChunk
from tools.executor import ToolExecutor
from tools.knowledge_search import KnowledgeSearchTool


DOC = RetrievedChunk(Chunk('Check VPN', {'source':'guide.pdf','page':3,'document_id':'a'*32},0,0,9),1.,'rrf')


class Retriever:
    def __init__(self): self.calls=[]
    def retrieve(self, query, top_k=3):
        self.calls.append((query,top_k))
        return [DOC]


def test_schema_and_preserved_evidence():
    retriever=Retriever()
    runner=ToolExecutor([KnowledgeSearchTool(retriever,3)])
    schema=runner.descriptions()[0]
    assert schema['name']=='knowledge_search'
    assert schema['parameters']['additionalProperties'] is False
    result=runner.run('knowledge_search',{'query':' VPN ','top_k':2},call_number=1)
    assert result.status=='ok' and result.data[0] is DOC
    assert retriever.calls==[('VPN',2)]
    assert 'query' not in result.summary() and 'data' not in result.summary()


@pytest.mark.parametrize('arguments', [None,[],{}, {'query':' ','top_k':1},
    {'query':'VPN','top_k':True},{'query':'VPN','top_k':'3'},
    {'query':'VPN','top_k':0},{'query':'VPN','top_k':1,'shell':'run'},
    {'query':'x'*1001,'top_k':1}])
def test_invalid_arguments_never_execute(arguments):
    retriever=Retriever()
    result=ToolExecutor([KnowledgeSearchTool(retriever,3)]).run('knowledge_search',arguments,call_number=1)
    assert result.error_code=='invalid_arguments' and not retriever.calls


def test_unknown_name_and_call_limit_never_execute():
    retriever=Retriever()
    runner=ToolExecutor([KnowledgeSearchTool(retriever,3)])
    assert runner.run('unknown',{},call_number=1).error_code=='unknown_tool'
    for count in [0,4,True]:
        assert runner.run('knowledge_search',{},call_number=count).error_code=='call_limit'
    assert not retriever.calls


def test_reject_duplicate_and_write_tool_registration():
    tool=KnowledgeSearchTool(Retriever(),3)
    with pytest.raises(ValueError): ToolExecutor([tool,tool])
    tool.read_only=False
    with pytest.raises(ValueError): ToolExecutor([tool])


def test_late_results_are_discarded_without_background_work():
    now=[0.]
    class Slow(Retriever):
        def retrieve(self,query,top_k=3):
            now[0]=2.
            return [DOC]
    runner=ToolExecutor([KnowledgeSearchTool(Slow(),3)],timeout=1,clock=lambda:now[0])
    result=runner.run('knowledge_search',{'query':'VPN','top_k':1},call_number=1)
    assert result.error_code=='timeout' and result.data is None
    assert result.elapsed_ms==2000


@pytest.mark.parametrize('error,code', [(OSError('secret'),'execution_failed'),
    (RuntimeError('secret'),'execution_failed'),(TimeoutError('secret'),'timeout'),
    (LocalModelError('secret'),'model_error')])
def test_tool_errors_are_structured_and_do_not_leak_messages(error,code):
    class Broken:
        def retrieve(self,*args,**kwargs): raise error
    result=ToolExecutor([KnowledgeSearchTool(Broken(),3)]).run('knowledge_search',{'query':'VPN','top_k':1},call_number=1)
    assert result.error_code==code and result.data is None
    assert 'secret' not in json.dumps(result.summary())


class Model:
    def __init__(self, sufficient): self.sufficient=sufficient
    def generate(self,messages,schema):
        if 'sufficient' in schema['properties']: return {'sufficient':self.sufficient}
        if 'query' in schema['properties']: return {'query':'VPN rewritten'}
        return {'answerable':True,'answer':'Check VPN','evidence':[{'source_id':1,'quote':'Check VPN'}]}


def test_graph_tools_keep_citations_and_fresh_call_budget():
    retriever=Retriever()
    agent=AgentGraph(retriever,Model(True))
    state=agent.invoke('VPN')
    assert state['result'].citations[0].page==3
    assert state['trace'][0]['tool']['name']=='knowledge_search'
    assert state['trace'][0]['tool']['status']=='ok'
    assert state['tool_call_count']==1
    refusal=AgentGraph(retriever,Model(False))
    for _ in range(2):
        state=refusal.invoke('VPN')
        assert state['tool_call_count']==3 and state['retry_count']==2
        assert [t['tool']['call_number'] for t in state['trace'] if t['node']=='retrieve']==[1,2,3]


def test_tool_failure_routes_to_fallback_without_model_call():
    class Broken:
        def retrieve(self,*args,**kwargs): raise RuntimeError('secret')
    state=AgentGraph(Broken(),None).invoke('VPN')
    assert [t['node'] for t in state['trace']]==['retrieve','fallback']
    assert state['trace'][0]['tool']['error_code']=='execution_failed'
    assert state['error_code']=='agent_error'
    assert not state['result'].answered and state['documents']==[]


def test_tool_timeout_configuration(tmp_path):
    assert load_config(tmp_path/'missing',{'AGENT_TOOL_TIMEOUT':'12.5'}).tool_timeout==12.5
    for value in [0,-1,True,float('inf'),float('nan')]:
        with pytest.raises(ValueError): ProjectConfig(tool_timeout=value)

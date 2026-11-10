import os
import json
import pytest
from core.config import ProjectConfig, PROJECT_ROOT, load_config
from project_config import ProjectConfig as LegacyConfig
from agents.graph import AgentGraph
from ingestion.chunker import Chunk
from retrieval.contracts import RetrievedChunk


def test_legacy_import_and_defaults():
    assert LegacyConfig is ProjectConfig
    assert ProjectConfig().documents_dir == PROJECT_ROOT / "data" / "documents"


def test_env_precedence_and_no_mutation(tmp_path):
    path = tmp_path / ".env"
    path.write_text("AGENT_TOP_K=4\nAGENT_LLM_TIMEOUT=30\nAGENT_DOCUMENTS_DIR=data/custom")
    before = dict(os.environ)
    config = load_config(path, {"AGENT_TOP_K": "7"})
    assert config.top_k == 7 and config.llm_timeout == 30
    assert config.documents_dir == PROJECT_ROOT / "data/custom"
    assert dict(os.environ) == before


@pytest.mark.parametrize("key,value", [("TOP_K","0"),("LLM_TIMEOUT","nan"),("LLM_MODEL","test:cloud"),("FILE_NAMES",'"guide.txt"'),("MAX_CONTEXT_CHARS","-1"),("CANDIDATE_K","abc")])
def test_invalid_settings(tmp_path,key,value):
    with pytest.raises(ValueError): load_config(tmp_path/'missing', {"AGENT_"+key:value})


def test_graph_passes_same_config_to_grade_and_generate():
    class Retriever:
        def retrieve(self, query, top_k):
            assert top_k == 4
            return [RetrievedChunk(Chunk('ABCDEFGHIJ',{'source':'guide'},0,0,10),1,'rrf')]
    class Model:
        def generate(self, messages, schema):
            payload = json.loads(messages[-1]['content'])
            if 'sufficient' in schema['properties']:
                assert payload['sources'] == ['ABCDE']
                return {'sufficient': True}
            assert payload['sources'][0]['content'] == 'ABCDE'
            return {'answerable':True, 'answer':'ABCDE', 'evidence':[{'source_id':1,'quote':'ABCDE'}]}
    state = AgentGraph(Retriever(), Model(), ProjectConfig(top_k=4,max_context_chars=5)).invoke('test')
    assert state['result'].answered


def test_api_runtime_reads_environment(monkeypatch):
    from app.services.runtime import Runtime
    monkeypatch.setenv('AGENT_TOP_K', '6')
    monkeypatch.setenv('AGENT_LLM_TIMEOUT', '45')
    runtime = Runtime()
    assert runtime.config.top_k == 6
    assert runtime.config.llm_timeout == 45
    assert runtime.config.to_report()['llm_timeout'] == 45
    assert runtime.agent is None


def test_retrieval_settings_do_not_invalidate_embeddings(tmp_path):
    from dataclasses import replace
    from ingestion.knowledge_base import compute_signature
    (tmp_path/'a.txt').write_text('test')
    config = ProjectConfig(documents_dir=tmp_path, file_names=('a.txt',))
    changed = replace(config, top_k=7, candidate_k=30, max_context_chars=3000, llm_model='qwen3:4b')
    assert compute_signature(config) == compute_signature(changed)

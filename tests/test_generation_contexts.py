import asyncio
import json
from types import SimpleNamespace
import pytest
from generation.rag import RagAssistant
from evaluation.benchmark import evaluate_agent
from evaluation.ragas_eval import evaluate_cases, read_cases


def test_records_exact_truncated_generation_context_and_benchmark():
    chunk=SimpleNamespace(content="Restart VPN. Secret tail",metadata={"source":"guide.txt"},chunk_index=0,start_index=0,end_index=24)
    class Retriever:
        def retrieve(self,*args,**kwargs):return [SimpleNamespace(chunk=chunk)]
    class Model:
        def generate(self,messages,schema):
            assert json.loads(messages[1]["content"])["sources"][0]["content"]=="Restart VPN."
            return {"answerable":True,"answer":"Restart VPN.","evidence":[{"source_id":1,"quote":"Restart"}]}
    result=RagAssistant(Retriever(),Model(),max_context_chars=12).answer("VPN?")
    assert result.generation_contexts==["Restart VPN."]
    agent=SimpleNamespace(invoke=lambda q:dict(result=result,trace=[],retry_count=0))
    report=evaluate_agent([dict(id="one",query="VPN?",answerable=True,expected_source="guide.txt")],agent)
    assert report["cases"][0]["generation_contexts"]==["Restart VPN."]


def test_generation_scoring_uses_full_context_not_quote():
    seen=[]
    async def judge(name,q,a,contexts):seen.append(contexts);return 1
    case=dict(id="1",query="q",answer="a",answered=True,citations=[{"quote":"short"}],generation_contexts=["full context"])
    report=asyncio.run(evaluate_cases([case],judge,"generation_contexts"))
    assert seen==[["full context"],["full context"]]
    assert report["metrics"]["generation_faithfulness"]["scored"]==1
    assert "citation_faithfulness" not in report["metrics"]


def test_old_report_does_not_silently_use_quotes_as_full_context():
    async def judge(*args):return 1
    case=dict(id="1",query="q",answer="a",answered=True,citations=[{"quote":"short"}])
    report=asyncio.run(evaluate_cases([case],judge,"generation_contexts"))
    assert report["metrics"]["generation_faithfulness"]==dict(mean=None,scored=0,failed=1)


@pytest.mark.parametrize("contexts",["text",[4],["x"*100001]])
def test_invalid_context_report(tmp_path,contexts):
    case=dict(id="1",query="q",answer="a",answered=True,citations=[],generation_contexts=contexts)
    path=tmp_path/"report.json";path.write_text(json.dumps({"agent":{"cases":[case]}}))
    with pytest.raises(ValueError):read_cases(path)

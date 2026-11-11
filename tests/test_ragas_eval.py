import asyncio
import json
from copy import deepcopy
import pytest
from evaluation import ragas_eval as module


def case(**updates):
    return dict(id='one', query='How?', answer='Restart', answered=True,
                citations=[{'quote':'Restart'}], **updates)


def test_scoring_preserves_zero_and_deduplicates_context():
    calls=[]
    async def judge(name, query, answer, contexts):
        calls.append(contexts)
        return 0
    data=case();data['citations'] *= 2
    result=asyncio.run(module.evaluate_cases([data],judge))
    assert calls==[['Restart'],['Restart']]
    assert result['metrics']['citation_faithfulness']==dict(mean=0,scored=1,failed=0)


def test_failures_and_refusals_are_not_successes():
    async def judge(*args): raise RuntimeError('private payload')
    refusal=case();refusal.update(id='two',answered=False)
    error=case();error.update(id='three',error='failure')
    result=asyncio.run(module.evaluate_cases([case(),refusal,error],judge))
    assert result['skipped']==2
    assert result['metrics']['citation_faithfulness']==dict(mean=None,scored=0,failed=1)
    assert 'private payload' not in json.dumps(result)


@pytest.mark.parametrize('score',[float('nan'),float('inf'),-1,2,0.5])
def test_invalid_binary_judgements(score):
    async def judge(*args): return score
    result=asyncio.run(module.evaluate_cases([case()],judge))
    assert result['metrics']['answer_addresses_question']['failed']==1


def test_missing_context_only_blocks_faithfulness():
    async def judge(*args): return 1
    data=case();data['citations']=[]
    result=asyncio.run(module.evaluate_cases([data],judge))
    assert result['metrics']['citation_faithfulness']['failed']==1
    assert result['metrics']['answer_addresses_question']['scored']==1


@pytest.mark.parametrize('data',[{},[],{'agent':None},{'agent':{'cases':[]}}, {'agent':{'cases':[case(),case()]}}])
def test_rejects_invalid_reports(tmp_path,data):
    path=tmp_path/'input.json';path.write_text(json.dumps(data))
    with pytest.raises(ValueError): module.read_cases(path)


def test_cli_writes_separate_report_without_text(tmp_path,monkeypatch):
    path=tmp_path/'input.json';path.write_text(json.dumps({'agent':{'cases':[case()]}}))
    output=tmp_path/'output.json'
    async def judge(*args): return 1
    monkeypatch.setattr(module,'make_judge',lambda *args:judge)
    assert module.main([str(path),'--output',str(output)])==0
    report=json.loads(output.read_text())
    assert report['context_scope']=='citation_excerpts' and len(report['source_sha256'])==64
    assert 'Restart' not in output.read_text()
    with pytest.raises(SystemExit): module.main([str(path),'--output',str(output)])


def test_cli_failed_judge_saves_failure_report(tmp_path,monkeypatch):
    path=tmp_path/'input.json';path.write_text(json.dumps({'agent':{'cases':[case()]}}))
    async def judge(*args): raise ValueError('private')
    monkeypatch.setattr(module,'make_judge',lambda *args:judge)
    output=tmp_path/'failed.json'
    assert module.main([str(path),'--output',str(output)])==1
    assert output.exists()


def test_real_ragas_adapter_with_scripted_local_model(monkeypatch):
    import importlib.util
    if importlib.util.find_spec("ragas") is None:
        pytest.skip("optional RAGAs dependency not installed")
    outputs=iter([
        {"statements":["Restart the client."]},
        {"statements":[{"statement":"Restart the client.","reason":"In context", "verdict":1}]},
        {"reason":"Direct answer", "verdict":1},
    ])
    calls=[]
    def generate(self,messages,schema):
        calls.append(messages)
        return next(outputs)
    monkeypatch.setattr("generation.local_llm.OllamaChat.generate",generate)
    judge=module.make_judge("qwen3:8b",10)
    result=asyncio.run(module.evaluate_cases([case()],judge))
    assert len(calls)==3
    assert result["metrics"]["citation_faithfulness"]["mean"]==1
    assert result["metrics"]["answer_addresses_question"]["mean"]==1

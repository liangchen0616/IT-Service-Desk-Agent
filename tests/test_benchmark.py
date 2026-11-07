import json
import pytest
from types import SimpleNamespace
from evaluation.benchmark import load_dataset, evaluate_retrieval, evaluate_agent


def test_metrics_separate_negative_candidates():
    cases = [dict(id='1',query='yes',answerable=True,expected_source='a'),
             dict(id='2',query='no',answerable=False,expected_source=None)]
    class Retriever:
        def retrieve(self, query, top_k):
            return [SimpleNamespace(chunk=SimpleNamespace(metadata={'source': s}), score=1) for s in ['b','a']]
    result = evaluate_retrieval(cases, {'test': Retriever()})['test']
    assert result['source_hit_at_k'] == 1
    assert result['source_mrr'] == .5
    assert result['source_top1'] == 0
    assert result['positive_count'] == 1


def test_runtime_error_is_not_successful_abstention():
    class Agent:
        def invoke(self, query):
            return dict(result=SimpleNamespace(answered=False, citations=[], answer='error'),
                        error='offline', retry_count=0, trace=[])
    cases = [dict(id='1',query='no',answerable=False,expected_source=None)]
    assert evaluate_agent(cases, Agent())['passed'] == 0


def test_duplicate_cases_rejected(tmp_path):
    case = dict(id='1', query='test', answerable=True, expected_source='a')
    p = tmp_path/'cases.json'; p.write_text(json.dumps([case,case]))
    with pytest.raises(ValueError): load_dataset(p)

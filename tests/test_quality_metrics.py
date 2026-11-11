import json
from types import SimpleNamespace
import pytest
from evaluation.benchmark import classify_answer,evaluate_agent,parse_dataset

CASE=dict(id='1',query='VPN',answerable=True,expected_source='guide.pdf',expected_page=2,expected_quote='Restart')
CITATION=dict(source='guide.pdf',page=2,quote='Restart the client.')

@pytest.mark.parametrize('answered,citations,error,outcome',[
 (True,[CITATION],None,'supported_answer'),
 (False,[],None,'false_refusal'),
 (True,[{**CITATION,'source':'wrong.pdf'}],None,'wrong_source'),
 (True,[{**CITATION,'page':1}],None,'wrong_page'),
 (True,[{**CITATION,'quote':'Other text'}],None,'missing_evidence'),
 (False,[],'failure','execution_error'),
])
def test_positive_outcomes(answered,citations,error,outcome):
 assert classify_answer(CASE,answered,citations,error)==outcome

def test_constraints_must_match_same_citation():
 citations=[{**CITATION,'page':1},{**CITATION,'quote':'Other'}]
 assert classify_answer(CASE,True,citations,None)=='missing_evidence'

@pytest.mark.parametrize('extra',[{'expected_page':True},{'expected_page':0},{'expected_quote':''},{'expected_quote':42}])
def test_invalid_evidence_labels(extra):
 with pytest.raises(ValueError):parse_dataset(json.dumps([{**CASE,**extra}]))

def test_failed_case_does_not_stop_run_or_count_as_refusal():
 class Agent:
  def invoke(self,query):
   if query=='broken':raise RuntimeError('secret detail')
   return dict(result=SimpleNamespace(answered=False,answer='No evidence',citations=[]),trace=[],retry_count=0,error=None)
 cases=[dict(id=str(i),query=q,answerable=False,expected_source=None) for i,q in enumerate(['broken','normal'])]
 report=evaluate_agent(cases,Agent())
 assert report['total']==2 and report['passed']==1
 assert report['outcome_counts']['execution_error']==1 and report['execution_error_rate']==.5
 assert report['outcome_counts']['correct_refusal']==1
 assert report['false_refusal_rate'] is None
 assert 'secret detail' not in json.dumps(report)

def test_negative_answer_is_distinct_from_error():
 case=dict(answerable=False,expected_source=None)
 assert classify_answer(case,True,[CITATION],None)=='unexpected_answer'
 assert classify_answer(case,False,[CITATION],None)=='unexpected_citation'
 with pytest.raises(ValueError):evaluate_agent([],None)

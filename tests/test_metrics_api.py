import json
import os
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.main import create_app


def report():
 return {'created_at':'2026-11-10T00:00:00+00:00','dataset_path':'private/path',
   'config':{'secret':'sensitive'},'retrieval':{'hybrid':{'top_k':3,'positive_count':18,
   'source_hit_at_k':1.,'source_top1':1.,'source_mrr':1.,'mean_ms':12.,
   'cases':[{'query':'private question'}]}},
   'agent':{'total':24,'passed':23,'p95_ms':100.,'cases':[{'answer':'private answer'}]}}


def test_metrics_no_report_and_no_model_initialization(tmp_path):
 runtime=SimpleNamespace(reports_dir=tmp_path/'missing')
 response=TestClient(create_app(runtime)).get('/metrics')
 assert response.status_code==404 and not runtime.reports_dir.exists()


def test_metrics_exposes_only_summary_and_latest(tmp_path):
 old=tmp_path/'benchmark-old.json';old.write_text(json.dumps(report()))
 new=tmp_path/'benchmark-new.json';value=report();value['agent']['passed']=24
 new.write_text(json.dumps(value));os.utime(old,(1,1));os.utime(new,(2,2))
 response=TestClient(create_app(SimpleNamespace(reports_dir=tmp_path))).get('/metrics')
 assert response.status_code==200,response.text
 assert response.json()['report_id']=='benchmark-new.json'
 assert response.json()['agent']['passed']==24
 for secret in ['private','sensitive','dataset_path','cases','config']: assert secret not in response.text


@pytest.mark.parametrize('data',['broken','[]','{"retrieval":{}}'])
def test_invalid_latest_report_is_not_silently_replaced(tmp_path,data):
 old=tmp_path/'benchmark-old.json';old.write_text(json.dumps(report()));os.utime(old,(1,1))
 (tmp_path/'benchmark-new.json').write_text(data)
 response=TestClient(create_app(SimpleNamespace(reports_dir=tmp_path))).get('/metrics')
 assert response.status_code==503


def test_invalid_metrics_are_rejected(tmp_path):
 value=report();value['agent']['passed']=25
 path=tmp_path/'benchmark-bad.json';path.write_text(json.dumps(value))
 client=TestClient(create_app(SimpleNamespace(reports_dir=tmp_path)))
 assert client.get('/metrics').status_code==503
 value=report();value['retrieval']['hybrid']['mean_ms']=float('nan')
 path.write_text(json.dumps(value))
 assert client.get('/metrics').status_code==503


def test_retrieval_only_report_has_no_fabricated_agent_scores(tmp_path):
 value=report();del value['agent']
 (tmp_path/'benchmark-retrieval.json').write_text(json.dumps(value))
 response=TestClient(create_app(SimpleNamespace(reports_dir=tmp_path))).get('/metrics')
 assert response.status_code==200 and response.json()['agent'] is None

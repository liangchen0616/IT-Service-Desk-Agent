from dataclasses import replace
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from memory.sqlite_sessions import SQLiteSessionStore
from core.config import ProjectConfig,load_config
from core.exceptions import SessionNotFound,SessionCapacity
from app.main import create_app
from app.services.runtime import Runtime


def test_restart_clear_delete_and_isolation(tmp_path):
 path=tmp_path/'history.sqlite3';store=SQLiteSessionStore(path)
 assert not path.exists()
 a,b=store.create(),store.create()
 store.append(a,'q','resolved','answer',True)
 restored=SQLiteSessionStore(path)
 assert restored.history(a)[0]['answer']=='answer' and restored.history(b)==[]
 restored.clear(a)
 assert SQLiteSessionStore(path).history(a)==[]
 restored.delete(a)
 with pytest.raises(SessionNotFound):SQLiteSessionStore(path).history(a)


def test_persistent_expiry_and_capacity(tmp_path):
 now=[100]
 path=tmp_path/'history.sqlite3'
 store=SQLiteSessionStore(path,max_sessions=1,ttl=10,clock=lambda:now[0])
 identifier=store.create()
 with pytest.raises(SessionCapacity):store.create()
 now[0]=111
 restored=SQLiteSessionStore(path,max_sessions=1,ttl=10,clock=lambda:now[0])
 with pytest.raises(SessionNotFound):restored.history(identifier)
 assert restored.create()!=identifier


def test_history_limits_survive_restart(tmp_path):
 path=tmp_path/'history.sqlite3'
 store=SQLiteSessionStore(path,max_turns=2,max_chars=30)
 identifier=store.create()
 for i in range(5):store.append(identifier,str(i),'q','answer',True)
 history=SQLiteSessionStore(path).history(identifier)
 assert len(history)==2 and history[-1]['question']=='4'
 history[0]['answer']='changed'
 assert store.history(identifier)[0]['answer']=='answer'


def test_failed_write_rolls_back(tmp_path,monkeypatch):
 path=tmp_path/'history.sqlite3';store=SQLiteSessionStore(path)
 identifier=store.create();store.append(identifier,'q','q','a',True)
 original=store._write
 def fail(connection,identifier,turns):
  original(connection,identifier,turns)
  raise OSError('simulated failure after SQL write')
 monkeypatch.setattr(store,'_write',fail)
 with pytest.raises(OSError):store.append(identifier,'bad','bad','bad',True)
 assert len(SQLiteSessionStore(path).history(identifier))==1


def test_atomic_capacity_across_connections(tmp_path):
 path=tmp_path/'history.sqlite3'
 def create(_):
  try:return SQLiteSessionStore(path,max_sessions=2).create()
  except SessionCapacity:return None
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(create,range(4)))
 assert len([v for v in results if v])==2


def test_api_runtime_restart_preserves_history_without_model_loading(tmp_path):
 config=ProjectConfig(session_backend='sqlite',session_db_path=tmp_path/'sessions.sqlite3')
 runtime=Runtime(config)
 with TestClient(create_app(runtime)) as client:
  identifier=client.post('/sessions').json()['session_id']
  runtime.sessions.append(identifier,'VPN?','VPN?','Check network',True)
 fresh=Runtime(config)
 with TestClient(create_app(fresh)) as client:
  assert client.get('/sessions/'+identifier).json()['turn_count']==1
  assert fresh.agent is None
  assert client.delete('/sessions/'+identifier+'/history').status_code==200
 assert runtime.sessions.history(identifier)==[]


def test_config_load_and_source_path_protection(tmp_path):
 config=load_config(tmp_path/'none',{'AGENT_SESSION_BACKEND':'sqlite','AGENT_SESSION_DB_PATH':str(tmp_path/'data.sqlite3'),'AGENT_SESSION_TTL':'86400'})
 assert config.session_backend=='sqlite' and config.session_ttl==86400
 with pytest.raises(ValueError):replace(config,session_db_path=config.index_path)
 with pytest.raises(ValueError):replace(config,session_ttl=0)


def test_invalid_database_is_not_silently_reset(tmp_path):
 path=tmp_path/'invalid.sqlite3';path.write_bytes(b'existing important data')
 with pytest.raises(sqlite3.DatabaseError):SQLiteSessionStore(path).create()
 assert path.read_bytes()==b'existing important data'

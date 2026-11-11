from threading import RLock
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from memory.sessions import SessionStore
from memory.sqlite_sessions import SQLiteSessionStore


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_listing_order_expiry_and_no_touch(tmp_path, backend):
    now=[0]
    factory=lambda: SessionStore(ttl=10,clock=lambda:now[0]) if backend=="memory" else SQLiteSessionStore(tmp_path/"sessions.db",ttl=10,clock=lambda:now[0])
    store=factory()
    assert store.list_sessions()==[]
    first=store.create()
    now[0]=1
    second=store.create()
    now[0]=2
    store.append(first,"private question","resolved","private answer",True)
    if backend=="sqlite":store=factory()
    assert store.list_sessions()==[{"session_id":first,"turn_count":1},{"session_id":second,"turn_count":0}]
    now[0]=9
    store.list_sessions()
    now[0]=11
    assert store.list_sessions()==[{"session_id":first,"turn_count":1}]
    now[0]=12
    assert store.list_sessions()==[]


def test_empty_sqlite_list_does_not_create_database(tmp_path):
    path=tmp_path/"missing"/"history.db"
    assert SQLiteSessionStore(path).list_sessions()==[]
    assert not path.parent.exists()


def test_api_listing_never_loads_models_or_exposes_history():
    store=SessionStore()
    identifier=store.create()
    store.append(identifier,"private question","resolved","private answer",True)
    client=TestClient(create_app(SimpleNamespace(lock=RLock(),sessions=store)))
    response=client.get("/sessions")
    assert response.status_code==200
    assert response.json()=={"total":1,"sessions":[{"session_id":identifier,"turn_count":1}]}
    assert "private" not in response.text
    store.delete(identifier)
    assert client.get("/sessions").json()=={"total":0,"sessions":[]}

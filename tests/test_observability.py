import asyncio
import json
import logging
from threading import RLock
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from core.exceptions import LocalModelError, AgentExecutionError
from core.logging import JsonFormatter, configure_logging, request_id
from app.services.chat_service import answer


def app_with_failure(error):
    app = create_app(SimpleNamespace(agent=None))
    @app.get('/failure')
    def fail(): raise error
    return app


@pytest.mark.parametrize('error,status,code', [(LocalModelError('secret'),503,'model_unavailable'),
    (AgentExecutionError('secret'),500,'agent_execution_failed'),(RuntimeError('secret'),500,'internal_error')])
def test_error_envelope_and_id(error,status,code):
    response = TestClient(app_with_failure(error)).get('/failure')
    assert response.status_code == status
    assert response.json()['code'] == code
    assert response.json()['request_id'] == response.headers['x-request-id']
    assert 'secret' not in response.text
    assert request_id.get() == '-'


def test_validation_and_missing_route():
    client = TestClient(create_app(SimpleNamespace(agent=None)))
    for response in (client.post('/chat',json={'question':''}),client.get('/missing')):
        assert response.status_code in (422,404)
        assert response.json()['request_id'] == response.headers['x-request-id']


def test_concurrent_request_context_isolation():
    app = create_app(SimpleNamespace(agent=None))
    @app.get('/context')
    async def context():
        first = request_id.get()
        await asyncio.sleep(.01)
        assert request_id.get() == first
        return {'id':first}
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            responses = await asyncio.gather(*[client.get('/context') for _ in range(8)])
            ids = [r.json()['id'] for r in responses]
            assert len(set(ids)) == 8
            assert all(r.headers['x-request-id']==r.json()['id'] for r in responses)
        assert request_id.get() == '-'
    asyncio.run(run())


def test_formatter_excludes_payload_and_exception_message():
    record = logging.LogRecord('it_agent',logging.ERROR,'',1,'node_failed',(),None)
    record.question='secret question'
    record.error_type='ValueError'
    value = json.loads(JsonFormatter().format(record))
    assert 'secret' not in json.dumps(value)
    assert value['error_type']=='ValueError'


def test_logger_setup_does_not_duplicate_handlers():
    logger=configure_logging()
    count=len(logger.handlers)
    configure_logging()
    assert len(logger.handlers)==count


@pytest.mark.parametrize('code,error', [('model_error',LocalModelError),('agent_error',AgentExecutionError)])
def test_service_preserves_failure_category(code,error):
    agent=SimpleNamespace(invoke=lambda q: {'error':'internal details','error_code':code})
    runtime=SimpleNamespace(lock=RLock(),ensure_ready=lambda:None,agent=agent)
    with pytest.raises(error): answer(runtime,'test')

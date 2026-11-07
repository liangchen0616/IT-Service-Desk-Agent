import pytest
from types import SimpleNamespace
from generation.rag import RagAssistant
from generation.local_llm import LocalModelError


class Retriever:
    def retrieve(self, *args, **kwargs):
        return [SimpleNamespace(chunk=SimpleNamespace(
            content='检查打印机的网络连接是否正常。', metadata={'source': 'printer.txt'},
            chunk_index=0, start_index=0, end_index=16))]


def response(quote):
    return {'answerable': True, 'answer': '请检查打印机网络。',
            'evidence': [{'source_id': 1, 'quote': quote}]}


class SequenceModel:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def generate(self, messages, schema):
        self.calls.append(messages)
        result = next(self.outputs)
        if isinstance(result, Exception):
            raise result
        return result


def test_corrected_quote_is_accepted_with_original_sources():
    model = SequenceModel([response('检查打印机网络。'), response('检查打印机的网络连接是否正常。')])
    answer = RagAssistant(Retriever(), model).answer('打印机离线怎么办？')
    assert answer.answered
    assert answer.citations[0].source == 'printer.txt'
    assert len(model.calls) == 2
    assert model.calls[1][:2] == model.calls[0]


def test_second_invalid_quote_is_rejected_without_third_attempt():
    model = SequenceModel([response('改写的原文'), response('仍然改写')])
    with pytest.raises(LocalModelError, match='原文不一致'):
        RagAssistant(Retriever(), model).answer('打印机离线怎么办？')
    assert len(model.calls) == 2


def test_service_error_is_not_retried():
    model = SequenceModel([LocalModelError('服务未启动')])
    with pytest.raises(LocalModelError, match='服务未启动'):
        RagAssistant(Retriever(), model).answer('打印机离线怎么办？')
    assert len(model.calls) == 1

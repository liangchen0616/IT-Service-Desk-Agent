from dataclasses import replace
import hashlib
import json

import pytest
from core.config import ProjectConfig
from embeddings.embedder import EmbeddedChunk
from evaluation import benchmark
from retrieval.contracts import RetrievedChunk
from retrieval.reranker import RerankerError


class Embedder:
    def embed_chunks(self, chunks): return [EmbeddedChunk(c, [1., 0.]) for c in chunks]
    def embed_query(self, query): return [1., 0.]


@pytest.fixture
def inputs(tmp_path):
    (tmp_path/'guide.txt').write_text('Restart VPN.')
    config = ProjectConfig(documents_dir=tmp_path, file_names=('guide.txt',),
                           index_path=tmp_path/'index.json', top_k=1, candidate_k=2)
    cases = [dict(id='vpn', query='VPN', answerable=True, expected_source='guide.txt')]
    return config, cases


def test_configured_roles_and_topk_reach_agent(inputs):
    config, cases = inputs
    calls = []
    class Model:
        def __init__(self, role): self.role = role
        def generate(self, messages, schema):
            calls.append(self.role)
            if self.role == 'grade': return {'sufficient': True}
            assert self.role == 'generate'
            return {'answerable': True, 'answer': 'Restart VPN.',
                    'evidence': [{'source_id': 1, 'quote': 'Restart VPN.'}]}
    class Factory:
        def get_model(self, role): return Model(role)
    report = benchmark.run_benchmark(cases, config, embedder=Embedder(), include_agent=True, model_factory=Factory())
    assert calls == ['grade', 'generate']
    assert report['agent']['passed'] == 1
    assert report['agent']['cases'][0]['citations'][0]['quote'] == 'Restart VPN.'
    assert set(report['retrieval']) == {'faiss', 'bm25', 'hybrid'}
    assert all(r['top_k'] == 1 for r in report['retrieval'].values())
    assert report['document_count'] == 1


@pytest.mark.parametrize('broken', [False, True])
def test_rerank_report_distinguishes_execution_from_fallback(inputs, broken):
    config, cases = inputs
    class Ranker:
        def rerank(self, query, candidates, top_k):
            if broken: raise RerankerError('unavailable')
            return [RetrievedChunk(c.chunk, 2., 'cross_encoder') for c in candidates[:top_k]]
    report = benchmark.run_benchmark(cases, replace(config, reranker_enabled=True),
                                     embedder=Embedder(), reranker=Ranker())
    reranked = report['retrieval']['hybrid_reranked']
    expected = 'fallback' if broken else 'applied'
    assert reranked['rerank_counts'][expected] == 1
    assert reranked['cases'][0]['rerank_status'] == expected
    assert reranked['cases'][0]['score_types'] == ['rrf' if broken else 'cross_encoder']


def test_mismatched_dataset_fails_before_embedding(inputs):
    config, cases = inputs
    cases[0]['expected_source'] = 'missing.pdf'
    with pytest.raises(ValueError, match='absent'):
        benchmark.run_benchmark(cases, config)


def test_changed_corpus_cannot_produce_report(inputs):
    config, cases = inputs
    class MutatingEmbedder(Embedder):
        def embed_query(self, query):
            (config.documents_dir/'guide.txt').write_text('Changed corpus.')
            return super().embed_query(query)
    with pytest.raises(ValueError, match='Corpus changed'):
        benchmark.run_benchmark(cases, config, embedder=MutatingEmbedder())


def test_cli_uses_dataset_snapshot_env_and_preserves_existing_output(tmp_path, monkeypatch, capsys):
    dataset = tmp_path/'questions.json'
    raw = b'[{"id":"1","query":"VPN","answerable":false,"expected_source":null}]'
    dataset.write_bytes(raw)
    env = tmp_path/'.env'
    env.write_text('AGENT_TOP_K=7\nAGENT_LLM_GRADE_MODEL=judge:1b\n')
    monkeypatch.delenv('AGENT_TOP_K', raising=False)
    monkeypatch.delenv('AGENT_LLM_GRADE_MODEL', raising=False)
    seen = []
    def run(cases, config, **kwargs):
        seen.append(config)
        assert cases[0]['id'] == '1'
        dataset.write_text('[]')
        return {'retrieval': {'hybrid': {'top_k': config.top_k, 'source_top1': None, 'source_hit_at_k': None}}}
    monkeypatch.setattr(benchmark, 'run_benchmark', run)
    output = tmp_path/'report.json'
    args = ['--dataset', str(dataset), '--env-file', str(env), '--output', str(output)]
    assert benchmark.main(args) == 0
    report = json.loads(output.read_text())
    assert report['dataset_sha256'] == hashlib.sha256(raw).hexdigest()
    assert seen[0].llm_grade_model == 'judge:1b'
    assert 'hit@7=' in capsys.readouterr().out
    original = output.read_bytes()
    with pytest.raises(SystemExit): benchmark.main(args)
    assert output.read_bytes() == original and len(seen) == 1


def test_overlong_dataset_query_is_rejected(tmp_path):
    path = tmp_path/'questions.json'
    path.write_text(json.dumps([dict(id='1', query='x'*1001, answerable=False, expected_source=None)]))
    with pytest.raises(ValueError, match='query'): benchmark.load_dataset(path)

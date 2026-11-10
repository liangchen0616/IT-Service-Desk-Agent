import pytest
from ingestion.chunker import Chunk
from retrieval.contracts import RetrievedChunk
from retrieval.reranker import CrossEncoderReranker,RerankingRetriever,RerankerError
from core.config import load_config,ProjectConfig


def candidates():
    return [RetrievedChunk(Chunk(t,{'source':t+'.txt'},0,0,len(t)),.01,'rrf') for t in ['a','b','c']]


def test_pair_scoring_preserves_sources_and_stable_ties():
    class Model:
        def predict(self,pairs,**kwargs):
            assert pairs==[('question',t) for t in ['a','b','c']]
            return [-2,5,5]
    original=candidates()
    result=CrossEncoderReranker(model=Model()).rerank('question',original,2)
    assert [r.source for r in result]==['b.txt','c.txt']
    assert result[0].chunk is original[1].chunk
    assert result[0].score_type=='cross_encoder'
    assert original[1].score==.01


@pytest.mark.parametrize('scores',[[1],[1,float('nan'),3],[1,float('inf'),3]])
def test_invalid_model_scores(scores):
    class Model:
        def predict(self,*args,**kwargs): return scores
    with pytest.raises(RerankerError): CrossEncoderReranker(model=Model()).rerank('q',candidates(),3)


def test_candidate_expansion_and_fallback():
    class Retriever:
        def retrieve(self,query,top_k):
            assert top_k==20
            return candidates()
    class Broken:
        def rerank(self,*args): raise RerankerError('offline')
    result=RerankingRetriever(Retriever(),Broken()).retrieve('q',top_k=1)
    assert result[0].source=='a.txt' and result[0].score_type=='rrf'


def test_no_model_load_for_empty_results():
    assert CrossEncoderReranker().rerank('q',[],3)==[]


def test_failed_loading_only_attempted_once(monkeypatch):
    import sentence_transformers
    calls=[]
    def load(*args,**kwargs):
        calls.append(kwargs)
        raise OSError('offline')
    monkeypatch.setattr(sentence_transformers,'CrossEncoder',load)
    ranker=CrossEncoderReranker()
    for _ in range(2):
        with pytest.raises(RerankerError): ranker.rerank('q',candidates(),1)
    assert len(calls)==1 and calls[0]['local_files_only'] is True


def test_config_and_runtime_connection(tmp_path):
    from app.services.runtime import Runtime
    assert Runtime(config=ProjectConfig()).reranker is None
    config=load_config(tmp_path/'none',{'AGENT_RERANKER_ENABLED':'true'})
    runtime=Runtime(config=config)
    assert isinstance(runtime.reranker,CrossEncoderReranker)
    assert runtime.reranker._model is None
    with pytest.raises(ValueError): load_config(tmp_path/'none',{'AGENT_RERANKER_ENABLED':'yes'})


def test_real_cross_encoder_local_tiny_model(tmp_path):
    # Exercise the installed library offline, not semantic ranking quality.
    from transformers import BertConfig,BertForSequenceClassification,BertTokenizer
    model_dir=tmp_path/'tiny';model_dir.mkdir()
    (model_dir/'vocab.txt').write_text('[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\na\nb\nc\nquestion\n')
    BertTokenizer(vocab_file=str(model_dir/'vocab.txt')).save_pretrained(model_dir)
    BertForSequenceClassification(BertConfig(vocab_size=9,hidden_size=16,num_hidden_layers=1,num_attention_heads=2,intermediate_size=32,num_labels=1)).save_pretrained(model_dir)
    output=CrossEncoderReranker(str(model_dir)).rerank('question',candidates(),2)
    assert len(output)==2 and all(v.score_type=='cross_encoder' for v in output)

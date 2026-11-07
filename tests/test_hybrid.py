import pytest
from ingestion.chunker import Chunk
from retrieval.contracts import RetrievedChunk
from retrieval.sparse import BM25Retriever
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.hybrid import HybridRetriever


def chunk(text, source="guide.txt"):
    return Chunk(text, {"source": source}, 0, 0, len(text))


def test_sparse_chinese_english_and_unknown():
    r = BM25Retriever([chunk("VPN connection reset"), chunk("打印机离线检查电源")])
    assert r.retrieve("vpn")[0].text == "VPN connection reset"
    assert r.retrieve("打印机")[0].text == "打印机离线检查电源"
    assert r.retrieve("xyzxyz") == []
    assert BM25Retriever([]).retrieve("vpn") == []


def test_bm25_single_term_score():
    from math import log
    r = BM25Retriever([chunk("vpn"), chunk("printer")])
    assert r.retrieve("vpn")[0].score == pytest.approx(log(2))


def test_fusion_consensus_dedup_and_score_semantics():
    a, b = chunk("a"), chunk("b")
    ra, rb = RetrievedChunk(a, 999, "bm25"), RetrievedChunk(b, .1, "cosine")
    out = reciprocal_rank_fusion([[ra, ra, rb], [rb]])
    assert out[0].text == "b"
    assert out[0].score == pytest.approx(1/62 + 1/61)
    assert out[1].score == pytest.approx(1/61)
    assert out[0].score_type == "rrf"


def test_same_text_different_sources_preserved():
    r = BM25Retriever([chunk("vpn", "a"), chunk("vpn", "b")])
    assert len(r.retrieve("vpn")) == 2


def test_hybrid_uses_both_and_expands_candidates():
    class Fake:
        def __init__(self): self.calls = []
        def retrieve(self, query, top_k):
            self.calls.append((query, top_k))
            return [RetrievedChunk(chunk("vpn"), 1, "cosine")]
    dense, sparse = Fake(), Fake()
    result = HybridRetriever(dense, sparse, candidate_k=2).retrieve("vpn", top_k=5)
    assert dense.calls == sparse.calls == [("vpn", 5)]
    assert len(result) == 1
    assert result[0].score == pytest.approx(2/61)


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_invalid_limits(bad):
    with pytest.raises(ValueError): BM25Retriever([]).retrieve("vpn", top_k=bad)
    with pytest.raises(ValueError): reciprocal_rank_fusion([], top_k=bad)
    with pytest.raises(ValueError): HybridRetriever(None, None, candidate_k=bad)


def test_index_snapshot():
    c = chunk("vpn")
    r = BM25Retriever([c])
    c.content = "changed"
    first = r.retrieve("vpn")[0]
    first.chunk.content = "also changed"
    assert r.retrieve("vpn")[0].text == "vpn"

import pytest

from embeddings.embedder import EmbeddedChunk
from ingestion.chunker import Chunk
from retrieval.retriever import KnowledgeRetriever
from vectorstore.memory_store import InMemoryVectorStore


class FakeEmbedder:
    """Provide a predictable query vector without loading a model."""

    def __init__(self):
        self.queries = []

    def embed_query(self, query):
        self.queries.append(query)
        return [1.0, 0.0]


def make_item(text, vector):
    chunk = Chunk(
        content=text,
        metadata={"source": "test.txt"},
        chunk_index=0,
        start_index=0,
        end_index=len(text),
    )
    return EmbeddedChunk(chunk=chunk, vector=vector)


@pytest.fixture
def prepared_retriever():
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()

    items = [
        make_item("食堂用餐说明", [0.0, 1.0]),
        make_item("VPN 连接排查步骤", [1.0, 0.0]),
        make_item("网络故障处理说明", [0.8, 0.6]),
    ]
    store.add(items)

    retriever = KnowledgeRetriever(
        embedder=embedder,
        store=store,
    )
    return retriever, embedder, store, items


def test_retrieve_returns_ranked_original_chunks(prepared_retriever):
    retriever, embedder, store, items = prepared_retriever
    query = "公司 VPN 连接不上怎么办？"

    results = retriever.retrieve(query)

    assert embedder.queries == [query]
    assert len(results) == 3

    assert results[0].chunk is items[1].chunk
    assert results[1].chunk is items[2].chunk
    assert results[2].chunk is items[0].chunk

    assert [result.score for result in results] == pytest.approx(
        [1.0, 0.8, 0.0]
    )
    assert results[0].chunk.metadata == {"source": "test.txt"}
    assert store.count() == 3


@pytest.mark.parametrize(
    "top_k, expected_count",
    [
        (1, 1),
        (2, 2),
        (10, 3),
    ],
)
def test_retrieve_respects_top_k(
    prepared_retriever,
    top_k,
    expected_count,
):
    retriever, _, _, _ = prepared_retriever

    results = retriever.retrieve("VPN 连接失败", top_k=top_k)

    assert len(results) == expected_count
    assert results[0].chunk.content == "VPN 连接排查步骤"


def test_retrieve_empty_store_returns_empty_list():
    retriever = KnowledgeRetriever(
        embedder=FakeEmbedder(),
        store=InMemoryVectorStore(),
    )

    results = retriever.retrieve("VPN 连接失败")

    assert results == []


def test_retrieve_propagates_embedding_error():
    class FailingEmbedder:
        def embed_query(self, query):
            raise ValueError("Embedding failed.")

    retriever = KnowledgeRetriever(
        embedder=FailingEmbedder(),
        store=InMemoryVectorStore(),
    )

    with pytest.raises(ValueError, match="Embedding failed"):
        retriever.retrieve("VPN 连接失败")


@pytest.mark.parametrize(
    "min_score, expected_scores",
    [
        (None, [1.0, 0.8, 0.0]),
        (0.0, [1.0, 0.8, 0.0]),
        (0.5, [1.0, 0.8]),
        (0.9, [1.0]),
        (1.0, [1.0]),
    ],
)
def test_retrieve_filters_by_min_score(
    prepared_retriever,
    min_score,
    expected_scores,
):
    retriever, _, store, _ = prepared_retriever

    results = retriever.retrieve(
        "VPN 连接失败",
        top_k=3,
        min_score=min_score,
    )

    assert [result.score for result in results] == pytest.approx(
        expected_scores
    )
    assert store.count() == 3

    unfiltered_results = retriever.retrieve("VPN 连接失败")

    assert len(unfiltered_results) == 3


def test_retrieve_returns_empty_when_all_scores_below_threshold():
    store = InMemoryVectorStore()
    store.add([
        make_item("测试资料", [0.0, 1.0]),
    ])
    retriever = KnowledgeRetriever(
        embedder=FakeEmbedder(),
        store=store,
    )

    results = retriever.retrieve(
        "测试问题",
        min_score=0.5,
    )

    assert results == []
    assert store.count() == 1
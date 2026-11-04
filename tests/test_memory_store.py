import pytest

from embeddings.embedder import EmbeddedChunk
from ingestion.chunker import Chunk
from vectorstore.memory_store import InMemoryVectorStore


def make_item(text: str, vector: list[float]) -> EmbeddedChunk:
    """Create a document embedding for testing."""
    chunk = Chunk(
        content=text,
        metadata={"source": "test.txt"},
        chunk_index=0,
        start_index=0,
        end_index=len(text),
    )
    return EmbeddedChunk(chunk=chunk, vector=vector)


def test_new_store_is_empty():
    store = InMemoryVectorStore()

    assert store.count() == 0


def test_add_appends_items():
    store = InMemoryVectorStore()

    first = make_item("VPN", [1.0, 0.0])
    second = make_item("食堂", [0.0, 1.0])

    store.add([first])
    assert store.count() == 1

    store.add([second])
    assert store.count() == 2


def test_add_multiple_items():
    store = InMemoryVectorStore()
    items = [
        make_item("VPN", [1.0, 0.0]),
        make_item("食堂", [0.0, 1.0]),
        make_item("邮箱", [0.6, 0.8]),
    ]

    store.add(items)

    assert store.count() == 3


@pytest.mark.parametrize("prepopulated", [False, True])
def test_add_empty_list_keeps_count(prepopulated):
    store = InMemoryVectorStore()

    if prepopulated:
        store.add([make_item("已有文档", [1.0, 0.0])])

    original_count = store.count()

    store.add([])

    assert store.count() == original_count


@pytest.mark.parametrize("prepopulated", [False, True])
def test_add_rejects_empty_vector_without_partial_write(prepopulated):
    store = InMemoryVectorStore()

    if prepopulated:
        store.add([make_item("已有文档", [1.0, 0.0])])

    original_count = store.count()
    items = [
        make_item("合法文档", [0.0, 1.0]),
        make_item("空向量文档", []),
    ]

    with pytest.raises(ValueError, match="empty"):
        store.add(items)

    assert store.count() == original_count


@pytest.mark.parametrize("prepopulated", [False, True])
def test_add_rejects_mixed_dimensions_without_partial_write(prepopulated):
    store = InMemoryVectorStore()

    if prepopulated:
        store.add([make_item("已有文档", [1.0, 0.0])])

    original_count = store.count()
    items = [
        make_item("二维文档", [0.0, 1.0]),
        make_item("三维文档", [1.0, 0.0, 0.0]),
    ]

    with pytest.raises(ValueError, match="dimensions"):
        store.add(items)

    assert store.count() == original_count


def test_add_rejects_dimension_different_from_existing():
    store = InMemoryVectorStore()
    store.add([make_item("已有二维文档", [1.0, 0.0])])

    new_items = [
        make_item("三维文档一", [1.0, 0.0, 0.0]),
        make_item("三维文档二", [0.0, 1.0, 0.0]),
    ]

    with pytest.raises(ValueError, match="dimensions"):
        store.add(new_items)

    assert store.count() == 1


def test_failed_first_add_does_not_lock_dimension():
    store = InMemoryVectorStore()
    invalid_items = [
        make_item("二维文档", [1.0, 0.0]),
        make_item("三维文档", [1.0, 0.0, 0.0]),
    ]

    with pytest.raises(ValueError, match="dimensions"):
        store.add(invalid_items)

    assert store.count() == 0

    store.add([make_item("新的三维文档", [0.0, 1.0, 0.0])])

    assert store.count() == 1

@pytest.mark.parametrize(
    "a, b, expected",
    [
        ([1.0, 0.0], [1.0, 0.0], 1.0),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 0.0], [-1.0, 0.0], -1.0),
        ([2.0, 0.0], [5.0, 0.0], 1.0),
        ([3.0, 4.0], [1.0, 0.0], 0.6),
    ],
)
def test_cosine_similarity_known_values(a, b, expected):
    score = InMemoryVectorStore._cosine_similarity(a, b)

    assert score == pytest.approx(expected)
    assert -1.0 <= score <= 1.0


@pytest.mark.parametrize(
    "a, b, message",
    [
        ([], [1.0, 0.0], "empty"),
        ([1.0, 0.0], [], "empty"),
        ([1.0], [1.0, 0.0], "dimensions"),
        ([0.0, 0.0], [1.0, 0.0], "nonzero"),
        ([1.0, 0.0], [0.0, 0.0], "nonzero"),
        ([float("nan"), 0.0], [1.0, 0.0], "finite"),
        ([1.0, 0.0], [float("inf"), 0.0], "finite"),
        ([float("-inf"), 0.0], [1.0, 0.0], "finite"),
    ],
)
def test_cosine_similarity_rejects_invalid_vectors(a, b, message):
    with pytest.raises(ValueError, match=message):
        InMemoryVectorStore._cosine_similarity(a, b)


@pytest.mark.parametrize("top_k", [1, 2, 3, 10])
def test_search_returns_ranked_results(top_k):
    store = InMemoryVectorStore()

    best = make_item("最相关", [1.0, 0.0])
    middle = make_item("部分相关", [3.0, 4.0])
    opposite = make_item("相反方向", [-1.0, 0.0])

    # Deliberately insert items in a different order.
    store.add([opposite, middle, best])

    results = store.search([1.0, 0.0], top_k=top_k)

    expected_items = [best, middle, opposite][:top_k]
    expected_scores = [1.0, 0.6, -1.0][:top_k]

    assert len(results) == len(expected_items)

    for result, expected_item, expected_score in zip(
        results,
        expected_items,
        expected_scores,
        strict=True,
    ):
        assert result.chunk is expected_item.chunk
        assert result.score == pytest.approx(expected_score)

    assert store.count() == 3


def test_search_empty_store_returns_empty_list():
    store = InMemoryVectorStore()

    results = store.search([1.0, 0.0])

    assert results == []


@pytest.mark.parametrize("top_k", [True, False, 1.5, "2", None])
def test_search_rejects_invalid_top_k_type(top_k):
    store = InMemoryVectorStore()

    with pytest.raises(TypeError, match="top_k"):
        store.search([1.0, 0.0], top_k=top_k)


@pytest.mark.parametrize("top_k", [0, -1])
def test_search_rejects_nonpositive_top_k(top_k):
    store = InMemoryVectorStore()

    with pytest.raises(ValueError, match="top_k"):
        store.search([1.0, 0.0], top_k=top_k)


@pytest.mark.parametrize("prepopulated", [False, True])
@pytest.mark.parametrize(
    "query_vector, message",
    [
        ([], "empty"),
        ([0.0, 0.0], "nonzero"),
        ([float("nan"), 0.0], "finite"),
        ([float("inf"), 0.0], "finite"),
        ([float("-inf"), 0.0], "finite"),
    ],
)
def test_search_rejects_invalid_query_vectors(
    prepopulated,
    query_vector,
    message,
):
    store = InMemoryVectorStore()

    if prepopulated:
        store.add([make_item("已有文档", [1.0, 0.0])])

    original_count = store.count()

    with pytest.raises(ValueError, match=message):
        store.search(query_vector)

    assert store.count() == original_count


def test_search_rejects_query_dimension_mismatch():
    store = InMemoryVectorStore()
    store.add([make_item("二维文档", [1.0, 0.0])])

    with pytest.raises(ValueError, match="dimensions"):
        store.search([1.0, 0.0, 0.0])


def test_search_keeps_insertion_order_for_equal_scores():
    store = InMemoryVectorStore()
    first = make_item("先添加", [1.0, 0.0])
    second = make_item("后添加", [2.0, 0.0])
    store.add([first, second])

    results = store.search([1.0, 0.0], top_k=2)

    assert len(results) == 2
    assert results[0].chunk is first.chunk
    assert results[1].chunk is second.chunk
    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(1.0)


def test_search_does_not_reorder_stored_items():
    store = InMemoryVectorStore()
    first = make_item("第一篇", [1.0, 0.0])
    second = make_item("第二篇", [0.0, 1.0])
    store.add([first, second])

    # This query ranks the second item first.
    results = store.search([0.0, 1.0], top_k=2)
    assert results[0].chunk is second.chunk

    # Equal scores should still follow the original insertion order.
    tied_results = store.search([1.0, 1.0], top_k=2)
    assert tied_results[0].chunk is first.chunk
    assert tied_results[1].chunk is second.chunk
    assert store.count() == 2


@pytest.mark.parametrize(
    "vector, message",
    [
        ([0.0, 0.0], "nonzero"),
        ([float("nan"), 0.0], "finite"),
        ([float("inf"), 0.0], "finite"),
        ([float("-inf"), 0.0], "finite"),
    ],
)
def test_search_rejects_invalid_stored_vectors(vector, message):
    store = InMemoryVectorStore()

    # add() currently checks emptiness and dimensions.
    # Invalid numeric values are rejected during similarity calculation.
    store.add([make_item("无效数值文档", vector)])

    with pytest.raises(ValueError, match=message):
        store.search([1.0, 0.0])
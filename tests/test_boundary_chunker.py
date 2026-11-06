import pytest

from ingestion.boundary_chunker import BoundaryChunker
from ingestion.loader import Document


def test_preserves_sentences_and_whole_sentence_overlap():
    text = "第一句。第二句。第三句。第四句。"

    chunks = BoundaryChunker(9, 4).chunk_document(
        Document(text, {})
    )

    assert [chunk.content for chunk in chunks] == [
        "第一句。第二句。",
        "第二句。第三句。",
        "第三句。第四句。",
    ]


@pytest.mark.parametrize("text", ["", "   ", "\n\t\n"])
def test_blank_document_has_no_chunks(text):
    chunks = BoundaryChunker().chunk_document(
        Document(text, {})
    )

    assert chunks == []


def test_long_sentence_is_split_without_losing_text():
    text = "ABCDEFGHIJ"

    chunks = BoundaryChunker(4, 1).chunk_document(
        Document(text, {})
    )

    assert [chunk.content for chunk in chunks] == [
        "ABCD",
        "EFGH",
        "IJ",
    ]


def test_metadata_is_preserved_and_independent():
    document = Document(
        "第一句。第二句。第三句。",
        {"source": "guide.txt"},
    )

    chunks = BoundaryChunker(8, 4).chunk_document(document)

    assert all(
        chunk.metadata == document.metadata
        for chunk in chunks
    )

    chunks[0].metadata["source"] = "changed.txt"

    assert document.metadata["source"] == "guide.txt"
    assert chunks[1].metadata["source"] == "guide.txt"


@pytest.mark.parametrize(
    "text",
    [
        "第一段\n第二段\n第三段\n结束",
        "First sentence. Next sentence! Last one?",
        "没有标点的很长中文资料" * 5,
        "第一句。\n\n第二句！第三句？最后一句。",
    ],
)
@pytest.mark.parametrize(
    "size, overlap",
    [
        (1, 0),
        (8, 0),
        (9, 4),
        (9, 8),
    ],
)
def test_size_offsets_progress_and_coverage(
    text,
    size,
    overlap,
):
    chunks = BoundaryChunker(size, overlap).chunk_document(
        Document(text, {})
    )

    covered = set()

    for index, chunk in enumerate(chunks):
        assert chunk.chunk_index == index
        assert chunk.content == text[
            chunk.start_index:chunk.end_index
        ]
        assert 0 < len(chunk.content) <= size

        if index:
            previous = chunks[index - 1]

            assert chunk.start_index > previous.start_index
            assert (
                previous.end_index - chunk.start_index
                <= overlap
            )

        covered.update(
            range(chunk.start_index, chunk.end_index)
        )

    assert all(
        index in covered
        for index, char in enumerate(text)
        if not char.isspace()
    )


@pytest.mark.parametrize(
    "size, overlap, error",
    [
        (0, 0, ValueError),
        (4, -1, ValueError),
        (4, 4, ValueError),
        (True, 0, TypeError),
        (4, 1.5, TypeError),
    ],
)
def test_reuses_setting_validation(size, overlap, error):
    with pytest.raises(error):
        BoundaryChunker(size, overlap)
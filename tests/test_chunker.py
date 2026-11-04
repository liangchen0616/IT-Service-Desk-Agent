from ingestion.loader import Document
from ingestion.chunker import DocumentChunker
import pytest

def test_chunk_document_with_overlap():
    document = Document(
        content="ABCDEFGHIJ",
        metadata={"source": "example.txt", "file_type": "txt"},
    )
    chunker = DocumentChunker(chunk_size=4, overlap=1)

    chunks = chunker.chunk_document(document)

    assert len(chunks) == 3
    assert [chunk.content for chunk in chunks] == [
        "ABCD",
        "DEFG",
        "GHIJ",
    ]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert [
        (chunk.start_index, chunk.end_index)
        for chunk in chunks
    ] == [(0, 4), (3, 7), (6, 10)]

def test_chunk_document_preserves_metadata():
    document = Document(
        content="ABCDEFGHIJ",
        metadata={
            "source": "manual.pdf",
            "file_type": "pdf",
            "page_count": 2,
        },
    )
    chunker = DocumentChunker(chunk_size=4, overlap=1)

    chunks = chunker.chunk_document(document)

    assert len(chunks) == 3

    for chunk in chunks:
        assert chunk.metadata == document.metadata
        assert chunk.metadata is not document.metadata

    chunks[0].metadata["source"] = "changed.pdf"

    assert document.metadata["source"] == "manual.pdf"
    assert chunks[1].metadata["source"] == "manual.pdf"
    assert chunks[2].metadata["source"] == "manual.pdf"

def test_chunk_document_empty():
    document = Document(
        content="",
        metadata={"source": "empty.txt", "file_type": "txt"},
    )
    chunker = DocumentChunker()

    chunks = chunker.chunk_document(document)

    assert chunks == []

def test_chunk_document_short():
    document = Document(
        content="ABC",
        metadata={"source": "short.txt", "file_type": "txt"},
    )
    chunker = DocumentChunker(chunk_size=5, overlap=2)

    chunks = chunker.chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].content == "ABC"
    assert chunks[0].chunk_index == 0
    assert chunks[0].start_index == 0
    assert chunks[0].end_index == 3

def test_chunk_document_without_overlap():
    document = Document(
        content="ABCDEFGHIJ",
        metadata={"source": "example.txt", "file_type": "txt"},
    )
    chunker = DocumentChunker(chunk_size=4, overlap=0)

    chunks = chunker.chunk_document(document)

    assert [chunk.content for chunk in chunks] == [
        "ABCD",
        "EFGH",
        "IJ",
    ]
    assert [
        (chunk.start_index, chunk.end_index)
        for chunk in chunks
    ] == [(0, 4), (4, 8), (8, 10)]
    assert "".join(chunk.content for chunk in chunks) == document.content

def test_chunker_rejects_zero_chunk_size():
    with pytest.raises(ValueError, match="chunk_size"):
        DocumentChunker(chunk_size=0, overlap=0)

@pytest.mark.parametrize("overlap", [-1, 4, 5])
def test_chunker_rejects_invalid_overlap(overlap):
    with pytest.raises(ValueError, match="overlap"):
        DocumentChunker(chunk_size=4, overlap=overlap)

@pytest.mark.parametrize("chunk_size", [4.5, "4", True])
def test_chunker_rejects_invalid_chunk_size_type(chunk_size):
    with pytest.raises(TypeError, match="chunk_size"):
        DocumentChunker(chunk_size=chunk_size, overlap=0)


@pytest.mark.parametrize("overlap", [1.5, "1", True])
def test_chunker_rejects_invalid_overlap_type(overlap):
    with pytest.raises(TypeError, match="overlap"):
        DocumentChunker(chunk_size=4, overlap=overlap)        
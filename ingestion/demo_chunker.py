from ingestion.loader import DocumentLoader
from ingestion.chunker import DocumentChunker


def main():
    loader = DocumentLoader()
    document = loader.load_pdf("data/documents/vpn_manual.pdf")

    chunker = DocumentChunker(chunk_size=300, overlap=50)
    chunks = chunker.chunk_document(document)

    print(f"Document length: {len(document.content)}")
    print(f"Total chunks: {len(chunks)}")

    for chunk in chunks:
        print("-" * 60)
        print(f"Chunk: {chunk.chunk_index}")
        print(f"Range: [{chunk.start_index}:{chunk.end_index}]")
        print(f"Length: {len(chunk.content)}")
        print(f"Metadata: {chunk.metadata}")
        print(chunk.content)


if __name__ == "__main__":
    main()
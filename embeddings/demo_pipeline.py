from ingestion.loader import DocumentLoader
from ingestion.chunker import DocumentChunker
from embeddings.embedder import LocalEmbedder


def main():
    loader = DocumentLoader()
    document = loader.load_pdf("data/documents/vpn_manual.pdf")

    chunker = DocumentChunker(chunk_size=300, overlap=50)
    chunks = chunker.chunk_document(document)
    print("Total chunks:", len(chunks))

    print("Loading model...")
    embedder = LocalEmbedder()

    print("Generating embeddings...")
    results = embedder.embed_chunks(chunks)
    print("Total embeddings:", len(results))

    for item in results:
        print("-" * 40)
        print("Chunk:", item.chunk.chunk_index)
        print("Source:", item.chunk.metadata["source"])
        print(
            "Range:",
            (item.chunk.start_index, item.chunk.end_index),
        )
        print("Vector dimension:", len(item.vector))


if __name__ == "__main__":
    main()
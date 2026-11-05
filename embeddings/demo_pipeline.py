from ingestion.loader import DocumentLoader
from ingestion.chunker import DocumentChunker
from embeddings.embedder import LocalEmbedder
from vectorstore.memory_store import InMemoryVectorStore
from retrieval.retriever import KnowledgeRetriever

def main():
    loader = DocumentLoader()
    documents = [
        loader.load_txt("data/documents/vpn_guide_zh.txt"),
        loader.load_txt("data/documents/printer_guide_zh.txt"),
    ]

    chunker = DocumentChunker(chunk_size=300, overlap=50)

    chunks = []
    for document in documents:
        document_chunks = chunker.chunk_document(document)
        chunks.extend(document_chunks)


    print("Total chunks:", len(chunks))

    print("Loading model...")
    embedder = LocalEmbedder()

    print("Generating embeddings...")
    results = embedder.embed_chunks(chunks)
    print("Total embeddings:", len(results))

    store = InMemoryVectorStore()
    store.add(results)
    print("Stored chunks:", store.count())

    retriever = KnowledgeRetriever(embedder=embedder, store=store)


    while True:
        query = input("\n请输入问题（输入 q 退出）：").strip()

        if query.lower() == "q":
            print("查询结束。")
            break

        if not query:
            print("请输入具体问题。")
            continue

        search_results = retriever.retrieve(
            query,
            top_k=3,
            min_score=0.5,
        )

        print("\nQuery:", query)

        if not search_results:
            print("未找到达到当前相关度门槛的资料，请尝试补充问题或添加相关文档。")
            continue

        for rank, result in enumerate(search_results, start=1):
            print("-" * 60)
            print("Rank:", rank)
            print("Score:", f"{result.score:.4f}")
            print("Source:", result.chunk.metadata["source"])
            print("Chunk:", result.chunk.chunk_index)
            print("Content:", result.chunk.content)
    


if __name__ == "__main__":
    main()
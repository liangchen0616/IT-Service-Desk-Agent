from embeddings.embedder import LocalEmbedder
from ingestion.chunker import Chunk


def main():
    text = "如果公司 VPN 无法连接，请先检查网络和账号密码。"

    chunk = Chunk(
        content=text,
        metadata={"source": "demo"},
        chunk_index=0,
        start_index=0,
        end_index=len(text),
    )

    print("Loading model...")
    embedder = LocalEmbedder()

    print("Generating embedding...")
    result = embedder.embed_chunk(chunk)

    print("Content:", result.chunk.content)
    print("Metadata:", result.chunk.metadata)
    print("Vector dimension:", len(result.vector))
    print("First 5 values:", result.vector[:5])

    norm = sum(value ** 2 for value in result.vector) ** 0.5
    print("Vector norm:", norm)

    query = "What should I do if I cannot connect to the company VPN?"
    query_vector = embedder.embed_query(query)

    unrelated_text = "公司食堂每天中午提供午餐，员工可以使用饭卡支付。"
    unrelated_chunk = Chunk(
        content=unrelated_text,
        metadata={"source": "cafeteria_demo"},
        chunk_index=0,
        start_index=0,
        end_index=len(unrelated_text),
    )
    unrelated_result = embedder.embed_chunk(unrelated_chunk)

    query_norm = sum(value ** 2 for value in query_vector) ** 0.5

    print("Query:", query)
    for label, item in [
        ("VPN document", result),
        ("Cafeteria document", unrelated_result),
    ]:
        dot_product = sum(
            a * b for a, b in zip(query_vector, item.vector, strict=True)
        )
        document_norm = sum(value ** 2 for value in item.vector) ** 0.5
        score = dot_product / (query_norm * document_norm)

        print(f"{label}: {score:.4f}")



if __name__ == "__main__":
    main()
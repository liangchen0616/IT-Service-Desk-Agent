import json
from pathlib import Path
from embeddings.embedder import LocalEmbedder
from ingestion.chunker import DocumentChunker
from ingestion.loader import DocumentLoader
from retrieval.retriever import KnowledgeRetriever
from vectorstore.memory_store import InMemoryVectorStore


def load_cases() -> list[dict]:
    cases_path = Path(__file__).resolve().parent / "retrieval_cases.json"

    with cases_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_retriever() -> KnowledgeRetriever:
    project_root = Path(__file__).resolve().parent.parent
    documents_dir = project_root / "data" / "documents"

    loader = DocumentLoader()
    chunker = DocumentChunker(chunk_size=300, overlap=50)

    chunks = []
    for filename in ["vpn_guide_zh.txt", "printer_guide_zh.txt"]:
        document = loader.load_txt(documents_dir / filename)
        chunks.extend(chunker.chunk_document(document))

    print("正在加载模型……")
    embedder = LocalEmbedder()

    print("正在生成资料向量……")
    items = embedder.embed_chunks(chunks)

    store = InMemoryVectorStore()
    store.add(items)

    return KnowledgeRetriever(embedder=embedder, store=store)


def main():
    cases = load_cases()
    retriever = build_retriever()

    print("资料库片段数量：", retriever.store.count())
    print("评估问题数量：", len(cases))

    passed_count = 0

    records = []

    for index, case in enumerate(cases, start=1):
        results = retriever.retrieve(
            case["query"],
            top_k=3,
            min_score=0.5,
        )

        actual_source = None
        if results:
            actual_source = results[0].chunk.metadata["source"]

        passed = actual_source == case["expected_source"]

        records.append({
            "query": case["query"],
            "expected_source": case["expected_source"],
            "actual_source": actual_source,
            "top_score": results[0].score if results else None,
            "passed": passed,
        })

        if passed:
            passed_count += 1

        print("-" * 60)
        print("题号：", index)
        print("问题：", case["query"])
        print("预期来源：", case["expected_source"])
        print("实际第一名来源：", actual_source)

        if results:
            print("第一名分数：", f"{results[0].score:.4f}")
        else:
            print("没有结果达到当前门槛。")

        print("检查结果：", "通过" if passed else "未通过")

    print("=" * 60)
    print(f"符合预期：{passed_count}/{len(cases)}")

    if cases:
        pass_rate = passed_count / len(cases)
        print(f"本题集通过率：{pass_rate:.1%}")

        report = {
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "chunk_size": 300,
        "overlap": 50,
        "top_k": 3,
        "min_score": 0.5,
        "total": len(cases),
        "passed": passed_count,
        "cases": records,
    }

    report_path = Path(__file__).resolve().parent / "retrieval_report.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    print("评估报告已保存：", report_path)


if __name__ == "__main__":
    main()
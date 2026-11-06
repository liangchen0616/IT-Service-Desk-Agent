import json
from pathlib import Path

from ingestion.knowledge_base import build_knowledge_base
from project_config import ProjectConfig
from retrieval.retriever import KnowledgeRetriever


def load_cases(path: Path | None = None) -> list[dict]:
    path = path if path is not None else Path(__file__).resolve().parent / "retrieval_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation cases must be a nonempty list.")
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError("Each case must contain a nonempty query.")
        if "expected_source" not in case:
            raise ValueError("Each case must contain expected_source.")
        source = case["expected_source"]
        if source is not None and (not isinstance(source, str) or not source.strip()):
            raise ValueError("expected_source must be a nonempty string or null.")
    return cases


def evaluate_cases(
    cases: list[dict],
    retriever: KnowledgeRetriever,
    config: ProjectConfig,
) -> dict:
    records = []
    for case in cases:
        results = retriever.retrieve(
            case["query"], top_k=config.top_k, min_score=config.min_score,
        )
        first = results[0] if results else None
        actual_source = first.chunk.metadata["source"] if first else None
        records.append({
            "query": case["query"],
            "expected_source": case["expected_source"],
            "actual_source": actual_source,
            "top_score": first.score if first else None,
            "top_chunk_index": first.chunk.chunk_index if first else None,
            "top_content": first.chunk.content if first else None,
            "passed": actual_source == case["expected_source"],
        })
    return {
        **config.to_report(),
        "total": len(records),
        "passed": sum(record["passed"] for record in records),
        "cases": records,
    }


def save_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    config = ProjectConfig()
    cases = load_cases()
    print("正在构建知识库，请稍候……")
    knowledge = build_knowledge_base(config)
    print("文档数量：", knowledge.document_count)
    print("资料片段数量：", knowledge.chunk_count)
    report = evaluate_cases(cases, knowledge.retriever, config)
    for index, record in enumerate(report["cases"], start=1):
        print("-" * 60)
        print("题号：", index)
        print("问题：", record["query"])
        print("预期来源：", record["expected_source"])
        print("实际第一名来源：", record["actual_source"])
        score = record["top_score"]
        print("第一名分数：", f"{score:.4f}" if score is not None else "无结果")
        print("检查结果：", "通过" if record["passed"] else "未通过")

    print("=" * 60)
    print(f"符合预期：{report['passed']}/{report['total']}")
    print(f"本题集通过率：{report['passed'] / report['total']:.1%}")
    report_path = Path(__file__).resolve().parent / f"retrieval_report_{config.chunk_mode}.json"
    save_report(report, report_path)
    print("评估报告已保存：", report_path)


if __name__ == "__main__":
    main()

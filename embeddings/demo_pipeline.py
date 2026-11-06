from ingestion.knowledge_base import build_knowledge_base
from project_config import ProjectConfig


def main():
    config = ProjectConfig()
    print("正在检查本地知识库并加载查询模型，请稍候……")
    knowledge = build_knowledge_base(config, use_cache=True)
    print("知识库状态：", "已读取保存的知识库" if knowledge.loaded_from_cache else "已重新构建并保存知识库")
    print("保存位置：", config.index_path)
    print("分块方式：", config.chunk_mode)
    print("文档数量：", knowledge.document_count)
    print("资料片段数量：", knowledge.chunk_count)

    while True:
        try:
            query = input("\n请输入问题（输入 q 退出）：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n查询结束。")
            break
        if query.lower() == "q":
            print("查询结束。")
            break
        if not query:
            print("请输入具体问题。")
            continue

        results = knowledge.retriever.retrieve(
            query, top_k=config.top_k, min_score=config.min_score,
        )
        print("\n问题：", query)
        if not results:
            print("未找到达到当前相关度门槛的资料，请补充问题或添加相关文档。")
            continue
        for rank, result in enumerate(results, start=1):
            print("-" * 60)
            print("排名：", rank)
            print("分数：", f"{result.score:.4f}")
            print("来源：", result.chunk.metadata["source"])
            print("片段编号：", result.chunk.chunk_index)
            print("原文位置：", (result.chunk.start_index, result.chunk.end_index))
            print("正文：", result.chunk.content)


if __name__ == "__main__":
    main()

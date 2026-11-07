from generation.local_llm import LocalModelError, OllamaChat
from generation.rag import RagAssistant
from ingestion.knowledge_base import build_knowledge_base
from project_config import ProjectConfig


def main():
    """Ask questions against the saved knowledge base and show cited answers."""
    config = ProjectConfig()
    print("正在读取知识库并加载查询向量模型，请稍候……")
    knowledge = build_knowledge_base(config, use_cache=True)
    llm = OllamaChat()
    assistant = RagAssistant(
        knowledge.retriever, llm,
        top_k=config.top_k, min_score=config.min_score,
    )
    print("知识库：", "已读取保存文件" if knowledge.loaded_from_cache else "已重新构建并保存")
    print("资料片段数量：", knowledge.chunk_count)
    print("回答模型：", llm.model_name)
    print("首次回答可能需要等待本地回答模型加载。")

    while True:
        try:
            query = input("\n请输入问题（输入 q 退出）：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n问答结束。")
            break
        if query.lower() == "q":
            print("问答结束。")
            break
        try:
            result = assistant.answer(query)
        except ValueError as error:
            print(error)
            continue
        except LocalModelError as error:
            print("本次未能生成回答：", error)
            continue

        print("\n回答：", result.answer)
        if result.citations:
            print("\n参考原文：")
        for citation in result.citations:
            print(f"[资料 {citation.source_id}] {citation.source}，片段 {citation.chunk_index}")
            print(f"原片段位置：[{citation.start_index}:{citation.end_index}]")
            print("原文摘录：", citation.quote)


if __name__ == "__main__":
    main()

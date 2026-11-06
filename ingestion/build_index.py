from ingestion.knowledge_base import build_knowledge_base
from project_config import ProjectConfig


def main():
    """Explicitly regenerate and save the selected documents' vectors."""
    config = ProjectConfig()
    print("正在重新生成资料向量并保存，请稍候……")
    knowledge = build_knowledge_base(config, use_cache=True, force_rebuild=True)
    print("文档数量：", knowledge.document_count)
    print("资料片段数量：", knowledge.chunk_count)
    print("知识库已保存：", config.index_path)


if __name__ == "__main__":
    main()

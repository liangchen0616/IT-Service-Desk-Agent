# IT-Service-Desk-Agent

基于本地 Qwen3 Embedding 的 IT 服务台知识检索与 Agent 学习项目。

目前提供从本地文档加载、分块、向量生成到检索评估的完整基础流程，并支持将向量索引保存为 JSON 后复用。

## 已完成功能

- 加载 TXT、Markdown 和 PDF 文档。
- 支持固定长度和边界感知两种分块方式，支持重叠，并保留来源信息和文本位置。
- 使用 Qwen/Qwen3-Embedding-0.6B 在本地 CPU 上生成向量。
- 支持文档和查询的向量化，已进行中文及跨语言检索示例验证。
- 实现内存及 JSON 向量存储、余弦相似度计算、Top-K 检索和最低相关度过滤。
- 知识库可根据文档内容、模型和分块设置校验缓存；缓存不匹配时重新构建。
- 提供统一项目配置、知识库构建入口及检索评估脚本。
- 边界分块检索评估样例当前结果：6/6 符合预期。

## 开发环境

- Python 3.13
- 使用虚拟环境管理依赖。
- 依赖列表见 requirements.txt。
- 首次加载模型需要联网下载，模型推理在本地执行。

## 安装依赖

在项目根目录、已激活虚拟环境的终端中执行：

    python -m pip install -r requirements.txt

## 运行测试

    python -m pytest tests -v

## 运行检索

启动交互式检索。首次运行会加载本地嵌入模型，并自动读取可用索引或重新构建索引：

    python -m embeddings.demo_pipeline

显式强制重建并保存向量索引：

    python -m ingestion.build_index

运行检索评估并生成报告：

    python -m evaluation.evaluate_retrieval

评估用例位于 `evaluation/retrieval_cases.json`，报告按分块模式写入 `evaluation/retrieval_report_<chunk_mode>.json`。

## 项目配置

默认配置定义在 `project_config.py`：

- 文档目录：`data/documents`；默认读取 VPN 和打印机中文指南。
- 分块模式：`boundary`；也可设为 `fixed`。
- 分块长度与重叠：300 和 50 个字符。
- 检索数量与最低分数：Top-3，最低余弦相似度 0.5。
- 索引文件：`data/indexes/knowledge_base.json`。

可通过创建 `ProjectConfig` 并传入 `build_knowledge_base` 使用自定义配置。

## 运行示例

文档分块：

    python -m ingestion.demo_chunker

中文及跨语言向量相似度示例：

    python -m embeddings.demo_embedder

文档加载、分块和向量生成：

    python -m embeddings.demo_pipeline

## 后续计划

- 扩充中文知识文档和检索评估用例。
- 接入基于检索结果的回答生成。
- 逐步实现 Agent 工具调用与应用接口。

## 当前限制

- 首次使用嵌入模型时需要联网下载；下载后模型在本地运行。
- 当前项目提供检索流程，尚未实现完整的问答 Agent 或回答生成。
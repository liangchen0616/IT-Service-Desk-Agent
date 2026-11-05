# IT-Service-Desk-Agent

基于本地 Qwen3 Embedding 的 IT 服务台知识检索与 Agent 学习项目。

目前已完成文档加载、文本分块、本地向量生成和内存向量检索基础模块。

## 已完成功能

- 加载 TXT、Markdown 和 PDF 文档。
- 按字符长度分块，支持重叠，并保留来源信息和文本位置。
- 使用 Qwen/Qwen3-Embedding-0.6B 在本地 CPU 上生成向量。
- 支持文档和查询的向量化，已进行中文及跨语言检索示例验证。
- 实现内存向量存储、余弦相似度计算和 Top-K 检索。
- 当前测试结果：86 项通过。

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

## 运行示例

文档分块：

    python -m ingestion.demo_chunker

中文及跨语言向量相似度示例：

    python -m embeddings.demo_embedder

文档加载、分块和向量生成：

    python -m embeddings.demo_pipeline

## 后续计划

- 将真实文档向量与内存检索串联，完成端到端检索演示。
- 实现向量索引保存与加载。
- 扩充中文知识文档和检索评估用例。
- 接入基于检索结果的回答生成。
- 逐步实现 Agent 工具调用与应用接口。

## 当前限制

- 内存向量库尚未持久化，程序退出后需要重新构建。
- 当前项目尚未实现完整的问答 Agent。
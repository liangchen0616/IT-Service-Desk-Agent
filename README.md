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
- 已实现混合检索、LangGraph 问答、引用校验与 FastAPI；界面暂缓，外部搜索及会话记忆尚未实现。
## V2.1 混合检索入口

安装更新后的 requirements.txt 后运行：

    python -m generation.demo_hybrid

该入口复用原有 JSON 缓存及 Qwen Embedding，启动时用缓存向量构建 FAISS，并建立 BM25。通过 RRF 融合结果，再交给现有回答生成与引用校验。FAISS 当前在内存运行，重启从 JSON 重建，无需重新生成文档向量。

RRF 分数不能套用原有 0.5 余弦阈值，因此该入口显式使用 min_score=None。相关性不足依赖模型的证据判断与引用校验；尚未接入 LangGraph 查询重写。原 generation.demo_rag 入口保留。

## V2.1 Agent 工作流

    python -m generation.demo_agent

agents/state.py、graph.py、routing.py 和 nodes 模块使用 LangGraph 编排检索、相关性判断、重写与生成。llm/client.py 沿用本地 Ollama。最多两次重写（三次检索），证据不足或模型错误时回退；生成使用原问题和已判断的证据，并保留引用检查。显示节点路径和重写次数，返回状态包含耗时及来源。引用纠正与查询重写独立计数。

判断依赖模型；已接入下述 HTTP API，UI 与外部搜索尚未实现。

## V2.1 HTTP API

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

打开 http://127.0.0.1:8000/docs 进行交互测试。

- GET /health：进程存活检查；knowledge_ready 表示知识库是否已初始化，不代表 Ollama 健康状态。
- POST /chat：JSON 请求 {"question":"VPN连接失败"}，返回 answer、answered、citations、retry_count、trace。
- POST /documents：multipart 表单字段 file，支持 PDF/TXT/MD，单文件最多 5 MiB；文本使用 UTF-8。成功返回 201 及 document_id、filename、chunk_count。上传后立即纳入问答，重启后从 data/uploads 恢复。

首次问答或有效上传会加载模型。模型不可用返回 503；非法文档返回 400，超限 413，问题校验失败 422。上传使用独立目录，不覆盖同名原文件；失败不切换知识库。当前仅支持本机单进程运行，问答和入库串行处理，请勿使用多个 workers。无登录鉴权，不适合直接开放公网。原命令行入口只读取原始知识库，API 上传资料由 API 服务管理。

## 核心评估（界面暂缓）

    python -m evaluation.benchmark
    python -m evaluation.benchmark --agent

第一条对比三种检索方式；第二条同时运行 24 题本地 Agent 评估。报告默认写入 evaluation/reports 的新文件，不覆盖历史结果。详见 docs/architecture.md 和 docs/api.md。小语料来源命中率不是回答事实准确率。

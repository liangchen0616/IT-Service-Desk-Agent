# IT Service Desk Agent

基于 **LangGraph + RAG** 构建的 IT 服务台智能问答系统。

项目面向企业内部 IT 支持场景，结合本地大语言模型、混合检索和 Agent 工作流，实现知识库问答、问题分析与文档管理。

## 核心功能

- **智能知识问答**：根据企业内部文档回答 IT 相关问题，并提供引用来源。
- **混合检索**：结合 FAISS 向量检索和 BM25 关键词检索，通过 RRF 融合结果。
- **Agent 工作流**：使用 LangGraph 编排检索、相关性判断、查询重写和回答生成。
- **查询重写**：检索结果不足时自动优化问题，最多重写两次。
- **文档管理**：支持 PDF、TXT、Markdown 文档上传、解析、分块和索引，新增列表、详情、可恢复删除及归档恢复；PDF 支持页码引用和[可选本地 OCR](docs/ocr.md)（需另装引擎）。
- **HTTP API**：通过 FastAPI 提供问答、文档上传和健康检查接口。
- **检索评估**：支持不同检索方案对比、可选页码/证据检查和问答失败分类。

- **可选公开搜索**：本地资料不足时，可按显式公开查询词搜索网页摘要并提供链接。
- **多轮对话**：通过会话编号承接追问，支持 SQLite 持久化、历史隔离和清除，每轮重新检索证据。

## 技术栈

| 模块 | 技术 |
|---|---|
| 开发语言 | Python |
| Agent 框架 | LangGraph |
| 大语言模型 | Ollama（本地部署） |
| Embedding | Qwen3-Embedding-0.6B |
| 向量检索 | FAISS |
| 关键词检索 | BM25 |
| 检索融合 | RRF |
| API 服务 | FastAPI |
| 测试 | Pytest |

## 系统工作流程

系统主要分为两个阶段：**知识库构建**和**Agent 智能问答**。

### 1. 知识库构建

```text
上传文档（PDF / TXT / Markdown）
              ↓
       文档解析与清洗
              ↓
       文本分块（Chunking）
              ↓
      Qwen3 Embedding 向量化
              ↓
       构建知识库索引
         ├── FAISS 向量索引
         └── BM25 关键词索引
              ↓
         知识库就绪
```

### 2. Agent 智能问答

```text
用户输入问题
      ↓
FastAPI 接收请求
      ↓
LangGraph Agent
      ↓
混合检索（Hybrid Search）
  ├── FAISS：语义相似度检索
  └── BM25：关键词匹配检索
      ↓
RRF 融合检索结果
      ↓
LLM 判断文档相关性
      ↓
  ┌── 是否有相关证据？ ──┐
  │                     │
  是                    否
  │                     │
  │                查询重写
  │                     ↓
  │                重新检索
  │                     ↓
  │             最多重写 2 次
  │                     │
  │             仍无有效证据
  │                     ↓
  │                无法可靠回答
  │
  ↓
本地 LLM 生成回答
      ↓
引用来源检查与校验
      ↓
返回回答、引用及执行信息
```

以上为默认本地问答流程。有会话历史时先整理追问；可选重排位于混合检索之后。启用公开搜索且请求提供公开查询词时，本地证据不足后可搜索一次，重新判断证据再回答。

### 3. 关键机制

| 机制 | 作用 |
|---|---|
| Hybrid Search | 结合语义检索与关键词检索，提高召回效果 |
| RRF Fusion | 融合不同检索器的排序结果 |
| Relevance Grading | 判断检索文档是否与问题相关 |
| Query Rewriting | 证据不足时优化查询，最多重写两次 |
| Answer Generation | 使用本地 LLM 根据检索证据生成回答 |
| Citation Validation | 检查回答引用，减少无依据的输出 |
| Fallback | 多次检索失败或模型异常时返回降级结果 |

系统通过 LangGraph 管理各节点之间的执行顺序和条件分支，实现从检索到回答的自动化流程。

**当前版本**已实现本地知识库检索、查询重写、回答生成和引用校验。新增文档管理、PDF 页码引用、只读工具接口、可选重排与公开搜索，以及可选持久化多轮会话。

## 项目结构

```text
IT-Service-Desk-Agent/
├── app/             # FastAPI 接口与服务
├── agents/          # LangGraph Agent 工作流
├── ingestion/       # 文档加载、分块与索引
├── embeddings/      # 文本向量化
├── retrieval/       # 检索与结果融合
├── vectorstore/     # 向量存储
├── generation/      # 回答生成与演示入口
├── llm/             # 大语言模型调用与模型工厂
├── core/            # 统一配置、日志与异常
├── tools/           # 知识库检索与公开搜索工具
├── memory/          # 有限会话历史
├── scripts/         # 上传、问答与管理命令
├── evaluation/      # 检索与 Agent 评估
├── data/            # 知识文档与索引
├── tests/           # 自动化测试
├── docs/            # 技术文档
├── project_config.py
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

建议使用 Python 3.13 和虚拟环境。

```bash
python -m pip install -r requirements.txt
```

### 2. 准备本地模型

安装并启动 Ollama，确保项目配置的本地大语言模型可用。

首次使用 Embedding 模型时，需要联网下载模型文件。

### 3. 构建知识库

将文档放入 `data/documents/` 并在配置中指定文件列表，然后执行：

```bash
python -m ingestion.build_index
```

### 4. 启动 Agent

```bash
python -m generation.demo_agent
```

运行混合检索问答：

```bash
python -m generation.demo_hybrid
```

### 5. 启动 API

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 API 文档：

http://127.0.0.1:8000/docs

主要接口：

| 接口 | 功能 |
|---|---|
| `GET /health` | 服务健康检查 |
| `GET /metrics` | 最近一次评估的汇总指标 |
| `POST /chat` | 智能问答 |
| `POST /documents` | 上传知识文档 |
| `GET /documents`、`GET /documents/{id}` | 文档列表与详情 |
| `DELETE /documents/{id}` | 从知识库移除并保留归档 |
| `GET /document-archives`、`POST /document-archives/{id}/restore` | 查看归档与恢复文档 |
| `POST /sessions`、`GET /sessions/{id}` | 创建会话与查看历史 |
| `DELETE /sessions/{id}/history`、`DELETE /sessions/{id}` | 清除历史与删除会话 |

`POST /chat` 可传 `session_id` 承接追问；可选 `public_web_query` 明确指定允许外发的公开查询词。用法见 [API](docs/api.md) 和 [命令行说明](docs/cli.md)。

## 测试与评估

自动检查配置及范围见 [CI 说明](docs/ci.md)。

运行自动化测试：

```bash
python -m pytest tests -v
```

运行检索评估：

```bash
python -m evaluation.benchmark
```

运行 Agent 评估：

```bash
python -m evaluation.benchmark --agent
```

最近全量测试为 **501 项通过、1 项可选测试跳过**（2026-11-10）。外部搜索与会话集成测试使用模拟服务或模型；开发集指标不代表完整回答准确率。

真实本地模型开发集验收：**24/24 通过**，平均约 3.54 秒；RAGAs 已完成单题链路验证，尚未完成全量质量验收。

## 开发进度

**已实现**

- 文档解析、分块与向量化
- FAISS + BM25 混合检索
- LangGraph Agent 工作流
- 查询重写与重试控制
- 本地 LLM 回答生成与引用校验
- FastAPI 问答与文档管理、PDF 页码引用
- 统一配置、日志、模型工厂和命令行工具
- 可选 Cross-Encoder 重排、公开搜索与网页摘要引用
- 可选持久化多轮会话及只读工具调用
- 自动化测试与检索评估；新增可选 [RAGAs 本地评分](docs/ragas.md)
- Windows/Linux CI 测试与安装包检查（配置已完成，远端运行待验证）
- [Docker/Compose 本地部署](docs/deployment.md)（配置已完成，容器实测待验证）

**未完成与待验证**

- 真实扫描件 OCR 效果验证、会话备份与多实例协调
- 真实公开搜索联调、正式重排效果和独立题集验证
- 文档归档永久清空接口
- 可视化交互界面（暂缓）
- CI 远端运行、Docker 实机部署和全量 RAGAs 验收
- 用户鉴权与生产部署完善

公开搜索默认关闭，需配置密钥并在请求中明确提供公开查询词；会话默认存内存，也可配置 SQLite 在重启后恢复未过期历史。详细配置与进度见 [配置说明](docs/configuration.md) 和 [开发进度](docs/STATUS.md)。

目前项目主要面向本地开发与演示，尚未实现用户鉴权，不建议直接部署到公网。

## 参考项目

本项目在学习和实践过程中参考了：

- [Enterprise Agentic RAG Platform](https://github.com/ara-5/Enterprise-Agentic-RAG-Platform)
- [LangGraph](https://github.com/langchain-ai/langgraph)

项目基于实际开发需求独立组织模块，并逐步完善企业 IT 服务台的 Agentic RAG 工作流程。

# IT Service Desk Agent

基于 **LangGraph + RAG** 的本地 IT 服务台问答项目。使用企业文档回答问题，提供来源引用，并支持文档管理、可选公开搜索和多轮对话。

技术栈：Python 3.13、FastAPI、LangGraph、Ollama、Qwen3 Embedding、FAISS、BM25。

## 已实现

- **知识库入库**：PDF / TXT / Markdown 解析、分块、向量化和 JSON 缓存；PDF 支持页码引用。
- **混合检索**：FAISS + BM25 + RRF，可选 Cross-Encoder 重排序。
- **Agent 问答**：检索、证据判断、最多两次问题重写、回答生成与引用检查；证据不足时明确拒答。
- **文档管理**：上传、列表、详情、可恢复删除，重启恢复有效上传。
- **工具调用**：只读工具接口、参数校验、调用限制、执行期限与运行轨迹。
- **公开搜索**：可选 Brave 搜索；本地资料不足且请求明确提供公开查询词时，搜索一次并返回网页摘要引用。
- **多轮对话**：会话创建、追问理解、历史隔离、清除和删除；每轮重新检索证据。
- **工程支持**：统一配置、模型工厂、请求日志、错误处理、API、命令行、打包和评估报告。

基本流程：

```text
问题 → 追问整理（有会话历史时）→ 混合检索 → 证据判断 → 回答与引用检查
                                   ↑          │
                                   └─ 重写问题 ┘（最多两次）
本地证据仍不足 → 可选公开搜索并重新判断，或明确拒答
```

## 当前限制与待完成

- 扫描 PDF 的 OCR 尚未实现；当前 PDF 依赖可提取的文本。
- 外部搜索默认关闭，需要本机配置密钥和每次请求的明确授权；真实服务联调待完成，仅使用搜索摘要。
- 会话仅存内存，重启后消失；最多保留 6 轮、6000 字符，空闲一小时过期。
- 文档删除保留隐藏归档，尚无恢复或清空归档接口。
- 正式重排模型效果、独立评估集和真实多轮理解效果仍需验证。
- 用户鉴权、持久化会话、其他模型后端、Docker 和 CI 待完成；可视化界面暂缓。

项目目前定位本机开发与演示，未实现用户鉴权。

## 快速开始

在项目根目录，使用 Python 3.13 虚拟环境：

```powershell
python -m pip install -e .
```

另行安装并启动 Ollama，准备默认生成模型 `qwen3:8b`。默认 Embedding 为 `Qwen/Qwen3-Embedding-0.6B`，首次使用需要下载或准备本地缓存。

可参考 [.env.example](.env.example) 创建 `.env`；不创建也可使用默认配置。基础文档由配置中的目录和文件列表决定。

启动本地 API：

```powershell
python -m scripts.serve
```

接口文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。首次问答或上传会初始化知识库和模型。

另开终端执行：

```powershell
python -m scripts.demo_query "VPN连接失败怎么办？"
python -m scripts.ingest "C:\资料\指南.pdf"
python -m scripts.documents list
python -m scripts.sessions create
```

创建会话后，将返回的编号用于后续提问：

```powershell
python -m scripts.demo_query "第二步怎么做？" --session-id <会话编号>
```

## 测试与评估

```powershell
python -m pytest tests -q
python -m evaluation.benchmark
python -m evaluation.benchmark --agent
```

截至 2026-11-08，全量测试 **436 项通过**。默认开发集共 24 题，其中 18 道有依据题的 FAISS / Hybrid 来源 Top-1 与 Hit@3 均为 18/18；这不代表完整回答准确率或独立泛化能力。新增搜索与会话测试使用模拟服务或模型。

## 文档

- [开发规范](docs/DEVELOPMENT_SPEC.md) · [完整进度](docs/STATUS.md)
- [配置](docs/configuration.md) · [安装](docs/installation.md) · [API](docs/api.md) · [命令行](docs/cli.md)
- [多轮对话](docs/sessions.md) · [公开搜索](docs/web_search.md) · [工具调用](docs/tools.md)
- [重排序](docs/reranking.md) · [评估](docs/evaluation.md)

## 参考项目

- [Enterprise Agentic RAG Platform](https://github.com/ara-5/Enterprise-Agentic-RAG-Platform)
- [LangGraph](https://github.com/langchain-ai/langgraph)

# V2.1 架构与运行边界

## 数据流

文档上传 → DocumentService → 解析与分块 → Embedding → JSON 缓存 → FAISS + BM25 → 新知识库快照。

提问 → ChatRoute → ChatService → AgentGraph → Retrieve → Grade → Generate。
Grade 不通过时进入 Rewrite，最多两次；仍不足则 Fallback。Generate 只使用同一批已判断的证据，保持原问题，并复用原有引用逐字检查和一次纠正。

## 模块职责

- app/api：请求、响应与 HTTP 状态。
- app/schemas：输入校验与响应契约。
- app/services：知识库生命周期、上传事务、业务调用。
- agents：State、独立 Node、条件路由、轨迹及耗时。
- llm：判断和重写提示词及输出校验；本地调用沿用 generation/local_llm.py。
- ingestion / embeddings：解析、分块及向量生成。
- retrieval：BM25、RRF、Hybrid、检索工厂。
- vectorstore：JSON 持久化与 FAISS 内存索引。
- evaluation：独立的原始评估与新增 24 题 benchmark。

## 一致性

API 单进程运行，问答与入库共享锁。上传先写临时目录，完成解析、Embedding 和新索引后发布目录并替换运行时快照。失败保留旧知识库。重启扫描已发布上传；原 CLI 只使用 ProjectConfig 指定的原始文档。

JSON 缓存记录模型、处理配置和原文件内容签名。FAISS 从缓存重建，避免再次编码文档。当前不保存 FAISS 二进制文件。BM25 为内存实现。

## 验证与已知限制

    python -m pytest tests -q
    python -m evaluation.benchmark
    python -m evaluation.benchmark --agent

benchmark 使用 24 条用例，18 条有依据、6 条无依据。分别报告 FAISS/BM25/Hybrid 来源级 Top-1、Hit@3、MRR；负例不参与来源命中分母。Agent 评估检查是否回答及预期来源，运行错误不算正确拒答。该自动检查不证明答案每个陈述都被证据支持。

评估语料仅两个小文档，Hit@3 容易饱和，不代表真实企业语料泛化能力。报告记录数据哈希、语料签名、配置和时间；模型预热与请求顺序影响耗时。重写语义由模型遵守提示词，不能形式化保证不漂移。

当前 UI 按用户要求暂缓。P1 重排序及外部搜索、P2 多轮记忆/容器/CI 未完成。API 无鉴权，定位本机演示。PDF 当前仅保留文档来源与字符位置，尚无逐页引用。不要将目录存在视为功能已完成。

# 可选 RAGAs 本地评分

该模块读取已有 benchmark --agent 报告，不重新运行问答、不改变在线回答流程。使用固定 RAGAs 0.3.9 接口和本地 Ollama 评审，不自动下载模型，不调用云端评审。建议在独立虚拟环境安装，以隔离评估依赖：

```powershell
python -m pip install ".[evaluation]"
python -m evaluation.ragas_eval data/reports/benchmark-具体时间.json --model qwen3:8b
```

`--timeout` 指定单次 Ollama 请求超时（默认 180 秒），不是整批耗时上限；每题可能调用多次模型。`--output` 可指定新文件，已有文件不会覆盖。默认保存为 data/reports/ragas-时间.json，不会被 GET /metrics 当作 benchmark 报告。

两个指标：
- citation_faithfulness：RAGAs Faithfulness，检查回答陈述能否从引用原文片段推出。范围 0–1。
- answer_addresses_question：RAGAs AspectCritic 自定义二值判断，回答是否直接切题。仅返回 0 或 1，**不是**标准 ResponseRelevancy 指标，不与其分数混用。

旧报告未记录生成上下文，默认模式只用引用 quote，并去除重复片段，不拿来源文件名冒充证据。报告明确标记 context_scope=citation_excerpts。没有引用时忠实度无法评分，但仍可以判断是否切题。拒答和 Agent 执行错误单独跳过，拒答正确性继续看原 benchmark。包括原 benchmark 未通过的已作答题，避免只挑正确答案评分。

单个指标失败会记录错误类型并继续，NaN 和越界分数不会进入均值。均值仅统计有效结果，同时列出 scored、failed、总题数及 skipped；全为失败或跳过时均值为 null。有指标失败或全无有效评分时命令返回非零状态，报告仍保留。输入无效、依赖缺失时不生成成功报告。

评分报告只保存题号、分数、错误类型、输入报告 SHA-256 和评审模型，不复制问题、答案与引用正文。评审时仍会把这些内容发给本机 Ollama；关闭 RAGAs 遥测和 LangSmith 自动跟踪，不配置外部地址或默认云模型。

模型评分是估计，并不证明事实正确。当前不含标准 Answer Relevancy、Context Precision/Recall、人工标准答案或完整检索上下文评估；使用同一模型生成和评审会有自评偏差，需要人工抽查与独立题集。

实现参考 [RAGAs Faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/) 和 [RAGAs 0.3.9 评审接口](https://github.com/vibrantlabsai/ragas/blob/v0.3.9/src/ragas/llms/base.py)。

## 本次验证

2026-11-10：主环境 494 passed、1 skipped；临时环境安装真实 RAGAs 后，此模块 16 项测试全部通过，pip check 无冲突。实测发现 langchain-community 0.4.2 移除了 RAGAs 使用的 VertexAI 导入路径，已固定为 0.4.1，并固定本次验证的 instructor/langchain-openai 版本。临时环境复用了主环境基础依赖，不是全新机器完整安装验收。

使用已有 benchmark 报告的第一题和本地 qwen3:8b 完成单题实测：citation_faithfulness=0.2，answer_addresses_question=1，无评审错误。此结果仅用于验证完整链路；未运行 24 题全量 RAGAs 评审，低忠实度可能来自引用范围、答案内容或评审偏差，需要人工逐条核对，不能直接断言实际准确率。主环境未安装可选依赖，使用该功能前仍需安装 evaluation 扩展。


## 按实际生成上下文评分（2026-11-11）

新版 `python -m evaluation.benchmark --agent` 的逐题报告新增 generation_contexts，记录经过长度截断、实际发给生成模型的资料正文。没有调用生成时为空；不支持记录的旧对象为 null。这不是所有检索候选，也不是人工标准证据。

```powershell
python -m evaluation.ragas_eval data/reports/benchmark-新报告.json --context generation_contexts
```

该模式输出 generation_faithfulness 和 answer_addresses_question，context_scope 为 generation_contexts；不与旧 citation_faithfulness 混用。旧报告没有上下文时，忠实度标记失败，不使用引用片段替代。默认仍是 citation_excerpts。

上下文仅进入本地 benchmark 原始报告，不增加普通 /chat 或 /metrics 响应内容。原始报告包含资料原文，继续由 Git 忽略。新增模式已加入自动测试，全量真实模型评分仍待运行。

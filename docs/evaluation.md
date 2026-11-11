# 评估入口

在项目根目录运行：

    python -m evaluation.benchmark
    python -m evaluation.benchmark --agent
    python -m evaluation.benchmark --dataset questions.json --env-file evaluation.env --output result.json

默认只评估检索；--agent 额外调用本地模型执行完整问答。配置优先级仍为环境变量 > 指定配置文件（默认 .env）> 默认值。回答、判断和重写采用模型工厂中的对应配置。

默认题集为 evaluation/dataset.json，共 24 题。自定义题集是非空 JSON 数组，每题包含唯一 id、query、布尔值 answerable、expected_source。有依据题必须提供配置文档中的文件名；无依据题使用 null。问题不得超过 1000 字符。题集可自行扩充，但自行编写的题不等于独立盲测集。

评估仅使用 AGENT_DOCUMENTS_DIR 与 AGENT_FILE_NAMES 指定的文档，不自动混入上传目录。这样可明确每次评估使用的语料。题集引用不存在的文件会在模型初始化前报错。

默认对比 FAISS、BM25、Hybrid；开启 AGENT_RERANKER_ENABLED 后增加 hybrid_reranked，并保留原 Hybrid 基线。重排权重仍需提前准备；报告会逐题标记 applied（已重排）、fallback（失败后回退）、empty（无候选），并汇总数量。出现回退不能宣称已验证重排模型效果。

报告记录配置、语料签名、题集哈希、来源命中率、排名、分数类型、PDF 页码及耗时；完整问答还记录答案、引用、路径和错误。来源指标只统计有依据题，原始分数不可跨检索方法比较。耗时不含索引构建，包含问题向量化及首次重排模型加载；结果受预热和运行顺序影响。

默认报告保存到运行根目录 data/reports，--output 可另选位置。已有同名文件不会覆盖，评估期间语料变化会报错而不保存报告。问答通过条件是回答/拒答符合预期，并包含预期来源；这不等于逐条证明回答事实正确。

## 证据标注与问题分类

有依据题可增加 expected_page（正整数物理页码）和 expected_quote（1–200 字符的短原文）。例如：

    {"id":"vpn-page","query":"VPN 如何重启？","answerable":true,"expected_source":"guide.pdf","expected_page":2,"expected_quote":"重新启动 VPN 客户端"}

这只是字段示例，不属于当前开发集。应根据实际文档人工标注；无依据题不能指定页码或证据。未标注的旧题仍按原有来源级条件检查。标注页码/证据时，同一条引用必须同时满足文件名、页码以及 quote 包含预期短原文，避免不同引用分别满足条件造成误判。

完整 Agent 报告逐题记录 outcome，并汇总 outcome_counts：supported_answer、correct_refusal、false_refusal、unexpected_answer、unexpected_citation、wrong_source、wrong_page、missing_evidence、execution_error。故障优先分类，不计作正确拒答；单题抛出异常时记录异常类型并继续其余题目，不保存异常消息正文。

false_refusal_rate 分母为有依据题数；unexpected_answer_rate 分母为无依据题数；分母为零时返回 null。execution_error_rate 分母为总题数。故障单独统计，不应只看拒答率或无依据作答率。报告还包含平均耗时和 P95。

证据片段检查采用精确子串，不是语义判断；等价但不同的引用可能不满足标注。supported_answer 仅表示通过该题自动检查，并不保证回答所有事实正确。当前未新增独立盲测集。

## 最近一次实测与结果查询

2026-11-10：默认两份文档、4 个分块、24 题开发集，本地 qwen3:8b 真实运行通过 24/24（有依据 18 题，无依据 6 题），执行错误 0；平均 3536.57 ms，P95 7901.76 ms。FAISS/Hybrid 来源 Top-1 与 Hit@3 均为 18/18，BM25 分别为 16/18、17/18。此次未开启重排、OCR 和公开搜索，也不覆盖多轮会话。

报告：benchmark-20261110-152450-860994.json。GET /metrics 可读取默认 data/reports 中最近修改报告的摘要；不是 Prometheus 文本接口，也不是实时运行指标。缺报告返回 404，最新报告无效返回 503，仅检索报告的 agent 为 null。原始报告保留逐题信息，应留在本地；Git 默认忽略 data/reports。

可选 RAGAs 评审入口为 `python -m evaluation.ragas_eval <benchmark报告>`。评分针对引用片段和切题性，单独输出 ragas-*.json，不混入 /metrics 的 benchmark 汇总。安装、范围和限制见 [RAGAs 说明](ragas.md)。

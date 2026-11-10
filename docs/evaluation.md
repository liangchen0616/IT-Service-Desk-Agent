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

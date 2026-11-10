# Cross-Encoder 重排序

新增 retrieval/reranker.py，作为 HybridRetriever 后的可选阶段。先取 max(top_k, candidate_k) 个 RRF 候选，再逐对输入“问题、片段”评分，选出 top_k。默认 candidate_k=20、top_k=3。相同分数保留原候选顺序，来源与原文不修改。

## 开启

在运行根目录 .env 中配置并重启服务：

    AGENT_RERANKER_ENABLED=true
    AGENT_RERANKER_MODEL=BAAI/bge-reranker-base
    AGENT_RERANKER_BATCH_SIZE=8

默认关闭。模型名称也可替换为本地模型目录。推荐候选 BAAI/bge-reranker-base 的官方模型说明包含中文、英文支持：https://huggingface.co/BAAI/bge-reranker-base 。本项目尚未验证它在当前知识库上的实际质量提升。

必须先自行准备模型权重；运行时 local_files_only=True，不自动下载，不加载远程自定义代码。模型首次使用才加载；同一 Runtime 内上传重建索引时复用模型。加载失败后本进程不重复尝试，准备好模型后需重启。

## 分数与失败处理

成功返回 score_type=cross_encoder；失败回退时保留 score_type=rrf。两者都不能使用旧余弦阈值 0.5。日志事件 rerank_completed / rerank_fallback 记录执行情况；回退不跳过后续证据判断与引用校验。

CPU 推理按批执行，最大输入长度 512 token，长文本可能截断。重排序只能重新排列已召回候选，不能找回未召回证据，也不能证明资料足以回答问题。

API 和完整本地 demo_agent 通过 Runtime 接入；API 客户端自动使用服务设置。原 demo_hybrid 保留基线；benchmark 在开启重排配置时增加 hybrid_reranked 对比，并记录 applied/fallback/empty 数量，详见 evaluation.md。下一步应准备正式权重并运行独立检索对比，再决定是否默认启用。

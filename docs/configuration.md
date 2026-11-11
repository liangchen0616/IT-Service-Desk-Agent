# 统一配置

配置定义位于 core/config.py，旧 project_config.py 保留兼容导入。API Runtime 和 generation.demo_agent 主入口启动时读取配置。

将 .env.example 复制为项目根目录的 .env 后按需修改。优先级为：环境变量 > .env > 默认值。程序不修改进程环境；路径相对于项目根目录解析，避免从不同终端目录启动时读取错误文件。配置创建后不可修改，非法参数在启动时立即报错。修改配置后需重启服务。

主要参数：AGENT_LLM_MODEL、AGENT_LLM_TIMEOUT、AGENT_TOP_K、AGENT_CANDIDATE_K、AGENT_RANK_CONSTANT、AGENT_MAX_CONTEXT_CHARS，以及文档目录、文件列表、分块和 Embedding 模型设置。文件列表使用 JSON 数组。

判断与生成共享相同上下文长度和检索数量。AGENT_MIN_SCORE 仅供原余弦检索，不作用于混合检索 RRF。重写两次的上限保持开发规范要求，不提供任意放大的开关。本地 Ollama 地址仍固定；统一日志和异常体系已接入。

benchmark 已接入统一配置和模型工厂，支持 --env-file 指定配置文件；原阶段演示仍保持显式默认配置。上传目录仍为默认 data/uploads 或 Runtime 显式传入值。完整 Agent 本地 CLI 启动时恢复上传资料；scripts 命令行通过 API 使用同一运行中知识库。benchmark 只评估配置中明确列出的文件，不自动合入 API 上传目录；原阶段演示仍使用原始语料。

不需要创建 .env 才能运行；没有该文件时保留原有默认行为。不要提交真实 .env。新环境模板不包含密钥。

## 按任务选择本地模型

- AGENT_LLM_MODEL：生成最终回答，默认 qwen3:8b。
- AGENT_LLM_GRADE_MODEL：判断资料能否回答问题；留空时使用 AGENT_LLM_MODEL。
- AGENT_LLM_REWRITE_MODEL：改写检索问题；留空时使用 AGENT_LLM_MODEL。

模型工厂 llm/factory.py 按模型名称复用 Ollama 客户端。API 和完整 Agent CLI 已接入，默认三个任务共用一个客户端。工厂构造时不发送请求、不下载模型；各模型需事先安装在本地 Ollama 中。客户端复用不保证 Ollama 同时保留所有模型权重。多个模型是否更快、更准确需要单独评估。

设置无效名称会在配置检查时被拒绝；格式合法但本地未安装的模型，会在对应节点调用时返回模型错误，不会偷偷换成其他模型。运行中上传文档重建 Agent 时复用已有客户端。修改模型配置后重启服务生效。

当前只实现 Ollama 后端；云端服务和其他推理后端尚未接入。benchmark 也使用上述模型分工；旧阶段演示仍使用其原有显式模型配置。

工具执行期限由 AGENT_TOOL_TIMEOUT 配置，默认 180 秒，必须是有限正数。这是协作式期限而非强制中断时间，详见 [工具调用](tools.md)。

可选公开搜索配置：AGENT_WEB_SEARCH_ENABLED（默认 false）、AGENT_WEB_SEARCH_API_KEY（不进入报告）、AGENT_WEB_SEARCH_TIMEOUT（默认 15 秒）。详情见 web_search.md。

会话配置：AGENT_SESSION_BACKEND=memory 或 sqlite；AGENT_SESSION_DB_PATH 默认为 data/sessions/history.sqlite3；AGENT_SESSION_TTL 默认为 3600 秒。SQLite 重启恢复说明见 sessions.md。

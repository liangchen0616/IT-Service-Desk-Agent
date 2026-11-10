# 日志与异常

core/logging.py 配置 it_agent 专用日志器，一行一个 JSON。API 与完整 Agent CLI 启用日志，不改写第三方库或 Uvicorn 的日志配置。当前输出到终端，尚无文件轮转、集中日志平台及可配置等级。

API 为每次请求生成独立编号，响应头 X-Request-ID 始终返回该编号。错误响应统一为 detail、code、request_id。客户端输入的请求编号不会被信任或复用。上下文在请求结束后恢复，支持并发请求编号隔离。成功响应正文保持原格式。

状态映射：无效文档 400；超限上传 413；无效请求 422；模型调用或输出失败 503；其他 Agent 运行失败及未知异常 500。证据不足仍为正常 200，不属于系统异常。404、405 也使用统一错误格式。

日志事件包含 request_completed、node_completed、node_failed 等，记录时间、级别、请求编号、路由模板、耗时、节点和错误类型。应用日志不记录问题正文、文档内容、查询参数或异常原文；API 返回通用错误说明。现有 Agent 状态中的 error 仍供内部测试和评估使用。第三方库日志不受本模块过滤。

core/exceptions.py 提供 LocalModelError、InvalidDocument、AgentExecutionError。旧模块仍导出原有异常类以兼容现有调用。新增 error_code 让业务层区分模型失败与检索等内部失败，不再将所有工作流故障都误报为模型不可用。

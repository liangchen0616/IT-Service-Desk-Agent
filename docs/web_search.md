# 可选公开搜索

接入 Brave Web Search API：https://api-dashboard.search.brave.com/api-reference/web/search/get 。当前读取搜索结果摘要，不抓取目标网页全文。实现和模拟网络测试已完成；尚未使用真实密钥验证服务连通性或搜索质量。

## 启用

在本机 .env 中配置并重启 API：

    AGENT_WEB_SEARCH_ENABLED=true
    AGENT_WEB_SEARCH_API_KEY=你的本地密钥
    AGENT_WEB_SEARCH_TIMEOUT=15

默认关闭。开启但未配置密钥会在启动时提示配置错误。真实密钥不要写入示例文件或提交 Git；配置 repr 和评估报告不包含密钥。

每次请求仍需显式提供 public_web_query，才允许外部搜索：

    {"question":"如何排查通用 VPN 连接问题？","public_web_query":"VPN connection troubleshooting"}

普通 question 请求始终只用本地知识库。public_web_query 表示调用方明确允许发送给 Brave 的公开查询词，最多 600 字符、75 个空白分隔词，不能含内部或敏感内容。程序只发送该字段，不发送本地文档、完整对话或模型改写词。程序不能自动保证调用方提供的查询不含敏感信息。

命令行：

    python -m scripts.demo_query "如何排查通用 VPN 连接问题？" --public-web-query "VPN connection troubleshooting"

该选项仅支持单次提问；独立交互 demo_agent 和默认 benchmark 不自动请求联网。

## 流程

本地 retrieve → grade，必要时最多两次 rewrite。仍不够时，如果配置已开启且请求包含公开查询，才调用 web_search 一次。成功结果经过 web_grade 判断，足够才进入 generate；没有结果或资料不足则正常拒答。服务错误、超时、限流和异常响应会记录工具错误并返回工作流故障，不冒充正常拒答。没有自动网络重试。

网页搜索使用固定 HTTPS API 地址，不跟随重定向，不使用环境代理，读取响应最多 1 MB。网络超时取工具剩余期限与搜索配置中较短者。最多保留 min(top_k, 5) 条有效摘要，过滤无效链接和重复链接，去除摘要 HTML 标签，每条最多 1500 字符。不会将网页结果写入本地向量库。

API citations 新增 url 和 source_type；网页摘要为 web_snippet，本地资料为 local。网页 source 使用真实结果 URL，url 不由生成模型提供；quote 仍须逐字出现在传给模型的摘要中。网页引用页码为 null。终端展示“公开网页摘要”和来源链接。

公开资料判断和生成提示词要求拒绝用网页证明公司内部规定、账号或服务器配置。这仍依赖模型语义判断，不是确定性的制度识别器；涉及内部规则时应保持本地查询。摘要可能不完整或过时，当前验证的是引用与摘要一致，不是逐条事实真伪。

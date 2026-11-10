# 命令行入口

推荐通过一个本地 API 进程统一管理模型与知识库。项目根目录先运行：

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

另一个已激活虚拟环境的终端执行：

    python -m scripts.ingest "C:\资料\指南.pdf"
    python -m scripts.demo_query "指南中有哪些排查步骤？"
    python -m scripts.demo_query
    python -m scripts.demo_query "VPN连接失败怎么办？" --json

不带问题时进入交互问答，q 退出。--json 可保存机器可读响应。两个脚本使用同一 API，上传成功后下一次问答即可检索；脚本自身不加载 Embedding 或生成模型。

可用 --api-url http://127.0.0.1:8001 切换本地端口。仅允许本地 HTTP 地址；连接失败、服务错误和超时返回非零退出码。服务错误显示请求编号，便于对应日志。上传只发送一次，不自动重试；超时后后台可能仍在处理，请勿立即重复上传。

离线本地入口 python -m generation.demo_agent 仍保留：不需要 FastAPI，但直接加载模型，并在启动时恢复已发布上传文档。运行期间 API 新增文档不会自动刷新其快照，需要重启。本机常规使用推荐上述 API 入口，避免重复加载模型或多个写入进程。

原 demo_rag、demo_hybrid、embeddings 演示及 benchmark 继续使用其原始配置语料，作为教学/评估入口，不应误认为它们包含完整上传知识库。

## 管理上传文档

先启动本地 API，然后执行：

    python -m scripts.documents list
    python -m scripts.documents show <document_id>
    python -m scripts.documents delete <document_id>

编号取自上传结果或列表。删除从知识库移除并保留隐藏归档，不会删除基础配置文档。输出为 JSON；失败返回非零退出码，写请求不自动重试。自定义地址放在子命令前：--api-url http://127.0.0.1:8000 list。重新安装本轮源码包后也可使用 it-agent-documents。

## 多轮对话

使用 python -m scripts.sessions create 创建会话，再通过 scripts.demo_query 的 --session-id 选项沿用。show / clear / delete 管理历史。完整示例和内存保留范围见 sessions.md。

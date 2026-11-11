# Docker / Compose 本地部署

需要 Docker Engine/Desktop 与 Compose v2，使用 Linux 容器。当前电脑未安装 Docker 命令，以下配置已完成静态检查和 Python 测试，尚未完成实际镜像构建、启动与持久化验收。

## 启动

在项目根目录依次执行：

```powershell
docker compose config
docker compose build api
docker compose up -d ollama
docker compose exec ollama ollama pull qwen3:8b
docker compose run --rm --no-deps api python -c "from embeddings.embedder import LocalEmbedder; LocalEmbedder()"
docker compose up -d api
```

先确认 Ollama 已启动再下载模型；模型下载失败时先重试该步骤。向量模型预加载也需要网络；缓存存在后重启可以复用。首次构建会下载 Python 依赖，镜像及模型体积较大，默认只配置 CPU，实际耗时和内存需求需在目标机器验证。不会自动复制 Windows 上已有的模型或业务数据。

访问 http://127.0.0.1:8000/docs。`GET /health` 只证明 API 进程可用，knowledge_ready=false 表示尚未初始化问答；Ollama 健康检查也不证明 qwen3:8b 已下载。完成模型准备后，应实际提交问答再验收。查看日志用 `docker compose logs --tail 100 api ollama`。

## 数据与网络

- agent-data 挂载 /data，保存基础文档、上传及归档、索引、SQLite 会话和评估报告。入口仅补齐缺少的示例文档，不覆盖已有文件。Compose 默认使用 SQLite，会话仍受过期时间限制。
- embedding-cache 保存 Hugging Face 缓存；ollama-models 保存 Ollama 模型。
- `docker compose down` 保留命名卷；不要使用 `down -v`，它会删除卷内数据。命名卷不等于备份，重要资料应另外备份。
- API 宿主端口只绑定 127.0.0.1:8000；Ollama 不发布宿主端口，API 通过服务名 ollama 访问。宿主已有 Ollama 的 11434 端口不会冲突。
- 镜像以普通用户 UID 10001 运行；自定义宿主目录挂载时需保证该用户可写。默认命名卷使用镜像中已设置的目录权限。

`.dockerignore` 仅允许打包源代码与元数据，不发送项目 .env、Git、虚拟环境、用户数据、会话、报告和模型缓存。镜像不含 OCR 引擎及 RAGAs 可选依赖；它们需要另建扩展镜像。默认配置没有 GPU、鉴权或公网入口。

## 模型连接配置

`AGENT_OLLAMA_ENDPOINT` 是进程环境变量，只允许 `http://127.0.0.1:11434/api/chat` 和 `http://ollama:11434/api/chat`。Compose 显式使用后者；普通本地运行不设置时行为不变。此项不读取项目 .env，不接受任意远程地址、凭据或查询参数，仍禁用代理与重定向。模型工厂和 RAGAs 共用此客户端。

业务配置可通过 Compose environment 或数据卷 /data/.env 设置；显式环境变量优先。Compose 不把宿主项目 .env 自动作为容器业务配置传入。容器内 API 监听 0.0.0.0，单进程运行；普通 `it-agent-serve` 仍只监听 127.0.0.1。

当前 Ollama 使用 latest 标签，Python 使用 3.13-slim，尚未固定镜像摘要；正式交付前应完成实机验收并固定已验证镜像版本。该配置面向本地演示，不代表生产部署已完成。

参考：[Docker Compose 服务网络](https://docs.docker.com/compose/how-tos/networking/)、[Ollama Docker](https://docs.ollama.com/docker)。

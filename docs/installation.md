# 安装与打包

已验证 Python 3.13 / Windows。保留现有依赖版本，pyproject.toml 从 requirements.txt 读取依赖，避免维护两份列表。打包范围采用明确的模块列表，不包括运行缓存、上传文件、模型、测试及评估报告。

## 从源码安装

在项目根目录且虚拟环境已激活：

    python -m pip install -e .

安装后可使用：it-agent-serve、it-agent-query、it-agent-ingest、it-agent-init。原 python -m 入口仍可用。

## 构建 wheel

    python -m pip wheel . --no-deps --wheel-dir dist
    python -m pip install dist/it_service_desk_agent-0.2.1-py3-none-any.whl

## 安装后运行

例如统一使用 C:\AgentData：

    it-agent-init --data-dir C:\AgentData
    it-agent-serve --data-dir C:\AgentData

另开终端：

    it-agent-query "VPN连接失败怎么办？"
    it-agent-ingest "C:\资料\指南.pdf"

初始化只创建不存在的示例文件，不覆盖用户内容。Ollama 需另行安装、启动并准备 qwen3:8b；首次 Embedding 仍需下载。

源码环境默认使用仓库根目录；wheel 安装默认使用用户目录下 .it-service-desk-agent。可用环境变量 AGENT_HOME 指定运行根目录，服务启动参数 --data-dir 也会设置它。该目录容纳 .env、原始文档、索引及上传文件，避免向 site-packages 写数据。AGENT_HOME 要在进程启动前设置，不能写进 .env 作为定位该文件的依据。

## 本次验证边界

成功构建 wheel，检查安装包未带入运行数据；在项目目录外的新虚拟环境安装，验证命令行帮助、样例初始化及 API 健康响应。验证环境通过 .pth 复用了现有项目的第三方依赖，未重新下载大型模型依赖，因此不是全新机器完整安装或全新模型问答验证。后者仍待执行。

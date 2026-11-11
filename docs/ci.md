# 自动测试与安装包检查

`.github/workflows/ci.yml` 在 push、pull request 和手动触发时执行。Windows 与 Ubuntu 分别使用 Python 3.13；两套任务独立报告结果，同一分支的新提交会取消旧任务。

检查顺序：
1. 安装 requirements.txt 和构建工具，运行 pip check 检查依赖冲突。
2. 运行全部 pytest 测试；任一失败使任务失败，保留 7 天 JUnit 测试结果。
3. 构建 wheel 并安装，然后离开源码目录检查包导入、内置示例、评估题集、/metrics 路由、五个命令入口及数据初始化。

测试期间开启 Hugging Face/Transformers 离线模式，模型和搜索使用现有测试替身；安装 Python 依赖仍需要网络。CI 不启动 Ollama、不下载模型、不使用搜索密钥，也不上传知识库、会话或真实评估报告。OCR 仍由模拟引擎测试。CI 成功不等于真实问答质量通过；真实评估继续按 evaluation.md 在本地运行。

工作流只有 contents: read 权限，检出代码不保留凭据。未配置自动发布或部署，也未修改分支保护规则。若要强制合并前检查通过，需要另行设置仓库规则。

本地验证（2026-11-10）：离线模式下 479 项测试通过，pip check 无冲突，wheel 构建成功；在源码目录外安装至临时目录，使用现有环境依赖检查导入、资源、五个入口和初始化均通过。这不是全新机器依赖安装验证。工作流尚未推送并在 GitHub 执行，Linux 环境与远端首次安装仍待验证。

配置参考官方说明：[setup-python](https://github.com/actions/setup-python)、[checkout](https://github.com/actions/checkout)、[upload-artifact](https://github.com/actions/upload-artifact)。

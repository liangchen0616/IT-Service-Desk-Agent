# 多轮对话

当前实现是单进程内存会话，默认单次问答行为不变。API 请求显式带 session_id 才会读取和记录对应历史；服务重启后历史消失。基础库和上传资料不受清除历史影响。

## API

- POST /sessions：创建会话，返回 session_id，状态码 201；不启动模型。
- POST /chat：原有 question、public_web_query 之外，可增加 session_id。返回 session_id 和 resolved_question，后者为本次实际用于检索和回答的独立问题。
- GET /sessions/{session_id}：查看最近历史，返回 turns 与 turn_count。
- DELETE /sessions/{session_id}/history：清空历史，保留会话编号。
- DELETE /sessions/{session_id}：删除整个会话。

不存在或已过期的会话返回 404，不会偷偷创建同名会话。chat 会话编号格式不正确返回 422。会话数量达到上限时创建返回 409，应删除不再使用的会话。

## 命令行

先启动 API，再创建会话：

    python -m scripts.sessions create

复制返回的编号：

    python -m scripts.demo_query "VPN 连接失败怎么办？" --session-id <编号>
    python -m scripts.demo_query "第二步怎么做？" --session-id <同一编号>
    python -m scripts.sessions show <编号>
    python -m scripts.sessions clear <编号>
    python -m scripts.sessions delete <编号>

也可以 python -m scripts.demo_query --session-id <编号> 进入同一会话的交互提问。独立 generation.demo_agent 仍为单次问答，不自动维护会话。自定义 API 地址参数放在 sessions 子命令之前。

## 工作方式

第一次提问没有历史，不额外调用模型。有历史时，使用已配置的 rewrite 模型（默认共用 qwen3:8b）把追问整理成独立问题，再从头执行 Agent 检索、判断和生成。成功响应的轨迹会包含 contextualize。上下文整理失败返回模型错误，不追加历史；检索或生成失败同样不追加。正常拒答可以进入历史，并记录 answered=false。

历史记录当前问题、整理后的问题、回答和是否作答，不把历史答案、旧引用或旧片段加入新的证据集合。每轮必须重新检索；删除文档后，即使旧回答仍在会话中，也不能继续引用已删除片段。模型整理仍可能误解指代，resolved_question 用于检查理解结果；测试通过不等于真实模型对所有追问都理解准确。

历史不沿用联网授权。外部搜索仍只发送当前请求显式提供的 public_web_query，不发送会话历史或整理后的问题。

## 上限与边界

每个服务进程最多 100 个会话，每会话最多保留最近 6 轮，三项文本总长度合计最多 6000 字符；较旧的整轮记录优先移除。问题与整理问题各截取最多 1000 字符，历史回答最多 2000 字符；这些截取只作用于历史保存，不缩短当次返回的完整答案。会话空闲 1 小时后在后续访问时惰性清理。

会话与问答、入库共用运行时锁，避免读写时交叉修改；当前串行处理，并非多进程共享存储。编号只用于隔离历史，不代表用户身份认证；服务仍定位本机使用。尚未实现磁盘持久化、用户鉴权或多实例会话共享。

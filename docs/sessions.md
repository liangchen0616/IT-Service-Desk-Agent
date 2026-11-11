# 多轮对话

当前支持内存与可选 SQLite 会话，默认单次问答行为不变。API 请求显式带 session_id 才会读取和记录对应历史；默认内存模式在服务重启后历史消失；SQLite 模式保留尚未过期的历史。基础库和上传资料不受清除历史影响。

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

每个服务进程最多 100 个会话，每会话最多保留最近 6 轮，三项文本总长度合计最多 6000 字符；较旧的整轮记录优先移除。问题与整理问题各截取最多 1000 字符，历史回答最多 2000 字符；这些截取只作用于历史保存，不缩短当次返回的完整答案。会话默认空闲 1 小时后在后续访问时惰性清理，AGENT_SESSION_TTL 可设置有效期秒数。

会话与问答、入库共用运行时锁，避免读写时交叉修改；当前完整问答流程仍串行处理；SQLite 的短事务保证单次历史写入原子性，不代表多个服务进程的整轮问答已协调。编号只用于隔离历史，不代表用户身份认证；服务仍定位本机使用。尚未实现用户鉴权或多实例整轮会话协调。

## 开启重启恢复

在本机 .env 中设置后重启服务：

    AGENT_SESSION_BACKEND=sqlite
    AGENT_SESSION_DB_PATH=data/sessions/history.sqlite3
    AGENT_SESSION_TTL=86400

此示例保留空闲一天内的会话；默认仍为 memory 和 3600 秒。相对数据库路径按运行根目录解析，无需额外数据库服务或依赖。仅首次会话操作创建数据库，健康检查不会创建文件或加载模型。重启后使用相同数据库路径与原 session_id 继续问答。

切换存储模式不会自动迁移原内存历史。SQLite 中保存问题、整理后的问题和回答原文，文件未加密；默认 data/sessions/ 已加入 Git 忽略规则，自定义路径应自行保持在版本库之外。请使用 clear/delete 接口清除不再需要的历史；删除记录不等于取证级磁盘擦除。

写入采用事务，失败回滚，已有记录保持完整；数据库损坏或不兼容时返回错误，不会静默清空数据库。过期时间用可持久化的时间戳计算，停机时间也计入有效期。备份应在服务停止后进行，当前没有自动备份或数据库迁移工具。


## 查找已有会话

GET /sessions 返回 sessions 和 total。每项包含 session_id、turn_count（当前保留轮数），按最近活动倒序排列，同一时间按编号倒序。支持内存和 SQLite，SQLite 重启后仍可列出未过期会话；列表不刷新有效期，不返回对话正文，不加载模型。当前为单用户本地服务，不提供按用户权限筛选。

命令：`python -m scripts.sessions list`，随后使用返回编号继续追问或查看历史。


追问条件保护：指代补全后保留当前用户原句，防止模型改写丢失已完成步骤、否定和限制条件。若原句已完整出现在改写中则不重复；组合超过 1000 字符时回退到完整原问题，不截断条件，此时可能失去历史指代补全。回答优先处理未解决步骤，但用户陈述仍不作为知识库事实证据。

# API 使用

启动（单进程）：

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

交互文档：http://127.0.0.1:8000/docs

## GET /health

返回 status=ok、knowledge_ready。检查进程是否响应，不探测 Ollama 或代表所有模型已就绪。

## POST /chat

JSON：{"question":"VPN连接失败怎么办？"}，问题长度 1–1000，不能为空白。

响应：answer、answered、citations、retry_count、trace。citations 包含 source_id、source、chunk_index、start_index、end_index、quote、page。page 为 PDF 物理页码（从 1 开始，包含空白页），TXT/MD 为 null；不是纸面印刷页号。trace 包含 node、elapsed_ms、retry_count、status，检索节点另含 sources。

证据不足是正常 200 响应，answered=false。输入无效 422；模型执行失败 503；未处理内部故障 500（具体信息记录日志）。

## POST /documents

multipart/form-data，字段 file。PDF/TXT/MD，最多 5 MiB，TXT/MD 要求 UTF-8。

201：document_id、filename、chunk_count。成功才发布到知识库；同名上传不会覆盖原文件。400 为无效格式/内容/文件名；413 为超限。上传完成后即可通过 /chat 提问。

首次问答或有效上传会初始化模型，可能需要较长时间。当前串行执行，客户端超时不等于服务器取消任务；不要据此反复上传。

### 错误与请求追踪

每次请求返回 `X-Request-ID` 响应头；错误正文包含 `detail`、`code`、`request_id`，成功正文不变。参数校验错误统一为简短说明。模型失败为 503，其他工作流失败为 500，资料不足仍返回 200。具体日志格式见 [日志与异常](observability.md)。

## 上传文档管理

- GET /documents：返回 documents 列表和 total，只包含通过上传接口发布的文档；每项有 document_id、filename、file_type、size_bytes。
- GET /documents/{document_id}：返回上述信息和最多 2000 字符的 text_preview、preview_truncated、PDF page_count（其他文件为 null）。
- DELETE /documents/{document_id}：返回 document_id、filename、deleted=true。从检索和列表中移除指定上传；无效编号、不存在或已移除返回 404。

列表和详情不会初始化模型。运行中的删除先构建替代索引，成功后将上传目录原子改名为 .deleted-<id>-<随机编号>，再发布新运行时；重建或改名失败时旧知识库仍可用。未初始化时只归档文件，下次初始化自然排除该文档。同名上传靠 document_id 区分，基础配置文档不在该删除接口范围内。

这是可恢复删除，归档仍占磁盘空间，保留原文与缓存；不属于彻底擦除。当前没有恢复/清空归档接口。重启跳过所有隐藏归档和未完成上传目录。仍采用单进程、共享锁模型；独立本地 demo_agent 为启动快照，API 删除后需重启它才能同步。

检索轨迹新增 trace[].tool：name、call_number、status、elapsed_ms、error_code。工具失败进入错误处理，不作为正常拒答；具体期限与调用限制见 tools.md。

## 可选公开查询

POST /chat 可额外传 public_web_query（非空，最多 600 字符、75 个词）。它明确允许发送给外部搜索服务；不传时保持纯本地。服务未启用搜索时传入该字段返回 400，格式无效为 422。开启方式和行为见 web_search.md。

citations 新增 url（本地为 null）与 source_type（local 或 web_snippet）。本地证据不足后的网页搜索仅执行一次，trace 新增 web_search 和 web_grade 节点。网页引用对应搜索摘要，不代表已抓取网页全文。

## 会话问答

POST /chat 可增加 session_id；响应新增 session_id 和 resolved_question。有历史时 trace 增加 contextualize。会话创建、查看、清除、删除及限制详见 sessions.md。不提供 session_id 时仍不使用历史。

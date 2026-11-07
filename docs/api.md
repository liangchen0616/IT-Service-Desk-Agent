# API 使用

启动（单进程）：

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

交互文档：http://127.0.0.1:8000/docs

## GET /health

返回 status=ok、knowledge_ready。检查进程是否响应，不探测 Ollama 或代表所有模型已就绪。

## POST /chat

JSON：{"question":"VPN连接失败怎么办？"}，问题长度 1–1000，不能为空白。

响应：answer、answered、citations、retry_count、trace。citations 包含 source_id、source、chunk_index、start_index、end_index、quote。trace 包含 node、elapsed_ms、retry_count、status，检索节点另含 sources。

证据不足是正常 200 响应，answered=false。输入无效 422；模型执行失败 503；未处理内部故障 500（具体信息记录日志）。

## POST /documents

multipart/form-data，字段 file。PDF/TXT/MD，最多 5 MiB，TXT/MD 要求 UTF-8。

201：document_id、filename、chunk_count。成功才发布到知识库；同名上传不会覆盖原文件。400 为无效格式/内容/文件名；413 为超限。上传完成后即可通过 /chat 提问。

首次问答或有效上传会初始化模型，可能需要较长时间。当前串行执行，客户端超时不等于服务器取消任务；不要据此反复上传。

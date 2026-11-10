"""Local API client shared by command-line tools; no automatic write retries."""
from pathlib import Path
from urllib.parse import urlsplit
import httpx


class ClientError(RuntimeError): pass


class ApiClient:
    def __init__(self, base_url="http://127.0.0.1:8000", timeout=1200, transport=None):
        url = urlsplit(base_url)
        if url.scheme != 'http' or url.hostname not in {'127.0.0.1','localhost','::1'} or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
            raise ValueError("API address must be a local HTTP origin")
        self.client = httpx.Client(base_url=base_url, timeout=httpx.Timeout(timeout, connect=5),
            trust_env=False, follow_redirects=False, transport=transport)

    def close(self): self.client.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def request(self, method, path, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ClientError("请求超时；服务可能仍在处理，请勿立即重复上传。") from exc
        except httpx.RequestError as exc:
            raise ClientError("无法连接本地 API，请先启动 python -m uvicorn app.main:app") from exc
        if not 200 <= response.status_code < 300:
            try: payload = response.json()
            except ValueError: payload = {}
            detail = payload.get('detail', '服务请求失败') if isinstance(payload, dict) else '服务请求失败'
            identifier = response.headers.get('x-request-id', '-')
            raise ClientError(f"HTTP {response.status_code}: {detail}（请求编号：{identifier}）")
        try:
            value = response.json()
        except ValueError as exc: raise ClientError("服务返回了无效 JSON") from exc
        if not isinstance(value, dict): raise ClientError("服务返回了无效数据结构")
        return value

    def ask(self, question, public_web_query=None, session_id=None):
        if not isinstance(question, str) or not question.strip() or len(question) > 1000:
            raise ClientError("问题需为 1–1000 个字符")
        payload={'question':question.strip()}
        if public_web_query is not None: payload['public_web_query']=public_web_query
        if session_id is not None: payload['session_id']=session_id
        value = self.request('POST', '/chat', json=payload)
        if not isinstance(value.get('answer'), str) or type(value.get('answered')) is not bool or not isinstance(value.get('citations'),list) or not isinstance(value.get('trace'),list) or type(value.get('retry_count')) is not int:
            raise ClientError("服务返回了无效问答结果")
        for citation in value['citations']:
            if not isinstance(citation,dict) or not isinstance(citation.get('source'),str) or not isinstance(citation.get('quote'),str) or type(citation.get('source_id')) is not int:
                raise ClientError("服务返回了无效引用")
        return value

    def upload(self, filename):
        path = Path(filename)
        if path.suffix.lower() not in {'.txt','.md','.pdf'}: raise ClientError("仅支持 TXT、MD、PDF")
        try:
            with path.open('rb') as handle: data = handle.read(5*1024*1024+1)
        except OSError as exc: raise ClientError("无法读取指定文件") from exc
        if not data or len(data)>5*1024*1024: raise ClientError("文件不能为空且不能超过 5 MiB")
        return self.request('POST','/documents',files={'file':(path.name,data)})

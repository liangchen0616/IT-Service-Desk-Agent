from dataclasses import replace
from pathlib import PureWindowsPath
from ntpath import isreserved
from tempfile import TemporaryDirectory
from uuid import uuid4
from pypdf.errors import PdfReadError
from ingestion.knowledge_base import build_knowledge_base, load_documents
from app.schemas.document import DocumentResponse

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class InvalidDocument(ValueError): pass


def validate_name(name):
    if (not name or len(name) > 150 or name != PureWindowsPath(name).name
        or any(c in name for c in '/\\:<>"|?*') or any(ord(c) < 32 for c in name)
        or isreserved(name) or name.endswith((' ', '.'))):
        raise InvalidDocument("请使用普通文件名")
    if PureWindowsPath(name).suffix.lower() not in {'.pdf', '.txt', '.md'}:
        raise InvalidDocument("仅支持 PDF、TXT、MD")


def ingest(runtime, name, data):
    validate_name(name)
    if not data or len(data) > MAX_UPLOAD_BYTES: raise InvalidDocument("文件为空或超过 5 MiB")
    with runtime.lock:
        runtime.uploads.mkdir(parents=True, exist_ok=True)
        document_id = uuid4().hex
        with TemporaryDirectory(prefix='.pending-', dir=runtime.uploads) as temporary:
            from pathlib import Path
            staging = Path(temporary)
            documents = staging / 'documents'
            documents.mkdir()
            (documents / name).write_bytes(data)
            config = replace(runtime.config, documents_dir=documents,
                file_names=(name,), index_path=staging / 'index.json')
            try:
                parsed = load_documents(config)
                if not any(d.content.strip() for d in parsed): raise InvalidDocument("文档没有可用文本")
            except (UnicodeError, PdfReadError) as exc:
                raise InvalidDocument("文档无法解析，请检查格式和 UTF-8 编码") from exc
            runtime.ensure_ready()
            kb = build_knowledge_base(config, runtime.embedder, use_cache=True)
            combined = runtime.items + kb.retriever.store.export_items()
            agent = runtime.make_agent(combined)
            # Publish only after parsing, embedding and index construction succeed.
            destination = runtime.uploads / document_id
            staging.rename(destination)
            runtime.items, runtime.agent = combined, agent
        return DocumentResponse(document_id=document_id, filename=name, chunk_count=kb.chunk_count)

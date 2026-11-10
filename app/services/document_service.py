from dataclasses import replace
from pathlib import PureWindowsPath
from ntpath import isreserved
from tempfile import TemporaryDirectory
from uuid import uuid4
from pypdf.errors import PdfReadError
from ingestion.knowledge_base import build_knowledge_base, load_documents
from app.schemas.document import DocumentResponse, DocumentInfo, DocumentDetail, DocumentList, DocumentDeleted
from app.services.upload_catalog import find_upload, published_uploads, tag_upload

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


from core.exceptions import InvalidDocument


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
            combined = runtime.items + tag_upload(kb.retriever.store.export_items(), document_id)
            agent = runtime.make_agent(combined)
            # Publish only after parsing, embedding and index construction succeed.
            destination = runtime.uploads / document_id
            staging.rename(destination)
            runtime.items, runtime.agent = combined, agent
        return DocumentResponse(document_id=document_id, filename=name, chunk_count=kb.chunk_count)


def describe_upload(folder, document):
    return DocumentInfo(document_id=folder.name, filename=document.name,
                        file_type=document.suffix.lower().lstrip("."), size_bytes=document.stat().st_size)


def list_documents(runtime):
    with runtime.lock:
        documents = [describe_upload(folder, path) for folder, path in published_uploads(runtime.uploads)]
        return DocumentList(documents=documents, total=len(documents))


def get_document(runtime, document_id):
    with runtime.lock:
        folder, path = find_upload(runtime.uploads, document_id)
        config = replace(runtime.config, documents_dir=folder / "documents",
                         file_names=(path.name,), index_path=folder / "index.json")
        parsed = load_documents(config)[0]
        return DocumentDetail(**describe_upload(folder, path).model_dump(),
            text_preview=parsed.content[:2000], preview_truncated=len(parsed.content) > 2000,
            page_count=parsed.metadata.get("page_count"))


def delete_document(runtime, document_id):
    with runtime.lock:
        folder, path = find_upload(runtime.uploads, document_id)
        combined, agent = None, None
        if runtime.agent is not None:
            combined = [item for item in runtime.items
                        if item.chunk.metadata.get("document_id") != document_id]
            agent = runtime.make_agent(combined)
        # Atomic publication change: readers and startup ignore hidden archives.
        # Build the replacement first, so failure leaves the active document intact.
        archive = runtime.uploads / (".deleted-" + document_id + "-" + uuid4().hex)
        if archive.resolve().parent != runtime.uploads.resolve():
            raise ValueError("Invalid archive destination")
        folder.rename(archive)
        if combined is not None:
            runtime.items, runtime.agent = combined, agent
        return DocumentDeleted(document_id=document_id, filename=path.name, deleted=True)

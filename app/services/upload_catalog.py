"""Locate published uploads without loading embedding or language models."""
import re
from core.exceptions import DocumentNotFound


def find_upload(uploads, document_id):
    if not isinstance(document_id, str) or not re.fullmatch(r"[0-9a-f]{32}", document_id):
        raise DocumentNotFound("文档不存在")
    return _find_folder(uploads, document_id)


def _find_folder(uploads, name):
    folder = uploads / name
    if (not folder.is_dir() or folder.is_symlink() or folder.is_junction()
            or folder.resolve().parent != uploads.resolve()):
        raise DocumentNotFound("文档不存在")
    documents = folder / "documents"
    if (not documents.is_dir() or documents.is_symlink() or documents.is_junction()
            or documents.resolve().parent != folder.resolve()):
        raise ValueError("Invalid stored upload directory")
    files = list(documents.iterdir())
    if (len(files) != 1 or not files[0].is_file() or files[0].is_symlink()
            or files[0].resolve().parent != documents.resolve()):
        raise ValueError("Invalid stored upload document")
    return folder, files[0]


def published_uploads(uploads):
    if not uploads.exists(): return []
    return [find_upload(uploads, folder.name) for folder in sorted(uploads.iterdir())
            if folder.is_dir() and not folder.name.startswith(".")]


def tag_upload(items, document_id):
    # Exported chunks are owned by this runtime, not the persisted vector cache.
    for item in items:
        item.chunk.metadata["document_id"] = document_id
    return items


def find_archive(uploads, archive_id):
    if not isinstance(archive_id,str) or not re.fullmatch(r"[0-9a-f]{32}-[0-9a-f]{32}",archive_id):
        raise DocumentNotFound("归档不存在")
    folder,document=_find_folder(uploads,".deleted-"+archive_id)
    index=folder/"index.json"
    if index.is_symlink() or index.resolve().parent!=folder.resolve():
        raise ValueError("Invalid archived index path")
    return folder,document


def archived_uploads(uploads):
    if not uploads.exists(): return []
    return [(folder.name[len(".deleted-"):], *find_archive(uploads,folder.name[len(".deleted-"):]))
            for folder in sorted(uploads.iterdir())
            if folder.is_dir() and re.fullmatch(r"\.deleted-[0-9a-f]{32}-[0-9a-f]{32}",folder.name)]

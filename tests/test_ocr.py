from dataclasses import replace
from types import SimpleNamespace
import subprocess
import sys
import pytest
from ingestion.loader import DocumentLoader
from ingestion.chunker import DocumentChunker
from ingestion.knowledge_base import compute_signature
from ingestion.ocr import TesseractOcr
from core.config import ProjectConfig
from core.exceptions import InvalidDocument,OcrError
from app.main import create_app
from fastapi.testclient import TestClient


def test_mixed_pages_preserve_text_and_page_numbers(tmp_path,monkeypatch):
    path=tmp_path/'mixed.pdf';path.write_bytes(b'fake')
    monkeypatch.setattr('ingestion.loader.PdfReader',lambda p:SimpleNamespace(pages=[
        SimpleNamespace(extract_text=lambda:'Native text'),SimpleNamespace(extract_text=lambda:''),
        SimpleNamespace(extract_text=lambda:'')]))
    calls=[]
    class Ocr:
        def read_page(self,path,page):
            calls.append(page)
            return 'Scanned instructions' if page==2 else ''
    document=DocumentLoader(Ocr()).load_pdf(path)
    chunks=DocumentChunker(100,10).chunk_document(document)
    assert calls==[2,3]
    assert document.metadata['page_count']==3
    assert [c.metadata['page'] for c in chunks]==[1,2]
    assert chunks[1].metadata['extraction_method']=='ocr'
    assert chunks[0].content=='Native text'
    assert document.content[chunks[1].start_index:chunks[1].end_index]==chunks[1].content
    with pytest.raises(InvalidDocument):DocumentLoader(Ocr(),ocr_max_pages=1).load_pdf(path)
    assert DocumentLoader().load_pdf(path).content=='Native text\n\n\n\n'


def test_ocr_settings_change_cache_signature(tmp_path):
    (tmp_path/'guide.txt').write_text('text')
    config=ProjectConfig(documents_dir=tmp_path,file_names=('guide.txt',))
    assert compute_signature(config)!=compute_signature(replace(config,ocr_enabled=True))
    assert compute_signature(replace(config,ocr_enabled=True))!=compute_signature(replace(config,ocr_enabled=True,ocr_language='eng'))


@pytest.mark.parametrize('failure',[None,'timeout','missing'])
def test_engine_command_cleanup_and_errors(tmp_path,monkeypatch,failure):
    closed=[]
    class Image:
        def close(self):closed.append('image')
        def save(self,path):path.write_bytes(b'image')
    class Bitmap:
        def close(self):closed.append('bitmap')
        def to_pil(self):return Image()
    class Page:
        def close(self):closed.append('page')
        def get_size(self):return 600,800
        def render(self,**kwargs):return Bitmap()
    class Pdf:
        def __init__(self,path):pass
        def close(self):closed.append('pdf')
        def __getitem__(self,index):assert index==1;return Page()
    monkeypatch.setitem(sys.modules,'pypdfium2',SimpleNamespace(PdfDocument=Pdf))
    paths=[]
    def run(args,**kwargs):
        from pathlib import Path
        paths.append(Path(args[1]).parent)
        assert args[0]=='tesseract' and args[-2:]==['-l','eng']
        assert kwargs['timeout']==4 and not kwargs.get('shell',False)
        if failure=='timeout':raise subprocess.TimeoutExpired(args,4)
        if failure=='missing':raise FileNotFoundError()
        Path(args[2]+'.txt').write_text('OCR words',encoding='utf-8')
    monkeypatch.setattr('ingestion.ocr.subprocess.run',run)
    if failure:
        with pytest.raises(OcrError):TesseractOcr('eng',4).read_page(tmp_path/'doc.pdf',2)
    else:assert TesseractOcr('eng',4).read_page(tmp_path/'doc.pdf',2)=='OCR words'
    assert closed==['image','bitmap','page','pdf']
    assert not paths[0].exists()


def test_ocr_error_has_explicit_api_response():
    app=create_app(SimpleNamespace())
    @app.get('/ocr-failure')
    def fail():raise OcrError('OCR 识别超时')
    response=TestClient(app).get('/ocr-failure')
    assert response.status_code==503 and response.json()['code']=='ocr_unavailable'


@pytest.mark.parametrize('kwargs',[{'ocr_language':'../eng'},{'ocr_timeout':0},{'ocr_max_pages':True},{'ocr_enabled':'yes'}])
def test_invalid_ocr_config(kwargs):
    with pytest.raises(ValueError):ProjectConfig(**kwargs)

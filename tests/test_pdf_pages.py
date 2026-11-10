import io
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.main import create_app
from app.services.runtime import Runtime
from embeddings.embedder import EmbeddedChunk
from ingestion.loader import DocumentLoader
from ingestion.chunker import DocumentChunker
from ingestion.boundary_chunker import BoundaryChunker
from project_config import ProjectConfig
from scripts.demo_query import display


def pdf_bytes():
    writer = PdfWriter()
    for text in ['First page guide.', '', 'Restart VPN client.']:
        page = writer.add_blank_page(300, 300)
        if text:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 20 250 Td ({text}) Tj ET'.encode())
            page[NameObject('/Contents')] = stream
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize('chunker_type', [DocumentChunker, BoundaryChunker])
@pytest.mark.parametrize('size,overlap', [(100, 10), (8, 3)])
def test_pdf_page_boundaries_and_global_offsets(tmp_path, chunker_type, size, overlap):
    path = tmp_path / 'guide.pdf'
    path.write_bytes(pdf_bytes())
    doc = DocumentLoader().load_pdf(path)
    chunks = chunker_type(size, overlap).chunk_document(doc)
    assert doc.metadata['page_count'] == 3
    assert {c.metadata['page'] for c in chunks} == {1, 3}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        start, end = doc.page_spans[chunk.metadata['page'] - 1]
        assert start <= chunk.start_index < chunk.end_index <= end
        assert chunk.content == doc.content[chunk.start_index:chunk.end_index]
    for page in [1, 3]:
        start, end = doc.page_spans[page - 1]
        covered = {i for c in chunks if c.metadata['page'] == page for i in range(c.start_index, c.end_index)}
        assert covered == set(range(start, end))


class Embedder:
    def embed_chunks(self, chunks):
        return [EmbeddedChunk(c, [1., 0.]) for c in chunks]
    def embed_query(self, query):
        return [1., 0.]


class Model:
    def generate(self, messages, schema):
        if 'sufficient' in schema['properties']:
            return {'sufficient': True}
        sources = json.loads(messages[1]['content'])['sources']
        source = next(s for s in sources if 'Restart VPN client.' in s['content'])
        return {'answerable': True, 'answer': 'Restart VPN client.',
                'evidence': [{'source_id': source['source_id'], 'quote': 'Restart VPN client.'}]}


def test_pdf_upload_citation_survives_restart(tmp_path, capsys):
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'base.txt').write_text('Base knowledge.', encoding='utf-8')
    config = ProjectConfig(documents_dir=docs, file_names=('base.txt',), index_path=tmp_path/'base.json')
    runtime = Runtime(config, tmp_path/'uploads', Embedder(), Model())
    with TestClient(create_app(runtime)) as client:
        response = client.post('/documents', files={'file': ('guide.pdf', pdf_bytes(), 'application/pdf')})
        assert response.status_code == 201, response.text
        assert response.json()['chunk_count'] == 2
    for instance in [runtime, Runtime(config, runtime.uploads, Embedder(), Model())]:
        with TestClient(create_app(instance)) as client:
            response = client.post('/chat', json={'question': 'Restart VPN client'})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['answered']
            assert result['citations'][0]['page'] == 3
            assert result['citations'][0]['source'] == 'guide.pdf'
            assert result['citations'][0]['quote'] == 'Restart VPN client.'
            assert next(i for i in instance.items if i.chunk.metadata['source'] == 'base.txt').chunk.metadata.get('page') is None
            display(result)
    assert '第 3 页' in capsys.readouterr().out


import pytest

from ingestion.loader import Document, DocumentLoader


def test_load_txt_success(tmp_path):
    # Arrange: create a temporary TXT document
    file_path = tmp_path / "vpn_guide.txt"
    file_path.write_text(
        "VPN connection failed.",
        encoding="utf-8",
    )

    # Act: load the document
    loader = DocumentLoader()
    document = loader.load_txt(str(file_path))

    # Assert: check the result
    assert isinstance(document, Document)
    assert document.content == "VPN connection failed."
    assert document.metadata["source"] == "vpn_guide.txt"
    assert document.metadata["file_type"] == "txt"


def test_load_txt_file_not_found():
    loader = DocumentLoader()

    with pytest.raises(FileNotFoundError):
        loader.load_txt("data/documents/not_exist.txt")


def test_load_txt_invalid_format(tmp_path):
    file_path = tmp_path / "guide.pdf"
    file_path.write_text("Test content", encoding="utf-8")

    loader = DocumentLoader()

    with pytest.raises(ValueError):
        loader.load_txt(str(file_path))


def test_load_txt_supports_chinese(tmp_path):
    file_path = tmp_path / "chinese_guide.txt"

    file_path.write_text(
        "VPN连接失败，请检查网络设置。",
        encoding="utf-8",
    )

    loader = DocumentLoader()
    document = loader.load_txt(str(file_path))

    assert document.content == "VPN连接失败，请检查网络设置。"


def test_load_markdown_success(tmp_path):
    # Arrange: create a temporary Markdown document
    file_path = tmp_path / "git_guide.md"

    markdown_content = (
        "# Git Troubleshooting Guide\n\n"
        "## Possible Causes\n\n"
        "1. Authentication failed.\n"
        "2. Network connection is unavailable.\n"
    )

    file_path.write_text(
        markdown_content,
        encoding="utf-8",
    )

    # Act: load the Markdown document
    loader = DocumentLoader()
    document = loader.load_markdown(str(file_path))

    # Assert: check the result
    assert isinstance(document, Document)
    assert document.content == markdown_content
    assert document.metadata["source"] == "git_guide.md"
    assert document.metadata["file_type"] == "md"


def test_load_markdown_invalid_format(tmp_path):
    file_path = tmp_path / "guide.txt"
    file_path.write_text("Test content", encoding="utf-8")

    loader = DocumentLoader()

    with pytest.raises(ValueError):
        loader.load_markdown(str(file_path))

def test_load_pdf_success(tmp_path, monkeypatch):
    # Arrange: create a temporary PDF file
    file_path = tmp_path / "it_manual.pdf"
    file_path.write_bytes(b"fake pdf content")

    # Create fake PDF pages
    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    # Create a fake PDF reader
    class FakePdfReader:
        def __init__(self, path):
            self.pages = [
                FakePage("VPN Troubleshooting Guide"),
                FakePage("Check your network connection."),
            ]

    # Replace the real PdfReader with our fake reader
    monkeypatch.setattr(
        "ingestion.loader.PdfReader",
        FakePdfReader,
    )

    # Act: load the PDF document
    loader = DocumentLoader()
    document = loader.load_pdf(str(file_path))

    # Assert: check the result
    assert isinstance(document, Document)

    assert document.content == (
        "VPN Troubleshooting Guide\n\n"
        "Check your network connection."
    )

    assert document.metadata["source"] == "it_manual.pdf"
    assert document.metadata["file_type"] == "pdf"
    assert document.metadata["page_count"] == 2


def test_load_pdf_file_not_found():
    loader = DocumentLoader()

    with pytest.raises(FileNotFoundError):
        loader.load_pdf("data/documents/nonexistent.pdf")


def test_load_pdf_invalid_format(tmp_path):
    file_path = tmp_path / "guide.txt"
    file_path.write_text("Test content", encoding="utf-8")

    loader = DocumentLoader()

    with pytest.raises(ValueError):
        loader.load_pdf(str(file_path))


from dataclasses import dataclass
from pathlib import Path
from pypdf import PdfReader


@dataclass
class Document:
    """A standardized document object."""

    content: str
    metadata: dict
    # Offsets in content, including empty pages; physical PDF order starts at 1.
    page_spans: list[tuple[int, int]] | None = None


class DocumentLoader:
    """Load text documents from the knowledge base."""

    def __init__(self, ocr=None, ocr_max_pages=30):
        self.ocr,self.ocr_max_pages=ocr,ocr_max_pages

    def load_txt(self, file_path: str) -> Document:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if path.suffix.lower() != ".txt":
            raise ValueError("Only TXT files are supported currently.")

        content = path.read_text(encoding="utf-8")

        metadata = {
            "source": path.name,
            "file_type": path.suffix.lower().lstrip("."),
        }

        return Document(
            content=content,
            metadata=metadata,
        )

    
    def load_markdown(self, file_path: str) -> Document:
        """Load a Markdown document."""

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if path.suffix.lower() != ".md":
            raise ValueError("Only Markdown files are supported.")

        content = path.read_text(encoding="utf-8")

        metadata = {
            "source": path.name,
            "file_type": "md",
        }

        return Document(
            content=content,
            metadata=metadata,
        )
    
    def load_pdf(self, file_path: str) -> Document:
        """Load a PDF document."""

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are supported.")

        reader = PdfReader(str(path))

        page_texts = []
        ocr_pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip() and self.ocr is not None:
                if len(ocr_pages)>=self.ocr_max_pages:
                    from core.exceptions import InvalidDocument
                    raise InvalidDocument("待识别页数超过 OCR 限制")
                text=self.ocr.read_page(path,page_number)
                ocr_pages.append(page_number)
            page_texts.append(text)

        content = "\n\n".join(page_texts)
        page_spans = []
        offset = 0
        for text in page_texts:
            page_spans.append((offset, offset + len(text)))
            offset += len(text) + 2

        metadata = {
            "source": path.name,
            "file_type": "pdf",
            "page_count": len(reader.pages),
            "ocr_pages": ocr_pages,
        }

        return Document(
            content=content,
            metadata=metadata,
            page_spans=page_spans,
        )




from dataclasses import dataclass
from pathlib import Path
from pypdf import PdfReader


@dataclass
class Document:
    """A standardized document object."""

    content: str
    metadata: dict


class DocumentLoader:
    """Load text documents from the knowledge base."""

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

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            page_texts.append(text)

        content = "\n\n".join(page_texts)

        metadata = {
            "source": path.name,
            "file_type": "pdf",
            "page_count": len(reader.pages),
        }

        return Document(
            content=content,
            metadata=metadata,
        )



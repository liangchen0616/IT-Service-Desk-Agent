from dataclasses import dataclass
from math import isfinite
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ProjectConfig:
    documents_dir: Path = PROJECT_ROOT / "data" / "documents"
    file_names: tuple[str, ...] = (
        "vpn_guide_zh.txt",
        "printer_guide_zh.txt",
    )
    model_name: str = "Qwen/Qwen3-Embedding-0.6B"
    chunk_mode: str = "boundary"
    chunk_size: int = 300
    overlap: int = 50
    top_k: int = 3
    min_score: float | None = 0.5
    index_path: Path = PROJECT_ROOT / "data" / "indexes" / "knowledge_base.json"

    def __post_init__(self):
        object.__setattr__(self, "documents_dir", Path(self.documents_dir).resolve())
        object.__setattr__(self, "index_path", Path(self.index_path).resolve())
        if not self.file_names or len(set(self.file_names)) != len(self.file_names):
            raise ValueError("file_names must be nonempty and unique.")
        for name in self.file_names:
            if not isinstance(name, str) or not name or Path(name).name != name:
                raise ValueError("Each file name must be a plain file name.")
            if Path(name).suffix.lower() not in {".txt", ".md", ".pdf"}:
                raise ValueError(f"Unsupported document type: {name}")
            if self.index_path == self.documents_dir / name:
                raise ValueError("index_path must not overwrite a source document.")
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError("model_name must not be empty.")
        if self.chunk_mode not in {"boundary", "fixed"}:
            raise ValueError("chunk_mode must be boundary or fixed.")
        for name in ("chunk_size", "overlap", "top_k"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"{name} must be an integer.")
        if self.chunk_size <= 0 or not 0 <= self.overlap < self.chunk_size:
            raise ValueError("Require chunk_size > 0 and 0 <= overlap < chunk_size.")
        if self.top_k <= 0:
            raise ValueError("top_k must be greater than 0.")
        if self.min_score is not None:
            if type(self.min_score) not in (int, float):
                raise TypeError("min_score must be numeric or None.")
            if not isfinite(self.min_score) or not -1 <= self.min_score <= 1:
                raise ValueError("min_score must be finite and between -1 and 1.")

    def to_report(self) -> dict:
        return {
            "model": self.model_name,
            "documents_dir": str(self.documents_dir),
            "file_names": list(self.file_names),
            "chunk_mode": self.chunk_mode,
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
            "top_k": self.top_k,
            "min_score": self.min_score,
            "index_path": str(self.index_path),
        }

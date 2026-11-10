from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
import os


def resolve_project_root():
    override = os.environ.get("AGENT_HOME")
    if override:
        return Path(override).expanduser().resolve()
    source = Path(__file__).resolve().parents[1]
    if (source / "pyproject.toml").is_file() and (source / "requirements.txt").is_file():
        return source
    return Path.home() / ".it-service-desk-agent"


PROJECT_ROOT = resolve_project_root()


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

    llm_model: str = "qwen3:8b"
    llm_grade_model: str | None = None
    llm_rewrite_model: str | None = None
    web_search_enabled: bool = False
    web_search_api_key: str = field(default="", repr=False)
    web_search_timeout: float = 15
    tool_timeout: float = 180
    llm_timeout: float = 180
    candidate_k: int = 20
    rank_constant: int = 60
    max_context_chars: int = 2000
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_batch_size: int = 8

    def __post_init__(self):
        if type(self.web_search_enabled) is not bool: raise ValueError("web_search_enabled must be boolean")
        if not isinstance(self.web_search_api_key,str): raise ValueError("Invalid web search key")
        if self.web_search_enabled and not self.web_search_api_key.strip():
            raise ValueError("Enabled web search requires AGENT_WEB_SEARCH_API_KEY")
        if type(self.web_search_timeout) not in (int,float) or not isfinite(self.web_search_timeout) or self.web_search_timeout<=0:
            raise ValueError("web_search_timeout must be positive and finite")
        if type(self.tool_timeout) not in (int, float) or not isfinite(self.tool_timeout) or self.tool_timeout <= 0:
            raise ValueError("tool_timeout must be positive and finite")
        for field in ("llm_grade_model", "llm_rewrite_model"):
            name = getattr(self, field)
            if name is not None and (not isinstance(name, str) or not name.strip() or name.strip().endswith(("-cloud", ":cloud"))):
                raise ValueError(f"{field} must name a local model or be None")
        if type(self.reranker_enabled) is not bool: raise ValueError("reranker_enabled must be boolean")
        if not isinstance(self.reranker_model,str) or not self.reranker_model.strip(): raise ValueError("reranker_model must not be blank")
        if type(self.reranker_batch_size) is not int or self.reranker_batch_size <= 0: raise ValueError("reranker_batch_size must be positive")
        for name in ("candidate_k", "rank_constant", "max_context_chars"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.llm_model, str) or not self.llm_model.strip() or self.llm_model.strip().endswith(("-cloud", ":cloud")):
            raise ValueError("llm_model must name a local model")
        if type(self.llm_timeout) not in (int, float) or not isfinite(self.llm_timeout) or self.llm_timeout <= 0:
            raise ValueError("llm_timeout must be positive and finite")
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
            "reranker_enabled": self.reranker_enabled,
            "reranker_model": self.reranker_model,
            "reranker_batch_size": self.reranker_batch_size,
            "llm_model": self.llm_model,
            "llm_grade_model": self.llm_grade_model or self.llm_model,
            "llm_rewrite_model": self.llm_rewrite_model or self.llm_model,
            "llm_timeout": self.llm_timeout,
            "tool_timeout": self.tool_timeout,
            "web_search_enabled": self.web_search_enabled,
            "web_search_timeout": self.web_search_timeout,
            "candidate_k": self.candidate_k,
            "rank_constant": self.rank_constant,
            "max_context_chars": self.max_context_chars,
            "documents_dir": str(self.documents_dir),
            "file_names": list(self.file_names),
            "chunk_mode": self.chunk_mode,
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
            "top_k": self.top_k,
            "min_score": self.min_score,
            "index_path": str(self.index_path),
        }



def parse_bool(value):
    if value.lower() not in {"true", "false"}: raise ValueError("Expected true or false")
    return value.lower() == "true"


def load_config(env_file=None, environ=None):
    """Read project .env, then environment overrides; never mutate os.environ."""
    import os
    import json
    from dotenv import dotenv_values
    values = dict(dotenv_values(env_file if env_file is not None else PROJECT_ROOT / ".env", interpolate=False))
    values.update(os.environ if environ is None else environ)
    conversions = {
        "WEB_SEARCH_ENABLED": ("web_search_enabled", parse_bool),
        "WEB_SEARCH_API_KEY": ("web_search_api_key", str),
        "WEB_SEARCH_TIMEOUT": ("web_search_timeout", float),
        "TOOL_TIMEOUT": ("tool_timeout", float),
        "LLM_GRADE_MODEL": ("llm_grade_model", lambda v: v.strip() or None),
        "LLM_REWRITE_MODEL": ("llm_rewrite_model", lambda v: v.strip() or None),
        "RERANKER_ENABLED": ("reranker_enabled", parse_bool),
        "RERANKER_MODEL": ("reranker_model", str),
        "RERANKER_BATCH_SIZE": ("reranker_batch_size", int),
        "MODEL_NAME": ("model_name", str), "LLM_MODEL": ("llm_model", str),
        "LLM_TIMEOUT": ("llm_timeout", float), "TOP_K": ("top_k", int),
        "CANDIDATE_K": ("candidate_k", int), "RANK_CONSTANT": ("rank_constant", int),
        "MAX_CONTEXT_CHARS": ("max_context_chars", int),
        "CHUNK_MODE": ("chunk_mode", str), "CHUNK_SIZE": ("chunk_size", int),
        "OVERLAP": ("overlap", int),
        "MIN_SCORE": ("min_score", lambda v: None if v.lower() == "none" else float(v)),
        "FILE_NAMES": ("file_names", lambda v: tuple(json.loads(v))),
    }
    kwargs = {}
    for suffix, (field, convert) in conversions.items():
        key = "AGENT_" + suffix
        if key in values:
            if values[key] is None: raise ValueError(f"Missing value for {key}")
            try:
                if suffix == "FILE_NAMES" and not isinstance(json.loads(values[key]), list): raise ValueError()
                kwargs[field] = convert(values[key])
            except (ValueError, TypeError) as exc: raise ValueError(f"Invalid setting {key}") from exc
    for suffix, field in (("DOCUMENTS_DIR", "documents_dir"), ("INDEX_PATH", "index_path")):
        key = "AGENT_" + suffix
        if key in values:
            if not values[key]: raise ValueError(f"Missing path for {key}")
            path = Path(values[key])
            kwargs[field] = path if path.is_absolute() else PROJECT_ROOT / path
    return ProjectConfig(**kwargs)

"""Read a bounded evaluation summary without initializing models."""
import json
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError, ConfigDict, model_validator
from fastapi import HTTPException


class RetrievalMetrics(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    top_k: int = Field(gt=0,strict=True)
    positive_count: int = Field(ge=0,strict=True)
    source_hit_at_k: float | None = Field(default=None,ge=0,le=1)
    source_top1: float | None = Field(default=None,ge=0,le=1)
    source_mrr: float | None = Field(default=None,ge=0,le=1)
    mean_ms: float = Field(ge=0)


class AgentMetrics(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    total: int = Field(gt=0,strict=True)
    passed: int = Field(ge=0,strict=True)
    p95_ms: float = Field(ge=0)
    mean_ms: float | None = Field(default=None,ge=0)
    false_refusal_rate: float | None = Field(default=None,ge=0,le=1)
    unexpected_answer_rate: float | None = Field(default=None,ge=0,le=1)
    execution_error_rate: float | None = Field(default=None,ge=0,le=1)

    @model_validator(mode="after")
    def valid_counts(self):
        if self.passed>self.total: raise ValueError("Invalid counts")
        return self


class MetricsSummary(BaseModel):
    report_id: str
    created_at: datetime
    retrieval: dict[str,RetrievalMetrics]
    agent: AgentMetrics | None = None


def latest_metrics(directory):
    candidates=[p for p in directory.glob("benchmark-*.json")
                if p.is_file() and not p.is_symlink() and p.resolve().parent==directory.resolve()]
    if not candidates: raise HTTPException(404,"暂无评估报告，请先运行 python -m evaluation.benchmark")
    path=max(candidates,key=lambda p:(p.stat().st_mtime_ns,p.name))
    try:
        with path.open("rb") as handle: raw=handle.read(10_000_001)
        if len(raw)>10_000_000: raise ValueError("Report too large")
        def reject_constant(value): raise ValueError("Non-finite number")
        report=json.loads(raw,parse_constant=reject_constant)
        retrieval={name:RetrievalMetrics.model_validate(value)
                   for name,value in report["retrieval"].items()
                   if name in {"faiss","bm25","hybrid","hybrid_reranked"}}
        if not retrieval: raise ValueError("Missing retrieval metrics")
        return MetricsSummary(report_id=path.name,created_at=report["created_at"],
            retrieval=retrieval,agent=AgentMetrics.model_validate(report["agent"]) if "agent" in report else None)
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        raise HTTPException(503,"最新评估报告不可读取或格式无效，请重新运行评估") from None

from fastapi import APIRouter, Depends
from app.api.dependencies import get_runtime
from app.services.metrics_service import latest_metrics,MetricsSummary

router=APIRouter()


@router.get("/metrics",response_model=MetricsSummary)
def metrics(runtime=Depends(get_runtime)):
    return latest_metrics(runtime.reports_dir)

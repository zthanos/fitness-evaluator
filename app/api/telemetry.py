"""Telemetry API — system health, request stats, recent logs, and chat traces."""
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import get_settings
from app.services.metrics_collector import metrics
from app.services.trace_collector import traces

router = APIRouter()


@router.get("/health", summary="System health overview")
async def get_health(db: Session = Depends(get_db)):
    settings = get_settings()

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    db_status = "healthy"
    db_latency_ms = None
    db_error = None
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        db_status = "unhealthy"
        db_error = str(e)

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_status = "unknown"
    llm_latency_ms = None
    llm_error = None
    try:
        base = settings.llm_base_url.rstrip('/')
        async with httpx.AsyncClient(timeout=5.0) as client:
            t0 = time.perf_counter()
            resp = await client.get(f"{base}/v1/models")
            llm_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            llm_status = "healthy" if resp.status_code == 200 else "degraded"
    except Exception as e:
        llm_status = "unhealthy"
        llm_error = str(e)

    # ── Overall ───────────────────────────────────────────────────────────────
    if db_status == "unhealthy":
        overall = "outage"
    elif llm_status in ("unhealthy", "degraded"):
        overall = "degraded"
    else:
        overall = "operational"

    model = settings.LM_STUDIO_MODEL if settings.LLM_TYPE.lower() == "lm-studio" else settings.OLLAMA_MODEL

    return {
        "overall": overall,
        "uptime_seconds": metrics.uptime_seconds,
        "services": {
            "database": {
                "status": db_status,
                "type": "postgresql",
                "latency_ms": db_latency_ms,
                "error": db_error,
            },
            "llm": {
                "status": llm_status,
                "type": settings.LLM_TYPE,
                "endpoint": settings.llm_base_url,
                "model": model,
                "latency_ms": llm_latency_ms,
                "error": llm_error,
            },
        },
    }


@router.get("/stats", summary="Request statistics")
async def get_stats(
    window: int = Query(default=3600, ge=60, le=86400, description="Time window in seconds"),
):
    return metrics.get_stats(window_seconds=window)


@router.get("/logs", summary="Recent application logs")
async def get_logs(
    level: str = Query(default=None, description="Filter by level: ERROR, WARNING, INFO"),
    limit: int = Query(default=50, ge=1, le=200),
):
    return {"logs": metrics.get_logs(level=level, limit=limit)}


@router.get("/traces", summary="Recent chat execution traces")
async def get_traces(
    limit: int = Query(default=30, ge=1, le=100, description="Number of traces to return"),
):
    """
    Return summary rows for the most recent chat executions.
    Use /traces/{trace_id} to drill into the full chain-of-thought for a specific request.
    """
    return {"traces": traces.list_traces(limit=limit)}


@router.get("/traces/{trace_id}", summary="Full chain-of-thought for one chat request")
async def get_trace(trace_id: str):
    """
    Return the complete execution trace for a single chat request, including:
    - Intent classification result
    - Context layer token counts
    - Full ReAct THINK/ACT/OBSERVE timeline
    - Tool invocations with parameters and result previews
    - Latency breakdown
    """
    trace = traces.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id!r} not found")
    return trace

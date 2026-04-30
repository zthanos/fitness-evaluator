"""Telemetry API — system health, request stats, recent logs, chat traces, and LLM calls.

Stats and traces are read from the fitness_telemetry database so data survives
server restarts.  Application logs are the only in-memory-only source (they are
not persisted).  All endpoints fall back to the in-memory collectors when the
telemetry DB is unavailable.
"""
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, desc

from app.database import get_db
from app.config import get_settings
from app.services.metrics_collector import metrics
from app.services.trace_collector import traces

# ── Model pricing ($ per 1M tokens, as of mid-2025) ──────────────────────────
_MODEL_PRICING = {
    "gpt-4o":             {"name": "GPT-4o",              "input": 2.50,  "output": 10.00},
    "gpt-4o-mini":        {"name": "GPT-4o mini",         "input": 0.15,  "output": 0.60},
    "claude-sonnet-4-6":  {"name": "Claude Sonnet 4.6",   "input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":   {"name": "Claude Haiku 4.5",    "input": 0.80,  "output": 4.00},
    "claude-opus-4-7":    {"name": "Claude Opus 4.7",     "input": 15.00, "output": 75.00},
    "gemini-2-flash":     {"name": "Gemini 2.0 Flash",    "input": 0.10,  "output": 0.40},
}

# ── Path normalization (mirrors metrics_collector) ────────────────────────────
_UUID    = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
_NUMERIC = re.compile(r'/\d+')


def _normalize(path: str) -> str:
    path = _UUID.sub(':id', path)
    path = _NUMERIC.sub('/:id', path)
    return path


def _percentile(sorted_data: list, p: float) -> float:
    if not sorted_data:
        return 0.0
    idx = max(0, int(p / 100 * (len(sorted_data) - 1)))
    return round(sorted_data[idx], 1)


def _estimate_tokens(messages: Optional[list], response: Optional[str]) -> tuple[int, int]:
    """Rough token estimate: 4 chars ≈ 1 token (English prose average)."""
    input_text = "".join(
        (m.get("content") or "") for m in (messages or []) if isinstance(m, dict)
    )
    return max(1, len(input_text) // 4), max(0, len(response or "") // 4)


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
    """Read request statistics from the telemetry DB.  Falls back to in-memory if DB unavailable."""
    from app.telemetry_database import get_session
    from app.models.telemetry import RequestMetric

    tdb = get_session()
    if tdb is None:
        return metrics.get_stats(window_seconds=window)

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window)
        rows = tdb.query(RequestMetric).filter(RequestMetric.ts >= cutoff).all()

        n = len(rows)
        if n == 0:
            return {
                "window_seconds": window,
                "total_requests": 0,
                "rps": 0.0,
                "success_rate": 100.0,
                "error_rate": 0.0,
                "latency": {"p50": 0, "p95": 0, "p99": 0, "avg": 0},
                "status_codes": {},
                "top_endpoints": [],
                "recent_errors": [],
                "uptime_seconds": metrics.uptime_seconds,
            }

        durations_sorted = sorted(r.duration_ms for r in rows)
        errors = [r for r in rows if r.status_code >= 400]

        # Per-path aggregation
        path_map: dict = {}
        for r in rows:
            key = _normalize(r.path)
            if key not in path_map:
                path_map[key] = {"count": 0, "errors": 0, "durations": []}
            path_map[key]["count"] += 1
            if r.status_code >= 400:
                path_map[key]["errors"] += 1
            path_map[key]["durations"].append(r.duration_ms)

        top_endpoints = sorted(
            [
                {
                    "path": p,
                    "count": s["count"],
                    "error_rate": round(s["errors"] / s["count"] * 100, 1),
                    "p95_ms": _percentile(sorted(s["durations"]), 95),
                    "avg_ms": round(sum(s["durations"]) / len(s["durations"]), 1),
                }
                for p, s in path_map.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        status_counts: dict = {}
        for r in rows:
            k = str(r.status_code)
            status_counts[k] = status_counts.get(k, 0) + 1

        recent_errors = [
            {
                "timestamp": r.ts.timestamp() if r.ts else None,
                "method": r.method,
                "path": r.path,
                "status": r.status_code,
                "duration_ms": round(r.duration_ms, 1),
                "error_detail": r.error_detail,
            }
            for r in sorted(errors, key=lambda x: x.ts or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        ][:20]

        last_minute_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        last_minute_count = sum(1 for r in rows if r.ts and r.ts >= last_minute_cutoff)
        rps = round(last_minute_count / 60, 3)

        return {
            "window_seconds": window,
            "total_requests": n,
            "rps": rps,
            "success_rate": round((n - len(errors)) / n * 100, 2),
            "error_rate": round(len(errors) / n * 100, 2),
            "latency": {
                "p50": _percentile(durations_sorted, 50),
                "p95": _percentile(durations_sorted, 95),
                "p99": _percentile(durations_sorted, 99),
                "avg": round(sum(durations_sorted) / n, 1),
            },
            "status_codes": status_counts,
            "top_endpoints": top_endpoints,
            "recent_errors": recent_errors,
            "uptime_seconds": metrics.uptime_seconds,
        }
    finally:
        tdb.close()


@router.get("/logs", summary="Recent application logs")
async def get_logs(
    level: str = Query(default=None, description="Filter by level: ERROR, WARNING, INFO"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Application logs are runtime-only (not persisted) — always from memory."""
    return {"logs": metrics.get_logs(level=level, limit=limit)}


@router.get("/traces", summary="Recent chat execution traces")
async def get_traces(
    limit: int = Query(default=30, ge=1, le=100, description="Number of traces to return"),
):
    """Return summary rows for the most recent chat executions, read from the telemetry DB."""
    from app.telemetry_database import get_session
    from app.models.telemetry import ChatTrace

    tdb = get_session()
    if tdb is None:
        return {"traces": traces.list_traces(limit=limit)}

    try:
        rows = (
            tdb.query(ChatTrace)
            .order_by(desc(ChatTrace.ts))
            .limit(limit)
            .all()
        )
        result = [
            {
                "trace_id":          r.trace_id,
                "timestamp":         r.ts.timestamp() if r.ts else None,
                "session_id":        r.session_id,
                "user_id":           r.user_id,
                "intent":            r.intent,
                "intent_used_tools": r.intent_used_tools,
                "tool_calls_made":   r.tool_calls_made,
                "iterations":        r.iterations,
                "total_latency_ms":  r.total_latency_ms,
                "model_used":        r.model_used,
                "user_message":      r.user_message,
            }
            for r in rows
        ]
        return {"traces": result}
    finally:
        tdb.close()


@router.get("/traces/{trace_id}", summary="Full chain-of-thought for one chat request")
async def get_trace(trace_id: str):
    """Return the complete execution trace from the telemetry DB."""
    from app.telemetry_database import get_session
    from app.models.telemetry import ChatTrace

    tdb = get_session()
    if tdb is None:
        trace = traces.get_trace(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id!r} not found")
        return trace

    try:
        row = tdb.query(ChatTrace).filter(ChatTrace.trace_id == trace_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id!r} not found")
        return row.full_trace
    finally:
        tdb.close()


# ── LLM call log (reads from fitness_telemetry DB) ───────────────────────────

@router.get("/llm-calls", summary="List LLM calls from skills and analysis pipelines")
async def list_llm_calls(
    source: Optional[str] = Query(None, description="Filter by source (e.g. TrainingPlanner)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    from app.telemetry_database import get_session
    from app.models.telemetry import LlmCall

    db = get_session()
    if db is None:
        return {"calls": [], "total": 0}

    try:
        q = db.query(LlmCall)
        if source:
            q = q.filter(LlmCall.source == source)
        total = q.count()
        rows = q.order_by(desc(LlmCall.ts)).offset(offset).limit(limit).all()

        calls = []
        for r in rows:
            in_tok, out_tok = _estimate_tokens(r.messages, r.response_content)
            calls.append({
                "id":        r.id,
                "call_id":   r.call_id,
                "ts":        r.ts.isoformat() if r.ts else None,
                "source":    r.source,
                "model":     r.model,
                "duration_ms": r.duration_ms,
                "input_tokens":  in_tok,
                "output_tokens": out_tok,
                "total_tokens":  in_tok + out_tok,
                "has_error": bool(r.error),
                "error":     r.error,
            })

        sources = [row[0] for row in db.query(LlmCall.source).distinct().all() if row[0]]
        return {"calls": calls, "total": total, "sources": sorted(sources)}
    finally:
        db.close()


@router.get("/llm-calls/{call_id}", summary="Full detail for one LLM call")
async def get_llm_call(call_id: str):
    from app.telemetry_database import get_session
    from app.models.telemetry import LlmCall

    db = get_session()
    if db is None:
        raise HTTPException(status_code=503, detail="Telemetry DB unavailable")

    try:
        row = db.query(LlmCall).filter(LlmCall.call_id == call_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"LLM call {call_id!r} not found")

        in_tok, out_tok = _estimate_tokens(row.messages, row.response_content)
        return {
            "call_id":         row.call_id,
            "ts":              row.ts.isoformat() if row.ts else None,
            "source":          row.source,
            "model":           row.model,
            "duration_ms":     row.duration_ms,
            "input_tokens":    in_tok,
            "output_tokens":   out_tok,
            "total_tokens":    in_tok + out_tok,
            "messages":        row.messages or [],
            "response_content": row.response_content,
            "tool_calls":      row.tool_calls,
            "error":           row.error,
        }
    finally:
        db.close()


@router.get("/llm-cost", summary="LLM usage cost estimation vs public models")
async def get_llm_cost(
    days: int = Query(default=7, ge=1, le=90, description="Lookback window in days"),
):
    from app.telemetry_database import get_session
    from app.models.telemetry import LlmCall

    db = get_session()
    if db is None:
        return {"period_days": days, "totals": {}, "by_source": [], "models": _MODEL_PRICING}

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = db.query(LlmCall).filter(LlmCall.ts >= cutoff).all()

        total_calls = len(rows)
        total_in = total_out = 0
        by_source: dict = {}

        for r in rows:
            in_tok, out_tok = _estimate_tokens(r.messages, r.response_content)
            total_in  += in_tok
            total_out += out_tok
            src = r.source or "unknown"
            if src not in by_source:
                by_source[src] = {"source": src, "calls": 0, "input_tokens": 0, "output_tokens": 0}
            by_source[src]["calls"]         += 1
            by_source[src]["input_tokens"]  += in_tok
            by_source[src]["output_tokens"] += out_tok

        def _cost(in_t, out_t, pricing):
            return round(
                (in_t / 1_000_000) * pricing["input"] +
                (out_t / 1_000_000) * pricing["output"],
                6,
            )

        model_estimates = {
            key: {
                "name":         p["name"],
                "input_price":  p["input"],
                "output_price": p["output"],
                "total_cost":   _cost(total_in, total_out, p),
            }
            for key, p in _MODEL_PRICING.items()
        }

        source_rows = sorted(by_source.values(), key=lambda x: x["calls"], reverse=True)
        for row in source_rows:
            row["cost_estimates"] = {
                key: _cost(row["input_tokens"], row["output_tokens"], p)
                for key, p in _MODEL_PRICING.items()
            }

        return {
            "period_days":   days,
            "total_calls":   total_calls,
            "total_input_tokens":  total_in,
            "total_output_tokens": total_out,
            "total_tokens":        total_in + total_out,
            "model_estimates": model_estimates,
            "by_source":     source_rows,
        }
    finally:
        db.close()

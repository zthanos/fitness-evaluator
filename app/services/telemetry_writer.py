"""Fire-and-forget persistence to the fitness_telemetry database.

All public functions submit a sync SQLAlchemy write to a background
ThreadPoolExecutor so they never block the request path.  Any failure
(DB unavailable, constraint violation, etc.) is swallowed silently and
logged at DEBUG level — the app must never degrade because of telemetry.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="telemetry")


def _submit(fn) -> None:
    try:
        _pool.submit(fn)
    except Exception as exc:
        logger.debug("telemetry_writer: pool submit failed: %s", exc)


# ── Public write functions ────────────────────────────────────────────────────

def persist_request_metric(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    error_detail: Optional[str] = None,
) -> None:
    def _write():
        from app.telemetry_database import get_session
        from app.models.telemetry import RequestMetric
        db = get_session()
        if db is None:
            return
        try:
            db.add(RequestMetric(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                error_detail=error_detail,
            ))
            db.commit()
        except Exception as exc:
            logger.debug("persist_request_metric: %s", exc)
            db.rollback()
        finally:
            db.close()

    _submit(_write)


def persist_chat_trace(trace: Dict[str, Any]) -> None:
    def _write():
        from app.telemetry_database import get_session
        from app.models.telemetry import ChatTrace
        db = get_session()
        if db is None:
            return
        try:
            db.add(ChatTrace(
                trace_id=trace.get("trace_id", ""),
                session_id=trace.get("session_id"),
                user_id=trace.get("user_id"),
                intent=trace.get("intent"),
                intent_used_tools=trace.get("intent_used_tools"),
                tool_calls_made=trace.get("tool_calls_made"),
                iterations=trace.get("iterations"),
                total_latency_ms=trace.get("total_latency_ms"),
                model_used=trace.get("model_used"),
                user_message=trace.get("user_message"),
                full_trace=trace,
            ))
            db.commit()
        except Exception as exc:
            logger.debug("persist_chat_trace: %s", exc)
            db.rollback()
        finally:
            db.close()

    _submit(_write)


def persist_llm_call(
    call_id: str,
    source: str,
    model: str,
    messages: List[dict],
    response_content: Optional[str],
    duration_ms: float,
    tool_calls: Optional[List[dict]] = None,
    error: Optional[str] = None,
) -> None:
    def _write():
        from app.telemetry_database import get_session
        from app.models.telemetry import LlmCall
        db = get_session()
        if db is None:
            return
        try:
            db.add(LlmCall(
                call_id=call_id,
                source=source,
                model=model,
                messages=messages,
                response_content=(response_content or "")[:3000],
                tool_calls=tool_calls,
                duration_ms=round(duration_ms, 1),
                error=error,
            ))
            db.commit()
        except Exception as exc:
            logger.debug("persist_llm_call: %s", exc)
            db.rollback()
        finally:
            db.close()

    _submit(_write)

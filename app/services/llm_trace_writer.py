"""Appends LLM call records to daily-rotated JSONL files in logs/traces/."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Anchored to project root: fitness-eval/logs/traces/
_LOG_DIR = Path(__file__).parent.parent.parent / "logs" / "traces"


def _today_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _LOG_DIR / f"{today}.jsonl"


def write_llm_trace(
    *,
    source: str,
    model: str,
    messages: list,
    response_content: Optional[str],
    duration_ms: float,
    tool_calls: Optional[list] = None,
    error: Optional[str] = None,
    call_id: Optional[str] = None,
) -> None:
    """Write one LLM call record to the telemetry DB and the daily JSONL fallback."""
    cid = call_id or str(uuid.uuid4())
    truncated_messages = _truncate_messages(messages)

    # ── Persist to telemetry database (fire-and-forget) ───────────────────────
    try:
        from app.services.telemetry_writer import persist_llm_call
        persist_llm_call(
            call_id=cid,
            source=source,
            model=model,
            messages=truncated_messages,
            response_content=response_content,
            duration_ms=duration_ms,
            tool_calls=tool_calls,
            error=error,
        )
    except Exception:
        pass

    # ── JSONL fallback (keeps working even if DB is unavailable) ─────────────
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "call_id": cid,
            "source": source,
            "model": model,
            "messages": truncated_messages,
            "response_content": (response_content or "")[:3000],
            "tool_calls": tool_calls,
            "duration_ms": round(duration_ms, 1),
            "error": error,
        }
        with _today_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        logger.debug("llm_trace_writer: failed to write JSONL trace", exc_info=True)


def _truncate_messages(messages: list, max_content: int = 2000) -> list:
    """Return messages with long content fields truncated."""
    out = []
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content") or ""
            if isinstance(content, str) and len(content) > max_content:
                content = content[:max_content] + f"…[+{len(content) - max_content} chars]"
            out.append({**m, "content": content})
        else:
            out.append(m)
    return out

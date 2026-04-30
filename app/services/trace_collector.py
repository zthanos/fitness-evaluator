"""In-memory chat execution trace store.

Follows the same singleton pattern as MetricsCollector — stores the last
100 chat traces so the telemetry page can display a chain-of-thought
drill-down without a database write on every request.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Dict, List, Optional


class TraceCollector:
    """Singleton in-memory store for recent chat execution traces."""

    _instance: Optional['TraceCollector'] = None

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._traces: deque[Dict[str, Any]] = deque(maxlen=100)
            cls._instance = inst
        return cls._instance

    def record(self, trace: Dict[str, Any]) -> None:
        """Prepend a new trace (most recent first)."""
        self._traces.appendleft(trace)
        try:
            from app.services.telemetry_writer import persist_chat_trace
            persist_chat_trace(trace)
        except Exception:
            pass

    def list_traces(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return summary rows — no tool results / context snapshots."""
        out = []
        for t in list(self._traces)[:limit]:
            out.append({
                "trace_id":        t["trace_id"],
                "timestamp":       t["timestamp"],
                "session_id":      t["session_id"],
                "user_id":         t["user_id"],
                "intent":          t["intent"],
                "intent_used_tools": t["intent_used_tools"],
                "tool_calls_made": t["tool_calls_made"],
                "iterations":      t["iterations"],
                "total_latency_ms": t["total_latency_ms"],
                "model_used":      t["model_used"],
                "user_message":    t["user_message"],
            })
        return out

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Return the full trace dict by ID, or None."""
        for t in self._traces:
            if t["trace_id"] == trace_id:
                return t
        return None


# Module-level singleton — import this everywhere
traces = TraceCollector()

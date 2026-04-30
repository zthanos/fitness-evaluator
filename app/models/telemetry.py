"""SQLAlchemy models for the fitness_telemetry database.

Three tables:
  request_metrics  — one row per HTTP API request (written by MetricsMiddleware)
  chat_traces      — one row per coach chat execution (written by ChatAgent)
  llm_calls        — one row per raw LLM API call (written by LlmClient)
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, Float, Integer, SmallInteger, String, Text, DateTime, JSON

from app.telemetry_database import TelemetryBase


def _now():
    return datetime.now(timezone.utc)


class RequestMetric(TelemetryBase):
    __tablename__ = "request_metrics"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    ts          = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    method      = Column(String(10), nullable=False)
    path        = Column(Text, nullable=False)
    status_code = Column(SmallInteger, nullable=False)
    duration_ms = Column(Float, nullable=False)
    error_detail = Column(Text, nullable=True)


class ChatTrace(TelemetryBase):
    __tablename__ = "chat_traces"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id         = Column(String(36), nullable=False, unique=True, index=True)
    ts               = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    session_id       = Column(Text, nullable=True)
    user_id          = Column(Integer, nullable=True, index=True)
    intent           = Column(Text, nullable=True)
    intent_used_tools = Column(Boolean, nullable=True)
    tool_calls_made  = Column(SmallInteger, nullable=True)
    iterations       = Column(SmallInteger, nullable=True)
    total_latency_ms = Column(Float, nullable=True)
    model_used       = Column(Text, nullable=True)
    user_message     = Column(Text, nullable=True)
    full_trace       = Column(JSON, nullable=True)


class LlmCall(TelemetryBase):
    __tablename__ = "llm_calls"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    call_id          = Column(String(36), nullable=False, index=True)
    ts               = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    source           = Column(Text, nullable=True)
    model            = Column(Text, nullable=True)
    messages         = Column(JSON, nullable=True)
    response_content = Column(Text, nullable=True)
    tool_calls       = Column(JSON, nullable=True)
    duration_ms      = Column(Float, nullable=True)
    error            = Column(Text, nullable=True)

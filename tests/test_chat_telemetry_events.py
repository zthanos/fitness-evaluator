"""
Tests for chat telemetry events (Task 5.3).

Verifies that retrieval latency, model latency, total latency, tokens in/out,
model used (primary/fallback), and fallback usage are emitted to invocations.jsonl.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.ai.adapter.langchain_adapter import LangChainAdapter
from app.ai.adapter.llm_adapter import LLMResponse, StreamChunk
from app.ai.context.builder import Context
from app.ai.telemetry.invocation_logger import InvocationLogger, InvocationLog
from pydantic import BaseModel


# --- Helpers ---

class DummyContract(BaseModel):
    text: str


def _make_context(token_count: int = 100) -> MagicMock:
    ctx = MagicMock(spec=Context)
    ctx.to_messages.return_value = [{"role": "user", "content": "hello"}]
    ctx.token_count = token_count
    return ctx


def _adapter_with_logger(tmp_path: str, **kwargs) -> LangChainAdapter:
    logger = InvocationLogger(log_file_path=tmp_path)
    return LangChainAdapter(invocation_logger=logger, **kwargs)


def _read_logs(tmp_path: str):
    with open(tmp_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# --- Tests ---

class TestInvokeTelemetryFields:
    """Verify invoke() emits all required telemetry fields."""

    @patch.object(LangChainAdapter, "_invoke_model")
    @patch.object(LangChainAdapter, "_count_response_tokens", return_value=42)
    def test_primary_model_emits_model_latency_and_no_fallback(
        self, _mock_count, mock_invoke_model, tmp_path
    ):
        log_path = str(tmp_path / "invocations.jsonl")
        adapter = _adapter_with_logger(log_path)
        mock_invoke_model.return_value = DummyContract(text="hi")

        ctx = _make_context(token_count=200)
        adapter.invoke(ctx, DummyContract, operation_type="chat_response", athlete_id=7)

        logs = _read_logs(log_path)
        assert len(logs) == 1
        rec = logs[0]

        # model_latency_ms should be present and positive
        assert rec["model_latency_ms"] is not None
        assert rec["model_latency_ms"] >= 0

        # total_latency_ms should be present
        assert rec["total_latency_ms"] is not None
        assert rec["total_latency_ms"] >= 0

        # fallback_used should be False for primary success
        assert rec["fallback_used"] is False

        # tokens in/out
        assert rec["context_token_count"] == 200
        assert rec["response_token_count"] == 42

        # model used
        assert rec["model_used"] == adapter.primary_model

        # success
        assert rec["success_status"] is True

    @patch.object(LangChainAdapter, "_invoke_model")
    @patch.object(LangChainAdapter, "_count_response_tokens", return_value=30)
    def test_fallback_model_emits_fallback_used_true(
        self, _mock_count, mock_invoke_model, tmp_path
    ):
        log_path = str(tmp_path / "invocations.jsonl")
        adapter = _adapter_with_logger(log_path)

        # Primary fails with timeout, fallback succeeds
        import requests.exceptions
        mock_invoke_model.side_effect = [
            requests.exceptions.Timeout("timeout"),
            DummyContract(text="fallback response"),
        ]

        ctx = _make_context(token_count=150)
        resp = adapter.invoke(ctx, DummyContract, operation_type="chat_response", athlete_id=5)

        logs = _read_logs(log_path)
        assert len(logs) == 1
        rec = logs[0]

        assert rec["fallback_used"] is True
        assert rec["model_used"] == adapter.fallback_model
        assert rec["success_status"] is True
        assert rec["model_latency_ms"] is not None
        assert rec["model_latency_ms"] >= 0

    @patch.object(LangChainAdapter, "_invoke_model")
    def test_failure_emits_fallback_used(self, mock_invoke_model, tmp_path):
        log_path = str(tmp_path / "invocations.jsonl")
        adapter = _adapter_with_logger(log_path)

        import requests.exceptions
        mock_invoke_model.side_effect = [
            requests.exceptions.Timeout("timeout"),
            requests.exceptions.ConnectionError("down"),
        ]

        ctx = _make_context()
        with pytest.raises(requests.exceptions.ConnectionError):
            adapter.invoke(ctx, DummyContract, operation_type="chat_response", athlete_id=1)

        logs = _read_logs(log_path)
        assert len(logs) == 1
        rec = logs[0]

        assert rec["success_status"] is False
        assert rec["fallback_used"] is True
        assert rec["error_message"] is not None


class TestStreamTelemetryFields:
    """Verify stream() emits all required telemetry fields."""

    @patch.object(LangChainAdapter, "_stream_from_model")
    def test_stream_primary_emits_telemetry(self, mock_stream, tmp_path):
        log_path = str(tmp_path / "invocations.jsonl")
        adapter = _adapter_with_logger(log_path)

        def fake_stream(model, messages, content_parts, tool_calls):
            content_parts.append("streamed text")
            yield StreamChunk(content="streamed text", chunk_type="content")

        mock_stream.side_effect = fake_stream

        ctx = _make_context(token_count=120)
        chunks = list(adapter.stream(ctx, operation_type="chat_response", athlete_id=3))

        # Last chunk should be "done"
        done = [c for c in chunks if c.chunk_type == "done"]
        assert len(done) == 1
        meta = done[0].metadata

        assert meta["model_used"] == adapter.primary_model
        assert meta["fallback_used"] is False
        assert meta["model_latency_ms"] is not None
        assert meta["context_token_count"] == 120
        assert meta["response_token_count"] > 0

        # Check JSONL log
        logs = _read_logs(log_path)
        assert len(logs) == 1
        rec = logs[0]
        assert rec["fallback_used"] is False
        assert rec["model_latency_ms"] is not None
        assert rec["total_latency_ms"] is not None

    @patch.object(LangChainAdapter, "_stream_from_model")
    def test_stream_fallback_emits_fallback_used(self, mock_stream, tmp_path):
        log_path = str(tmp_path / "invocations.jsonl")
        adapter = _adapter_with_logger(log_path)

        import requests.exceptions

        call_count = 0

        def fake_stream(model, messages, content_parts, tool_calls):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.Timeout("timeout")
            content_parts.append("fallback text")
            yield StreamChunk(content="fallback text", chunk_type="content")

        mock_stream.side_effect = fake_stream

        ctx = _make_context(token_count=80)
        chunks = list(adapter.stream(ctx, operation_type="chat_response", athlete_id=2))

        done = [c for c in chunks if c.chunk_type == "done"]
        assert len(done) == 1
        meta = done[0].metadata
        assert meta["fallback_used"] is True
        assert meta["model_used"] == adapter.fallback_model

        logs = _read_logs(log_path)
        assert len(logs) == 1
        assert logs[0]["fallback_used"] is True


class TestChatAgentTelemetryFields:
    """Verify ChatAgent.execute() returns retrieval/model/total latency."""

    @pytest.mark.asyncio
    async def test_execute_returns_retrieval_and_total_latency(self):
        from app.services.chat_agent import ChatAgent

        # Mock context builder
        mock_cb = MagicMock()
        mock_context = MagicMock()
        mock_context.token_count = 300
        mock_context.to_messages.return_value = [{"role": "system", "content": "hi"}]
        mock_cb.build.return_value = mock_context
        mock_cb.gather_data.return_value = mock_cb
        mock_cb.add_system_instructions = MagicMock()
        mock_cb.add_task_instructions = MagicMock()
        mock_cb.add_domain_knowledge = MagicMock()

        # Mock LLM adapter
        mock_adapter = MagicMock()
        mock_parsed = MagicMock()
        mock_parsed.response_text = "Great workout!"
        mock_parsed.evidence_cards = []
        mock_adapter.invoke.return_value = LLMResponse(
            parsed_output=mock_parsed,
            model_used="mixtral:8x7b-instruct",
            token_count=350,
            latency_ms=500.0,
        )

        agent = ChatAgent(
            context_builder=mock_cb,
            llm_adapter=mock_adapter,
            db=MagicMock(),
            tool_orchestrator=MagicMock(),
        )

        result = await agent.execute(
            user_message="How was my run?",
            session_id=1,
            user_id=42,
            conversation_history=[],
            system_instructions="You are a coach",
            task_instructions="Respond helpfully",
        )

        # retrieval_latency_ms should be present and non-negative
        assert "retrieval_latency_ms" in result
        assert result["retrieval_latency_ms"] >= 0

        # model_latency_ms should be present (from LLMResponse)
        assert "model_latency_ms" in result
        assert result["model_latency_ms"] == 500.0

        # total_latency_ms should be present and >= retrieval + model
        assert "total_latency_ms" in result
        assert result["total_latency_ms"] >= 0

        # tokens
        assert result["context_token_count"] == 300
        assert result["response_token_count"] == 50  # 350 - 300

        # model used
        assert result["model_used"] == "mixtral:8x7b-instruct"

    @pytest.mark.asyncio
    async def test_execute_orchestrator_path_includes_telemetry(self):
        from app.services.chat_agent import ChatAgent

        mock_cb = MagicMock()
        mock_context = MagicMock()
        mock_context.token_count = 200
        mock_context.to_messages.return_value = [{"role": "system", "content": "hi"}]
        mock_cb.build.return_value = mock_context
        mock_cb.gather_data.return_value = mock_cb
        mock_cb.add_system_instructions = MagicMock()
        mock_cb.add_task_instructions = MagicMock()
        mock_cb.add_domain_knowledge = MagicMock()

        # No LLM adapter → falls back to orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.orchestrate = MagicMock()

        import asyncio
        async def fake_orchestrate(*args, **kwargs):
            return {
                "content": "Tool result",
                "tool_calls_made": 2,
                "iterations": 1,
                "model_used": "llama3.1:8b-instruct",
                "response_token_count": 80,
                "model_latency_ms": 300.0,
            }

        mock_orchestrator.orchestrate = fake_orchestrate

        agent = ChatAgent(
            context_builder=mock_cb,
            llm_adapter=None,
            db=MagicMock(),
            tool_orchestrator=mock_orchestrator,
        )

        result = await agent.execute(
            user_message="What tools do I need?",
            session_id=2,
            user_id=10,
            conversation_history=[],
            system_instructions="Coach",
            task_instructions="Help",
        )

        assert "retrieval_latency_ms" in result
        assert result["retrieval_latency_ms"] >= 0
        assert "total_latency_ms" in result
        assert result["total_latency_ms"] >= 0
        assert result["model_latency_ms"] == 300.0


class TestInvocationLogDataclass:
    """Verify InvocationLog includes all new telemetry fields."""

    def test_log_with_all_telemetry_fields(self):
        log = InvocationLog(
            timestamp="2026-03-15T10:00:00Z",
            operation_type="chat_response",
            athlete_id=42,
            model_used="mixtral:8x7b-instruct",
            context_token_count=200,
            response_token_count=50,
            latency_ms=1500.0,
            success_status=True,
            error_message=None,
            retrieval_latency_ms=120.5,
            model_latency_ms=1200.0,
            total_latency_ms=1500.0,
            fallback_used=False,
        )

        assert log.retrieval_latency_ms == 120.5
        assert log.model_latency_ms == 1200.0
        assert log.total_latency_ms == 1500.0
        assert log.fallback_used is False

    def test_log_defaults_to_none(self):
        log = InvocationLog(
            timestamp="2026-03-15T10:00:00Z",
            operation_type="chat_response",
            athlete_id=1,
            model_used="mixtral",
            context_token_count=100,
            response_token_count=50,
            latency_ms=500.0,
            success_status=True,
        )

        assert log.retrieval_latency_ms is None
        assert log.model_latency_ms is None
        assert log.total_latency_ms is None
        assert log.fallback_used is None

    def test_log_serializes_new_fields_to_jsonl(self, tmp_path):
        log_path = str(tmp_path / "invocations.jsonl")
        logger = InvocationLogger(log_file_path=log_path)

        log = InvocationLog(
            timestamp="2026-03-15T10:00:00Z",
            operation_type="chat_response",
            athlete_id=42,
            model_used="mixtral:8x7b-instruct",
            context_token_count=200,
            response_token_count=50,
            latency_ms=1500.0,
            success_status=True,
            retrieval_latency_ms=120.5,
            model_latency_ms=1200.0,
            total_latency_ms=1500.0,
            fallback_used=False,
        )
        logger.log(log)

        logs = _read_logs(log_path)
        assert len(logs) == 1
        rec = logs[0]
        assert rec["retrieval_latency_ms"] == 120.5
        assert rec["model_latency_ms"] == 1200.0
        assert rec["total_latency_ms"] == 1500.0
        assert rec["fallback_used"] is False

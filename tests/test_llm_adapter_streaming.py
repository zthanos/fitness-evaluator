"""
Tests for LLMAdapter streaming support.

Covers:
- Basic content streaming (5.2.1)
- Tool-call detection during streaming (5.2.2)
- Telemetry emission after stream completes (5.2.3)
- Error handling without breaking the stream (5.2.4)
- Primary/fallback model switching during streaming
- StreamChunk dataclass contract
"""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import List
from unittest.mock import Mock, patch, MagicMock

import pytest

from app.ai.adapter.langchain_adapter import LangChainAdapter
from app.ai.adapter.llm_adapter import StreamChunk
from app.ai.context.builder import Context
from app.ai.telemetry.invocation_logger import InvocationLogger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(token_count: int = 100) -> Context:
    return Context(
        system_instructions="You are a test assistant",
        task_instructions="Generate a test response",
        domain_knowledge={},
        retrieved_data=[],
        token_count=token_count,
    )


def _make_ai_chunk(content: str = "", tool_call_chunks=None):
    """Return a lightweight object that quacks like AIMessageChunk."""
    chunk = SimpleNamespace(content=content)
    if tool_call_chunks is not None:
        chunk.tool_call_chunks = tool_call_chunks
    else:
        chunk.tool_call_chunks = []
    return chunk


def _collect(gen) -> List[StreamChunk]:
    return list(gen)


# ---------------------------------------------------------------------------
# Tests: basic content streaming
# ---------------------------------------------------------------------------

class TestStreamContentChunks:
    """stream() yields content chunks and a terminal done chunk."""

    def test_yields_content_chunks(self):
        adapter = LangChainAdapter()
        context = _make_context()

        fake_chunks = [
            _make_ai_chunk("Hello "),
            _make_ai_chunk("world"),
        ]

        with patch.object(adapter, "_stream_from_model") as mock_sfm:
            mock_sfm.return_value = iter([
                StreamChunk(content="Hello ", chunk_type="content"),
                StreamChunk(content="world", chunk_type="content"),
            ])
            # We also need content_parts to be populated for token counting.
            # Since we're mocking _stream_from_model, we need to simulate
            # the side-effect of populating content_parts.
            original_sfm = LangChainAdapter._stream_from_model

            def side_effect(self_inner, model, msgs, content_parts, tc_list):
                content_parts.extend(["Hello ", "world"])
                yield StreamChunk(content="Hello ", chunk_type="content")
                yield StreamChunk(content="world", chunk_type="content")

            with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
                chunks = _collect(adapter.stream(context, operation_type="test"))

        content_chunks = [c for c in chunks if c.chunk_type == "content"]
        assert len(content_chunks) == 2
        assert content_chunks[0].content == "Hello "
        assert content_chunks[1].content == "world"

    def test_done_chunk_is_last(self):
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            content_parts.append("ok")
            yield StreamChunk(content="ok", chunk_type="content")

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        assert chunks[-1].chunk_type == "done"

    def test_done_metadata_contains_required_keys(self):
        adapter = LangChainAdapter()
        context = _make_context(token_count=42)

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            content_parts.append("hi")
            yield StreamChunk(content="hi", chunk_type="content")

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context, operation_type="chat"))

        done = chunks[-1]
        meta = done.metadata
        assert meta is not None
        assert meta["model_used"] == adapter.primary_model
        assert meta["context_token_count"] == 42
        assert meta["response_token_count"] > 0
        assert meta["latency_ms"] >= 0
        assert meta["success"] is True
        assert isinstance(meta["tool_calls"], list)


# ---------------------------------------------------------------------------
# Tests: tool-call streaming
# ---------------------------------------------------------------------------

class TestStreamToolCalls:
    """stream() detects and yields tool-call chunks."""

    def test_yields_tool_call_chunks(self):
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            payload = {"name": "get_weather", "arguments": {"city": "NYC"}}
            tc_list.append(payload)
            yield StreamChunk(chunk_type="tool_call", tool_call=payload)

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        tc_chunks = [c for c in chunks if c.chunk_type == "tool_call"]
        assert len(tc_chunks) == 1
        assert tc_chunks[0].tool_call["name"] == "get_weather"
        assert tc_chunks[0].tool_call["arguments"] == {"city": "NYC"}

    def test_tool_calls_included_in_done_metadata(self):
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            payload = {"name": "search", "arguments": {"q": "test"}}
            tc_list.append(payload)
            yield StreamChunk(chunk_type="tool_call", tool_call=payload)

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        done = chunks[-1]
        assert len(done.metadata["tool_calls"]) == 1
        assert done.metadata["tool_calls"][0]["name"] == "search"

    def test_mixed_content_and_tool_calls(self):
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            content_parts.append("Let me check.")
            yield StreamChunk(content="Let me check.", chunk_type="content")
            payload = {"name": "lookup", "arguments": {}}
            tc_list.append(payload)
            yield StreamChunk(chunk_type="tool_call", tool_call=payload)

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        types = [c.chunk_type for c in chunks]
        assert "content" in types
        assert "tool_call" in types
        assert types[-1] == "done"


# ---------------------------------------------------------------------------
# Tests: telemetry emission
# ---------------------------------------------------------------------------

class TestStreamTelemetry:
    """Telemetry is logged after stream completes."""

    def test_telemetry_logged_on_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "invocations.jsonl"
            inv_logger = InvocationLogger(log_file_path=str(log_file))
            adapter = LangChainAdapter(invocation_logger=inv_logger)
            context = _make_context(token_count=50)

            def side_effect(self_inner, model, msgs, content_parts, tc_list):
                content_parts.append("response text")
                yield StreamChunk(content="response text", chunk_type="content")

            with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
                _collect(adapter.stream(context, operation_type="chat_stream", athlete_id=7))

            assert log_file.exists()
            entry = json.loads(log_file.read_text().strip().split("\n")[-1])
            assert entry["operation_type"] == "chat_stream"
            assert entry["athlete_id"] == 7
            assert entry["success_status"] is True
            assert entry["context_token_count"] == 50
            assert entry["response_token_count"] > 0

    def test_telemetry_logged_on_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "invocations.jsonl"
            inv_logger = InvocationLogger(log_file_path=str(log_file))
            adapter = LangChainAdapter(invocation_logger=inv_logger)
            context = _make_context()

            def side_effect(self_inner, model, msgs, content_parts, tc_list):
                raise ValueError("boom")

            with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
                _collect(adapter.stream(context, operation_type="chat_err", athlete_id=3))

            entry = json.loads(log_file.read_text().strip().split("\n")[-1])
            assert entry["success_status"] is False
            assert "boom" in (entry["error_message"] or "")


# ---------------------------------------------------------------------------
# Tests: error handling without breaking stream
# ---------------------------------------------------------------------------

class TestStreamErrorHandling:
    """Errors yield error chunks instead of raising."""

    def test_non_retryable_error_yields_error_chunk(self):
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            raise RuntimeError("unexpected failure")

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        error_chunks = [c for c in chunks if c.chunk_type == "error"]
        assert len(error_chunks) == 1
        assert "unexpected failure" in error_chunks[0].error

        # done chunk should still be present
        assert chunks[-1].chunk_type == "done"
        assert chunks[-1].metadata["success"] is False

    def test_connection_error_triggers_fallback(self):
        adapter = LangChainAdapter()
        context = _make_context()
        call_models = []

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            call_models.append(model)
            if model == adapter.primary_model:
                import requests.exceptions
                raise requests.exceptions.ConnectionError("refused")
            content_parts.append("fallback ok")
            yield StreamChunk(content="fallback ok", chunk_type="content")

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        assert adapter.primary_model in call_models
        assert adapter.fallback_model in call_models

        done = chunks[-1]
        assert done.metadata["model_used"] == adapter.fallback_model
        assert done.metadata["success"] is True

    def test_timeout_error_triggers_fallback(self):
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            if model == adapter.primary_model:
                import requests.exceptions
                raise requests.exceptions.Timeout("timed out")
            content_parts.append("ok")
            yield StreamChunk(content="ok", chunk_type="content")

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        done = chunks[-1]
        assert done.metadata["model_used"] == adapter.fallback_model
        assert done.metadata["success"] is True

    def test_both_models_fail_yields_error(self):
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            import requests.exceptions
            raise requests.exceptions.ConnectionError(f"{model} down")

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        error_chunks = [c for c in chunks if c.chunk_type == "error"]
        assert len(error_chunks) == 1
        assert adapter.fallback_model in error_chunks[0].error

        done = chunks[-1]
        assert done.metadata["success"] is False

    def test_generic_connection_string_error_triggers_fallback(self):
        """Errors with 'connection' in the message also trigger fallback."""
        adapter = LangChainAdapter()
        context = _make_context()

        def side_effect(self_inner, model, msgs, content_parts, tc_list):
            if model == adapter.primary_model:
                raise OSError("connection reset by peer")
            content_parts.append("recovered")
            yield StreamChunk(content="recovered", chunk_type="content")

        with patch.object(LangChainAdapter, "_stream_from_model", side_effect):
            chunks = _collect(adapter.stream(context))

        done = chunks[-1]
        assert done.metadata["model_used"] == adapter.fallback_model
        assert done.metadata["success"] is True


# ---------------------------------------------------------------------------
# Tests: StreamChunk dataclass
# ---------------------------------------------------------------------------

class TestStreamChunkContract:
    def test_default_values(self):
        c = StreamChunk()
        assert c.content == ""
        assert c.chunk_type == "content"
        assert c.tool_call is None
        assert c.error is None
        assert c.metadata is None

    def test_content_chunk(self):
        c = StreamChunk(content="hi", chunk_type="content")
        assert c.content == "hi"

    def test_error_chunk(self):
        c = StreamChunk(chunk_type="error", error="oops")
        assert c.error == "oops"

    def test_done_chunk(self):
        c = StreamChunk(chunk_type="done", metadata={"model_used": "test"})
        assert c.metadata["model_used"] == "test"

    def test_tool_call_chunk(self):
        c = StreamChunk(chunk_type="tool_call", tool_call={"name": "fn", "arguments": {}})
        assert c.tool_call["name"] == "fn"

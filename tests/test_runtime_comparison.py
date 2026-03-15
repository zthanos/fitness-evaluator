"""Tests for Side-by-Side Runtime Comparison Mode (Phase 6, Task 6.3)

Validates the ENABLE_RUNTIME_COMPARISON setting, comparison report format,
diff logging, and telemetry integration.

Requirements: 6.2
"""
import json
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

from app.config import Settings
from app.models.chat_message import ChatMessage
from app.services.chat_message_handler import ChatMessageHandler
from app.services.runtime_comparison import (
    ComparisonReport,
    RuntimeResult,
    run_comparison,
    _log_comparison_telemetry,
)

_CHAT_SERVICE_PATCH = "app.services.chat_service.ChatService"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def mock_session_service():
    svc = Mock()
    svc.get_active_buffer = Mock(return_value=[])
    svc.append_messages = Mock()
    return svc


@pytest.fixture
def ce_response():
    return {
        "content": "CE says: rest day tomorrow.",
        "tool_calls_made": 2,
        "iterations": 3,
        "latency_ms": 150.0,
        "model_used": "mixtral",
        "context_token_count": 1200,
        "response_token_count": 45,
        "intent": "recovery_status",
        "evidence_cards": [],
    }


@pytest.fixture
def mock_agent(ce_response):
    agent = Mock()
    agent.execute = AsyncMock(return_value=ce_response)
    return agent


def _make_legacy_chat_service(content="Legacy reply", iterations=1):
    svc = MagicMock()
    svc.get_chat_response = AsyncMock(return_value={
        "content": content,
        "iterations": iterations,
    })
    return svc


def _comparison_settings(ce_active=True):
    return Settings(
        USE_CE_CHAT_RUNTIME=ce_active,
        LEGACY_CHAT_ENABLED=True,
        ENABLE_RUNTIME_COMPARISON=True,
    )


@pytest.fixture
def comparison_handler(mock_db, mock_session_service, mock_agent):
    """Handler with comparison mode enabled and CE as primary."""
    return ChatMessageHandler(
        db=mock_db,
        session_service=mock_session_service,
        agent=mock_agent,
        user_id=1,
        session_id=10,
        settings=_comparison_settings(ce_active=True),
    )


# ---------------------------------------------------------------------------
# 6.3.1 – ENABLE_RUNTIME_COMPARISON setting
# ---------------------------------------------------------------------------

class TestComparisonSetting:
    def test_setting_defaults_to_false(self):
        s = Settings()
        assert s.ENABLE_RUNTIME_COMPARISON is False

    def test_setting_can_be_enabled(self):
        s = Settings(ENABLE_RUNTIME_COMPARISON=True)
        assert s.ENABLE_RUNTIME_COMPARISON is True


# ---------------------------------------------------------------------------
# 6.3.2 – Comparison mode invokes both runtimes
# ---------------------------------------------------------------------------

class TestComparisonModeInvokesBoth:
    @pytest.mark.asyncio
    async def test_both_runtimes_called(
        self, comparison_handler, mock_agent
    ):
        mock_svc = _make_legacy_chat_service()
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await comparison_handler.handle_message("How's my recovery?")

        # CE agent was called
        mock_agent.execute.assert_called_once()
        # Legacy service was called
        mock_svc.get_chat_response.assert_called_once()
        # Comparison report attached
        assert "comparison" in result

    @pytest.mark.asyncio
    async def test_primary_result_returned_when_ce_active(
        self, comparison_handler
    ):
        mock_svc = _make_legacy_chat_service()
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await comparison_handler.handle_message("Plan my week")

        assert result["runtime"] == "ce"
        assert result["content"] == "CE says: rest day tomorrow."

    @pytest.mark.asyncio
    async def test_legacy_primary_when_ce_flag_off(
        self, mock_db, mock_session_service, mock_agent
    ):
        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=mock_agent,
            user_id=1,
            session_id=10,
            settings=Settings(
                USE_CE_CHAT_RUNTIME=False,
                ENABLE_RUNTIME_COMPARISON=True,
            ),
        )
        mock_svc = _make_legacy_chat_service("Legacy primary")
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await handler.handle_message("Hello")

        assert result["runtime"] == "legacy"
        assert result["content"] == "Legacy primary"

    @pytest.mark.asyncio
    async def test_comparison_disabled_skips_dual_run(
        self, mock_db, mock_session_service, mock_agent
    ):
        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=mock_agent,
            user_id=1,
            session_id=10,
            settings=Settings(
                USE_CE_CHAT_RUNTIME=True,
                ENABLE_RUNTIME_COMPARISON=False,
            ),
        )
        result = await handler.handle_message("Hi")
        # No comparison key when disabled
        assert "comparison" not in result

    @pytest.mark.asyncio
    async def test_ce_failure_falls_back_to_legacy_result(
        self, mock_db, mock_session_service
    ):
        failing_agent = Mock()
        failing_agent.execute = AsyncMock(side_effect=RuntimeError("CE boom"))

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=failing_agent,
            user_id=1,
            session_id=10,
            settings=_comparison_settings(ce_active=True),
        )
        mock_svc = _make_legacy_chat_service("Legacy fallback")
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            result = await handler.handle_message("Hello")

        # Falls back to legacy since CE failed
        assert result["runtime"] == "legacy"
        assert result["content"] == "Legacy fallback"

    @pytest.mark.asyncio
    async def test_both_fail_raises(
        self, mock_db, mock_session_service
    ):
        failing_agent = Mock()
        failing_agent.execute = AsyncMock(side_effect=RuntimeError("CE boom"))

        handler = ChatMessageHandler(
            db=mock_db,
            session_service=mock_session_service,
            agent=failing_agent,
            user_id=1,
            session_id=10,
            settings=_comparison_settings(ce_active=True),
        )
        mock_svc = MagicMock()
        mock_svc.get_chat_response = AsyncMock(
            side_effect=RuntimeError("Legacy boom")
        )
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            with pytest.raises(RuntimeError, match="Both runtimes failed"):
                await handler.handle_message("Hello")


# ---------------------------------------------------------------------------
# 6.3.3 – Log differences in latency, quality, tool calls, tokens
# ---------------------------------------------------------------------------

class TestComparisonDiffLogging:
    def test_compute_diffs_latency(self):
        report = ComparisonReport(
            timestamp="2026-01-01T00:00:00Z",
            user_message="test",
            user_id=1,
            session_id=10,
            ce_result=RuntimeResult(
                runtime="ce", content="A", latency_ms=200.0,
                tool_calls_made=2, iterations=3, context_token_count=1000,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="BB", latency_ms=300.0,
                tool_calls_made=1, iterations=1, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()

        assert report.latency_diff_ms == -100.0
        assert report.ce_faster is True

    def test_compute_diffs_tokens(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult(
                runtime="ce", content="x", latency_ms=100,
                tool_calls_made=0, iterations=0, context_token_count=800,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="x", latency_ms=100,
                tool_calls_made=0, iterations=0, context_token_count=200,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        assert report.token_diff == 600

    def test_compute_diffs_tool_calls(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult(
                runtime="ce", content="", latency_ms=0,
                tool_calls_made=3, iterations=2, context_token_count=0,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="", latency_ms=0,
                tool_calls_made=1, iterations=1, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        assert report.tool_calls_diff == 2
        assert report.iterations_diff == 1

    def test_compute_diffs_content_length(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult(
                runtime="ce", content="short", latency_ms=0,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="a much longer response here", latency_ms=0,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        assert report.content_length_diff == len("short") - len("a much longer response here")

    def test_both_succeeded_flag(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult(
                runtime="ce", content="ok", latency_ms=0,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="ok", latency_ms=0,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        assert report.both_succeeded is True

    def test_both_succeeded_false_on_error(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult(
                runtime="ce", content="", latency_ms=0,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=True, error="boom",
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="ok", latency_ms=0,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        assert report.both_succeeded is False

    def test_summary_includes_diffs(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult(
                runtime="ce", content="abc", latency_ms=100,
                tool_calls_made=1, iterations=1, context_token_count=500,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="abcdef", latency_ms=200,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        s = report.summary()
        assert "latency_diff=" in s
        assert "token_diff=" in s
        assert "tool_calls_diff=" in s
        assert "faster=ce" in s

    def test_summary_on_failure(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult.from_error("ce", RuntimeError("oops")),
            legacy_result=RuntimeResult(
                runtime="legacy", content="ok", latency_ms=0,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        s = report.summary()
        assert "incomplete" in s
        assert "ce" in s


# ---------------------------------------------------------------------------
# 6.3.4 – Comparison report format
# ---------------------------------------------------------------------------

class TestComparisonReportFormat:
    def test_to_dict_contains_all_fields(self):
        report = ComparisonReport(
            timestamp="2026-01-01T00:00:00Z",
            user_message="test",
            user_id=1,
            session_id=10,
            ce_result=RuntimeResult(
                runtime="ce", content="A", latency_ms=100,
                tool_calls_made=1, iterations=1, context_token_count=500,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="B", latency_ms=200,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        d = report.to_dict()

        assert d["timestamp"] == "2026-01-01T00:00:00Z"
        assert d["user_message"] == "test"
        assert d["user_id"] == 1
        assert d["session_id"] == 10
        assert "latency_diff_ms" in d
        assert "token_diff" in d
        assert "tool_calls_diff" in d
        assert "iterations_diff" in d
        assert "content_length_diff" in d
        assert "both_succeeded" in d
        assert "ce_faster" in d
        assert "ce" in d
        assert "legacy" in d

    def test_to_dict_is_json_serializable(self):
        report = ComparisonReport(
            timestamp="t", user_message="q", user_id=1, session_id=1,
            ce_result=RuntimeResult(
                runtime="ce", content="ok", latency_ms=50,
                tool_calls_made=0, iterations=0, context_token_count=100,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="ok", latency_ms=60,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()
        # Should not raise
        serialized = json.dumps(report.to_dict())
        assert isinstance(serialized, str)

    def test_runtime_result_from_response(self):
        resp = {
            "runtime": "ce",
            "content": "hello",
            "latency_ms": 42.0,
            "tool_calls_made": 1,
            "iterations": 2,
            "context_token_count": 300,
            "ce_context_used": True,
        }
        r = RuntimeResult.from_response(resp)
        assert r.runtime == "ce"
        assert r.content == "hello"
        assert r.latency_ms == 42.0
        assert r.error is None

    def test_runtime_result_from_error(self):
        r = RuntimeResult.from_error("legacy", ValueError("bad"))
        assert r.runtime == "legacy"
        assert r.error == "bad"
        assert r.content == ""


# ---------------------------------------------------------------------------
# 6.3.5 – Comparison results written to telemetry
# ---------------------------------------------------------------------------

class TestComparisonTelemetry:
    @pytest.mark.asyncio
    async def test_telemetry_logged_on_comparison(
        self, comparison_handler
    ):
        mock_logger = Mock()
        comparison_handler._invocation_logger = mock_logger

        mock_svc = _make_legacy_chat_service()
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            await comparison_handler.handle_message("Check my stats")

        mock_logger.log.assert_called_once()
        logged = mock_logger.log.call_args[0][0]
        assert logged.operation_type == "runtime_comparison"
        assert logged.athlete_id == 1

    @pytest.mark.asyncio
    async def test_telemetry_not_logged_when_no_logger(
        self, comparison_handler
    ):
        comparison_handler._invocation_logger = None
        mock_svc = _make_legacy_chat_service()
        with patch(_CHAT_SERVICE_PATCH, return_value=mock_svc):
            # Should not raise even without logger
            result = await comparison_handler.handle_message("Hi")
        assert "comparison" in result

    def test_log_comparison_telemetry_fields(self):
        mock_logger = Mock()
        report = ComparisonReport(
            timestamp="2026-01-01T00:00:00Z",
            user_message="test",
            user_id=42,
            session_id=7,
            ce_result=RuntimeResult(
                runtime="ce", content="A", latency_ms=100,
                tool_calls_made=1, iterations=1, context_token_count=500,
                ce_context_used=True,
            ),
            legacy_result=RuntimeResult(
                runtime="legacy", content="B", latency_ms=200,
                tool_calls_made=0, iterations=0, context_token_count=0,
                ce_context_used=False,
            ),
        )
        report.compute_diffs()

        _log_comparison_telemetry(mock_logger, report)

        mock_logger.log.assert_called_once()
        logged = mock_logger.log.call_args[0][0]
        assert logged.operation_type == "runtime_comparison"
        assert logged.athlete_id == 42
        assert logged.model_used == "comparison"
        assert logged.success_status is True
        assert logged.context_token_count == 500
        # total_latency_ms = ce + legacy
        assert logged.total_latency_ms == 300.0
        # latency_ms = max of both
        assert logged.latency_ms == 200.0


# ---------------------------------------------------------------------------
# run_comparison standalone tests
# ---------------------------------------------------------------------------

class TestRunComparison:
    @pytest.mark.asyncio
    async def test_captures_both_results(self):
        async def ce_fn(msg):
            return {
                "runtime": "ce", "content": "CE", "latency_ms": 50,
                "tool_calls_made": 1, "iterations": 1,
                "context_token_count": 400, "ce_context_used": True,
            }

        async def legacy_fn(msg):
            return {
                "runtime": "legacy", "content": "Legacy", "latency_ms": 80,
                "tool_calls_made": 0, "iterations": 0,
                "context_token_count": 0, "ce_context_used": False,
            }

        report = await run_comparison(
            user_message="hi",
            session_id=1,
            user_id=1,
            ce_handler_fn=ce_fn,
            legacy_handler_fn=legacy_fn,
        )

        assert report.ce_result is not None
        assert report.legacy_result is not None
        assert report.both_succeeded is True
        assert report.ce_faster is True

    @pytest.mark.asyncio
    async def test_captures_errors_without_raising(self):
        async def ce_fn(msg):
            raise RuntimeError("CE fail")

        async def legacy_fn(msg):
            return {
                "runtime": "legacy", "content": "ok", "latency_ms": 10,
                "tool_calls_made": 0, "iterations": 0,
                "context_token_count": 0, "ce_context_used": False,
            }

        report = await run_comparison(
            user_message="hi",
            session_id=1,
            user_id=1,
            ce_handler_fn=ce_fn,
            legacy_handler_fn=legacy_fn,
        )

        assert report.ce_result.error == "CE fail"
        assert report.legacy_result.error is None
        assert report.both_succeeded is False

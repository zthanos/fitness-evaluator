"""Tests for ToolOrchestrator failure handling (Task 4.4).

Validates:
- 4.4.1: Try-catch around tool execution with error classification
- 4.4.2: Structured error responses with error_type and is_retryable
- 4.4.3: LLM sees structured errors and can retry
- 4.4.4: Failure recovery strategies (retry respects is_retryable)
- 4.4.5: All tool failures logged with full detail
"""

import json
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.tool_orchestrator import (
    FailurePolicy,
    ReActStep,
    ToolErrorType,
    ToolFailureDetail,
    ToolInvocationRecord,
    ToolOrchestrator,
    ToolOrchestrationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOL_DEFS = [{"type": "function", "function": {"name": "get_data", "parameters": {}}}]


def _make_tool_call(name="get_data", args=None, call_id="tc_1"):
    return {
        "id": call_id,
        "function": {"name": name, "arguments": json.dumps(args or {})},
    }


def _llm_final(content="Done", model="test-model"):
    return {"content": content, "model": model}


def _llm_with_tools(tool_calls, content="", model="test-model"):
    return {"content": content, "tool_calls": tool_calls, "model": model}


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_llm():
    return MagicMock()


def _patch_execute_tool(monkeypatch, return_value=None, side_effect=None):
    coro = AsyncMock(return_value=return_value or {"success": True}, side_effect=side_effect)
    monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
    return coro


# ---------------------------------------------------------------------------
# 4.4.1 – Try-catch around tool execution with error classification
# ---------------------------------------------------------------------------


class TestTryCatchErrorClassification:
    """Each exception type is caught and classified into a ToolErrorType."""

    @pytest.mark.asyncio
    async def test_timeout_error_classified(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=TimeoutError("timed out"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.success is False
        assert rec.error_type == ToolErrorType.TIMEOUT_ERROR
        assert rec.is_retryable is True

    @pytest.mark.asyncio
    async def test_permission_error_classified(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=PermissionError("forbidden"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.error_type == ToolErrorType.PERMISSION_ERROR
        assert rec.is_retryable is False

    @pytest.mark.asyncio
    async def test_not_found_error_classified(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=FileNotFoundError("missing"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.error_type == ToolErrorType.NOT_FOUND_ERROR
        assert rec.is_retryable is False

    @pytest.mark.asyncio
    async def test_connection_error_classified(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=ConnectionError("refused"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.error_type == ToolErrorType.CONNECTION_ERROR
        assert rec.is_retryable is True

    @pytest.mark.asyncio
    async def test_value_error_classified_as_validation(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=ValueError("bad value"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.error_type == ToolErrorType.VALIDATION_ERROR
        assert rec.is_retryable is False

    @pytest.mark.asyncio
    async def test_generic_exception_classified_as_runtime(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=RuntimeError("unexpected"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.error_type == ToolErrorType.RUNTIME_ERROR
        assert rec.is_retryable is False

    @pytest.mark.asyncio
    async def test_lookup_error_classified_as_not_found(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=LookupError("not found"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.error_type == ToolErrorType.NOT_FOUND_ERROR


# ---------------------------------------------------------------------------
# 4.4.2 – Structured error responses
# ---------------------------------------------------------------------------


class TestStructuredErrorResponses:
    """Failed tool results include error_type and is_retryable in tool_results."""

    @pytest.mark.asyncio
    async def test_tool_results_contain_error_type(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=TimeoutError("slow"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        err_entry = result["tool_results"][0]
        assert err_entry["error_type"] == "timeout_error"
        assert err_entry["is_retryable"] is True
        assert "slow" in err_entry["error"]

    @pytest.mark.asyncio
    async def test_tool_results_non_retryable_error(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=PermissionError("denied"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        err_entry = result["tool_results"][0]
        assert err_entry["error_type"] == "permission_error"
        assert err_entry["is_retryable"] is False

    @pytest.mark.asyncio
    async def test_invocation_record_has_failure_detail(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=RuntimeError("crash"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.failure_detail is not None
        assert isinstance(rec.failure_detail, ToolFailureDetail)
        assert rec.failure_detail.tool_name == "get_data"
        assert rec.failure_detail.error_type == ToolErrorType.RUNTIME_ERROR
        assert rec.failure_detail.error_message == "crash"
        assert rec.failure_detail.traceback_summary is not None
        assert rec.failure_detail.user_id == 1

    @pytest.mark.asyncio
    async def test_successful_record_has_no_failure_detail(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, return_value={"ok": True})
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.success is True
        assert rec.failure_detail is None
        assert rec.error_type is None

    @pytest.mark.asyncio
    async def test_validation_error_has_error_type_in_record(self, mock_llm, mock_db, monkeypatch):
        """Parameter validation failures also get error_type on the record."""
        _patch_execute_tool(monkeypatch)
        tool_defs = [{
            "type": "function",
            "function": {
                "name": "save_goal",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        }]
        tc = _make_tool_call("save_goal", {})  # missing required 'name'
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([tc]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], tool_defs, user_id=1)

        rec = orch.invocation_log[0]
        assert rec.error_type == ToolErrorType.VALIDATION_ERROR
        assert rec.is_retryable is False


# ---------------------------------------------------------------------------
# 4.4.3 – LLM sees structured errors and can retry
# ---------------------------------------------------------------------------


class TestLLMSeesErrors:
    """Error details are appended to conversation so the LLM can react."""

    @pytest.mark.asyncio
    async def test_error_appended_to_conversation_with_type(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=TimeoutError("slow query"))
        conversation = []
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Let me try differently"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate(conversation, TOOL_DEFS, user_id=1)

        # Find the tool result message in conversation
        tool_msgs = [m for m in conversation if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        content = json.loads(tool_msgs[0]["content"])
        assert content["success"] is False
        assert content["error_type"] == "timeout_error"
        assert content["is_retryable"] is True
        assert "slow query" in content["error"]

    @pytest.mark.asyncio
    async def test_llm_receives_error_and_produces_final_answer(self, mock_llm, mock_db, monkeypatch):
        """After seeing an error, the LLM can choose to answer without tools."""
        _patch_execute_tool(monkeypatch, side_effect=ConnectionError("offline"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("I couldn't fetch the data, but based on what I know..."),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert "couldn't fetch" in result["content"]
        # LLM was called twice: once with tools, once after seeing error
        assert mock_llm.chat_completion.call_count == 2

    @pytest.mark.asyncio
    async def test_llm_retries_with_different_tool_after_error(self, mock_llm, mock_db, monkeypatch):
        """LLM sees error, then requests a different tool on next iteration."""
        call_count = 0

        async def _selective_execute(**kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("tool_name") == "get_data":
                raise ValueError("invalid params")
            return {"result": "ok"}

        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", _selective_execute)

        tc1 = _make_tool_call("get_data", call_id="c1")
        tc2 = _make_tool_call("backup_tool", call_id="c2")
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([tc1]),       # first try get_data
            _llm_with_tools([tc2]),       # LLM sees error, tries backup_tool
            _llm_final("Got it"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["content"] == "Got it"
        assert result["tool_calls_made"] == 1  # only backup_tool succeeded


# ---------------------------------------------------------------------------
# 4.4.4 – Failure recovery strategies (retry respects is_retryable)
# ---------------------------------------------------------------------------


class TestFailureRecoveryStrategies:
    """RETRY policy only retries retryable errors; non-retryable skip through."""

    @pytest.mark.asyncio
    async def test_retry_policy_retries_timeout(self, mock_llm, mock_db, monkeypatch):
        """TimeoutError is retryable, so RETRY policy should attempt again."""
        _patch_execute_tool(
            monkeypatch,
            side_effect=[TimeoutError("slow"), {"data": 42}],
        )
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.RETRY)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["tool_calls_made"] == 1
        assert len(orch.invocation_log) == 2
        assert orch.invocation_log[0].success is False
        assert orch.invocation_log[0].is_retryable is True
        assert orch.invocation_log[1].success is True

    @pytest.mark.asyncio
    async def test_retry_policy_retries_connection_error(self, mock_llm, mock_db, monkeypatch):
        """ConnectionError is retryable."""
        _patch_execute_tool(
            monkeypatch,
            side_effect=[ConnectionError("refused"), {"ok": True}],
        )
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.RETRY)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["tool_calls_made"] == 1
        assert orch.invocation_log[0].error_type == ToolErrorType.CONNECTION_ERROR

    @pytest.mark.asyncio
    async def test_retry_policy_skips_non_retryable_permission_error(self, mock_llm, mock_db, monkeypatch):
        """PermissionError is NOT retryable, so RETRY policy should NOT retry."""
        exec_mock = _patch_execute_tool(
            monkeypatch,
            side_effect=PermissionError("forbidden"),
        )
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Access denied"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.RETRY)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        # Only one invocation (no retry attempted)
        assert len(orch.invocation_log) == 1
        assert orch.invocation_log[0].is_retryable is False
        assert exec_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_policy_skips_non_retryable_value_error(self, mock_llm, mock_db, monkeypatch):
        """ValueError is NOT retryable."""
        exec_mock = _patch_execute_tool(
            monkeypatch,
            side_effect=ValueError("bad input"),
        )
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.RETRY)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert len(orch.invocation_log) == 1
        assert exec_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_fail_fast_raises_regardless_of_retryable(self, mock_llm, mock_db, monkeypatch):
        """FAIL_FAST always raises, even for retryable errors."""
        _patch_execute_tool(monkeypatch, side_effect=TimeoutError("slow"))
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_with_tools([_make_tool_call()])
        )
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.FAIL_FAST)

        with pytest.raises(ToolOrchestrationError, match="slow"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

    @pytest.mark.asyncio
    async def test_skip_continues_regardless_of_retryable(self, mock_llm, mock_db, monkeypatch):
        """SKIP always continues, even for retryable errors."""
        _patch_execute_tool(monkeypatch, side_effect=TimeoutError("slow"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Recovered"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["content"] == "Recovered"
        assert len(orch.invocation_log) == 1


# ---------------------------------------------------------------------------
# 4.4.5 – Log all tool failures with details
# ---------------------------------------------------------------------------


class TestToolFailureLogging:
    """Tool failures are logged with error_type, retryable flag, and traceback."""

    @pytest.mark.asyncio
    async def test_failure_log_includes_error_type(self, mock_llm, mock_db, monkeypatch, caplog):
        _patch_execute_tool(monkeypatch, side_effect=TimeoutError("slow"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        with caplog.at_level(logging.ERROR, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        error_msgs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_msgs) >= 1
        msg = error_msgs[0].message
        assert "error_type=timeout_error" in msg
        assert "retryable=True" in msg

    @pytest.mark.asyncio
    async def test_failure_log_includes_retryable_false(self, mock_llm, mock_db, monkeypatch, caplog):
        _patch_execute_tool(monkeypatch, side_effect=PermissionError("denied"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        with caplog.at_level(logging.ERROR, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        error_msgs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_msgs) >= 1
        msg = error_msgs[0].message
        assert "retryable=False" in msg

    @pytest.mark.asyncio
    async def test_failure_log_extra_has_structured_fields(self, mock_llm, mock_db, monkeypatch, caplog):
        _patch_execute_tool(monkeypatch, side_effect=ConnectionError("refused"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        with caplog.at_level(logging.ERROR, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1
        rec = error_records[0]
        assert rec.error_type == "connection_error"
        assert rec.is_retryable is True
        assert rec.tool_name == "get_data"
        assert rec.user_id == 1
        assert rec.traceback_summary is not None

    @pytest.mark.asyncio
    async def test_failure_detail_has_traceback_summary(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=RuntimeError("boom"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        detail = orch.invocation_log[0].failure_detail
        assert detail is not None
        assert "RuntimeError" in detail.traceback_summary
        assert "boom" in detail.traceback_summary

    @pytest.mark.asyncio
    async def test_act_step_metadata_includes_error_type(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, side_effect=ValueError("bad"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        act_steps = [r for r in orch.react_log if r.step == ReActStep.ACT]
        assert len(act_steps) == 1
        assert act_steps[0].metadata["error_type"] == "validation_error"
        assert act_steps[0].metadata["is_retryable"] is False

    @pytest.mark.asyncio
    async def test_retry_skip_logged_for_non_retryable(self, mock_llm, mock_db, monkeypatch, caplog):
        """When RETRY policy encounters non-retryable error, it logs the skip."""
        _patch_execute_tool(monkeypatch, side_effect=PermissionError("no"))
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.RETRY)

        with caplog.at_level(logging.INFO, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        skip_msgs = [r for r in caplog.records if "Skipping retry" in r.message]
        assert len(skip_msgs) == 1
        assert "not retryable" in skip_msgs[0].message

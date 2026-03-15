"""Tests for ToolOrchestrator execution policy (Task 4.3).

Validates:
- 4.3.1: Configurable max_iterations with validation
- 4.3.2: Configurable failure behavior (fail_fast, retry, skip)
- 4.3.3: Tool invocation logging with structured records
- 4.3.4: user_id scoping enforcement
- 4.3.5: Parameter validation before execution
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.tool_orchestrator import (
    FailurePolicy,
    ReActStep,
    ToolInvocationRecord,
    ToolOrchestrator,
    ToolOrchestrationError,
    ToolParameterValidationError,
    _MAX_ITERATIONS_CEILING,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_data",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback days"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_goal",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_type": {
                        "type": "string",
                        "enum": ["weight_loss", "performance"],
                    },
                    "description": {"type": "string"},
                },
                "required": ["goal_type", "description"],
            },
        },
    },
]


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


def _patch_execute_tool(monkeypatch, return_value=None):
    coro = AsyncMock(return_value=return_value or {"success": True})
    monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
    return coro


# ---------------------------------------------------------------------------
# 4.3.1 – Configurable max_iterations (default: 5)
# ---------------------------------------------------------------------------


class TestMaxIterationsConfig:
    """max_iterations is validated at construction time."""

    def test_default_max_iterations_is_five(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db)
        assert orch.max_iterations == 5

    def test_custom_max_iterations(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db, max_iterations=10)
        assert orch.max_iterations == 10

    def test_max_iterations_one_is_valid(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db, max_iterations=1)
        assert orch.max_iterations == 1

    def test_max_iterations_zero_raises(self, mock_llm, mock_db):
        with pytest.raises(ValueError, match="positive integer"):
            ToolOrchestrator(mock_llm, mock_db, max_iterations=0)

    def test_max_iterations_negative_raises(self, mock_llm, mock_db):
        with pytest.raises(ValueError, match="positive integer"):
            ToolOrchestrator(mock_llm, mock_db, max_iterations=-1)

    def test_max_iterations_exceeds_ceiling_raises(self, mock_llm, mock_db):
        with pytest.raises(ValueError, match="cannot exceed"):
            ToolOrchestrator(mock_llm, mock_db, max_iterations=_MAX_ITERATIONS_CEILING + 1)

    def test_max_iterations_at_ceiling_is_valid(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db, max_iterations=_MAX_ITERATIONS_CEILING)
        assert orch.max_iterations == _MAX_ITERATIONS_CEILING

    def test_max_iterations_non_int_raises(self, mock_llm, mock_db):
        with pytest.raises(ValueError, match="positive integer"):
            ToolOrchestrator(mock_llm, mock_db, max_iterations=2.5)

    @pytest.mark.asyncio
    async def test_iteration_limit_enforced_at_runtime(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_with_tools([_make_tool_call()])
        )
        orch = ToolOrchestrator(mock_llm, mock_db, max_iterations=2)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["max_iterations_reached"] is True
        assert result["iterations"] == 2


# ---------------------------------------------------------------------------
# 4.3.2 – Configurable failure behavior (fail_fast, retry, skip)
# ---------------------------------------------------------------------------


class TestFailureBehavior:
    """Failure policy controls how tool errors are handled."""

    def test_default_failure_policy_is_skip(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db)
        assert orch.failure_policy == FailurePolicy.SKIP

    def test_failure_policy_from_string(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy="retry")
        assert orch.failure_policy == FailurePolicy.RETRY

    def test_failure_policy_from_enum(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.FAIL_FAST)
        assert orch.failure_policy == FailurePolicy.FAIL_FAST

    @pytest.mark.asyncio
    async def test_skip_continues_after_failure(self, mock_llm, mock_db, monkeypatch):
        coro = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Recovered"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["content"] == "Recovered"
        assert any(r.get("error") for r in result["tool_results"])

    @pytest.mark.asyncio
    async def test_fail_fast_raises_on_failure(self, mock_llm, mock_db, monkeypatch):
        coro = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_with_tools([_make_tool_call()])
        )
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.FAIL_FAST)

        with pytest.raises(ToolOrchestrationError, match="boom"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

    @pytest.mark.asyncio
    async def test_retry_retries_once_on_failure(self, mock_llm, mock_db, monkeypatch):
        # First call fails with retryable error, second succeeds
        coro = AsyncMock(side_effect=[TimeoutError("transient"), {"data": 42}])
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.RETRY)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["content"] == "Done"
        assert result["tool_calls_made"] == 1
        # Two invocation records: original failure + retry success
        assert len(orch.invocation_log) == 2
        assert orch.invocation_log[0].success is False
        assert orch.invocation_log[1].success is True

    @pytest.mark.asyncio
    async def test_retry_falls_through_on_second_failure(self, mock_llm, mock_db, monkeypatch):
        coro = AsyncMock(side_effect=[TimeoutError("fail1"), TimeoutError("fail2")])
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.RETRY)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["content"] == "Sorry"
        # Both attempts failed
        assert len(orch.invocation_log) == 2
        assert all(not r.success for r in orch.invocation_log)


# ---------------------------------------------------------------------------
# 4.3.3 – Tool invocation logging
# ---------------------------------------------------------------------------


class TestToolInvocationLogging:
    """Every tool invocation is recorded with structured fields."""

    @pytest.mark.asyncio
    async def test_invocation_record_has_all_fields(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, {"value": 1})
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call("get_data", {"days": 7})]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=42)

        assert len(orch.invocation_log) == 1
        rec = orch.invocation_log[0]
        assert rec.tool_name == "get_data"
        assert rec.parameters == {"days": 7}
        assert rec.result == {"value": 1}
        assert rec.error is None
        assert rec.latency_ms >= 0
        assert rec.iteration == 1
        assert rec.success is True
        assert rec.user_id == 42
        assert rec.timestamp > 0

    @pytest.mark.asyncio
    async def test_failed_invocation_records_error(self, mock_llm, mock_db, monkeypatch):
        coro = AsyncMock(side_effect=RuntimeError("db down"))
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=5)

        rec = orch.invocation_log[0]
        assert rec.success is False
        assert "db down" in rec.error
        assert rec.user_id == 5

    @pytest.mark.asyncio
    async def test_multiple_tools_all_logged(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        tc1 = _make_tool_call("get_data", call_id="c1")
        tc2 = _make_tool_call("save_goal", {"goal_type": "performance", "description": "run faster"}, call_id="c2")
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([tc1, tc2]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert len(orch.invocation_log) == 2
        assert orch.invocation_log[0].tool_name == "get_data"
        assert orch.invocation_log[1].tool_name == "save_goal"

    @pytest.mark.asyncio
    async def test_invocation_log_cleared_between_runs(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("A"),
            _llm_final("B"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)
        assert len(orch.invocation_log) == 1

        await orch.orchestrate([], TOOL_DEFS, user_id=1)
        # Second run had no tools, log should be empty
        assert len(orch.invocation_log) == 0

    @pytest.mark.asyncio
    async def test_invocation_logging_includes_user_id(self, mock_llm, mock_db, monkeypatch, caplog):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        import logging
        with caplog.at_level(logging.INFO, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=99)

        exec_msgs = [r for r in caplog.records if "Executing tool" in r.message]
        assert len(exec_msgs) >= 1
        assert "user_id=99" in exec_msgs[0].message


# ---------------------------------------------------------------------------
# 4.3.4 – user_id scoping enforcement
# ---------------------------------------------------------------------------


class TestUserIdScoping:
    """user_id must be provided and is passed to every tool call."""

    @pytest.mark.asyncio
    async def test_none_user_id_raises(self, mock_llm, mock_db):
        orch = ToolOrchestrator(mock_llm, mock_db)

        with pytest.raises(ToolOrchestrationError, match="user_id is required"):
            await orch.orchestrate([], TOOL_DEFS, user_id=None)

    @pytest.mark.asyncio
    async def test_user_id_passed_to_execute_tool(self, mock_llm, mock_db, monkeypatch):
        exec_mock = _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=77)

        exec_mock.assert_called_once()
        call_kwargs = exec_mock.call_args
        assert call_kwargs.kwargs.get("user_id") == 77 or call_kwargs[1].get("user_id") == 77

    @pytest.mark.asyncio
    async def test_user_id_recorded_in_invocation_log(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=33)

        assert orch.invocation_log[0].user_id == 33


# ---------------------------------------------------------------------------
# 4.3.5 – Parameter validation before execution
# ---------------------------------------------------------------------------


class TestParameterValidation:
    """Tool parameters are validated against schemas before execution."""

    def test_validate_missing_required_param(self, mock_llm, mock_db):
        error = ToolOrchestrator._validate_tool_params(
            "save_goal",
            {"goal_type": "performance"},  # missing 'description'
            {
                "save_goal": {
                    "type": "object",
                    "properties": {
                        "goal_type": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["goal_type", "description"],
                }
            },
        )
        assert error is not None
        assert "description" in error

    def test_validate_unknown_param(self, mock_llm, mock_db):
        error = ToolOrchestrator._validate_tool_params(
            "get_data",
            {"days": 7, "bogus": "value"},
            {
                "get_data": {
                    "type": "object",
                    "properties": {"days": {"type": "integer"}},
                    "required": [],
                }
            },
        )
        assert error is not None
        assert "bogus" in error

    def test_validate_wrong_type(self, mock_llm, mock_db):
        error = ToolOrchestrator._validate_tool_params(
            "get_data",
            {"days": "seven"},
            {
                "get_data": {
                    "type": "object",
                    "properties": {"days": {"type": "integer"}},
                    "required": [],
                }
            },
        )
        assert error is not None
        assert "days" in error
        assert "integer" in error

    def test_validate_enum_violation(self, mock_llm, mock_db):
        error = ToolOrchestrator._validate_tool_params(
            "save_goal",
            {"goal_type": "invalid_type", "description": "test"},
            {
                "save_goal": {
                    "type": "object",
                    "properties": {
                        "goal_type": {
                            "type": "string",
                            "enum": ["weight_loss", "performance"],
                        },
                        "description": {"type": "string"},
                    },
                    "required": ["goal_type", "description"],
                }
            },
        )
        assert error is not None
        assert "invalid_type" in error

    def test_validate_valid_params_returns_none(self, mock_llm, mock_db):
        error = ToolOrchestrator._validate_tool_params(
            "save_goal",
            {"goal_type": "performance", "description": "run faster"},
            {
                "save_goal": {
                    "type": "object",
                    "properties": {
                        "goal_type": {
                            "type": "string",
                            "enum": ["weight_loss", "performance"],
                        },
                        "description": {"type": "string"},
                    },
                    "required": ["goal_type", "description"],
                }
            },
        )
        assert error is None

    def test_validate_unknown_tool_skips_validation(self, mock_llm, mock_db):
        error = ToolOrchestrator._validate_tool_params(
            "unknown_tool",
            {"anything": "goes"},
            {},
        )
        assert error is None

    def test_validate_empty_params_with_no_required(self, mock_llm, mock_db):
        error = ToolOrchestrator._validate_tool_params(
            "get_data",
            {},
            {
                "get_data": {
                    "type": "object",
                    "properties": {"days": {"type": "integer"}},
                    "required": [],
                }
            },
        )
        assert error is None

    @pytest.mark.asyncio
    async def test_validation_failure_skips_execution(self, mock_llm, mock_db, monkeypatch):
        """When validation fails, execute_tool should NOT be called."""
        exec_mock = _patch_execute_tool(monkeypatch)
        # Missing required 'description' param
        tc = _make_tool_call("save_goal", {"goal_type": "performance"})
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([tc]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        # execute_tool should not have been called
        exec_mock.assert_not_called()
        # But the error should be in tool_results
        assert any("Validation error" in str(r.get("error", "")) for r in result["tool_results"])

    @pytest.mark.asyncio
    async def test_validation_failure_with_fail_fast_raises(self, mock_llm, mock_db, monkeypatch):
        exec_mock = _patch_execute_tool(monkeypatch)
        tc = _make_tool_call("save_goal", {"goal_type": "performance"})
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_with_tools([tc])
        )
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.FAIL_FAST)

        with pytest.raises(ToolOrchestrationError, match="Validation error"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        exec_mock.assert_not_called()

    def test_validate_number_accepts_int_and_float(self, mock_llm, mock_db):
        """'number' type should accept both int and float."""
        schema = {
            "tool": {
                "type": "object",
                "properties": {"value": {"type": "number"}},
                "required": ["value"],
            }
        }
        assert ToolOrchestrator._validate_tool_params("tool", {"value": 42}, schema) is None
        assert ToolOrchestrator._validate_tool_params("tool", {"value": 3.14}, schema) is None
        error = ToolOrchestrator._validate_tool_params("tool", {"value": "nope"}, schema)
        assert error is not None

"""Tests for ToolOrchestrator ReAct pattern logging (Task 4.2).

Validates:
- Think step logging on each LLM invocation
- Act step logging on each tool execution
- Observe step logging when tool results are appended
- Full Think → Act → Observe → Repeat loop
- Debug summary emitted at orchestration end
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.tool_orchestrator import (
    FailurePolicy,
    ReActStep,
    ReActStepRecord,
    ToolOrchestrator,
    ToolOrchestrationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOL_DEFS = [{"type": "function", "function": {"name": "get_data", "parameters": {}}}]


def _make_tool_call(name: str = "get_data", args: dict = None, call_id: str = "tc_1"):
    return {
        "id": call_id,
        "function": {"name": name, "arguments": json.dumps(args or {})},
    }


def _llm_final(content: str = "Done", model: str = "test-model"):
    """LLM response with no tool calls (final answer)."""
    return {"content": content, "model": model}


def _llm_with_tools(tool_calls, content: str = "", model: str = "test-model"):
    """LLM response requesting tool calls."""
    return {"content": content, "tool_calls": tool_calls, "model": model}


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_llm():
    return MagicMock()


def _patch_execute_tool(monkeypatch, return_value=None):
    """Patch execute_tool to return a canned value."""
    coro = AsyncMock(return_value=return_value or {"success": True})
    monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
    return coro


# ---------------------------------------------------------------------------
# 4.2.1 – Reasoning (Think) step logging
# ---------------------------------------------------------------------------

class TestThinkStepLogging:
    """Think steps are recorded whenever the LLM is invoked."""

    @pytest.mark.asyncio
    async def test_think_logged_on_final_answer(self, mock_llm, mock_db, monkeypatch):
        mock_llm.chat_completion = AsyncMock(return_value=_llm_final("Hello"))
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        think_steps = [r for r in orch.react_log if r.step == ReActStep.THINK]
        assert len(think_steps) == 1
        assert "final answer" in think_steps[0].detail.lower()
        assert think_steps[0].iteration == 1
        assert think_steps[0].latency_ms >= 0

    @pytest.mark.asyncio
    async def test_think_logged_when_tools_requested(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Result"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        think_steps = [r for r in orch.react_log if r.step == ReActStep.THINK]
        assert len(think_steps) == 2
        # First think should mention tool names
        assert "get_data" in think_steps[0].detail
        assert think_steps[0].metadata["tool_calls_requested"] == ["get_data"]

    @pytest.mark.asyncio
    async def test_think_records_model_in_metadata(self, mock_llm, mock_db, monkeypatch):
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_final("Hi", model="mixtral")
        )
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        think = orch.react_log[0]
        assert think.metadata["model"] == "mixtral"


# ---------------------------------------------------------------------------
# 4.2.2 – Action (Act) step logging
# ---------------------------------------------------------------------------

class TestActStepLogging:
    """Act steps are recorded for each tool execution."""

    @pytest.mark.asyncio
    async def test_act_logged_on_successful_tool(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, {"data": 42})
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        act_steps = [r for r in orch.react_log if r.step == ReActStep.ACT]
        assert len(act_steps) == 1
        assert "get_data" in act_steps[0].detail
        assert "successfully" in act_steps[0].detail.lower()
        assert act_steps[0].metadata["success"] is True

    @pytest.mark.asyncio
    async def test_act_logged_on_failed_tool_skip(self, mock_llm, mock_db, monkeypatch):
        coro = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        act_steps = [r for r in orch.react_log if r.step == ReActStep.ACT]
        assert len(act_steps) == 1
        assert "FAILED" in act_steps[0].detail
        assert act_steps[0].metadata["success"] is False

    @pytest.mark.asyncio
    async def test_act_logged_before_fail_fast_raises(self, mock_llm, mock_db, monkeypatch):
        coro = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_with_tools([_make_tool_call()])
        )
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.FAIL_FAST)

        with pytest.raises(ToolOrchestrationError):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        act_steps = [r for r in orch.react_log if r.step == ReActStep.ACT]
        assert len(act_steps) == 1
        assert act_steps[0].metadata["failure_policy"] == "fail_fast"

    @pytest.mark.asyncio
    async def test_multiple_tools_each_get_act_step(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        tc1 = _make_tool_call("tool_a", call_id="tc_1")
        tc2 = _make_tool_call("tool_b", call_id="tc_2")
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([tc1, tc2]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        act_steps = [r for r in orch.react_log if r.step == ReActStep.ACT]
        assert len(act_steps) == 2
        names = [s.metadata["tool_name"] for s in act_steps]
        assert names == ["tool_a", "tool_b"]


# ---------------------------------------------------------------------------
# 4.2.3 – Observation (Observe) step logging
# ---------------------------------------------------------------------------

class TestObserveStepLogging:
    """Observe steps are recorded when tool results are appended."""

    @pytest.mark.asyncio
    async def test_observe_logged_after_tool_execution(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, {"value": "ok"})
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        obs_steps = [r for r in orch.react_log if r.step == ReActStep.OBSERVE]
        assert len(obs_steps) == 1
        assert "get_data" in obs_steps[0].detail
        assert "appended" in obs_steps[0].detail.lower()
        assert obs_steps[0].metadata["success"] is True
        assert obs_steps[0].metadata["result_length"] > 0

    @pytest.mark.asyncio
    async def test_observe_logged_for_failed_tool(self, mock_llm, mock_db, monkeypatch):
        coro = AsyncMock(side_effect=ValueError("bad input"))
        monkeypatch.setattr("app.services.tool_orchestrator.execute_tool", coro)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Sorry"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db, failure_policy=FailurePolicy.SKIP)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        obs_steps = [r for r in orch.react_log if r.step == ReActStep.OBSERVE]
        assert len(obs_steps) == 1
        assert obs_steps[0].metadata["success"] is False

    @pytest.mark.asyncio
    async def test_observe_truncates_long_results(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch, {"data": "x" * 200})
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        obs = [r for r in orch.react_log if r.step == ReActStep.OBSERVE][0]
        # The preview in the detail should be truncated
        assert "…" in obs.detail or obs.metadata["result_length"] > 120


# ---------------------------------------------------------------------------
# 4.2.4 – Full Think → Act → Observe → Repeat loop
# ---------------------------------------------------------------------------

class TestReActLoop:
    """The full loop cycles through Think, Act, Observe correctly."""

    @pytest.mark.asyncio
    async def test_single_iteration_sequence(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Answer"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        steps = [r.step for r in orch.react_log]
        # Iteration 1: Think → Act → Observe, then Iteration 2: Think (final)
        assert steps == [
            ReActStep.THINK,
            ReActStep.ACT,
            ReActStep.OBSERVE,
            ReActStep.THINK,
        ]

    @pytest.mark.asyncio
    async def test_multi_iteration_sequence(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call("t1", call_id="c1")]),
            _llm_with_tools([_make_tool_call("t2", call_id="c2")]),
            _llm_final("Final"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        steps = [r.step for r in orch.react_log]
        assert steps == [
            ReActStep.THINK, ReActStep.ACT, ReActStep.OBSERVE,  # iter 1
            ReActStep.THINK, ReActStep.ACT, ReActStep.OBSERVE,  # iter 2
            ReActStep.THINK,  # iter 3 – final answer
        ]

    @pytest.mark.asyncio
    async def test_no_tool_calls_only_think(self, mock_llm, mock_db, monkeypatch):
        mock_llm.chat_completion = AsyncMock(return_value=_llm_final("Direct"))
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        steps = [r.step for r in orch.react_log]
        assert steps == [ReActStep.THINK]

    @pytest.mark.asyncio
    async def test_max_iterations_still_logs_all_steps(self, mock_llm, mock_db, monkeypatch):
        _patch_execute_tool(monkeypatch)
        # Always request tools → will hit max_iterations
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_with_tools([_make_tool_call()])
        )
        orch = ToolOrchestrator(mock_llm, mock_db, max_iterations=2)

        result = await orch.orchestrate([], TOOL_DEFS, user_id=1)

        assert result["max_iterations_reached"] is True
        think_steps = [r for r in orch.react_log if r.step == ReActStep.THINK]
        act_steps = [r for r in orch.react_log if r.step == ReActStep.ACT]
        observe_steps = [r for r in orch.react_log if r.step == ReActStep.OBSERVE]
        assert len(think_steps) == 2
        assert len(act_steps) == 2
        assert len(observe_steps) == 2

    @pytest.mark.asyncio
    async def test_react_log_cleared_between_runs(self, mock_llm, mock_db, monkeypatch):
        mock_llm.chat_completion = AsyncMock(return_value=_llm_final("A"))
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)
        assert len(orch.react_log) == 1

        await orch.orchestrate([], TOOL_DEFS, user_id=1)
        # Should be fresh, not accumulated
        assert len(orch.react_log) == 1


# ---------------------------------------------------------------------------
# 4.2.5 – Debug logging for transparency
# ---------------------------------------------------------------------------

class TestDebugSummary:
    """A debug summary is emitted at the end of orchestration."""

    @pytest.mark.asyncio
    async def test_summary_logged_on_final_answer(self, mock_llm, mock_db, caplog, monkeypatch):
        mock_llm.chat_completion = AsyncMock(return_value=_llm_final("Hi"))
        orch = ToolOrchestrator(mock_llm, mock_db)

        import logging
        with caplog.at_level(logging.DEBUG, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        summary_msgs = [r for r in caplog.records if "ReAct summary" in r.message]
        assert len(summary_msgs) == 1
        assert "1 iteration(s)" in summary_msgs[0].message
        assert "0 tool call(s)" in summary_msgs[0].message

    @pytest.mark.asyncio
    async def test_summary_logged_on_max_iterations(self, mock_llm, mock_db, caplog, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(
            return_value=_llm_with_tools([_make_tool_call()])
        )
        orch = ToolOrchestrator(mock_llm, mock_db, max_iterations=1)

        import logging
        with caplog.at_level(logging.DEBUG, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        summary_msgs = [r for r in caplog.records if "ReAct summary" in r.message]
        assert len(summary_msgs) == 1
        assert "max_reached=True" in summary_msgs[0].message

    @pytest.mark.asyncio
    async def test_step_level_debug_logs_emitted(self, mock_llm, mock_db, caplog, monkeypatch):
        _patch_execute_tool(monkeypatch)
        mock_llm.chat_completion = AsyncMock(side_effect=[
            _llm_with_tools([_make_tool_call()]),
            _llm_final("Done"),
        ])
        orch = ToolOrchestrator(mock_llm, mock_db)

        import logging
        with caplog.at_level(logging.DEBUG, logger="app.services.tool_orchestrator"):
            await orch.orchestrate([], TOOL_DEFS, user_id=1)

        messages = [r.message for r in caplog.records]
        think_msgs = [m for m in messages if "[THINK]" in m]
        act_msgs = [m for m in messages if "[ACT]" in m]
        observe_msgs = [m for m in messages if "[OBSERVE]" in m]
        assert len(think_msgs) >= 1
        assert len(act_msgs) >= 1
        assert len(observe_msgs) >= 1

    @pytest.mark.asyncio
    async def test_react_step_record_has_timestamp(self, mock_llm, mock_db, monkeypatch):
        mock_llm.chat_completion = AsyncMock(return_value=_llm_final("Hi"))
        orch = ToolOrchestrator(mock_llm, mock_db)

        await orch.orchestrate([], TOOL_DEFS, user_id=1)

        for record in orch.react_log:
            assert record.timestamp > 0

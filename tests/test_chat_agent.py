"""Unit tests for ChatAgent (Phase 3 + Phase 4 + Phase 5 LLMAdapter integration).

Tests cover:
- 3.4.1 Simple query execution (no tool calls)
- 3.4.2 Execution with tool calls (via ToolOrchestrator)
- 3.4.3 Agent receives session context (conversation history)
- 3.4.4 Agent returns metadata
- 3.4.5 Agent handles LLM/orchestrator errors
- 3.4.6 Agent tracks latency
- 5.1.1 LLMAdapter replaces direct LLMClient calls
- 5.1.2 Context object passed to LLMAdapter.invoke()
- 5.1.4 LLMResponse metadata extracted into AgentResult

Requirements: 3.1, 3.2, 4.5, 5.1
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.chat_agent import ChatAgent
from app.services.tool_orchestrator import ToolOrchestrator
from app.ai.context.chat_context import ChatContextBuilder
from app.ai.adapter.llm_adapter import LLMProviderAdapter, LLMResponse
from app.ai.contracts.chat_contract import ChatResponseContract
from app.models.chat_message import ChatMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def mock_llm_client():
    """LLM client that returns a simple response with no tool calls."""
    client = Mock()
    client.chat_completion = AsyncMock(return_value={
        "content": "Great job on your run!",
        "model": "test-model",
    })
    return client


@pytest.fixture
def mock_llm_adapter():
    """LLMAdapter that returns a structured ChatResponseContract."""
    adapter = Mock(spec=LLMProviderAdapter)
    contract = ChatResponseContract(
        response_text="Great job on your run!",
        evidence_cards=[],
        confidence_score=0.85,
        follow_up_suggestions=None,
    )
    adapter.invoke.return_value = LLMResponse(
        parsed_output=contract,
        model_used="mixtral:8x7b-instruct",
        token_count=150,
        latency_ms=320,
    )
    return adapter


@pytest.fixture
def mock_context_builder(mock_db):
    """ChatContextBuilder with mocked internals so no DB/RAG needed."""
    builder = ChatContextBuilder(db=mock_db, token_budget=32000)

    # Stub out gather_data so it doesn't hit RAG/DB
    builder.gather_data = Mock(return_value=builder)

    return builder


@pytest.fixture
def mock_tool_orchestrator():
    """ToolOrchestrator that returns a simple response with no tool calls."""
    orchestrator = Mock(spec=ToolOrchestrator)
    orchestrator.orchestrate = AsyncMock(return_value={
        "content": "Great job on your run!",
        "tool_calls_made": 0,
        "iterations": 1,
        "tool_results": [],
        "max_iterations_reached": False,
        "model_used": "test-model",
        "response_token_count": 0,
        "intent": "general",
        "evidence_cards": [],
    })
    return orchestrator


@pytest.fixture
def agent(mock_context_builder, mock_llm_adapter, mock_db, mock_tool_orchestrator):
    """ChatAgent wired with mocked dependencies including LLMAdapter."""
    ag = ChatAgent(
        context_builder=mock_context_builder,
        llm_adapter=mock_llm_adapter,
        db=mock_db,
        tool_orchestrator=mock_tool_orchestrator,
    )
    # Pre-inject loaders so _load_defaults doesn't hit the filesystem
    ag._system_loader = Mock()
    ag._system_loader.load.return_value = "You are a coach."
    ag._task_loader = Mock()
    ag._task_loader.load.return_value = "Respond to the athlete."
    ag._domain_loader = Mock()
    dk_mock = Mock()
    dk_mock.to_dict.return_value = {"zones": ["Z1", "Z2"]}
    ag._domain_loader.load.return_value = dk_mock
    ag._behavior_summary = Mock()
    ag._behavior_summary.generate_summary.return_value = "Runs 4x/week."
    return ag


@pytest.fixture
def agent_no_adapter(mock_context_builder, mock_db, mock_llm_client, mock_tool_orchestrator):
    """ChatAgent with llm_adapter=None to test fallback to orchestrator."""
    ag = ChatAgent(
        context_builder=mock_context_builder,
        llm_adapter=None,
        db=mock_db,
        tool_orchestrator=mock_tool_orchestrator,
    )
    ag._system_loader = Mock()
    ag._system_loader.load.return_value = "You are a coach."
    ag._task_loader = Mock()
    ag._task_loader.load.return_value = "Respond to the athlete."
    ag._domain_loader = Mock()
    dk_mock = Mock()
    dk_mock.to_dict.return_value = {"zones": ["Z1", "Z2"]}
    ag._domain_loader.load.return_value = dk_mock
    ag._behavior_summary = Mock()
    ag._behavior_summary.generate_summary.return_value = "Runs 4x/week."
    return ag


def _make_message(role: str, content: str) -> ChatMessage:
    """Helper to create a ChatMessage without DB."""
    msg = Mock(spec=ChatMessage)
    msg.id = None
    msg.session_id = 1
    msg.role = role
    msg.content = content
    msg.created_at = datetime.utcnow()
    return msg


# ---------------------------------------------------------------------------
# 3.4.1 – Simple query (no tool calls) — now via LLMAdapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_execute_simple_query(agent, mock_llm_adapter):
    """Agent returns content from LLMAdapter when structured output succeeds."""
    result = await agent.execute(
        user_message="How was my run?",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="You are a coach.",
        task_instructions="Respond to the athlete.",
        domain_knowledge={"zones": ["Z1"]},
        athlete_summary="Runs 4x/week.",
    )

    assert result["content"] == "Great job on your run!"
    assert result["tool_calls_made"] == 0
    assert result["iterations"] == 0
    assert result["model_used"] == "mixtral:8x7b-instruct"
    mock_llm_adapter.invoke.assert_called_once()


# ---------------------------------------------------------------------------
# 5.1.2 – Context object passed to LLMAdapter.invoke()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_passed_to_llm_adapter(agent, mock_llm_adapter):
    """LLMAdapter.invoke() receives the Context object and ChatResponseContract."""
    await agent.execute(
        user_message="How was my run?",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={"z": 1},
        athlete_summary="Summary.",
    )

    call_kwargs = mock_llm_adapter.invoke.call_args
    # Positional or keyword: context and contract
    assert call_kwargs.kwargs.get("contract") is ChatResponseContract
    assert call_kwargs.kwargs.get("operation_type") == "chat_response"
    assert call_kwargs.kwargs.get("athlete_id") == 7
    # context should be a Context object with token_count
    ctx = call_kwargs.kwargs.get("context")
    assert hasattr(ctx, "token_count")
    assert hasattr(ctx, "to_messages")


# ---------------------------------------------------------------------------
# 5.1.4 – LLMResponse metadata extracted into AgentResult
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_response_metadata_extracted(agent, mock_llm_adapter):
    """Agent extracts model_used, token counts from LLMResponse."""
    contract = ChatResponseContract(
        response_text="Your pace improved!",
        evidence_cards=[],
        confidence_score=0.9,
        follow_up_suggestions=["Try intervals next week"],
    )
    mock_llm_adapter.invoke.return_value = LLMResponse(
        parsed_output=contract,
        model_used="llama3.1:8b-instruct",
        token_count=200,
        latency_ms=450,
    )

    result = await agent.execute(
        user_message="How is my pace?",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={"z": 1},
        athlete_summary="Summary.",
    )

    assert result["content"] == "Your pace improved!"
    assert result["model_used"] == "llama3.1:8b-instruct"
    assert result["tool_calls_made"] == 0
    assert result["evidence_cards"] == []


# ---------------------------------------------------------------------------
# 5.1.1 / 5.1.5 – Fallback to orchestrator when adapter is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_to_orchestrator_when_no_adapter(agent_no_adapter, mock_tool_orchestrator):
    """When llm_adapter is None, agent falls back to ToolOrchestrator."""
    result = await agent_no_adapter.execute(
        user_message="How was my run?",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={"z": 1},
        athlete_summary="Summary.",
    )

    assert result["content"] == "Great job on your run!"
    mock_tool_orchestrator.orchestrate.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5.1.1 – Fallback to orchestrator when adapter raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_to_orchestrator_on_adapter_error(agent, mock_llm_adapter, mock_tool_orchestrator):
    """When LLMAdapter.invoke() raises, agent falls back to ToolOrchestrator."""
    mock_llm_adapter.invoke.side_effect = ConnectionError("Model unreachable")

    result = await agent.execute(
        user_message="How was my run?",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={"z": 1},
        athlete_summary="Summary.",
    )

    assert result["content"] == "Great job on your run!"
    mock_tool_orchestrator.orchestrate.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3.4.2 – Execution with tool calls (via ToolOrchestrator fallback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_execute_with_tool_calls(agent, mock_llm_adapter, mock_tool_orchestrator):
    """Agent delegates tool calls to ToolOrchestrator when adapter fails."""
    # Simulate adapter failure so orchestrator path is taken
    mock_llm_adapter.invoke.side_effect = Exception("Structured output failed")

    mock_tool_orchestrator.orchestrate = AsyncMock(return_value={
        "content": "You ran 10 km yesterday at a 5:30 pace.",
        "tool_calls_made": 1,
        "iterations": 2,
        "tool_results": [{"tool_name": "get_my_recent_activities", "result": {"activities": [{"distance": 10}]}}],
        "max_iterations_reached": False,
        "model_used": "test-model",
        "response_token_count": 0,
        "intent": "general",
        "evidence_cards": [],
    })

    result = await agent.execute(
        user_message="What did I do yesterday?",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="You are a coach.",
        task_instructions="Respond.",
        domain_knowledge={"zones": ["Z1"]},
        athlete_summary="Runs daily.",
    )

    assert result["content"] == "You ran 10 km yesterday at a 5:30 pace."
    assert result["tool_calls_made"] == 1
    assert result["iterations"] == 2
    mock_tool_orchestrator.orchestrate.assert_awaited_once()
    call_kwargs = mock_tool_orchestrator.orchestrate.call_args.kwargs
    assert "conversation" in call_kwargs
    assert "tool_definitions" in call_kwargs
    assert "user_id" in call_kwargs
    assert call_kwargs["user_id"] == 7


# ---------------------------------------------------------------------------
# 3.4.3 – Agent receives session context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_receives_session_context(agent, mock_context_builder):
    """Conversation history from the session is forwarded to context builder."""
    history = [
        _make_message("user", "Hello"),
        _make_message("assistant", "Hi there!"),
    ]

    await agent.execute(
        user_message="Follow up question",
        session_id=1,
        user_id=7,
        conversation_history=history,
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={"z": 1},
        athlete_summary="Summary.",
    )

    # gather_data should have been called with the history converted to dicts
    mock_context_builder.gather_data.assert_called_once()
    call_kwargs = mock_context_builder.gather_data.call_args
    passed_history = call_kwargs.kwargs.get(
        "conversation_history",
        call_kwargs.args[2] if len(call_kwargs.args) > 2 else None,
    )
    assert len(passed_history) == 2
    assert passed_history[0]["role"] == "user"
    assert passed_history[1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# 3.4.4 – Agent returns metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_returns_metadata(agent):
    """Result dict contains all AgentResult fields."""
    result = await agent.execute(
        user_message="Check my goals",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={"z": 1},
        athlete_summary="Summary.",
    )

    # Required keys from AgentResult contract
    assert "content" in result
    assert "tool_calls_made" in result
    assert "iterations" in result
    assert "latency_ms" in result
    assert "model_used" in result
    assert "context_token_count" in result
    assert "response_token_count" in result
    assert "intent" in result
    assert "evidence_cards" in result

    # Types
    assert isinstance(result["content"], str)
    assert isinstance(result["tool_calls_made"], int)
    assert isinstance(result["iterations"], int)
    assert isinstance(result["latency_ms"], float)
    assert isinstance(result["model_used"], str)
    assert isinstance(result["context_token_count"], int)
    assert isinstance(result["evidence_cards"], list)


# ---------------------------------------------------------------------------
# 3.4.5 – Agent handles LLM errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_handles_llm_errors(agent, mock_llm_adapter, mock_tool_orchestrator):
    """When both adapter and orchestrator fail, exception propagates."""
    mock_llm_adapter.invoke.side_effect = ConnectionError("LLM unreachable")
    mock_tool_orchestrator.orchestrate = AsyncMock(
        side_effect=ConnectionError("LLM unreachable")
    )

    with pytest.raises(ConnectionError, match="LLM unreachable"):
        await agent.execute(
            user_message="Hello",
            session_id=1,
            user_id=7,
            conversation_history=[],
            system_instructions="Coach.",
            task_instructions="Respond.",
            domain_knowledge={"z": 1},
            athlete_summary="Summary.",
        )


# ---------------------------------------------------------------------------
# 3.4.6 – Agent tracks latency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_tracks_latency(agent):
    """Returned latency_ms is a positive float."""
    result = await agent.execute(
        user_message="Quick question",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={"z": 1},
        athlete_summary="Summary.",
    )

    assert result["latency_ms"] >= 0
    assert isinstance(result["latency_ms"], float)


# ---------------------------------------------------------------------------
# Extra: max iterations reached (via orchestrator fallback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_max_iterations_reached(mock_context_builder, mock_db):
    """When ToolOrchestrator hits max_iterations, agent returns the capped result."""
    adapter = Mock(spec=LLMProviderAdapter)
    adapter.invoke.side_effect = Exception("Force orchestrator path")

    orchestrator = Mock(spec=ToolOrchestrator)
    orchestrator.orchestrate = AsyncMock(return_value={
        "content": (
            "I apologize, but I need to simplify my approach. "
            "Could you rephrase your request?"
        ),
        "tool_calls_made": 2,
        "iterations": 2,
        "tool_results": [],
        "max_iterations_reached": True,
        "model_used": "unknown",
        "response_token_count": 0,
        "intent": "general",
        "evidence_cards": [],
    })

    ag = ChatAgent(
        context_builder=mock_context_builder,
        llm_adapter=adapter,
        db=mock_db,
        tool_orchestrator=orchestrator,
    )
    ag._system_loader = Mock()
    ag._system_loader.load.return_value = "Coach."
    ag._task_loader = Mock()
    ag._task_loader.load.return_value = "Respond."
    ag._domain_loader = Mock()
    dk = Mock(); dk.to_dict.return_value = {}
    ag._domain_loader.load.return_value = dk
    ag._behavior_summary = Mock()
    ag._behavior_summary.generate_summary.return_value = ""

    result = await ag.execute(
        user_message="Loop forever",
        session_id=1,
        user_id=7,
        conversation_history=[],
        system_instructions="Coach.",
        task_instructions="Respond.",
        domain_knowledge={},
        athlete_summary="",
    )

    assert result["iterations"] == 2
    assert "simplify my approach" in result["content"]
    assert result["tool_calls_made"] == 2
    orchestrator.orchestrate.assert_awaited_once()


# ---------------------------------------------------------------------------
# Extra: llm_client required when no tool_orchestrator provided
# ---------------------------------------------------------------------------


def test_agent_requires_llm_client_or_orchestrator(mock_context_builder, mock_db):
    """Raises ValueError when neither tool_orchestrator nor llm_client given."""
    adapter = Mock(spec=LLMProviderAdapter)
    with pytest.raises(ValueError, match="Either tool_orchestrator or llm_client"):
        ChatAgent(
            context_builder=mock_context_builder,
            llm_adapter=adapter,
            db=mock_db,
        )

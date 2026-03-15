"""Tests for Chat Message Handler (Thin Coordinator)

Verifies that ChatMessageHandler correctly coordinates between
ChatSessionService and ChatAgent without owning any business logic.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.chat_message_handler import ChatMessageHandler
from app.models.chat_message import ChatMessage
from app.config import Settings


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_session_service():
    """Mock ChatSessionService."""
    service = Mock()
    service.get_active_buffer = Mock(return_value=[])
    service.append_messages = Mock()
    return service


@pytest.fixture
def mock_agent():
    """Mock ChatAgent."""
    agent = Mock()
    agent.execute = AsyncMock(return_value={
        "content": "Hello! How can I help you today?",
        "tool_calls_made": 0,
        "iterations": 1,
        "latency_ms": 50.0,
        "model_used": "mixtral",
        "context_token_count": 800,
        "response_token_count": 20,
        "intent": "general",
        "evidence_cards": [],
    })
    return agent


@pytest.fixture
def ce_settings():
    """Settings with CE runtime enabled."""
    return Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True)


@pytest.fixture
def handler(mock_db, mock_session_service, mock_agent, ce_settings):
    """Create thin coordinator handler."""
    return ChatMessageHandler(
        db=mock_db,
        session_service=mock_session_service,
        agent=mock_agent,
        user_id=1,
        session_id=42,
        settings=ce_settings,
    )


@pytest.mark.asyncio
async def test_handle_message_delegates_to_agent(handler, mock_session_service, mock_agent):
    """Handler delegates execution to ChatAgent."""
    response = await handler.handle_message("Hello")

    assert response["content"] == "Hello! How can I help you today?"
    assert response["tool_calls_made"] == 0
    assert response["iterations"] == 1
    assert response["latency_ms"] >= 0
    assert response["ce_context_used"] is True

    # Agent was called with correct args
    mock_agent.execute.assert_called_once()
    call_kwargs = mock_agent.execute.call_args[1]
    assert call_kwargs["user_message"] == "Hello"
    assert call_kwargs["session_id"] == 42
    assert call_kwargs["user_id"] == 1


@pytest.mark.asyncio
async def test_handle_message_loads_session_buffer(handler, mock_session_service, mock_agent):
    """Handler loads conversation history from session service before calling agent."""
    history = [
        ChatMessage(session_id=42, role="user", content="Hi"),
        ChatMessage(session_id=42, role="assistant", content="Hello!"),
    ]
    mock_session_service.get_active_buffer.return_value = history

    await handler.handle_message("What are my goals?")

    mock_session_service.get_active_buffer.assert_called_once_with(42)
    call_kwargs = mock_agent.execute.call_args[1]
    assert call_kwargs["conversation_history"] == history


@pytest.mark.asyncio
async def test_handle_message_persists_messages(handler, mock_session_service, mock_agent):
    """Handler persists user and assistant messages after agent execution."""
    await handler.handle_message("Tell me about my training")

    mock_session_service.append_messages.assert_called_once_with(
        42,
        "Tell me about my training",
        "Hello! How can I help you today?",
    )


@pytest.mark.asyncio
async def test_handle_message_with_tool_calls(handler, mock_agent):
    """Handler passes through tool call metadata from agent."""
    mock_agent.execute.return_value = {
        "content": "Based on your goals...",
        "tool_calls_made": 2,
        "iterations": 3,
        "context_token_count": 1200,
        "model_used": "mixtral",
    }

    response = await handler.handle_message("What are my goals?")

    assert response["content"] == "Based on your goals..."
    assert response["tool_calls_made"] == 2
    assert response["iterations"] == 3
    assert response["context_token_count"] == 1200


@pytest.mark.asyncio
async def test_handle_message_propagates_agent_errors(handler, mock_agent):
    """Handler propagates exceptions from agent without swallowing them."""
    mock_agent.execute.side_effect = RuntimeError("LLM connection failed")

    with pytest.raises(RuntimeError, match="LLM connection failed"):
        await handler.handle_message("Hello")


@pytest.mark.asyncio
async def test_handle_message_performance(handler, mock_agent):
    """Latency should be minimal since handler only coordinates."""
    response = await handler.handle_message("Hello")
    assert response["latency_ms"] < 3000

"""Integration tests for ChatMessageHandler with CE architecture (Phase 3).

Verifies that the thin coordinator handler delegates to ChatAgent,
which owns all CE components (context builder, loaders, etc.).
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime

from app.services.chat_message_handler import ChatMessageHandler
from app.services.chat_session_service import ChatSessionService
from app.services.chat_agent import ChatAgent
from app.services.llm_client import LLMClient
from app.ai.context.chat_context import ChatContextBuilder
from app.models.chat_message import ChatMessage
from app.config import Settings


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_session_service():
    """Mock chat session service."""
    service = Mock(spec=ChatSessionService)
    service.get_active_buffer.return_value = []
    service.append_messages = Mock()
    return service


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = Mock(spec=LLMClient)
    client.chat_completion = AsyncMock(return_value={
        'content': 'Test response',
        'tool_calls': None
    })
    return client


@pytest.fixture
def agent(mock_db, mock_llm_client):
    """Create ChatAgent with real CE components."""
    context_builder = ChatContextBuilder(db=mock_db, token_budget=2400)
    agent = ChatAgent(
        context_builder=context_builder,
        llm_adapter=None,
        db=mock_db,
        llm_client=mock_llm_client,
    )
    agent._ensure_loaders()
    return agent


@pytest.fixture
def ce_settings():
    """Settings with CE runtime enabled."""
    return Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True)


@pytest.fixture
def chat_handler(mock_db, mock_session_service, agent, ce_settings):
    """Create thin coordinator ChatMessageHandler."""
    return ChatMessageHandler(
        db=mock_db,
        session_service=mock_session_service,
        agent=agent,
        user_id=1,
        session_id=1,
        settings=ce_settings,
    )


def test_chat_handler_has_no_legacy_methods(chat_handler):
    """Handler should not own context building, tool orchestration, or LLM logic."""
    assert not hasattr(chat_handler, '_retrieve_context')
    assert not hasattr(chat_handler, '_build_conversation')
    assert not hasattr(chat_handler, '_get_system_prompt')
    assert not hasattr(chat_handler, '_orchestrate_tools')
    assert not hasattr(chat_handler, 'context_builder')
    assert not hasattr(chat_handler, 'system_loader')
    assert not hasattr(chat_handler, 'llm_client')


def test_chat_handler_is_thin_coordinator(chat_handler):
    """Handler should only have session_service, agent, and identifiers."""
    assert hasattr(chat_handler, 'session_service')
    assert hasattr(chat_handler, 'agent')
    assert hasattr(chat_handler, 'user_id')
    assert hasattr(chat_handler, 'session_id')


def test_agent_initializes_ce_components(agent):
    """ChatAgent should own all CE components."""
    assert agent.context_builder is not None
    assert agent._system_loader is not None
    assert agent._task_loader is not None
    assert agent._domain_loader is not None
    assert agent._behavior_summary is not None


@pytest.mark.asyncio
async def test_handle_message_delegates_to_agent(chat_handler, mock_session_service):
    """handle_message should delegate to ChatAgent.execute."""
    # Mock the agent's execute method
    chat_handler.agent.execute = AsyncMock(return_value={
        'content': 'Agent response',
        'tool_calls_made': 0,
        'iterations': 1,
        'context_token_count': 800,
    })

    result = await chat_handler.handle_message("Test message")

    assert result['content'] == 'Agent response'
    assert result['ce_context_used'] is True
    assert result['context_token_count'] == 800
    chat_handler.agent.execute.assert_called_once()
    mock_session_service.append_messages.assert_called_once()


@pytest.mark.asyncio
async def test_handle_message_passes_session_history(chat_handler, mock_session_service):
    """Handler should pass session buffer to agent."""
    history = [
        ChatMessage(session_id=1, role='user', content='Hi'),
        ChatMessage(session_id=1, role='assistant', content='Hello!'),
    ]
    mock_session_service.get_active_buffer.return_value = history

    chat_handler.agent.execute = AsyncMock(return_value={
        'content': 'Response',
        'tool_calls_made': 0,
        'iterations': 1,
        'context_token_count': 500,
    })

    await chat_handler.handle_message("Follow up")

    call_kwargs = chat_handler.agent.execute.call_args[1]
    assert call_kwargs['conversation_history'] == history
    assert call_kwargs['user_message'] == "Follow up"


def test_system_loader_can_load_template(agent):
    """System loader should load versioned templates."""
    system_instructions = agent._system_loader.load(version="1.0.0")
    assert isinstance(system_instructions, str)
    assert len(system_instructions) > 0


def test_task_loader_can_load_template(agent):
    """Task loader should load versioned templates."""
    task_instructions = agent._task_loader.load(
        operation="chat_response",
        version="1.0.0",
        params={
            "athlete_id": 1,
            "session_id": 1,
            "timestamp": datetime.now().isoformat()
        }
    )
    assert isinstance(task_instructions, str)
    assert len(task_instructions) > 0


def test_domain_loader_can_load_knowledge(agent):
    """Domain loader should load domain knowledge."""
    domain_knowledge = agent._domain_loader.load()
    assert hasattr(domain_knowledge, 'training_zones')
    assert hasattr(domain_knowledge, 'effort_levels')
    assert hasattr(domain_knowledge, 'recovery_guidelines')
    assert hasattr(domain_knowledge, 'nutrition_targets')
    assert len(domain_knowledge.training_zones) > 0

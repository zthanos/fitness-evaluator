"""Tests for Chat Message Handler

Tests multi-step tool orchestration, RAG context retrieval, and performance.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.chat_message_handler import ChatMessageHandler
from app.models.chat_message import ChatMessage


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_rag_engine():
    """Mock RAG engine."""
    engine = Mock()
    engine.retrieve_context = Mock(return_value="=== Current Session ===\nuser: Hello\nassistant: Hi there!")
    engine.persist_session = Mock()
    return engine


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = Mock()
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture
def handler(mock_db, mock_rag_engine, mock_llm_client):
    """Create chat message handler."""
    return ChatMessageHandler(
        db=mock_db,
        rag_engine=mock_rag_engine,
        llm_client=mock_llm_client,
        user_id=1,
        session_id=42
    )


@pytest.mark.asyncio
async def test_handle_message_without_tools(handler, mock_rag_engine, mock_llm_client):
    """Test handling a message that doesn't require tools."""
    # Mock LLM response without tool calls
    mock_llm_client.chat_completion.return_value = {
        'content': 'Hello! How can I help you today?',
        'role': 'assistant'
    }
    
    # Handle message
    response = await handler.handle_message("Hello")
    
    # Verify response
    assert response['content'] == 'Hello! How can I help you today?'
    assert response['tool_calls_made'] == 0
    assert response['iterations'] == 1
    assert response['latency_ms'] > 0
    assert response['context_retrieved'] is True
    
    # Verify context was retrieved
    mock_rag_engine.retrieve_context.assert_called_once()
    
    # Verify LLM was called
    mock_llm_client.chat_completion.assert_called_once()


@pytest.mark.asyncio
async def test_handle_message_with_single_tool(handler, mock_db, mock_llm_client):
    """Test handling a message that requires one tool call."""
    # Mock LLM responses
    mock_llm_client.chat_completion.side_effect = [
        # First call: LLM requests tool
        {
            'content': '',
            'tool_calls': [
                {
                    'id': 'call_1',
                    'function': {
                        'name': 'get_my_goals',
                        'arguments': '{}'
                    }
                }
            ]
        },
        # Second call: LLM responds with tool result
        {
            'content': 'Based on your goals, here are my recommendations...',
            'role': 'assistant'
        }
    ]
    
    # Mock tool execution
    with patch('app.services.chat_message_handler.execute_tool') as mock_execute:
        mock_execute.return_value = {
            'success': True,
            'goals': [{'goal_type': 'performance', 'description': 'Run a sub-4 hour marathon'}]
        }
        
        # Handle message
        response = await handler.handle_message("What are my goals?")
        
        # Verify response
        assert 'recommendations' in response['content']
        assert response['tool_calls_made'] == 1
        assert response['iterations'] == 2
        
        # Verify tool was executed
        mock_execute.assert_called_once()


@pytest.mark.asyncio
async def test_handle_message_with_multiple_tools(handler, mock_db, mock_llm_client):
    """Test handling a message that requires multiple sequential tool calls."""
    # Mock LLM responses
    mock_llm_client.chat_completion.side_effect = [
        # First call: LLM requests first tool
        {
            'content': '',
            'tool_calls': [
                {
                    'id': 'call_1',
                    'function': {
                        'name': 'get_my_recent_activities',
                        'arguments': '{"days": 28}'
                    }
                }
            ]
        },
        # Second call: LLM requests second tool
        {
            'content': '',
            'tool_calls': [
                {
                    'id': 'call_2',
                    'function': {
                        'name': 'get_my_weekly_metrics',
                        'arguments': '{"weeks": 4}'
                    }
                }
            ]
        },
        # Third call: LLM responds with final answer
        {
            'content': 'Based on your recent training, I recommend...',
            'role': 'assistant'
        }
    ]
    
    # Mock tool execution
    with patch('app.services.chat_message_handler.execute_tool') as mock_execute:
        mock_execute.side_effect = [
            {'success': True, 'activities': [], 'count': 0},
            {'success': True, 'weekly_metrics': [], 'weeks': 4}
        ]
        
        # Handle message
        response = await handler.handle_message("Analyze my training")
        
        # Verify response
        assert 'recommend' in response['content']
        assert response['tool_calls_made'] == 2
        assert response['iterations'] == 3
        
        # Verify tools were executed
        assert mock_execute.call_count == 2


@pytest.mark.asyncio
async def test_handle_message_max_iterations(handler, mock_llm_client):
    """Test that max iterations limit is enforced."""
    # Mock LLM to always request tools
    mock_llm_client.chat_completion.return_value = {
        'content': '',
        'tool_calls': [
            {
                'id': 'call_1',
                'function': {
                    'name': 'get_my_goals',
                    'arguments': '{}'
                }
            }
        ]
    }
    
    # Mock tool execution
    with patch('app.services.chat_message_handler.execute_tool') as mock_execute:
        mock_execute.return_value = {'success': True, 'goals': []}
        
        # Handle message with low max iterations
        response = await handler.handle_message("Test", max_tool_iterations=2)
        
        # Verify max iterations reached
        assert response['iterations'] == 2
        assert 'simplify' in response['content'].lower() or 'rephrase' in response['content'].lower()


@pytest.mark.asyncio
async def test_handle_message_tool_error(handler, mock_llm_client):
    """Test handling of tool execution errors."""
    # Mock LLM responses
    mock_llm_client.chat_completion.side_effect = [
        # First call: LLM requests tool
        {
            'content': '',
            'tool_calls': [
                {
                    'id': 'call_1',
                    'function': {
                        'name': 'get_my_goals',
                        'arguments': '{}'
                    }
                }
            ]
        },
        # Second call: LLM handles error
        {
            'content': 'I encountered an error retrieving your goals. Please try again.',
            'role': 'assistant'
        }
    ]
    
    # Mock tool execution to raise error
    with patch('app.services.chat_message_handler.execute_tool') as mock_execute:
        mock_execute.side_effect = Exception("Database error")
        
        # Handle message
        response = await handler.handle_message("What are my goals?")
        
        # Verify error was handled gracefully
        assert response['content']
        assert response['tool_calls_made'] == 0  # Tool failed, not counted


@pytest.mark.asyncio
async def test_handle_message_performance(handler, mock_llm_client):
    """Test that performance target is met (< 3 seconds)."""
    # Mock simple response
    mock_llm_client.chat_completion.return_value = {
        'content': 'Quick response',
        'role': 'assistant'
    }
    
    # Handle message
    response = await handler.handle_message("Hello")
    
    # Verify latency is reasonable (should be much less than 3000ms in tests)
    assert response['latency_ms'] < 3000


def test_update_active_buffer(handler):
    """Test updating active session buffer."""
    # Initially empty
    assert len(handler.active_session_messages) == 0
    
    # Update buffer
    handler._update_active_buffer("Hello", "Hi there!")
    
    # Verify messages added
    assert len(handler.active_session_messages) == 2
    assert handler.active_session_messages[0].role == 'user'
    assert handler.active_session_messages[0].content == "Hello"
    assert handler.active_session_messages[1].role == 'assistant'
    assert handler.active_session_messages[1].content == "Hi there!"


def test_load_session_messages(handler):
    """Test loading existing session messages."""
    # Create mock messages
    messages = [
        ChatMessage(session_id=42, role='user', content='Hello'),
        ChatMessage(session_id=42, role='assistant', content='Hi!')
    ]
    
    # Load messages
    handler.load_session_messages(messages)
    
    # Verify loaded
    assert len(handler.active_session_messages) == 2
    assert handler.active_session_messages[0].content == 'Hello'


def test_clear_active_buffer(handler):
    """Test clearing active session buffer."""
    # Add some messages
    handler._update_active_buffer("Hello", "Hi!")
    assert len(handler.active_session_messages) == 2
    
    # Clear buffer
    handler.clear_active_buffer()
    
    # Verify cleared
    assert len(handler.active_session_messages) == 0


@pytest.mark.asyncio
async def test_persist_session(handler, mock_rag_engine):
    """Test persisting session to vector store."""
    # Add messages to buffer
    handler._update_active_buffer("Hello", "Hi there!")
    
    # Persist session
    await handler.persist_session(eval_score=8.5)
    
    # Verify RAG engine was called
    mock_rag_engine.persist_session.assert_called_once()
    call_args = mock_rag_engine.persist_session.call_args
    assert call_args[1]['user_id'] == 1
    assert call_args[1]['session_id'] == 42
    assert call_args[1]['eval_score'] == 8.5
    assert len(call_args[1]['messages']) == 2


@pytest.mark.asyncio
async def test_persist_session_empty_buffer(handler, mock_rag_engine):
    """Test persisting empty session does nothing."""
    # Persist empty session
    await handler.persist_session()
    
    # Verify RAG engine was not called
    mock_rag_engine.persist_session.assert_not_called()


def test_build_conversation_with_context(handler):
    """Test building conversation with retrieved context."""
    # Add some messages to buffer
    handler._update_active_buffer("Previous message", "Previous response")
    
    # Build conversation
    conversation = handler._build_conversation(
        user_message="New message",
        context="=== Current Session ===\nuser: Hello"
    )
    
    # Verify structure
    assert len(conversation) >= 3  # system + previous messages + new message
    assert conversation[0]['role'] == 'system'
    assert 'Retrieved Context' in conversation[0]['content']
    assert conversation[-1]['role'] == 'user'
    assert conversation[-1]['content'] == "New message"


def test_build_conversation_without_context(handler):
    """Test building conversation without context."""
    # Build conversation
    conversation = handler._build_conversation(
        user_message="Hello",
        context=""
    )
    
    # Verify structure
    assert len(conversation) == 2  # system + user message
    assert conversation[0]['role'] == 'system'
    assert 'Retrieved Context' not in conversation[0]['content']
    assert conversation[1]['role'] == 'user'
    assert conversation[1]['content'] == "Hello"

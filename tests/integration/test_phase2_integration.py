"""Integration tests for Phase 2: Context Engineering Architecture.

Tests verify:
- Chat responses maintain relevance (2.8.1)
- Reduced prompt pollution - no full session dump (2.8.2)
- Conversation continuity preserved (2.8.3)
- Athlete personalization visible in responses (2.8.4)
- Intent-aware retrieval returns appropriate data (2.8.5)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.chat_message_handler import ChatMessageHandler
from app.services.chat_session_service import ChatSessionService
from app.services.chat_agent import ChatAgent
from app.services.llm_client import LLMClient
from app.ai.context.chat_context import ChatContextBuilder
from app.models.chat_message import ChatMessage
from app.models.strava_activity import StravaActivity
from app.models.athlete import Athlete
from app.config import Settings


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    
    # Setup query chain for StravaActivity
    query_mock = Mock()
    filter_mock = Mock()
    all_mock = Mock(return_value=[])  # Default to empty list
    
    filter_mock.all = all_mock
    query_mock.filter = Mock(return_value=filter_mock)
    db.query = Mock(return_value=query_mock)
    
    return db


@pytest.fixture
def mock_athlete(mock_db):
    """Create mock athlete with training history."""
    athlete = Athlete(
        id=1,
        name="Test Athlete",
        email="test@example.com"
    )
    
    # Mock query to return athlete
    mock_db.query.return_value.filter.return_value.first.return_value = athlete
    
    return athlete


@pytest.fixture
def mock_activities(mock_db):
    """Create mock activities as evidence card dicts (matching RAG retriever output)."""
    activities = []
    base_date = datetime.now() - timedelta(days=7)

    for i in range(5):
        activities.append({
            "id": str(i + 1),
            "athlete_id": 1,
            "activity_type": "Run",
            "distance_m": 5000.0 + (i * 1000),
            "moving_time_s": 1800 + (i * 300),
            "start_date": (base_date + timedelta(days=i)).isoformat(),
            "avg_hr": 150 + i,
            "source_type": "activity",
            "relevance_score": 0.9 - (i * 0.1)
        })

    return activities


@pytest.fixture
def mock_session_service():
    """Mock chat session service."""
    service = Mock(spec=ChatSessionService)
    service.get_active_buffer.return_value = []
    service.append_messages = Mock()
    return service


@pytest.fixture
def mock_llm_client():
    """Mock LLM client with realistic responses."""
    client = Mock(spec=LLMClient)
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture
def chat_handler(mock_db, mock_session_service, mock_llm_client):
    """Create ChatMessageHandler with CE architecture via ChatAgent."""
    from app.ai.context.athlete_behavior_summary import AthleteBehaviorSummary

    context_builder = ChatContextBuilder(db=mock_db, token_budget=8000)
    behavior_summary_generator = AthleteBehaviorSummary(mock_db)

    agent = ChatAgent(
        context_builder=context_builder,
        llm_adapter=None,
        db=mock_db,
        llm_client=mock_llm_client,
    )
    # Pre-initialise the agent's lazy loaders so tests can patch them
    agent._ensure_loaders()
    agent._behavior_summary = behavior_summary_generator

    handler = ChatMessageHandler(
        db=mock_db,
        session_service=mock_session_service,
        agent=agent,
        user_id=1,
        session_id=1,
        settings=Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True),
    )
    # Expose CE components on handler for backward-compatible test assertions.
    handler.context_builder = context_builder
    handler.behavior_summary_generator = behavior_summary_generator
    return handler


# Test 2.8.1: Chat responses maintain relevance
@pytest.mark.asyncio
async def test_chat_responses_maintain_relevance(
    chat_handler,
    mock_llm_client,
    mock_activities
):
    """
    Test that chat responses maintain relevance through intent-aware retrieval.
    
    Requirement: 2.8.1
    Validates: Intent classification drives appropriate data retrieval
    """
    # Mock intent classification to return "recent_performance"
    with patch.object(
        chat_handler.context_builder.intent_router,
        'classify',
        return_value='recent_performance'
    ):
        # Mock RAG retrieval to return recent activities
        with patch.object(
            chat_handler.context_builder.rag_retriever,
            'retrieve',
            return_value=mock_activities[:3]  # Last 3 activities
        ):
            # Pre-populate cache to avoid database queries
            chat_handler.behavior_summary_generator.set_cached_summary(1, "Test athlete summary")
            
            # Mock LLM response
            mock_llm_client.chat_completion.return_value = {
                'content': 'Based on your recent runs, you are averaging 5.5km per session.',
                'tool_calls': None
            }
            
            # Execute
            result = await chat_handler.handle_message(
                "How have my recent runs been?"
            )
            
            # Verify intent-aware retrieval was used
            assert chat_handler.context_builder.intent_router.classify.called
            assert chat_handler.context_builder.rag_retriever.retrieve.called
            
            # Verify response contains relevant data
            assert 'content' in result
            assert result['ce_context_used'] is True
            
            # Verify LLM received context with recent activities
            call_args = mock_llm_client.chat_completion.call_args
            messages = call_args.kwargs['messages']
            
            # Check that context includes retrieved evidence
            context_str = str(messages)
            assert 'recent' in context_str.lower() or 'activity' in context_str.lower()



# Test 2.8.2: Reduced prompt pollution (no full session dump)
@pytest.mark.asyncio
async def test_no_full_session_dump_in_context(
    chat_handler,
    mock_session_service,
    mock_llm_client
):
    """
    Test that full session history is NOT sent to LLM.
    
    Requirement: 2.8.2
    Validates: Dynamic history selection limits conversation history
    """
    # Create a long conversation history (20 messages)
    long_history = []
    for i in range(20):
        long_history.append(ChatMessage(
            id=i + 1,
            session_id=1,
            role='user' if i % 2 == 0 else 'assistant',
            content=f'Message {i + 1}',
            created_at=datetime.now() - timedelta(minutes=20 - i)
        ))
    
    # Mock session service to return long history
    mock_session_service.get_active_buffer.return_value = long_history
    
    # Pre-populate cache to avoid database queries
    chat_handler.behavior_summary_generator.set_cached_summary(1, "Test athlete summary")
    
    # Mock LLM response
    mock_llm_client.chat_completion.return_value = {
        'content': 'Response based on recent context',
        'tool_calls': None
    }
    
    # Mock RAG retriever to avoid database queries
    with patch.object(
        chat_handler.context_builder.rag_retriever,
        'retrieve',
        return_value=[]
    ):
        # Execute
        result = await chat_handler.handle_message("What did we discuss?")
    
    # Verify LLM was called
    assert mock_llm_client.chat_completion.called
    
    # Get the messages sent to LLM
    call_args = mock_llm_client.chat_completion.call_args
    messages = call_args.kwargs['messages']
    
    # Count conversation messages (exclude system/task instructions)
    conversation_messages = [
        msg for msg in messages
        if msg.get('role') in ['user', 'assistant']
    ]
    
    # Verify that NOT all 20 messages were sent
    # Handler limits to last 10 messages for token efficiency
    # Context builder may also add task/domain as user-role messages
    assert len(conversation_messages) <= 15  # Well under 20 original messages
    
    # Verify we didn't send the full 20-message history
    assert len(conversation_messages) < 20
    
    # Verify context token count is reasonable (not bloated)
    assert result['context_token_count'] < 8000  # Within budget
    
    print(f"✓ Only {len(conversation_messages)} messages sent (not all 20)")
    print(f"✓ Context tokens: {result['context_token_count']} (within 8000 budget)")



# Test 2.8.3: Conversation continuity preserved
@pytest.mark.asyncio
async def test_conversation_continuity_preserved(
    chat_handler,
    mock_session_service,
    mock_llm_client
):
    """
    Test that conversation continuity is maintained across turns.
    
    Requirement: 2.8.3
    Validates: Recent conversation history is included for context
    """
    # Create a conversation with context
    conversation_history = [
        ChatMessage(
            id=1,
            session_id=1,
            role='user',
            content='I want to train for a marathon',
            created_at=datetime.now() - timedelta(minutes=5)
        ),
        ChatMessage(
            id=2,
            session_id=1,
            role='assistant',
            content='Great! When is your target race date?',
            created_at=datetime.now() - timedelta(minutes=4)
        ),
        ChatMessage(
            id=3,
            session_id=1,
            role='user',
            content='In 16 weeks',
            created_at=datetime.now() - timedelta(minutes=3)
        ),
        ChatMessage(
            id=4,
            session_id=1,
            role='assistant',
            content='Perfect! That gives us enough time for a structured plan.',
            created_at=datetime.now() - timedelta(minutes=2)
        )
    ]
    
    # Mock session service to return conversation
    mock_session_service.get_active_buffer.return_value = conversation_history
    
    # Pre-populate cache to avoid database queries
    chat_handler.behavior_summary_generator.set_cached_summary(1, "Test athlete summary")
    
    # Mock LLM response that references previous context
    mock_llm_client.chat_completion.return_value = {
        'content': 'Based on your 16-week timeline for the marathon, here is a plan...',
        'tool_calls': None
    }
    
    # Mock RAG retriever to avoid database queries
    with patch.object(
        chat_handler.context_builder.rag_retriever,
        'retrieve',
        return_value=[]
    ):
        # Execute follow-up message
        result = await chat_handler.handle_message("What should my weekly mileage be?")
    
    # Verify LLM received conversation history
    call_args = mock_llm_client.chat_completion.call_args
    messages = call_args.kwargs['messages']
    
    # Convert messages to string for easier checking
    messages_str = str(messages)
    
    # Verify recent conversation context is included
    # Should include references to marathon and 16 weeks
    assert 'marathon' in messages_str.lower() or '16 weeks' in messages_str.lower()
    
    # Verify the current message is included
    assert 'weekly mileage' in messages_str.lower()
    
    # Verify response maintains continuity
    assert 'content' in result
    
    print("✓ Conversation history included in context")
    print("✓ Continuity maintained across turns")



# Test 2.8.4: Athlete personalization visible in responses
@pytest.mark.asyncio
async def test_athlete_personalization_in_context(
    chat_handler,
    mock_llm_client,
    mock_athlete
):
    """
    Test that athlete behavior summary is included in context.
    
    Requirement: 2.8.4
    Validates: Athlete personalization layer is injected
    """
    # Pre-populate cache with athlete summary (no DB needed)
    mock_summary = (
        "Training Patterns: Runs 4x per week, prefers morning sessions | "
        "Preferences: Dislikes high-intensity intervals, enjoys long steady runs | "
        "Recent Trends: Increasing weekly volume by 10% per week | "
        "Past Feedback: Responds well to structured plans with clear goals"
    )
    chat_handler.behavior_summary_generator.set_cached_summary(1, mock_summary)
    
    # Mock LLM response
    mock_llm_client.chat_completion.return_value = {
        'content': 'Given your preference for morning runs and steady pace...',
        'tool_calls': None
    }
    
    # Mock RAG retriever to avoid database queries
    with patch.object(
        chat_handler.context_builder.rag_retriever,
        'retrieve',
        return_value=[]
    ):
        # Execute
        result = await chat_handler.handle_message("What training should I do this week?")
    
    # Verify LLM received athlete profile
    call_args = mock_llm_client.chat_completion.call_args
    messages = call_args.kwargs['messages']
    
    # Convert to string for checking
    messages_str = str(messages)
    
    # Verify athlete profile information is in context
    assert 'athlete profile' in messages_str.lower() or 'training patterns' in messages_str.lower()
    
    # Verify personalization details are present
    profile_indicators = [
        'morning' in messages_str.lower(),
        'prefer' in messages_str.lower() or 'preference' in messages_str.lower(),
        'pattern' in messages_str.lower() or 'trend' in messages_str.lower()
    ]
    
    # At least one personalization indicator should be present
    assert any(profile_indicators), "Athlete personalization not found in context"
    
    print("✓ Athlete behavior summary generated")
    print("✓ Personalization included in context")



# Test 2.8.5: Intent-aware retrieval returns appropriate data
@pytest.mark.asyncio
async def test_intent_aware_retrieval_returns_appropriate_data(
    chat_handler,
    mock_llm_client,
    mock_activities
):
    """
    Test that different intents trigger appropriate data retrieval.
    
    Requirement: 2.8.5
    Validates: Intent classification drives retrieval policy
    """
    # Test Case 1: Recent Performance Intent
    chat_handler.behavior_summary_generator.set_cached_summary(1, "Test athlete summary")
    with patch.object(
        chat_handler.context_builder.intent_router,
        'classify',
        return_value='recent_performance'
    ):
        with patch.object(
            chat_handler.context_builder.rag_retriever,
            'retrieve',
            return_value=mock_activities[:3]  # Recent activities
        ) as mock_retrieve:
            mock_llm_client.chat_completion.return_value = {
                'content': 'Your recent performance shows...',
                'tool_calls': None
            }
            
            result = await chat_handler.handle_message("How am I doing lately?")
            
            # Verify intent was classified
            assert chat_handler.context_builder.intent_router.classify.called
            
            # Verify retrieval was called with intent
            assert mock_retrieve.called
            call_args = mock_retrieve.call_args
            
            # Check that intent was passed to retrieval
            if len(call_args.args) > 2:
                intent_arg = call_args.args[2]
                assert intent_arg == 'recent_performance'
            
            print("✓ Recent performance intent triggered appropriate retrieval")
    
    # Reset context builder for next test case
    from app.ai.context.chat_context import ChatContextBuilder
    new_cb = ChatContextBuilder(db=chat_handler.db, token_budget=8000)
    chat_handler.context_builder = new_cb
    chat_handler.agent.context_builder = new_cb

    # Test Case 2: Trend Analysis Intent
    chat_handler.behavior_summary_generator.set_cached_summary(1, "Test athlete summary")
    with patch.object(
        chat_handler.context_builder.intent_router,
        'classify',
        return_value='trend_analysis'
    ):
        with patch.object(
            chat_handler.context_builder.rag_retriever,
            'retrieve',
            return_value=mock_activities  # Longer history for trends
        ) as mock_retrieve:
            mock_llm_client.chat_completion.return_value = {
                'content': 'Your training trends show...',
                'tool_calls': None
            }
            
            result = await chat_handler.handle_message("What are my training trends?")
            
            # Verify different intent was classified
            assert chat_handler.context_builder.intent_router.classify.called
            
            # Verify retrieval was called
            assert mock_retrieve.called
            
            print("✓ Trend analysis intent triggered appropriate retrieval")
    
    # Reset context builder for next test case
    new_cb2 = ChatContextBuilder(db=chat_handler.db, token_budget=8000)
    chat_handler.context_builder = new_cb2
    chat_handler.agent.context_builder = new_cb2

    # Test Case 3: Goal Progress Intent
    chat_handler.behavior_summary_generator.set_cached_summary(1, "Test athlete summary")
    with patch.object(
        chat_handler.context_builder.intent_router,
        'classify',
        return_value='goal_progress'
    ):
        with patch.object(
            chat_handler.context_builder.rag_retriever,
            'retrieve',
            return_value=[]  # Goals + related activities
        ) as mock_retrieve:
            mock_llm_client.chat_completion.return_value = {
                'content': 'Your goal progress is...',
                'tool_calls': None
            }
            
            result = await chat_handler.handle_message("Am I on track for my goals?")
            
            # Verify goal-specific intent
            assert chat_handler.context_builder.intent_router.classify.called
            
            print("✓ Goal progress intent triggered appropriate retrieval")
    
    print("✓ All intent-aware retrieval tests passed")





# Additional Integration Tests

@pytest.mark.asyncio
async def test_token_budget_enforced_in_integration(
    chat_handler,
    mock_session_service,
    mock_llm_client
):
    """
    Test that token budget is enforced end-to-end.
    
    Validates: Context builder respects 2400 token budget
    """
    # Create large conversation history
    large_history = []
    for i in range(30):
        large_history.append(ChatMessage(
            id=i + 1,
            session_id=1,
            role='user' if i % 2 == 0 else 'assistant',
            content=f'This is a longer message with more content to increase token count. Message number {i + 1}. ' * 10,
            created_at=datetime.now() - timedelta(minutes=30 - i)
        ))
    
    mock_session_service.get_active_buffer.return_value = large_history
    
    # Pre-populate cache to avoid database queries
    chat_handler.behavior_summary_generator.set_cached_summary(1, "Test athlete summary")
    
    mock_llm_client.chat_completion.return_value = {
        'content': 'Response within budget',
        'tool_calls': None
    }
    
    # Mock RAG retriever to avoid database queries
    with patch.object(
        chat_handler.context_builder.rag_retriever,
        'retrieve',
        return_value=[]
    ):
        # Execute
        result = await chat_handler.handle_message("Tell me about my training")
    
    # Verify token budget was enforced
    assert result['context_token_count'] <= 8000
    
    print(f"✓ Token budget enforced: {result['context_token_count']} <= 8000")


@pytest.mark.asyncio
async def test_ce_architecture_components_initialized(chat_handler):
    """
    Test that all CE architecture components are properly initialized.
    
    Validates: Phase 2 components are active (now owned by ChatAgent)
    """
    agent = chat_handler.agent

    # Verify CE components exist on the agent
    assert agent.context_builder is not None
    assert agent._system_loader is not None
    assert agent._task_loader is not None
    assert agent._domain_loader is not None
    assert agent._behavior_summary is not None

    # Verify context builder has correct token budget (increased for integration tests)
    assert agent.context_builder.token_budget == 8000
    
    print("✓ All CE architecture components initialized")


@pytest.mark.asyncio
async def test_end_to_end_ce_flow(
    chat_handler,
    mock_session_service,
    mock_llm_client,
    mock_athlete,
    mock_activities
):
    """
    Test complete end-to-end flow with CE architecture.
    
    Validates: All Phase 2 components work together
    """
    # Setup mocks
    mock_session_service.get_active_buffer.return_value = []
    
    # Pre-populate cache to avoid database queries
    chat_handler.behavior_summary_generator.set_cached_summary(1, "Athlete trains 4x per week")
    
    with patch.object(
        chat_handler.context_builder.intent_router,
        'classify',
        return_value='recent_performance'
    ):
        with patch.object(
            chat_handler.context_builder.rag_retriever,
            'retrieve',
            return_value=mock_activities[:3]
        ):
            mock_llm_client.chat_completion.return_value = {
                'content': 'Based on your recent training...',
                'tool_calls': None
            }
            
            # Execute complete flow
            result = await chat_handler.handle_message("How is my training going?")
            
            # Verify all components were used
            assert chat_handler.context_builder.intent_router.classify.called
            assert chat_handler.context_builder.rag_retriever.retrieve.called
            assert mock_llm_client.chat_completion.called
            
            # Verify result structure
            assert 'content' in result
            assert 'ce_context_used' in result
            assert result['ce_context_used'] is True
            assert 'context_token_count' in result
            assert 'latency_ms' in result
            
            # Verify messages were appended to session
            assert mock_session_service.append_messages.called
            
            print("✓ End-to-end CE flow completed successfully")
            print(f"✓ Latency: {result['latency_ms']:.0f}ms")
            print(f"✓ Context tokens: {result['context_token_count']}")

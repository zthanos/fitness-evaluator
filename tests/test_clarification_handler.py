"""Tests for Clarification Handler

Tests detection of low-confidence intent and clarification generation.
"""
import pytest
from unittest.mock import Mock, AsyncMock

from app.services.clarification_handler import ClarificationHandler


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = Mock()
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture
def handler(mock_llm_client):
    """Create clarification handler."""
    return ClarificationHandler(llm_client=mock_llm_client)


def test_needs_clarification_short_ambiguous(handler):
    """Test that short ambiguous messages need clarification."""
    # Short message with ambiguous keyword
    assert handler.needs_clarification("I need a plan", []) is True
    assert handler.needs_clarification("Help me train", []) is True
    assert handler.needs_clarification("Create a workout", []) is True


def test_needs_clarification_vague_request(handler):
    """Test that vague requests need clarification."""
    # Very vague requests
    assert handler.needs_clarification("Help me", []) is True
    assert handler.needs_clarification("What should I do", []) is True
    assert handler.needs_clarification("I want to improve", []) is True


def test_needs_clarification_plan_without_specifics(handler):
    """Test that plan requests without specifics need clarification."""
    # Plan request without sport, duration, or goal
    assert handler.needs_clarification("I want a training plan", []) is True
    assert handler.needs_clarification("Create a plan for me", []) is True


def test_no_clarification_specific_request(handler):
    """Test that specific requests don't need clarification."""
    # Specific requests with sufficient context
    assert handler.needs_clarification(
        "I want a 12-week marathon training plan for a sub-4 hour finish",
        []
    ) is False
    
    assert handler.needs_clarification(
        "Create a cycling plan to prepare for a century ride in 8 weeks",
        []
    ) is False
    
    assert handler.needs_clarification(
        "I need help analyzing my recent running activities to see if I'm improving",
        []
    ) is False


def test_no_clarification_long_message(handler):
    """Test that longer messages with context don't need clarification."""
    # Long message with sufficient context
    long_message = """I'm training for my first marathon in 16 weeks. 
    I've been running consistently for 6 months, averaging 20 miles per week. 
    Can you help me create a training plan?"""
    
    assert handler.needs_clarification(long_message, []) is False


def test_no_clarification_non_ambiguous(handler):
    """Test that non-ambiguous messages don't need clarification."""
    # Clear, specific messages
    assert handler.needs_clarification("What's my resting heart rate trend?", []) is False
    assert handler.needs_clarification("Show me my activities from last week", []) is False
    assert handler.needs_clarification("How many miles did I run this month?", []) is False


@pytest.mark.asyncio
async def test_generate_clarification_success(handler, mock_llm_client):
    """Test successful clarification generation."""
    # Mock LLM response
    mock_llm_client.chat_completion.return_value = {
        'content': """I'd love to help you create a training plan! To make it perfect for you, I need:

**What sport?**
- Running
- Cycling
- Swimming

**What's your goal?**
- Race preparation
- General fitness
- Weight loss

Let me know!"""
    }
    
    # Generate clarification
    clarification = await handler.generate_clarification(
        user_message="I need a plan",
        conversation_history=[]
    )
    
    # Verify clarification
    assert "sport" in clarification.lower()
    assert "goal" in clarification.lower()
    assert len(clarification) > 50


@pytest.mark.asyncio
async def test_generate_clarification_with_history(handler, mock_llm_client):
    """Test clarification generation with conversation history."""
    # Mock LLM response
    mock_llm_client.chat_completion.return_value = {
        'content': "Based on our conversation, I need to know..."
    }
    
    # Generate clarification with history
    conversation_history = [
        {'role': 'user', 'content': 'Hello'},
        {'role': 'assistant', 'content': 'Hi! How can I help?'},
        {'role': 'user', 'content': 'I want to train'}
    ]
    
    clarification = await handler.generate_clarification(
        user_message="I want to train",
        conversation_history=conversation_history
    )
    
    # Verify LLM was called with history
    mock_llm_client.chat_completion.assert_called_once()
    call_args = mock_llm_client.chat_completion.call_args
    prompt = call_args[1]['messages'][1]['content']
    assert 'Recent conversation' in prompt


@pytest.mark.asyncio
async def test_generate_clarification_fallback(handler, mock_llm_client):
    """Test fallback clarification when LLM fails."""
    # Mock LLM to raise error
    mock_llm_client.chat_completion.side_effect = Exception("LLM error")
    
    # Generate clarification (should use fallback)
    clarification = await handler.generate_clarification(
        user_message="I need a plan",
        conversation_history=[]
    )
    
    # Verify fallback was used
    assert len(clarification) > 50
    assert "sport" in clarification.lower() or "goal" in clarification.lower()


def test_generate_fallback_clarification_plan(handler):
    """Test fallback clarification for plan requests."""
    clarification = handler._generate_fallback_clarification("I need a training plan")
    
    assert "sport" in clarification.lower()
    assert "goal" in clarification.lower()
    assert "weeks" in clarification.lower()


def test_generate_fallback_clarification_goal(handler):
    """Test fallback clarification for goal requests."""
    clarification = handler._generate_fallback_clarification("I want to set a goal")
    
    assert "goal" in clarification.lower()
    assert "timeframe" in clarification.lower()
    assert "target" in clarification.lower()


def test_generate_fallback_clarification_improve(handler):
    """Test fallback clarification for improvement requests."""
    clarification = handler._generate_fallback_clarification("Help me get better")
    
    assert "improve" in clarification.lower()
    assert "activity" in clarification.lower()
    assert "level" in clarification.lower()


def test_generate_fallback_clarification_generic(handler):
    """Test fallback clarification for generic requests."""
    clarification = handler._generate_fallback_clarification("Help me")
    
    assert "achieve" in clarification.lower()
    assert "sport" in clarification.lower()
    assert "experience" in clarification.lower()


@pytest.mark.asyncio
async def test_process_with_clarification(handler):
    """Test processing original request with clarification."""
    # Process with clarification
    combined = await handler.process_with_clarification(
        original_message="I need a plan",
        clarification_response="I want a 12-week marathon training plan",
        conversation_history=[]
    )
    
    # Verify combined context
    assert "I need a plan" in combined
    assert "12-week marathon training plan" in combined
    assert "Original request" in combined
    assert "Additional details" in combined


def test_build_clarification_prompt(handler):
    """Test building clarification prompt."""
    prompt = handler._build_clarification_prompt(
        user_message="I need help",
        conversation_history=[
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi!'}
        ]
    )
    
    # Verify prompt structure
    assert "I need help" in prompt
    assert "ambiguous" in prompt.lower()
    assert "Recent conversation" in prompt
    assert "Hello" in prompt


def test_build_clarification_prompt_no_history(handler):
    """Test building clarification prompt without history."""
    prompt = handler._build_clarification_prompt(
        user_message="I need help",
        conversation_history=[]
    )
    
    # Verify prompt structure
    assert "I need help" in prompt
    assert "ambiguous" in prompt.lower()
    assert "Recent conversation" not in prompt

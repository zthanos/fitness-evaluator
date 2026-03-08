"""
Preservation Property Tests for Chat Data Retrieval Tools Bugfix

**IMPORTANT**: These tests MUST PASS on unfixed code - they establish baseline behavior.

This test validates requirements 3.1, 3.2, 3.3, 3.4 from bugfix.md:
- 3.1: save_athlete_goal tool continues to work correctly
- 3.2: RAG system continues to include relevant training data in context
- 3.3: Chat service continues to use LangChain's tool calling mechanism correctly
- 3.4: Agent continues to provide appropriate responses for non-data-related questions

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime
from app.services.langchain_chat_service import LangChainChatService
from app.models import AthleteGoal

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_goal_service():
    """Create a mock goal service."""
    service = Mock()
    service.save_goal = Mock(return_value={'success': True, 'goal_id': 1})
    service.get_active_goals = Mock(return_value=[])
    return service


@pytest.fixture
def mock_rag_system():
    """Create a mock RAG system."""
    rag = Mock()
    rag.search = Mock(return_value=[])
    return rag


# ============================================================================
# Property 2: Preservation - Goal Setting Functionality (Requirement 3.1)
# ============================================================================

@settings(
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=10,
    deadline=None  # Disable deadline for initialization overhead
)
@given(
    goal_type=st.sampled_from(['weight_loss', 'muscle_gain', 'endurance', 'strength']),
    description=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    target_value=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
def test_property_save_athlete_goal_tool_exists(goal_type, description, target_value, mock_db):
    """
    Property 2: Preservation - save_athlete_goal tool continues to exist
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Tests that the save_athlete_goal tool is available in the tool list.
    This tool must continue to work after adding data retrieval tools.
    
    **Validates: Requirement 3.1**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_names = [tool.name for tool in tools]
    
    # Verify save_athlete_goal tool exists
    assert "save_athlete_goal" in tool_names, (
        f"save_athlete_goal tool is missing. "
        f"Available tools: {tool_names}. "
        f"This violates requirement 3.1: The save_athlete_goal tool must continue to exist."
    )


def test_concrete_save_athlete_goal_tool_callable(mock_db):
    """
    Concrete test: Verify save_athlete_goal tool can be invoked
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Tests that the save_athlete_goal tool can be called with valid arguments.
    
    **Validates: Requirement 3.1**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Find the save_athlete_goal tool
    save_goal_tool = None
    for tool in service.tools:
        if tool.name == "save_athlete_goal":
            save_goal_tool = tool
            break
    
    assert save_goal_tool is not None, "save_athlete_goal tool not found"
    
    # Mock the goal service to return success
    with patch.object(service.goal_service, 'save_goal', return_value={'success': True, 'goal_id': 1}):
        # Invoke the tool
        result = save_goal_tool.invoke({
            'goal_type': 'weight_loss',
            'description': 'Lose 10 pounds',
            'target_value': 10.0,
            'target_date': '2024-12-31'
        })
        
        # Verify result indicates success
        assert '✅' in result or 'saved' in result.lower(), (
            f"Tool invocation did not return success message. Result: {result}"
        )


# ============================================================================
# Property 2: Preservation - RAG Context Retrieval (Requirement 3.2)
# ============================================================================

@pytest.mark.asyncio
async def test_concrete_rag_context_loading(mock_db):
    """
    Concrete test: Verify RAG system loads context into system prompt
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Tests that when RAG system returns results, they are included in the system prompt.
    
    **Validates: Requirement 3.2**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Mock RAG system to return sample results
    mock_rag_results = [
        {
            'record_type': 'activity',
            'text': 'Ran 5 miles on 2024-01-15',
            'similarity': 0.95
        },
        {
            'record_type': 'metric',
            'text': 'Weight: 180 lbs on 2024-01-15',
            'similarity': 0.90
        }
    ]
    
    if service.rag_system:
        with patch.object(service.rag_system, 'search', return_value=mock_rag_results):
            # Load system prompt with RAG context
            rag_context = service._format_rag_context(mock_rag_results)
            system_prompt = service._load_system_prompt(rag_context)
            
            # Verify RAG context is included in system prompt
            assert 'Ran 5 miles' in system_prompt or 'Activity' in system_prompt, (
                f"RAG context not included in system prompt. "
                f"This violates requirement 3.2: RAG system must continue to include relevant data."
            )


def test_concrete_system_prompt_includes_athlete_profile(mock_db):
    """
    Concrete test: Verify system prompt includes athlete profile
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Tests that the system prompt includes athlete profile information.
    
    **Validates: Requirement 3.2**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Load system prompt
    system_prompt = service._load_system_prompt()
    
    # Verify athlete profile is included
    assert 'Athlete Profile' in system_prompt or 'Athlete' in system_prompt, (
        f"Athlete profile not included in system prompt. "
        f"This violates requirement 3.2: System prompt must include athlete context."
    )


def test_concrete_system_prompt_includes_active_goals(mock_db):
    """
    Concrete test: Verify system prompt includes active goals when available
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Tests that when active goals exist, they are included in the system prompt.
    
    **Validates: Requirement 3.2**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Mock active goals
    mock_goal = Mock(spec=AthleteGoal)
    mock_goal.goal_type = 'weight_loss'
    mock_goal.description = 'Lose 10 pounds'
    mock_goal.target_value = 10.0
    mock_goal.target_date = datetime(2024, 12, 31)
    
    with patch.object(service.goal_service, 'get_active_goals', return_value=[mock_goal]):
        # Load system prompt
        system_prompt = service._load_system_prompt()
        
        # Verify active goals are included
        assert 'Active Goals' in system_prompt or 'Lose 10 pounds' in system_prompt, (
            f"Active goals not included in system prompt. "
            f"This violates requirement 3.2: System prompt must include active goals context."
        )


# ============================================================================
# Property 2: Preservation - Tool Execution Flow (Requirement 3.3)
# ============================================================================

def test_concrete_tool_binding_works(mock_db):
    """
    Concrete test: Verify LangChain tool binding mechanism works
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Tests that tools are properly bound to the LLM using bind_tools().
    
    **Validates: Requirement 3.3**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Verify llm_with_tools exists
    assert hasattr(service, 'llm_with_tools'), (
        "llm_with_tools attribute not found. "
        "This violates requirement 3.3: Tool binding mechanism must work."
    )
    
    # Verify tools are bound
    assert service.llm_with_tools is not None, (
        "llm_with_tools is None. "
        "This violates requirement 3.3: Tools must be bound to LLM."
    )
    
    # Verify the bound object has the expected type (RunnableBinding from LangChain)
    assert hasattr(service.llm_with_tools, 'ainvoke'), (
        "llm_with_tools missing ainvoke method. "
        "This violates requirement 3.3: Tool binding must create proper LangChain runnable."
    )


# ============================================================================
# Property 2: Preservation - General Advice Responses (Requirement 3.4)
# ============================================================================

def test_concrete_get_chat_response_method_exists(mock_db):
    """
    Concrete test: Verify get_chat_response method exists and is callable
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Tests that the get_chat_response method exists and can be called.
    This is the core method for handling chat interactions.
    
    **Validates: Requirement 3.4**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Verify get_chat_response method exists
    assert hasattr(service, 'get_chat_response'), (
        "get_chat_response method not found. "
        "This violates requirement 3.4: Chat service must handle responses."
    )
    
    # Verify it's callable
    assert callable(service.get_chat_response), (
        "get_chat_response is not callable. "
        "This violates requirement 3.4: Chat service must handle responses."
    )
    
    # Verify it's an async method
    import inspect
    assert inspect.iscoroutinefunction(service.get_chat_response), (
        "get_chat_response is not an async function. "
        "This violates requirement 3.4: Chat service must handle async responses."
    )


# ============================================================================
# Property 2: Preservation - Tool Count Baseline
# ============================================================================

def test_concrete_baseline_tool_count(mock_db):
    """
    Concrete test: Document baseline tool count before fix
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior)
    
    Documents that the current implementation has 1 tool (save_athlete_goal).
    After the fix, this will increase to 4 tools, but the original tool must remain.
    
    **Validates: Requirements 3.1, 3.3**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_count = len(tools)
    
    # Document baseline: currently 1 tool
    # After fix: will be 4 tools (save_athlete_goal + 3 data retrieval tools)
    assert tool_count >= 1, (
        f"Expected at least 1 tool (save_athlete_goal), got {tool_count}. "
        f"This violates requirement 3.1: save_athlete_goal must exist."
    )
    
    # Verify save_athlete_goal is present
    tool_names = [tool.name for tool in tools]
    assert "save_athlete_goal" in tool_names, (
        f"save_athlete_goal missing from tool list: {tool_names}. "
        f"This violates requirement 3.1: save_athlete_goal must continue to work."
    )

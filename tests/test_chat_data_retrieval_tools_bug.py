"""
Bug Condition Exploration Test for Chat Data Retrieval Tools

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
**DO NOT attempt to fix the test or the code when it fails.**

This test validates requirements 2.1, 2.2, 2.3, 2.4 from bugfix.md:
- 2.1: System SHALL use data retrieval tools for progress questions
- 2.2: System SHALL call appropriate tools for metrics/activities
- 2.3: System SHALL have access to tools for querying activities, logs, measurements
- 2.4: _create_tools() SHALL return multiple tools including data retrieval tools

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from app.services.langchain_chat_service import LangChainChatService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


@settings(
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None  # Disable deadline for initialization-heavy tests
)
@given(
    question=st.sampled_from([
        "How am I progressing?",
        "What activities did I do?",
        "What's my weight?",
        "What are my goals?",
        "How am I progressing with my training?",
        "What activities did I do this week?",
        "What's my current weight?",
        "Show me my recent workouts",
        "What are my fitness goals?",
    ])
)
def test_property_data_retrieval_tools_missing(question, mock_db):
    """
    Property 1: Fault Condition - Data Retrieval Tools Missing
    
    EXPECTED OUTCOME: This test FAILS (proves bug exists)
    
    Tests that when user asks data retrieval questions (progress, activities, 
    metrics, goals), the agent does NOT have access to appropriate tools.
    
    The tool list should contain:
    - get_recent_activities (or get_my_recent_activities)
    - get_athlete_goals (or get_my_goals)
    - get_weekly_metrics (or get_my_weekly_metrics)
    
    But currently only contains:
    - save_athlete_goal
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_names = [tool.name for tool in tools]
    
    # EXPECTED TO PASS AFTER FIX: Tool list should contain data retrieval tools
    assert "get_recent_activities" in tool_names or "get_my_recent_activities" in tool_names, (
        f"Missing data retrieval tool for activities. "
        f"Available tools: {tool_names}. "
        f"This confirms bug 2.2: System cannot retrieve recent activities when user asks '{question}'. "
        f"Expected tool 'get_recent_activities' or 'get_my_recent_activities' to be available."
    )
    
    assert "get_athlete_goals" in tool_names or "get_my_goals" in tool_names, (
        f"Missing data retrieval tool for goals. "
        f"Available tools: {tool_names}. "
        f"This confirms bug 2.2: System cannot retrieve athlete goals when user asks '{question}'. "
        f"Expected tool 'get_athlete_goals' or 'get_my_goals' to be available."
    )
    
    assert "get_weekly_metrics" in tool_names or "get_my_weekly_metrics" in tool_names, (
        f"Missing data retrieval tool for metrics. "
        f"Available tools: {tool_names}. "
        f"This confirms bug 2.2: System cannot retrieve weekly metrics when user asks '{question}'. "
        f"Expected tool 'get_weekly_metrics' or 'get_my_weekly_metrics' to be available."
    )


def test_concrete_tool_count_is_one_not_four(mock_db):
    """
    Concrete test case: Verify that _create_tools() returns only 1 tool instead of 4.
    
    This is the exact scenario from the bug report:
    - Current: _create_tools() returns 1 tool (save_athlete_goal)
    - Expected: _create_tools() returns 4 tools (save_athlete_goal + 3 data retrieval tools)
    
    **Validates: Requirements 2.4**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_count = len(tools)
    
    # EXPECTED TO PASS AFTER FIX: Tool count should be 4
    assert tool_count >= 4, (
        f"Tool count is incorrect. "
        f"Current: {tool_count} tools, "
        f"Expected: at least 4 tools (save_athlete_goal + 3 data retrieval tools). "
        f"This confirms bug 2.4: _create_tools() only returns save_athlete_goal, "
        f"missing get_recent_activities, get_athlete_goals, and get_weekly_metrics."
    )


def test_concrete_missing_get_recent_activities_tool(mock_db):
    """
    Concrete test case: Verify that get_recent_activities tool is missing.
    
    When user asks "What activities did I do this week?", the agent needs
    get_recent_activities tool to retrieve Strava activities from the database.
    
    **Validates: Requirements 2.1, 2.2**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_names = [tool.name for tool in tools]
    
    # EXPECTED TO PASS AFTER FIX: Tool list should contain get_recent_activities
    assert "get_recent_activities" in tool_names or "get_my_recent_activities" in tool_names, (
        f"Missing get_recent_activities tool. "
        f"Available tools: {tool_names}. "
        f"This confirms bug 2.1, 2.2: When user asks 'What activities did I do this week?', "
        f"the agent has no tool to retrieve activities from the database. "
        f"Expected tool 'get_recent_activities' or 'get_my_recent_activities' to be available."
    )


def test_concrete_missing_get_athlete_goals_tool(mock_db):
    """
    Concrete test case: Verify that get_athlete_goals tool is missing.
    
    When user asks "What are my goals?", the agent needs get_athlete_goals
    tool to retrieve active goals from the database.
    
    **Validates: Requirements 2.1, 2.2**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_names = [tool.name for tool in tools]
    
    # EXPECTED TO PASS AFTER FIX: Tool list should contain get_athlete_goals
    assert "get_athlete_goals" in tool_names or "get_my_goals" in tool_names, (
        f"Missing get_athlete_goals tool. "
        f"Available tools: {tool_names}. "
        f"This confirms bug 2.1, 2.2: When user asks 'What are my goals?', "
        f"the agent has no tool to retrieve goals from the database. "
        f"Expected tool 'get_athlete_goals' or 'get_my_goals' to be available."
    )


def test_concrete_missing_get_weekly_metrics_tool(mock_db):
    """
    Concrete test case: Verify that get_weekly_metrics tool is missing.
    
    When user asks "What's my current weight?", the agent needs get_weekly_metrics
    tool to retrieve body measurements from the database.
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_names = [tool.name for tool in tools]
    
    # EXPECTED TO PASS AFTER FIX: Tool list should contain get_weekly_metrics
    assert "get_weekly_metrics" in tool_names or "get_my_weekly_metrics" in tool_names, (
        f"Missing get_weekly_metrics tool. "
        f"Available tools: {tool_names}. "
        f"This confirms bug 2.1, 2.2, 2.3: When user asks 'What's my current weight?', "
        f"the agent has no tool to retrieve metrics from the database. "
        f"Expected tool 'get_weekly_metrics' or 'get_my_weekly_metrics' to be available."
    )


def test_concrete_only_save_athlete_goal_available(mock_db):
    """
    Concrete test case: Document that only save_athlete_goal is currently available.
    
    This test explicitly shows that the current implementation only provides
    the save_athlete_goal tool, with no data retrieval capabilities.
    
    **Validates: Requirements 2.4**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_names = [tool.name for tool in tools]
    
    # Document current state
    assert "save_athlete_goal" in tool_names, (
        f"Expected save_athlete_goal to be available. "
        f"Available tools: {tool_names}. "
        f"This is unexpected - save_athlete_goal should exist in the current implementation."
    )
    
    # EXPECTED TO PASS AFTER FIX: Additional data retrieval tools should be available
    data_retrieval_tools = [
        name for name in tool_names 
        if "get" in name.lower() and name != "save_athlete_goal"
    ]
    
    assert len(data_retrieval_tools) >= 3, (
        f"Missing data retrieval tools. "
        f"Current tools: {tool_names}. "
        f"Data retrieval tools found: {data_retrieval_tools}. "
        f"This confirms bug 2.4: _create_tools() only returns save_athlete_goal, "
        f"missing at least 3 data retrieval tools (get_recent_activities, "
        f"get_athlete_goals, get_weekly_metrics)."
    )


@settings(
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None  # Disable deadline for initialization-heavy tests
)
@given(
    tool_name=st.sampled_from([
        "get_my_recent_activities",
        "get_my_goals",
        "get_my_weekly_metrics",
    ])
)
def test_property_specific_data_retrieval_tool_missing(tool_name, mock_db):
    """
    Property 1: Fault Condition - Specific Data Retrieval Tool Missing
    
    EXPECTED OUTCOME: This test FAILS (proves bug exists)
    
    Tests that specific data retrieval tools are missing from the tool list.
    Each of these tools is required for the agent to answer data-driven questions.
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    """
    # Initialize the chat service
    service = LangChainChatService(db=mock_db)
    
    # Get the tool list
    tools = service.tools
    tool_names = [tool.name for tool in tools]
    
    # EXPECTED TO PASS AFTER FIX: Tool should be in the list
    assert tool_name in tool_names, (
        f"Missing required data retrieval tool: {tool_name}. "
        f"Available tools: {tool_names}. "
        f"This confirms bug 2.1, 2.2, 2.3, 2.4: System lacks tools to retrieve "
        f"athlete data when answering progress, activity, metric, or goal questions."
    )

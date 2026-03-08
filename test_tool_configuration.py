"""
Test tool configuration to verify web search is disabled by default.

This test validates Requirement 5.1.7: Web search tools disabled by default.
"""

import pytest
from app.ai.tools import (
    get_enabled_tools,
    is_web_search_enabled,
    load_tool_config,
    TOOL_CATEGORIES,
)


def test_web_search_disabled_by_default():
    """
    Test that web search tools are disabled by default.
    
    Validates Requirement 5.1.7: The Context_Engineering_System SHALL disable 
    web search tools by default (require explicit intent-gating for future use).
    """
    # Load tool configuration
    config = load_tool_config()
    
    # Verify web search is disabled
    web_search_config = config.get("web_search", {})
    assert web_search_config.get("enabled", False) is False, \
        "Web search should be disabled by default"
    
    # Verify intent gating is enabled
    assert web_search_config.get("intent_gating", True) is True, \
        "Intent gating should be enabled for web search"
    
    # Verify no intents are allowed by default
    allowed_intents = web_search_config.get("allowed_intents", [])
    assert len(allowed_intents) == 0, \
        "No intents should be allowed for web search by default"


def test_web_search_not_in_enabled_tools():
    """
    Test that web search tools are not included in the enabled tools list.
    
    Validates that get_enabled_tools() does not return web search tools
    when they are disabled.
    """
    # Get enabled tools without intent
    enabled_tools = get_enabled_tools()
    
    # Get web search tools
    web_search_tools = TOOL_CATEGORIES.get("web_search", [])
    
    # Verify no web search tools are in enabled tools
    for tool in web_search_tools:
        assert tool not in enabled_tools, \
            f"Web search tool {tool} should not be in enabled tools"


def test_web_search_not_enabled_for_any_intent():
    """
    Test that web search is not enabled for any intent by default.
    
    Validates that is_web_search_enabled() returns False for all intents.
    """
    # Test common intents
    test_intents = [
        "recent_performance",
        "trend_analysis",
        "goal_progress",
        "recovery_status",
        "training_plan",
        "comparison",
        "general",
        "research",
        "external_info",
    ]
    
    for intent in test_intents:
        assert is_web_search_enabled(intent) is False, \
            f"Web search should not be enabled for intent: {intent}"
    
    # Test with no intent
    assert is_web_search_enabled() is False, \
        "Web search should not be enabled without intent"


def test_data_retrieval_tools_enabled():
    """
    Test that data retrieval tools are enabled by default.
    
    Validates that the standard data retrieval tools (GetRecentActivities,
    GetAthleteGoals, GetWeeklyMetrics) are available.
    """
    # Get enabled tools
    enabled_tools = get_enabled_tools()
    
    # Get data retrieval tools
    data_retrieval_tools = TOOL_CATEGORIES.get("data_retrieval", [])
    
    # Verify all data retrieval tools are enabled
    for tool in data_retrieval_tools:
        assert tool in enabled_tools, \
            f"Data retrieval tool {tool} should be in enabled tools"
    
    # Verify we have at least 3 data retrieval tools
    assert len(data_retrieval_tools) >= 3, \
        "Should have at least 3 data retrieval tools (GetRecentActivities, GetAthleteGoals, GetWeeklyMetrics)"


def test_tool_configuration_structure():
    """
    Test that the tool configuration has the expected structure.
    
    Validates that model_profiles.yaml contains the required tool configuration.
    """
    config = load_tool_config()
    
    # Verify enabled_categories exists
    assert "enabled_categories" in config, \
        "Tool configuration should have enabled_categories"
    
    # Verify data_retrieval is in enabled categories
    enabled_categories = config.get("enabled_categories", [])
    assert "data_retrieval" in enabled_categories, \
        "data_retrieval should be in enabled categories"
    
    # Verify web_search is NOT in enabled categories
    assert "web_search" not in enabled_categories, \
        "web_search should NOT be in enabled categories by default"
    
    # Verify web_search configuration exists
    assert "web_search" in config, \
        "Tool configuration should have web_search section"
    
    # Verify data_retrieval configuration exists
    assert "data_retrieval" in config, \
        "Tool configuration should have data_retrieval section"


def test_future_intent_gating_configuration():
    """
    Test that the configuration supports future intent-gated web search.
    
    Validates that the configuration structure allows for future enabling
    of web search with specific intents.
    """
    config = load_tool_config()
    web_search_config = config.get("web_search", {})
    
    # Verify configuration has intent_gating flag
    assert "intent_gating" in web_search_config, \
        "Web search config should have intent_gating flag"
    
    # Verify configuration has allowed_intents list
    assert "allowed_intents" in web_search_config, \
        "Web search config should have allowed_intents list"
    
    # Verify configuration has enabled flag
    assert "enabled" in web_search_config, \
        "Web search config should have enabled flag"
    
    # The structure is ready for future use, even though it's disabled now
    assert isinstance(web_search_config.get("allowed_intents", []), list), \
        "allowed_intents should be a list for future configuration"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

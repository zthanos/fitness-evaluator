"""
LangChain StructuredTools for data retrieval operations.

This module provides structured tools for LLM interactions with the fitness platform.
Tools are organized by category and can be enabled/disabled via configuration.
"""

from typing import List
import yaml
import os
from pathlib import Path

from app.ai.tools.get_recent_activities import get_recent_activities
from app.ai.tools.get_athlete_goals import get_athlete_goals
from app.ai.tools.get_weekly_metrics import get_weekly_metrics


# All available tools organized by category
TOOL_CATEGORIES = {
    "data_retrieval": [
        get_recent_activities,
        get_athlete_goals,
        get_weekly_metrics,
    ],
    "web_search": [
        # Web search tools would go here
        # Currently disabled by default (see model_profiles.yaml)
    ],
}


def load_tool_config() -> dict:
    """
    Load tool configuration from model_profiles.yaml.
    
    Returns:
        Tool configuration dictionary
    """
    config_path = Path(__file__).parent.parent / "config" / "model_profiles.yaml"
    
    if not config_path.exists():
        # Return default configuration if file doesn't exist
        return {
            "enabled_categories": ["data_retrieval"],
            "web_search": {
                "enabled": False,
                "intent_gating": True,
                "allowed_intents": [],
            },
            "data_retrieval": {
                "enabled": True,
                "max_results_per_query": 20,
                "timeout_seconds": 5,
            },
        }
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        return config.get("tools", {})


def get_enabled_tools(intent: str = None) -> List:
    """
    Get list of enabled tools based on configuration.
    
    Web search tools are disabled by default and require explicit intent-gating.
    Data retrieval tools are enabled by default.
    
    Args:
        intent: Optional intent type for intent-gated tool access
        
    Returns:
        List of enabled tool functions
    """
    config = load_tool_config()
    enabled_categories = config.get("enabled_categories", ["data_retrieval"])
    
    tools = []
    
    # Add tools from enabled categories
    for category in enabled_categories:
        if category in TOOL_CATEGORIES:
            tools.extend(TOOL_CATEGORIES[category])
    
    # Handle web search with intent gating
    web_search_config = config.get("web_search", {})
    if web_search_config.get("enabled", False):
        # Check if intent gating is required
        if web_search_config.get("intent_gating", True):
            # Only enable web search for allowed intents
            allowed_intents = web_search_config.get("allowed_intents", [])
            if intent and intent in allowed_intents:
                tools.extend(TOOL_CATEGORIES.get("web_search", []))
        else:
            # Intent gating disabled, add web search tools
            tools.extend(TOOL_CATEGORIES.get("web_search", []))
    
    return tools


def is_web_search_enabled(intent: str = None) -> bool:
    """
    Check if web search tools are enabled for the given intent.
    
    Args:
        intent: Optional intent type for intent-gated access
        
    Returns:
        True if web search is enabled, False otherwise
    """
    config = load_tool_config()
    web_search_config = config.get("web_search", {})
    
    if not web_search_config.get("enabled", False):
        return False
    
    if web_search_config.get("intent_gating", True):
        allowed_intents = web_search_config.get("allowed_intents", [])
        return intent in allowed_intents if intent else False
    
    return True


__all__ = [
    "get_recent_activities",
    "get_athlete_goals",
    "get_weekly_metrics",
    "get_enabled_tools",
    "is_web_search_enabled",
    "load_tool_config",
    "TOOL_CATEGORIES",
]

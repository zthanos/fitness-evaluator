"""
Test for GetRecentActivities LangChain tool.
"""

import pytest
from datetime import datetime, timedelta
from app.ai.tools.get_recent_activities import get_recent_activities, GetRecentActivitiesInput


def test_get_recent_activities_input_validation():
    """Test that input validation works correctly."""
    # Valid input
    valid_input = GetRecentActivitiesInput(athlete_id=1, days_back=30)
    assert valid_input.athlete_id == 1
    assert valid_input.days_back == 30
    
    # Invalid athlete_id (must be > 0)
    with pytest.raises(Exception):
        GetRecentActivitiesInput(athlete_id=0, days_back=30)
    
    # Invalid days_back (must be > 0)
    with pytest.raises(Exception):
        GetRecentActivitiesInput(athlete_id=1, days_back=0)
    
    # Invalid days_back (must be <= 365)
    with pytest.raises(Exception):
        GetRecentActivitiesInput(athlete_id=1, days_back=400)


def test_get_recent_activities_tool_invocation():
    """Test that the tool can be invoked correctly."""
    # Test with a non-existent athlete ID (should return empty list)
    result = get_recent_activities.invoke({"athlete_id": 999999, "days_back": 30})
    assert isinstance(result, list)
    assert result == []


def test_get_recent_activities_tool_with_real_data():
    """Test that the tool retrieves activities from the actual database if data exists."""
    # This test will pass if there's no data (empty list) or if there is data (non-empty list)
    # We're just verifying the tool works without errors
    result = get_recent_activities.invoke({"athlete_id": 1, "days_back": 30})
    assert isinstance(result, list)
    
    # If there are results, verify the structure
    if result:
        activity = result[0]
        assert "type" in activity
        assert activity["type"] == "activity"
        assert "id" in activity
        assert "date" in activity
        assert "activity_type" in activity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


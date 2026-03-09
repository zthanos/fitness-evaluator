"""
Test for GetAthleteGoals LangChain tool.
"""

import pytest
from app.ai.tools.get_athlete_goals import get_athlete_goals, GetAthleteGoalsInput


def test_get_athlete_goals_input_validation():
    """Test that input validation works correctly."""
    # Valid input
    valid_input = GetAthleteGoalsInput(athlete_id=1)
    assert valid_input.athlete_id == 1
    
    # Invalid athlete_id (must be > 0)
    with pytest.raises(Exception):
        GetAthleteGoalsInput(athlete_id=0)


def test_get_athlete_goals_tool_invocation():
    """Test that the tool can be invoked correctly."""
    # Test with a non-existent athlete ID (should return empty list)
    result = get_athlete_goals.invoke({"athlete_id": 999999})
    assert isinstance(result, list)
    assert result == []


def test_get_athlete_goals_tool_with_real_data():
    """Test that the tool retrieves goals from the actual database if data exists."""
    # This test will pass if there's no data (empty list) or if there is data (non-empty list)
    # We're just verifying the tool works without errors
    result = get_athlete_goals.invoke({"athlete_id": 1})
    assert isinstance(result, list)
    
    # If there are results, verify the structure
    if result:
        goal = result[0]
        assert "type" in goal
        assert goal["type"] == "goal"
        assert "id" in goal
        assert "goal_type" in goal
        assert "description" in goal
        assert "status" in goal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

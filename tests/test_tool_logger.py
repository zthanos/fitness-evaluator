"""
Unit tests for tool invocation logging.

Tests that tool invocations are logged with tool name, parameters, and result count.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from app.ai.telemetry.tool_logger import ToolLogger, ToolInvocationLog


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file for testing."""
    log_file = tmp_path / "test_tool_invocations.jsonl"
    return str(log_file)


@pytest.fixture
def tool_logger(temp_log_file):
    """Create a ToolLogger instance with a temporary log file."""
    return ToolLogger(log_file_path=temp_log_file)


def test_tool_logger_logs_successful_invocation(tool_logger, temp_log_file):
    """Test that successful tool invocations are logged correctly."""
    # Create a log entry
    log_entry = ToolInvocationLog(
        timestamp=datetime.now().isoformat(),
        tool_name="get_recent_activities",
        parameters={"athlete_id": 123, "days_back": 7},
        result_count=5,
        success_status=True,
        error_message=None
    )
    
    # Log the entry
    tool_logger.log(log_entry)
    
    # Read the log file
    log_file = Path(temp_log_file)
    assert log_file.exists()
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    assert len(lines) == 1
    
    # Parse the JSON
    logged_data = json.loads(lines[0])
    
    # Verify the logged data
    assert logged_data["tool_name"] == "get_recent_activities"
    assert logged_data["parameters"] == {"athlete_id": 123, "days_back": 7}
    assert logged_data["result_count"] == 5
    assert logged_data["success_status"] is True
    assert logged_data["error_message"] is None


def test_tool_logger_logs_failed_invocation(tool_logger, temp_log_file):
    """Test that failed tool invocations are logged with error messages."""
    # Create a log entry for a failed invocation
    log_entry = ToolInvocationLog(
        timestamp=datetime.now().isoformat(),
        tool_name="get_athlete_goals",
        parameters={"athlete_id": 456},
        result_count=0,
        success_status=False,
        error_message="Database connection failed"
    )
    
    # Log the entry
    tool_logger.log(log_entry)
    
    # Read the log file
    log_file = Path(temp_log_file)
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    assert len(lines) == 1
    
    # Parse the JSON
    logged_data = json.loads(lines[0])
    
    # Verify the logged data
    assert logged_data["tool_name"] == "get_athlete_goals"
    assert logged_data["parameters"] == {"athlete_id": 456}
    assert logged_data["result_count"] == 0
    assert logged_data["success_status"] is False
    assert logged_data["error_message"] == "Database connection failed"


def test_tool_logger_log_invocation_with_list_result(tool_logger, temp_log_file):
    """Test that log_invocation correctly counts list results."""
    # Log an invocation with a list result
    result = [{"id": 1}, {"id": 2}, {"id": 3}]
    tool_logger.log_invocation(
        tool_name="get_recent_activities",
        parameters={"athlete_id": 123, "days_back": 7},
        result=result
    )
    
    # Read the log file
    log_file = Path(temp_log_file)
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    logged_data = json.loads(lines[0])
    
    # Verify result count is the length of the list
    assert logged_data["result_count"] == 3
    assert logged_data["success_status"] is True


def test_tool_logger_log_invocation_with_dict_result(tool_logger, temp_log_file):
    """Test that log_invocation correctly counts dict results."""
    # Log an invocation with a dict result
    result = {"id": 1, "name": "test"}
    tool_logger.log_invocation(
        tool_name="get_weekly_metrics",
        parameters={"athlete_id": 123, "week_id": "2024-W15"},
        result=result
    )
    
    # Read the log file
    log_file = Path(temp_log_file)
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    logged_data = json.loads(lines[0])
    
    # Verify result count is 1 for a dict
    assert logged_data["result_count"] == 1
    assert logged_data["success_status"] is True


def test_tool_logger_log_invocation_with_none_result(tool_logger, temp_log_file):
    """Test that log_invocation correctly handles None results."""
    # Log an invocation with None result
    tool_logger.log_invocation(
        tool_name="get_weekly_metrics",
        parameters={"athlete_id": 123, "week_id": "2024-W15"},
        result=None
    )
    
    # Read the log file
    log_file = Path(temp_log_file)
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    logged_data = json.loads(lines[0])
    
    # Verify result count is 0 for None
    assert logged_data["result_count"] == 0
    assert logged_data["success_status"] is True


def test_tool_logger_log_invocation_with_error(tool_logger, temp_log_file):
    """Test that log_invocation correctly logs errors."""
    # Log an invocation with an error
    error = ValueError("Invalid parameter")
    tool_logger.log_invocation(
        tool_name="get_athlete_goals",
        parameters={"athlete_id": -1},
        result=None,
        error=error
    )
    
    # Read the log file
    log_file = Path(temp_log_file)
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    logged_data = json.loads(lines[0])
    
    # Verify error is logged
    assert logged_data["success_status"] is False
    assert "Invalid parameter" in logged_data["error_message"]


def test_tool_logger_multiple_invocations(tool_logger, temp_log_file):
    """Test that multiple invocations are logged correctly."""
    # Log multiple invocations
    tool_logger.log_invocation(
        tool_name="get_recent_activities",
        parameters={"athlete_id": 123, "days_back": 7},
        result=[{"id": 1}, {"id": 2}]
    )
    
    tool_logger.log_invocation(
        tool_name="get_athlete_goals",
        parameters={"athlete_id": 123},
        result=[{"id": 1}]
    )
    
    tool_logger.log_invocation(
        tool_name="get_weekly_metrics",
        parameters={"athlete_id": 123, "week_id": "2024-W15"},
        result={"id": 1}
    )
    
    # Read the log file
    log_file = Path(temp_log_file)
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    # Verify all three invocations are logged
    assert len(lines) == 3
    
    # Parse and verify each entry
    log1 = json.loads(lines[0])
    assert log1["tool_name"] == "get_recent_activities"
    assert log1["result_count"] == 2
    
    log2 = json.loads(lines[1])
    assert log2["tool_name"] == "get_athlete_goals"
    assert log2["result_count"] == 1
    
    log3 = json.loads(lines[2])
    assert log3["tool_name"] == "get_weekly_metrics"
    assert log3["result_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test JSONL logging functionality for InvocationLogger.

Validates Requirements 4.2.3:
- Write invocation logs to app/ai/telemetry/invocations.jsonl
- Append one JSON object per line
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime

from app.ai.telemetry.invocation_logger import InvocationLogger, InvocationLog


def test_jsonl_logging_writes_to_correct_path():
    """Test that logs are written to the correct file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path))
        
        # Create a test invocation log
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        
        # Log the invocation
        logger.log(invocation)
        
        # Verify file exists
        assert log_path.exists(), "Log file should be created"
        
        # Verify content
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content.strip(), "Log file should not be empty"


def test_jsonl_logging_one_json_per_line():
    """Test that each invocation is written as one JSON object per line."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path))
        
        # Create multiple test invocation logs
        invocations = [
            InvocationLog(
                timestamp=datetime.now().isoformat(),
                operation_type="weekly_eval",
                athlete_id=123,
                model_used="mixtral",
                context_token_count=2500,
                response_token_count=500,
                latency_ms=1234.5,
                success_status=True,
                error_message=None
            ),
            InvocationLog(
                timestamp=datetime.now().isoformat(),
                operation_type="chat_response",
                athlete_id=456,
                model_used="llama",
                context_token_count=1800,
                response_token_count=300,
                latency_ms=987.3,
                success_status=True,
                error_message=None
            ),
            InvocationLog(
                timestamp=datetime.now().isoformat(),
                operation_type="weekly_eval",
                athlete_id=789,
                model_used="mixtral",
                context_token_count=3000,
                response_token_count=600,
                latency_ms=2000.0,
                success_status=False,
                error_message="Timeout error"
            )
        ]
        
        # Log all invocations
        for invocation in invocations:
            logger.log(invocation)
        
        # Read and verify JSONL format
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Should have exactly 3 lines
        assert len(lines) == 3, f"Expected 3 lines, got {len(lines)}"
        
        # Each line should be valid JSON
        for i, line in enumerate(lines):
            try:
                log_data = json.loads(line)
                assert isinstance(log_data, dict), f"Line {i+1} should be a JSON object"
                
                # Verify required fields are present
                assert "timestamp" in log_data
                assert "operation_type" in log_data
                assert "athlete_id" in log_data
                assert "model_used" in log_data
                assert "context_token_count" in log_data
                assert "response_token_count" in log_data
                assert "latency_ms" in log_data
                assert "success_status" in log_data
                
            except json.JSONDecodeError as e:
                raise AssertionError(f"Line {i+1} is not valid JSON: {e}")


def test_jsonl_logging_appends_not_overwrites():
    """Test that logging appends to the file rather than overwriting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path))
        
        # Log first invocation
        invocation1 = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(invocation1)
        
        # Log second invocation
        invocation2 = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="chat_response",
            athlete_id=456,
            model_used="llama",
            context_token_count=1800,
            response_token_count=300,
            latency_ms=987.3,
            success_status=True,
            error_message=None
        )
        logger.log(invocation2)
        
        # Verify both logs are present
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 2, "Both invocations should be present"
        
        # Verify first log
        log1 = json.loads(lines[0])
        assert log1["athlete_id"] == 123
        assert log1["operation_type"] == "weekly_eval"
        
        # Verify second log
        log2 = json.loads(lines[1])
        assert log2["athlete_id"] == 456
        assert log2["operation_type"] == "chat_response"


def test_jsonl_logging_with_error_message():
    """Test that error messages are properly logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path))
        
        # Create invocation with error
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=0,
            latency_ms=500.0,
            success_status=False,
            error_message="Connection timeout after 30 seconds"
        )
        
        logger.log(invocation)
        
        # Verify error message is logged
        with open(log_path, 'r', encoding='utf-8') as f:
            log_data = json.loads(f.readline())
        
        assert log_data["success_status"] is False
        assert log_data["error_message"] == "Connection timeout after 30 seconds"


def test_jsonl_logging_creates_directory_if_not_exists():
    """Test that the logger creates the directory structure if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "nested" / "path" / "invocations.jsonl"
        logger = InvocationLogger(log_file_path=str(log_path))
        
        # Create a test invocation log
        invocation = InvocationLog(
            timestamp=datetime.now().isoformat(),
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        
        # Log the invocation
        logger.log(invocation)
        
        # Verify directory and file were created
        assert log_path.parent.exists(), "Parent directory should be created"
        assert log_path.exists(), "Log file should be created"


if __name__ == "__main__":
    test_jsonl_logging_writes_to_correct_path()
    test_jsonl_logging_one_json_per_line()
    test_jsonl_logging_appends_not_overwrites()
    test_jsonl_logging_with_error_message()
    test_jsonl_logging_creates_directory_if_not_exists()
    print("All JSONL logging tests passed!")

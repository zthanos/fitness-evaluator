"""
Unit tests for InvocationLogger.

Tests the InvocationLog dataclass and InvocationLogger JSONL writing functionality.
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime

from app.ai.telemetry import InvocationLog, InvocationLogger


def test_invocation_log_creation():
    """Test that InvocationLog dataclass can be created with all required fields."""
    log = InvocationLog(
        timestamp="2024-01-15T10:30:00Z",
        operation_type="weekly_eval",
        athlete_id=123,
        model_used="mixtral",
        context_token_count=2500,
        response_token_count=500,
        latency_ms=1234.5,
        success_status=True,
        error_message=None
    )
    
    assert log.timestamp == "2024-01-15T10:30:00Z"
    assert log.operation_type == "weekly_eval"
    assert log.athlete_id == 123
    assert log.model_used == "mixtral"
    assert log.context_token_count == 2500
    assert log.response_token_count == 500
    assert log.latency_ms == 1234.5
    assert log.success_status is True
    assert log.error_message is None


def test_invocation_log_with_error():
    """Test that InvocationLog can capture error information."""
    log = InvocationLog(
        timestamp="2024-01-15T10:30:00Z",
        operation_type="chat_response",
        athlete_id=456,
        model_used="llama",
        context_token_count=1800,
        response_token_count=0,
        latency_ms=500.0,
        success_status=False,
        error_message="Connection timeout"
    )
    
    assert log.success_status is False
    assert log.error_message == "Connection timeout"


def test_invocation_logger_writes_jsonl():
    """Test that InvocationLogger writes logs in JSONL format."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as tmp:
        tmp_path = tmp.name
    
    try:
        # Create logger with temporary file
        logger = InvocationLogger(log_file_path=tmp_path)
        
        # Log a successful invocation
        log1 = InvocationLog(
            timestamp="2024-01-15T10:30:00Z",
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True,
            error_message=None
        )
        logger.log(log1)
        
        # Log a failed invocation
        log2 = InvocationLog(
            timestamp="2024-01-15T10:31:00Z",
            operation_type="chat_response",
            athlete_id=456,
            model_used="llama",
            context_token_count=1800,
            response_token_count=0,
            latency_ms=500.0,
            success_status=False,
            error_message="Connection timeout"
        )
        logger.log(log2)
        
        # Read and verify the JSONL file
        with open(tmp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        
        # Parse first line
        record1 = json.loads(lines[0])
        assert record1['timestamp'] == "2024-01-15T10:30:00Z"
        assert record1['operation_type'] == "weekly_eval"
        assert record1['athlete_id'] == 123
        assert record1['model_used'] == "mixtral"
        assert record1['context_token_count'] == 2500
        assert record1['response_token_count'] == 500
        assert record1['latency_ms'] == 1234.5
        assert record1['success_status'] is True
        assert record1['error_message'] is None
        
        # Parse second line
        record2 = json.loads(lines[1])
        assert record2['timestamp'] == "2024-01-15T10:31:00Z"
        assert record2['operation_type'] == "chat_response"
        assert record2['athlete_id'] == 456
        assert record2['model_used'] == "llama"
        assert record2['success_status'] is False
        assert record2['error_message'] == "Connection timeout"
        
    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)


def test_invocation_logger_appends_to_existing_file():
    """Test that InvocationLogger appends to existing log files."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as tmp:
        tmp_path = tmp.name
    
    try:
        logger = InvocationLogger(log_file_path=tmp_path)
        
        # Log first invocation
        log1 = InvocationLog(
            timestamp="2024-01-15T10:30:00Z",
            operation_type="weekly_eval",
            athlete_id=123,
            model_used="mixtral",
            context_token_count=2500,
            response_token_count=500,
            latency_ms=1234.5,
            success_status=True
        )
        logger.log(log1)
        
        # Create a new logger instance (simulating app restart)
        logger2 = InvocationLogger(log_file_path=tmp_path)
        
        # Log second invocation
        log2 = InvocationLog(
            timestamp="2024-01-15T10:31:00Z",
            operation_type="chat_response",
            athlete_id=456,
            model_used="llama",
            context_token_count=1800,
            response_token_count=300,
            latency_ms=800.0,
            success_status=True
        )
        logger2.log(log2)
        
        # Verify both records are in the file
        with open(tmp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_invocation_log_creation()
    test_invocation_log_with_error()
    test_invocation_logger_writes_jsonl()
    test_invocation_logger_appends_to_existing_file()
    print("All tests passed!")

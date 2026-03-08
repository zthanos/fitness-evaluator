"""
Test telemetry integration in LangChainAdapter.

This test verifies that the LangChainAdapter correctly logs invocation
telemetry including token counts, latency, model used, and success/failure status.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from pydantic import BaseModel

from app.ai.adapter.langchain_adapter import LangChainAdapter
from app.ai.context.builder import Context
from app.ai.telemetry.invocation_logger import InvocationLogger


class TestContract(BaseModel):
    """Test output contract"""
    message: str
    score: int


def test_langchain_adapter_logs_successful_invocation():
    """Test that successful invocations are logged with correct telemetry"""
    # Create a temporary log file
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test_invocations.jsonl"
        
        # Create logger and adapter
        logger = InvocationLogger(log_file_path=str(log_file))
        adapter = LangChainAdapter(invocation_logger=logger)
        
        # Create a mock context
        context = Context(
            system_instructions="You are a test assistant",
            task_instructions="Generate a test response",
            domain_knowledge={},
            retrieved_data=[],
            token_count=100
        )
        
        # Mock the _invoke_model method to return a test response
        test_response = TestContract(message="Test response", score=85)
        with patch.object(adapter, '_invoke_model', return_value=test_response):
            # Invoke the adapter
            result = adapter.invoke(
                context=context,
                contract=TestContract,
                operation_type="test_operation",
                athlete_id=123
            )
            
            # Verify the result
            assert result.parsed_output == test_response
            assert result.model_used == adapter.primary_model
            assert result.latency_ms >= 0  # Latency should be non-negative
            assert result.token_count > 100  # Should include response tokens
        
        # Verify the log file was created and contains the invocation
        assert log_file.exists()
        
        # Read and parse the log entry
        with open(log_file, 'r') as f:
            log_entry = json.loads(f.readline())
        
        # Verify log entry fields
        assert log_entry['operation_type'] == "test_operation"
        assert log_entry['athlete_id'] == 123
        assert log_entry['model_used'] == adapter.primary_model
        assert log_entry['context_token_count'] == 100
        assert log_entry['response_token_count'] > 0
        assert log_entry['latency_ms'] >= 0  # Latency should be non-negative
        assert log_entry['success_status'] is True
        assert log_entry['error_message'] is None
        assert 'timestamp' in log_entry


def test_langchain_adapter_logs_failed_invocation():
    """Test that failed invocations are logged with error details"""
    # Create a temporary log file
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test_invocations.jsonl"
        
        # Create logger and adapter
        logger = InvocationLogger(log_file_path=str(log_file))
        adapter = LangChainAdapter(invocation_logger=logger)
        
        # Create a mock context
        context = Context(
            system_instructions="You are a test assistant",
            task_instructions="Generate a test response",
            domain_knowledge={},
            retrieved_data=[],
            token_count=100
        )
        
        # Mock the _invoke_model method to raise an exception
        test_error = ValueError("Test error message")
        with patch.object(adapter, '_invoke_model', side_effect=test_error):
            # Invoke the adapter and expect an exception
            try:
                adapter.invoke(
                    context=context,
                    contract=TestContract,
                    operation_type="test_operation",
                    athlete_id=456
                )
                assert False, "Expected exception was not raised"
            except ValueError:
                pass  # Expected
        
        # Verify the log file was created and contains the invocation
        assert log_file.exists()
        
        # Read and parse the log entry
        with open(log_file, 'r') as f:
            log_entry = json.loads(f.readline())
        
        # Verify log entry fields
        assert log_entry['operation_type'] == "test_operation"
        assert log_entry['athlete_id'] == 456
        assert log_entry['model_used'] == adapter.primary_model
        assert log_entry['context_token_count'] == 100
        assert log_entry['response_token_count'] == 0
        assert log_entry['latency_ms'] >= 0  # Latency should be non-negative
        assert log_entry['success_status'] is False
        assert "ValueError: Test error message" in log_entry['error_message']
        assert 'timestamp' in log_entry


def test_langchain_adapter_logs_fallback_invocation():
    """Test that fallback invocations are logged with correct model name"""
    # Create a temporary log file
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test_invocations.jsonl"
        
        # Create logger and adapter
        logger = InvocationLogger(log_file_path=str(log_file))
        adapter = LangChainAdapter(invocation_logger=logger)
        
        # Create a mock context
        context = Context(
            system_instructions="You are a test assistant",
            task_instructions="Generate a test response",
            domain_knowledge={},
            retrieved_data=[],
            token_count=100
        )
        
        # Mock the _invoke_model method to fail on primary, succeed on fallback
        test_response = TestContract(message="Fallback response", score=75)
        
        def mock_invoke_model(model_name, messages, contract):
            if model_name == adapter.primary_model:
                import requests.exceptions
                raise requests.exceptions.Timeout("Primary model timeout")
            return test_response
        
        with patch.object(adapter, '_invoke_model', side_effect=mock_invoke_model):
            # Invoke the adapter
            result = adapter.invoke(
                context=context,
                contract=TestContract,
                operation_type="test_operation",
                athlete_id=789
            )
            
            # Verify the result uses fallback model
            assert result.parsed_output == test_response
            assert result.model_used == adapter.fallback_model
        
        # Verify the log file was created and contains the invocation
        assert log_file.exists()
        
        # Read and parse the log entry
        with open(log_file, 'r') as f:
            log_entry = json.loads(f.readline())
        
        # Verify log entry shows fallback model was used
        assert log_entry['model_used'] == adapter.fallback_model
        assert log_entry['success_status'] is True


if __name__ == "__main__":
    print("Running telemetry integration tests...")
    test_langchain_adapter_logs_successful_invocation()
    print("✓ Successful invocation logging test passed")
    
    test_langchain_adapter_logs_failed_invocation()
    print("✓ Failed invocation logging test passed")
    
    test_langchain_adapter_logs_fallback_invocation()
    print("✓ Fallback invocation logging test passed")
    
    print("\nAll tests passed!")

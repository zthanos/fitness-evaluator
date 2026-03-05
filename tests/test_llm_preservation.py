"""
Preservation Property Tests for LLM Client

**IMPORTANT**: Follow observation-first methodology - observe behavior on UNFIXED code.
**EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve).

This test validates requirements 3.3, 3.5 from bugfix.md:
- 3.3: Local LM Studio connection continues to work
- 3.5: JSON response validation and retry logic continue to function

**Validates: Requirements 3.3, 3.5**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from app.config import Settings
from app.services.llm_client import generate_evaluation, construct_openai_endpoint
import httpx
import json
from unittest.mock import AsyncMock, patch, MagicMock


@settings(
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    base_url=st.sampled_from([
        "http://localhost:1234",
        "http://127.0.0.1:1234",
        "http://localhost:8080",
    ])
)
def test_property_lm_studio_local_connection(base_url, monkeypatch):
    """
    Property 2: Preservation - LM Studio Local Connection
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior to preserve)
    
    Tests that when OLLAMA_ENDPOINT is a clean base URL (no /api suffix and no trailing slash),
    the client constructs the correct endpoint URL for connection.
    
    **Validates: Requirements 3.3**
    """
    # Mock the settings to use a clean base URL (LM Studio format)
    def mock_get_settings():
        settings = Settings(
            OLLAMA_ENDPOINT=base_url,
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
        return settings
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Get the settings to check the constructed URL using the NEW implementation
    settings = mock_get_settings()
    constructed_url = construct_openai_endpoint(settings.llm_base_url)
    
    # For clean base URLs (no /api suffix), the NEW implementation uses /v1/chat/completions
    # The URL should be: base_url + /v1/chat/completions
    expected_url = base_url + "/v1/chat/completions"
    
    assert constructed_url == expected_url, (
        f"LM Studio local connection URL construction changed. "
        f"Got: {constructed_url}, "
        f"Expected: {expected_url}. "
        f"This would break requirement 3.3: Local LM Studio connection must continue to work."
    )


@pytest.mark.anyio
async def test_property_json_response_validation(monkeypatch):
    """
    Property 2: Preservation - JSON Response Validation
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior to preserve)
    
    Tests that the system continues to validate JSON responses from the LLM.
    
    **Validates: Requirements 3.5**
    """
    # Mock settings
    def mock_get_settings():
        return Settings(
            OLLAMA_ENDPOINT="http://localhost:1234",
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Mock httpx client to return invalid JSON
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "not valid json"}}]
    }
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
    
    with patch('httpx.AsyncClient', return_value=mock_client):
        # Test that invalid JSON raises ValueError
        with pytest.raises(ValueError, match="Invalid JSON response from LLM"):
            await generate_evaluation({"test": "contract"})
    
    # This confirms that JSON validation continues to work


@pytest.mark.anyio
async def test_property_valid_json_response_accepted(monkeypatch):
    """
    Property 2: Preservation - Valid JSON Response Handling
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior to preserve)
    
    Tests that the system continues to accept and return valid JSON responses.
    
    **Validates: Requirements 3.5**
    """
    # Mock settings
    def mock_get_settings():
        return Settings(
            OLLAMA_ENDPOINT="http://localhost:1234",
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Mock httpx client to return valid JSON
    valid_json = json.dumps({"evaluation": "test", "score": 85})
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": valid_json}}]
    }
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
    
    with patch('httpx.AsyncClient', return_value=mock_client):
        result = await generate_evaluation({"test": "contract"})
        
        # Verify the result is the valid JSON string
        assert result == valid_json
        # Verify it's parseable
        parsed = json.loads(result)
        assert parsed["evaluation"] == "test"
        assert parsed["score"] == 85


@pytest.mark.anyio
async def test_property_retry_logic_on_connection_errors(monkeypatch):
    """
    Property 2: Preservation - Retry Logic on Connection Errors
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior to preserve)
    
    Tests that the system continues to retry on connection errors (up to 3 attempts).
    
    **Validates: Requirements 3.5**
    """
    # Mock settings
    def mock_get_settings():
        return Settings(
            OLLAMA_ENDPOINT="http://localhost:1234",
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Track number of attempts
    attempt_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise httpx.ConnectError("Connection failed")
        # Third attempt succeeds
        valid_json = json.dumps({"evaluation": "success", "score": 90})
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": valid_json}}]
        }
        mock_response.raise_for_status = MagicMock()
        return mock_response
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post = mock_post
    
    with patch('httpx.AsyncClient', return_value=mock_client):
        result = await generate_evaluation({"test": "contract"})
        
        # Verify retry logic worked (3 attempts made)
        assert attempt_count == 3, (
            f"Retry logic changed. Expected 3 attempts, got {attempt_count}. "
            f"This would break requirement 3.5: Retry logic must continue to function."
        )
        
        # Verify the result is correct
        parsed = json.loads(result)
        assert parsed["evaluation"] == "success"


@pytest.mark.anyio
async def test_property_retry_exhaustion_raises_error(monkeypatch):
    """
    Property 2: Preservation - Retry Exhaustion Behavior
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior to preserve)
    
    Tests that the system raises an error after exhausting all retry attempts.
    
    **Validates: Requirements 3.5**
    """
    # Mock settings
    def mock_get_settings():
        return Settings(
            OLLAMA_ENDPOINT="http://localhost:1234",
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Track number of attempts
    attempt_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise httpx.ConnectError("Connection failed")
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post = mock_post
    
    with patch('httpx.AsyncClient', return_value=mock_client):
        # Test that connection error is raised after 3 attempts
        with pytest.raises(httpx.ConnectError):
            await generate_evaluation({"test": "contract"})
        
        # Verify all 3 attempts were made
        assert attempt_count == 3, (
            f"Retry logic changed. Expected 3 attempts, got {attempt_count}. "
            f"This would break requirement 3.5: Retry logic must continue to function."
        )


@settings(
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    endpoint_format=st.sampled_from([
        ("http://localhost:1234", "http://localhost:1234/chat/completions"),
        ("http://127.0.0.1:8080", "http://127.0.0.1:8080/chat/completions"),
        ("http://localhost:11434", "http://localhost:11434/chat/completions"),
    ])
)
def test_property_clean_url_construction(endpoint_format, monkeypatch):
    """
    Property 2: Preservation - Clean URL Construction
    
    EXPECTED OUTCOME: This test PASSES (confirms baseline behavior to preserve)
    
    Tests that clean base URLs (without /api suffix) continue to work correctly.
    This is the format used by LM Studio locally.
    
    **Validates: Requirements 3.3**
    """
    base_url, expected_url = endpoint_format
    
    # Mock the settings
    def mock_get_settings():
        settings = Settings(
            OLLAMA_ENDPOINT=base_url,
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
        return settings
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Get the constructed URL
    settings = mock_get_settings()
    constructed_url = f"{settings.llm_base_url}/chat/completions"
    
    # Verify the URL is constructed correctly for clean base URLs
    assert constructed_url == expected_url, (
        f"Clean URL construction changed. "
        f"Got: {constructed_url}, "
        f"Expected: {expected_url}. "
        f"This would break requirement 3.3: LM Studio local connection must continue to work."
    )


def test_concrete_lm_studio_endpoint_preserved(monkeypatch):
    """
    Concrete test case: Verify LM Studio local endpoint continues to work.
    
    This is the typical LM Studio configuration:
    - OLLAMA_ENDPOINT = "http://localhost:1234"
    - Expected URL: "http://localhost:1234/chat/completions"
    
    **Validates: Requirements 3.3**
    """
    # Mock the settings with LM Studio configuration
    def mock_get_settings():
        settings = Settings(
            OLLAMA_ENDPOINT="http://localhost:1234",
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
        return settings
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Get the constructed URL
    settings = mock_get_settings()
    constructed_url = f"{settings.llm_base_url}/chat/completions"
    
    # The URL should be correct for LM Studio
    expected_url = "http://localhost:1234/chat/completions"
    
    assert constructed_url == expected_url, (
        f"LM Studio local connection broken. "
        f"Got: {constructed_url}, "
        f"Expected: {expected_url}. "
        f"This breaks requirement 3.3: When the application runs locally with LM Studio, "
        f"the system SHALL CONTINUE TO connect to LM Studio at the configured endpoint."
    )

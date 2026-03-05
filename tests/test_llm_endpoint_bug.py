"""
Bug Condition Exploration Test for LLM Endpoint Construction

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
**DO NOT attempt to fix the test or the code when it fails.**

This test validates requirements 1.4, 1.5, 1.6 from bugfix.md:
- 1.4: Docker evaluation requests fail with 404 Not Found
- 1.5: LLM client constructs incorrect endpoint URL
- 1.6: System returns 404 error to frontend

**Validates: Requirements 1.4, 1.5, 1.6**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from app.config import Settings
from app.services.llm_client import generate_evaluation, construct_openai_endpoint
import httpx


@settings(
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    base_url=st.sampled_from([
        "http://ollama:11434/api",
        "http://ollama:11434/api/",
        "http://localhost:11434/api",
        "http://localhost:11434/api/",
    ])
)
def test_property_incorrect_endpoint_url_construction(base_url, monkeypatch):
    """
    Property 1: Fault Condition - Incorrect LLM Endpoint URL
    
    EXPECTED OUTCOME: This test FAILS (proves bug exists)
    
    Tests that when OLLAMA_ENDPOINT contains `/api` suffix, the constructed URL
    is incorrect: `http://ollama:11434/api/chat/completions` instead of the
    correct OpenAI-compatible endpoint `http://ollama:11434/v1/chat/completions`.
    
    **Validates: Requirements 1.5**
    """
    # Mock the settings to use the problematic base URL
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
    
    # EXPECTED TO PASS AFTER FIX: The URL should be correct
    # When base_url has `/api`, it should create `/v1/chat/completions` (correct)
    expected_url = base_url.rstrip('/').replace('/api', '') + "/v1/chat/completions"
    
    assert constructed_url == expected_url, (
        f"Incorrect endpoint URL construction. "
        f"Got: {constructed_url}, "
        f"Expected: {expected_url}. "
        f"This confirms bug 1.5: LLM client appends /chat/completions to base URL with /api suffix, "
        f"creating incorrect path instead of OpenAI-compatible /v1/chat/completions."
    )


@settings(
    phases=[Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    base_url_format=st.sampled_from([
        ("http://ollama:11434/api", "http://ollama:11434/api/chat/completions"),
        ("http://ollama:11434/api/", "http://ollama:11434/api/chat/completions"),
        ("http://localhost:11434/api", "http://localhost:11434/api/chat/completions"),
    ])
)
def test_property_constructed_url_format(base_url_format, monkeypatch):
    """
    Property 1: Fault Condition - Incorrect LLM Endpoint URL
    
    EXPECTED OUTCOME: This test FAILS (proves bug exists)
    
    Tests that the current implementation produces the INCORRECT URL format
    when given a base URL with `/api` suffix.
    
    **Validates: Requirements 1.5**
    """
    base_url, expected_incorrect_url = base_url_format
    
    # Mock the settings
    def mock_get_settings():
        settings = Settings(
            OLLAMA_ENDPOINT=base_url,
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
        return settings
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Get the constructed URL using the NEW implementation
    settings = mock_get_settings()
    constructed_url = construct_openai_endpoint(settings.llm_base_url)
    
    # The correct URL should use /v1/chat/completions
    correct_url = base_url.rstrip('/').replace('/api', '') + "/v1/chat/completions"
    
    # EXPECTED TO PASS AFTER FIX: Current implementation produces correct URL
    assert constructed_url == correct_url, (
        f"URL construction produces incorrect endpoint. "
        f"Current (incorrect): {constructed_url}, "
        f"Expected (correct): {correct_url}. "
        f"This confirms bug 1.5: System appends /chat/completions to base URL with /api, "
        f"instead of using OpenAI-compatible /v1/chat/completions path."
    )


def test_concrete_ollama_api_suffix_produces_wrong_url(monkeypatch):
    """
    Concrete test case: Verify that OLLAMA_ENDPOINT with /api suffix produces wrong URL.
    
    This is the exact scenario from the bug report:
    - OLLAMA_ENDPOINT = "http://ollama:11434/api"
    - Current (wrong): "http://ollama:11434/api/chat/completions"
    - Expected (correct): "http://ollama:11434/v1/chat/completions"
    
    **Validates: Requirements 1.4, 1.5**
    """
    # Mock the settings with the problematic configuration
    def mock_get_settings():
        settings = Settings(
            OLLAMA_ENDPOINT="http://ollama:11434/api",
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
        return settings
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Get the constructed URL using the NEW implementation
    settings = mock_get_settings()
    constructed_url = construct_openai_endpoint(settings.llm_base_url)
    
    # The correct URL should be
    correct_url = "http://ollama:11434/v1/chat/completions"
    
    # EXPECTED TO PASS AFTER FIX: Current implementation produces correct URL
    assert constructed_url == correct_url, (
        f"LLM endpoint URL construction is incorrect. "
        f"Current: {constructed_url}, "
        f"Expected: {correct_url}. "
        f"This confirms bug 1.5: When OLLAMA_ENDPOINT is 'http://ollama:11434/api', "
        f"the system creates 'http://ollama:11434/api/chat/completions' instead of "
        f"the correct OpenAI-compatible endpoint 'http://ollama:11434/v1/chat/completions'."
    )


def test_concrete_trailing_slash_handling(monkeypatch):
    """
    Concrete test case: Verify trailing slash handling in URL construction.
    
    Tests that base URLs with trailing slashes are handled correctly.
    
    **Validates: Requirements 1.5**
    """
    # Mock the settings with trailing slash
    def mock_get_settings():
        settings = Settings(
            OLLAMA_ENDPOINT="http://ollama:11434/api/",
            LLM_TYPE="ollama",
            OLLAMA_MODEL="mistral"
        )
        return settings
    
    monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
    
    # Get the constructed URL using the NEW implementation
    settings = mock_get_settings()
    constructed_url = construct_openai_endpoint(settings.llm_base_url)
    
    # The correct URL should normalize the base and use /v1
    correct_url = "http://ollama:11434/v1/chat/completions"
    
    # EXPECTED TO PASS AFTER FIX: Current implementation normalizes URLs correctly
    assert constructed_url == correct_url, (
        f"URL construction doesn't handle trailing slashes correctly. "
        f"Current: {constructed_url}, "
        f"Expected: {correct_url}. "
        f"This confirms bug 1.5: System doesn't normalize base URLs before appending path."
    )


def test_concrete_url_construction_logic(monkeypatch):
    """
    Concrete test case: Document the current (buggy) URL construction logic.
    
    This test explicitly shows that the current implementation simply appends
    /chat/completions to the base URL without any normalization or path correction.
    
    **Validates: Requirements 1.5**
    """
    test_cases = [
        ("http://ollama:11434/api", "http://ollama:11434/v1/chat/completions"),
        ("http://ollama:11434/api/", "http://ollama:11434/v1/chat/completions"),
        ("http://localhost:11434/api", "http://localhost:11434/v1/chat/completions"),
    ]
    
    for base_url, expected_correct_url in test_cases:
        # Mock the settings
        def mock_get_settings():
            settings = Settings(
                OLLAMA_ENDPOINT=base_url,
                LLM_TYPE="ollama",
                OLLAMA_MODEL="mistral"
            )
            return settings
        
        monkeypatch.setattr("app.services.llm_client.get_settings", mock_get_settings)
        
        # Get the constructed URL using the NEW implementation
        settings = mock_get_settings()
        constructed_url = construct_openai_endpoint(settings.llm_base_url)
        
        # EXPECTED TO PASS AFTER FIX: Current implementation produces correct URLs
        assert constructed_url == expected_correct_url, (
            f"URL construction failed for base_url='{base_url}'. "
            f"Current: {constructed_url}, "
            f"Expected: {expected_correct_url}. "
            f"This confirms bug 1.5: System doesn't use correct OpenAI-compatible endpoint path."
        )

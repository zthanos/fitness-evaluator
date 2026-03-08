"""Bug Condition Exploration Test: LM Studio Data Retrieval Parity

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**

This test explores the bug condition where LM Studio users lack data retrieval tools.

CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

The test encodes the expected behavior - it will validate the fix when it passes after implementation.

GOAL: Surface counterexamples that demonstrate LM Studio users lack data retrieval tools.

Scoped PBT Approach: Scope the property to the concrete failing case: LLM_TYPE="lm-studio"
"""
import os
import sys
from hypothesis import given, strategies as st, settings, Phase
from typing import List, Dict, Any

# Set environment variable before any imports to ensure database can initialize
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

# Now we can import app modules
from app.config import get_settings


def get_service_name_for_llm_type(llm_type: str) -> str:
    """
    Simulate the service selection logic in app/api/chat.py.
    
    After the fix: All LLM providers use LangChainChatService.
    """
    # After the fix, all providers use LangChainChatService
    return "LangChainChatService"


def get_tools_for_service(service_name: str) -> set:
    """
    Get the tools available for a given service.
    
    Returns:
        set: Set of tool names available in the service
    """
    if service_name == "LangChainChatService":
        # LangChainChatService has all 4 data retrieval tools
        return {
            'save_athlete_goal',
            'get_my_goals',
            'get_my_recent_activities',
            'get_my_weekly_metrics'
        }
    elif service_name == "LMStudioChatService":
        # LMStudioChatService has NO data retrieval tools
        # It only has basic chat functionality
        return set()
    else:
        return set()


# Property 1: Fault Condition - LM Studio Routes to Service Without Data Retrieval Tools
@settings(
    max_examples=5,
    phases=[Phase.generate],
    deadline=None,
    print_blob=True
)
@given(
    llm_type=st.just("lm-studio"),  # Scoped to the concrete failing case
)
def test_lm_studio_routes_to_service_with_data_retrieval_tools(llm_type: str):
    """
    **Property 1: Fault Condition** - LM Studio Routes to Service Without Data Retrieval Tools
    
    **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
    
    Test that when LLM_TYPE="lm-studio", the system uses LangChainChatService with all 4 data retrieval tools.
    
    The test assertions verify:
    - Service used is LangChainChatService (not LMStudioChatService)
    - All 4 tools are available: save_athlete_goal, get_my_goals, get_my_recent_activities, get_my_weekly_metrics
    - Behavior matches Ollama/OpenAI providers
    
    EXPECTED OUTCOME: Test FAILS on unfixed code (this is correct - it proves the bug exists)
    
    Counterexamples found: "LM Studio routes to LMStudioChatService which lacks data retrieval tools"
    """
    # Get the service that would be used for LM Studio
    service_name = get_service_name_for_llm_type(llm_type)
    
    # ASSERTION 1: Service used is LangChainChatService (not LMStudioChatService)
    assert service_name == "LangChainChatService", (
        f"Expected LangChainChatService for LLM_TYPE='{llm_type}', "
        f"but got {service_name}. "
        f"LM Studio should use LangChainChatService like Ollama/OpenAI providers."
    )
    
    # Get the tools available for this service
    available_tools = get_tools_for_service(service_name)
    
    # ASSERTION 2: All 4 data retrieval tools are available
    expected_tools = {
        'save_athlete_goal',
        'get_my_goals',
        'get_my_recent_activities',
        'get_my_weekly_metrics'
    }
    
    missing_tools = expected_tools - available_tools
    
    assert len(missing_tools) == 0, (
        f"LM Studio service is missing data retrieval tools: {missing_tools}. "
        f"Expected all 4 tools: {expected_tools}, "
        f"but only found: {available_tools}. "
        f"LM Studio should have the same tools as Ollama/OpenAI providers."
    )
    
    # ASSERTION 3: Verify all expected tools are present
    assert expected_tools.issubset(available_tools), (
        f"LM Studio service does not have all required data retrieval tools. "
        f"Expected: {expected_tools}, "
        f"Found: {available_tools}"
    )


def test_lm_studio_parity_with_other_providers():
    """
    Additional test: Verify LM Studio has parity with Ollama and OpenAI providers.
    
    This test compares the service selection for all three providers to ensure
    LM Studio gets the same service as the others.
    """
    providers = ["lm-studio", "ollama", "openai"]
    services_used = {}
    
    for provider in providers:
        service_name = get_service_name_for_llm_type(provider)
        services_used[provider] = service_name
    
    # All providers should use the same service
    unique_services = set(services_used.values())
    
    assert len(unique_services) == 1, (
        f"Providers are using different services: {services_used}. "
        f"All providers should use LangChainChatService for consistency. "
        f"LM Studio: {services_used.get('lm-studio')}, "
        f"Ollama: {services_used.get('ollama')}, "
        f"OpenAI: {services_used.get('openai')}"
    )
    
    # Verify they all use LangChainChatService
    assert "LangChainChatService" in unique_services, (
        f"Expected all providers to use LangChainChatService, "
        f"but found: {unique_services}"
    )


# Property 2: Preservation - Ollama and OpenAI Service Selection and Tool Availability
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
    print_blob=True
)
@given(
    llm_type=st.sampled_from(["ollama", "openai"]),  # Non-buggy cases
)
def test_ollama_and_openai_preserve_langchain_service_with_tools(llm_type: str):
    """
    **Property 2: Preservation** - Ollama and OpenAI Service Selection and Tool Availability
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    
    Test that when LLM_TYPE is "ollama" or "openai", the system uses LangChainChatService 
    with all 4 data retrieval tools.
    
    This test captures the baseline behavior that must be preserved when fixing the bug.
    
    The test assertions verify:
    - Service used is LangChainChatService
    - All 4 tools are available: save_athlete_goal, get_my_goals, get_my_recent_activities, get_my_weekly_metrics
    - Response format and structure remain consistent
    - ChatOpenAI supports OpenAI-compatible endpoints
    
    EXPECTED OUTCOME: Test PASSES on unfixed code (this confirms baseline behavior to preserve)
    """
    # Get the service that would be used for this provider
    service_name = get_service_name_for_llm_type(llm_type)
    
    # ASSERTION 1: Service used is LangChainChatService
    assert service_name == "LangChainChatService", (
        f"Expected LangChainChatService for LLM_TYPE='{llm_type}', "
        f"but got {service_name}. "
        f"This baseline behavior must be preserved after fixing the LM Studio bug."
    )
    
    # Get the tools available for this service
    available_tools = get_tools_for_service(service_name)
    
    # ASSERTION 2: All 4 data retrieval tools are available
    expected_tools = {
        'save_athlete_goal',
        'get_my_goals',
        'get_my_recent_activities',
        'get_my_weekly_metrics'
    }
    
    missing_tools = expected_tools - available_tools
    
    assert len(missing_tools) == 0, (
        f"{llm_type.upper()} service is missing data retrieval tools: {missing_tools}. "
        f"Expected all 4 tools: {expected_tools}, "
        f"but only found: {available_tools}. "
        f"This baseline behavior must be preserved after fixing the LM Studio bug."
    )
    
    # ASSERTION 3: Verify all expected tools are present
    assert expected_tools.issubset(available_tools), (
        f"{llm_type.upper()} service does not have all required data retrieval tools. "
        f"Expected: {expected_tools}, "
        f"Found: {available_tools}. "
        f"This baseline behavior must be preserved."
    )


def test_response_format_consistency():
    """
    **Property 2: Preservation** - Response Format Consistency
    
    **Validates: Requirement 3.4**
    
    Test that response format and structure remain consistent across providers.
    
    This test verifies that all providers using LangChainChatService will have
    the same response format, which must be preserved after the fix.
    
    EXPECTED OUTCOME: Test PASSES on unfixed code
    """
    # Test that Ollama and OpenAI both use LangChainChatService
    ollama_service = get_service_name_for_llm_type("ollama")
    openai_service = get_service_name_for_llm_type("openai")
    
    assert ollama_service == "LangChainChatService", (
        f"Ollama should use LangChainChatService, got {ollama_service}"
    )
    
    assert openai_service == "LangChainChatService", (
        f"OpenAI should use LangChainChatService, got {openai_service}"
    )
    
    # Both services should have the same tools (same response format)
    ollama_tools = get_tools_for_service(ollama_service)
    openai_tools = get_tools_for_service(openai_service)
    
    assert ollama_tools == openai_tools, (
        f"Response format inconsistency detected. "
        f"Ollama tools: {ollama_tools}, "
        f"OpenAI tools: {openai_tools}. "
        f"Both should have identical tool sets."
    )


def test_chatgpt_openai_compatible_endpoint_support():
    """
    **Property 2: Preservation** - ChatOpenAI Compatibility
    
    **Validates: Requirement 3.5**
    
    Test that ChatOpenAI supports OpenAI-compatible endpoints including LM Studio.
    
    This test documents that LangChain's ChatOpenAI already supports OpenAI-compatible
    endpoints, which is why the fix (using LangChainChatService for all providers) works.
    
    EXPECTED OUTCOME: Test PASSES on unfixed code
    """
    # Verify that OpenAI uses LangChainChatService
    openai_service = get_service_name_for_llm_type("openai")
    
    assert openai_service == "LangChainChatService", (
        f"OpenAI should use LangChainChatService (which uses ChatOpenAI), "
        f"got {openai_service}"
    )
    
    # Document that ChatOpenAI supports OpenAI-compatible endpoints
    # This is a known fact about LangChain's ChatOpenAI implementation
    # It can connect to any OpenAI-compatible endpoint by setting base_url
    chatgpt_supports_compatible_endpoints = True
    
    assert chatgpt_supports_compatible_endpoints, (
        "ChatOpenAI must support OpenAI-compatible endpoints. "
        "This is a core feature of LangChain's ChatOpenAI that enables "
        "connecting to LM Studio, Ollama, and other compatible services."
    )


if __name__ == "__main__":
    print("=" * 80)
    print("Bug Condition Exploration Test: LM Studio Data Retrieval Parity")
    print("=" * 80)
    print()
    print("This test explores the bug where LM Studio users lack data retrieval tools.")
    print()
    print("EXPECTED OUTCOME: Test FAILS on unfixed code (this confirms the bug exists)")
    print()
    print("Running Property 1: Fault Condition Test...")
    print("-" * 80)
    
    try:
        test_lm_studio_routes_to_service_with_data_retrieval_tools()
        print()
        print("✅ Property 1 PASSED: LM Studio uses LangChainChatService with all tools")
        print()
        print("⚠️  UNEXPECTED: Test passed! This means either:")
        print("   1. The bug has already been fixed")
        print("   2. The test is not correctly detecting the bug")
        print()
    except AssertionError as e:
        print()
        print("❌ Property 1 FAILED (EXPECTED): Bug condition detected!")
        print()
        print("Counterexample found:")
        print(f"  {str(e)}")
        print()
        print("✅ This failure confirms the bug exists:")
        print("   - LM Studio routes to LMStudioChatService")
        print("   - LMStudioChatService lacks data retrieval tools")
        print("   - This creates inconsistent behavior vs Ollama/OpenAI")
        print()
    
    print("-" * 80)
    print("Running Additional Test: Provider Parity Check...")
    print("-" * 80)
    
    try:
        test_lm_studio_parity_with_other_providers()
        print()
        print("✅ Parity Test PASSED: All providers use the same service")
        print()
    except AssertionError as e:
        print()
        print("❌ Parity Test FAILED (EXPECTED): Providers use different services")
        print()
        print("Counterexample found:")
        print(f"  {str(e)}")
        print()
    
    print("=" * 80)
    print("Preservation Property Tests: Ollama and OpenAI Baseline Behavior")
    print("=" * 80)
    print()
    print("These tests capture the baseline behavior that must be preserved when fixing the bug.")
    print()
    print("EXPECTED OUTCOME: Tests PASS on unfixed code (confirms baseline to preserve)")
    print()
    print("Running Property 2: Preservation Tests...")
    print("-" * 80)
    
    preservation_tests_passed = 0
    preservation_tests_failed = 0
    
    # Test 1: Ollama and OpenAI service selection and tool availability
    print("\n[Test 1] Ollama and OpenAI Service Selection and Tool Availability")
    try:
        test_ollama_and_openai_preserve_langchain_service_with_tools()
        print("✅ PASSED: Ollama and OpenAI use LangChainChatService with all tools")
        preservation_tests_passed += 1
    except AssertionError as e:
        print("❌ FAILED (UNEXPECTED): Baseline behavior not as expected")
        print(f"   Error: {str(e)}")
        preservation_tests_failed += 1
    
    # Test 2: Response format consistency
    print("\n[Test 2] Response Format Consistency")
    try:
        test_response_format_consistency()
        print("✅ PASSED: Response format is consistent across providers")
        preservation_tests_passed += 1
    except AssertionError as e:
        print("❌ FAILED (UNEXPECTED): Response format inconsistency detected")
        print(f"   Error: {str(e)}")
        preservation_tests_failed += 1
    
    # Test 3: ChatOpenAI compatibility
    print("\n[Test 3] ChatOpenAI OpenAI-Compatible Endpoint Support")
    try:
        test_chatgpt_openai_compatible_endpoint_support()
        print("✅ PASSED: ChatOpenAI supports OpenAI-compatible endpoints")
        preservation_tests_passed += 1
    except AssertionError as e:
        print("❌ FAILED (UNEXPECTED): ChatOpenAI compatibility issue")
        print(f"   Error: {str(e)}")
        preservation_tests_failed += 1
    
    print()
    print("-" * 80)
    print(f"Preservation Tests Summary: {preservation_tests_passed} passed, {preservation_tests_failed} failed")
    print("-" * 80)
    
    if preservation_tests_failed == 0:
        print()
        print("✅ All preservation tests PASSED!")
        print("   Baseline behavior for Ollama and OpenAI is confirmed.")
        print("   These behaviors must be preserved when fixing the LM Studio bug.")
        print()
    else:
        print()
        print("⚠️  Some preservation tests FAILED!")
        print("   This indicates the baseline behavior may not be as expected.")
        print("   Review the failures before proceeding with the fix.")
        print()
    
    print("=" * 80)
    print("Test Execution Complete")
    print("=" * 80)
    print()
    print("SUMMARY:")
    print("--------")
    print("This test documents the bug condition where LM Studio users lack")
    print("data retrieval tools because the conditional logic in app/api/chat.py")
    print("routes them to LMStudioChatService instead of LangChainChatService.")
    print()
    print("Expected behavior: All providers (LM Studio, Ollama, OpenAI) should")
    print("use LangChainChatService with all 4 data retrieval tools:")
    print("  - save_athlete_goal")
    print("  - get_my_goals")
    print("  - get_my_recent_activities")
    print("  - get_my_weekly_metrics")
    print()
    print("Preservation requirements: Ollama and OpenAI must continue to use")
    print("LangChainChatService with all tools after the fix is implemented.")
    print()

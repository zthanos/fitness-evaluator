# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Fault Condition** - LM Studio Routes to Service Without Data Retrieval Tools
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate LM Studio users lack data retrieval tools
  - **Scoped PBT Approach**: Scope the property to the concrete failing case: LLM_TYPE="lm-studio"
  - Test that when LLM_TYPE="lm-studio", the system uses LangChainChatService with all 4 data retrieval tools
  - The test assertions should verify:
    - Service used is LangChainChatService (not LMStudioChatService)
    - All 4 tools are available: save_athlete_goal, get_my_goals, get_my_recent_activities, get_my_weekly_metrics
    - Behavior matches Ollama/OpenAI providers
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: "LM Studio routes to LMStudioChatService which lacks data retrieval tools"
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Ollama and OpenAI Service Selection and Tool Availability
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (Ollama and OpenAI)
  - Write property-based tests capturing observed behavior patterns:
    - When LLM_TYPE="ollama", system uses LangChainChatService with all 4 tools
    - When LLM_TYPE="openai", system uses LangChainChatService with all 4 tools
    - Response format and structure remain consistent
    - ChatOpenAI supports OpenAI-compatible endpoints
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3. Fix for LM Studio data retrieval parity

  - [x] 3.1 Remove conditional service selection in app/api/chat.py
    - Remove the conditional import logic (lines 23-28) that checks LLM_TYPE
    - Replace with direct import of LangChainChatService
    - Remove import of LMStudioChatService
    - Simplify to single service path: always use LangChainChatService
    - Update print statement to reflect unified service usage
    - _Bug_Condition: input.llm_type == "lm-studio" AND input.service_used == "LMStudioChatService" AND NOT has_data_retrieval_tools(input.service_used)_
    - _Expected_Behavior: result.service_used == "LangChainChatService" AND has_all_tools(result.service_used, ["save_athlete_goal", "get_my_goals", "get_my_recent_activities", "get_my_weekly_metrics"]) AND result.behavior == result_for_other_providers(["ollama", "openai"])_
    - _Preservation: For all inputs where input.llm_type IN ["ollama", "openai"], service selection, tool availability, response format, and ChatOpenAI compatibility must remain unchanged_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - LM Studio Uses LangChainChatService with All Tools
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify LM Studio users now get LangChainChatService with all 4 data retrieval tools
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Ollama and OpenAI Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm Ollama and OpenAI users still get LangChainChatService with all tools
    - Confirm response format and ChatOpenAI compatibility unchanged
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

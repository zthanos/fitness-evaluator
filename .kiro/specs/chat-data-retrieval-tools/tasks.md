# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Fault Condition** - Data Retrieval Tools Missing
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases - data retrieval questions with missing tools
  - Test that when user asks data retrieval questions (progress, activities, metrics, goals), the agent has access to appropriate tools
  - Verify tool list contains `get_recent_activities`, `get_athlete_goals`, and `get_weekly_metrics`
  - Test cases: "How am I progressing?", "What activities did I do?", "What's my weight?", "What are my goals?"
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (tool list only contains `save_athlete_goal`, missing 3 data retrieval tools)
  - Document counterexamples found: agent cannot answer data-driven questions, tool count is 1 instead of 4
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Tool Functionality
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-data-retrieval interactions
  - Test goal-setting conversations: "I want to lose 10 pounds" → verify `save_athlete_goal` is called
  - Test general advice questions: "What's a good workout routine?" → verify response generation works
  - Test RAG context retrieval: verify system prompt loading with athlete profile works
  - Test tool execution flow: verify `get_chat_response()` handles tool calls correctly
  - Write property-based tests capturing observed behavior patterns
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix for missing data retrieval tools

  - [x] 3.1 Add imports for existing data retrieval tools
    - Import `get_athlete_goals` from `app.ai.tools.get_athlete_goals`
    - Import `get_recent_activities` from `app.ai.tools.get_recent_activities`
    - Import `get_weekly_metrics` from `app.ai.tools.get_weekly_metrics`
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Add default athlete context
    - Add `self.default_athlete_id = 1` in `__init__` method for single-athlete MVP
    - This provides athlete context that the existing tools require
    - _Requirements: 2.4_

  - [x] 3.3 Create wrapper tools with athlete context injection
    - Create `get_my_goals()` wrapper that calls `get_athlete_goals` with `default_athlete_id`
    - Create `get_my_recent_activities(days_back: int)` wrapper that calls `get_recent_activities` with `default_athlete_id`
    - Create `get_my_weekly_metrics(week_id: str)` wrapper that calls `get_weekly_metrics` with `default_athlete_id`
    - Use `@langchain_tool` decorator for each wrapper
    - Include clear docstrings describing what each tool does
    - _Bug_Condition: isBugCondition(input) where input.content contains intent to retrieve activities, progress, metrics, or goals AND available_tools does not contain data retrieval tools_
    - _Expected_Behavior: For all data retrieval questions, _create_tools() returns list containing get_recent_activities, get_athlete_goals, and get_weekly_metrics_
    - _Preservation: save_athlete_goal tool, RAG context retrieval, tool binding, tool execution flow, and system prompt loading remain unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.4 Update _create_tools() return statement
    - Modify return statement to include all 4 tools: `[save_athlete_goal, get_my_goals, get_my_recent_activities, get_my_weekly_metrics]`
    - Tool count log will automatically update to show 4 tools
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Data Retrieval Tools Available
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (tool list now contains 4 tools including all data retrieval tools)
    - Verify agent can now answer data-driven questions by calling appropriate tools
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Tool Functionality
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm goal-setting, general advice, RAG context, and tool execution all work identically
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

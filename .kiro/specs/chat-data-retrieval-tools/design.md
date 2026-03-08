# Chat Data Retrieval Tools Bugfix Design

## Overview

The LangChain chat service currently lacks data retrieval tools, preventing the AI coach from providing data-driven responses when athletes ask about their training progress. The `_create_tools()` method only returns a single tool (`save_athlete_goal`) for saving goals, but provides no tools for retrieving activities, metrics, daily logs, or progress data.

The fix involves integrating existing data retrieval tools (`get_athlete_goals`, `get_recent_activities`, `get_weekly_metrics`) into the LangChain chat service's tool list. These tools are already implemented in `app/ai/tools/` and follow the LangChain structured tool pattern with proper input validation, telemetry logging, and evidence card formatting.

The fix is straightforward: import the existing tools and add them to the list returned by `_create_tools()`. However, there's a critical issue - the existing tools require an `athlete_id` parameter, but the chat service doesn't currently have a way to provide this context. The fix must address this by either hardcoding a default athlete ID (for single-athlete MVP) or implementing proper athlete context management.

## Glossary

- **Bug_Condition (C)**: The condition where the chat agent needs to retrieve athlete data but has no tools available
- **Property (P)**: The desired behavior where data retrieval tools are available and can be called by the agent
- **Preservation**: Existing goal-saving functionality and RAG context retrieval that must remain unchanged
- **LangChainChatService**: The service class in `app/services/langchain_chat_service.py` that manages LLM interactions with tool calling
- **_create_tools()**: The method that returns a list of LangChain tools to bind to the LLM
- **Evidence Card**: A standardized dictionary format for tool results with type, id, and data fields
- **Tool Logger**: Telemetry system that logs tool invocations for debugging and monitoring

## Bug Details

### Fault Condition

The bug manifests when an athlete asks questions requiring data retrieval (e.g., "How am I progressing with my training?", "What activities did I do this week?", "What's my current weight?"). The `_create_tools()` method returns only one tool (`save_athlete_goal`), so the LLM has no way to retrieve activities, metrics, logs, or goal progress from the database.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ChatMessage
  OUTPUT: boolean
  
  RETURN (input.content CONTAINS_INTENT "retrieve activities" 
          OR input.content CONTAINS_INTENT "check progress"
          OR input.content CONTAINS_INTENT "view metrics"
          OR input.content CONTAINS_INTENT "see goals")
         AND available_tools DOES_NOT_CONTAIN "get_recent_activities"
         AND available_tools DOES_NOT_CONTAIN "get_athlete_goals"
         AND available_tools DOES_NOT_CONTAIN "get_weekly_metrics"
END FUNCTION
```

### Examples

- **Example 1**: User asks "How am I progressing with my training?" → Agent responds with generic questions instead of retrieving recent activities and providing specific feedback
- **Example 2**: User asks "What activities did I do this week?" → Agent cannot call `get_recent_activities` and asks user to manually describe their workouts
- **Example 3**: User asks "What's my current weight?" → Agent cannot call `get_weekly_metrics` and asks user to provide the information
- **Edge Case**: User asks "What are my goals?" → Agent cannot call `get_athlete_goals` even though the tool exists but isn't registered

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- The `save_athlete_goal` tool must continue to work exactly as before
- RAG context retrieval in `_load_system_prompt()` must remain unchanged
- Tool binding with `self.llm.bind_tools()` must continue to work
- Tool execution flow in `get_chat_response()` must remain unchanged
- System prompt loading with athlete profile and active goals must remain unchanged

**Scope:**
All inputs that do NOT involve data retrieval questions should be completely unaffected by this fix. This includes:
- Goal-setting conversations that use `save_athlete_goal`
- General fitness advice questions that don't require specific athlete data
- Conversations that rely on RAG context in the system prompt
- Any other tool-calling or non-tool-calling interactions

## Hypothesized Root Cause

Based on the bug description and code analysis, the root cause is clear:

1. **Missing Tool Registration**: The `_create_tools()` method only defines and returns `save_athlete_goal`, even though three data retrieval tools already exist in `app/ai/tools/`:
   - `get_athlete_goals` - retrieves active goals
   - `get_recent_activities` - retrieves Strava activities by date range
   - `get_weekly_metrics` - retrieves weekly body measurements

2. **Athlete Context Issue**: The existing tools require an `athlete_id` parameter, but the chat service doesn't currently provide athlete context. The service needs to either:
   - Use a hardcoded default athlete ID (for single-athlete MVP)
   - Implement proper athlete context management (for multi-athlete support)

3. **Tool Import Missing**: The existing tools are not imported in `langchain_chat_service.py`

## Correctness Properties

Property 1: Fault Condition - Data Retrieval Tools Available

_For any_ chat message where the user asks about their training progress, activities, metrics, or goals, the fixed `_create_tools()` method SHALL return a list containing `get_recent_activities`, `get_athlete_goals`, and `get_weekly_metrics` tools, enabling the LLM to retrieve athlete data from the database.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Existing Tool Functionality

_For any_ chat interaction that does NOT require data retrieval tools (goal-setting, general advice, RAG-based responses), the fixed code SHALL produce exactly the same behavior as the original code, preserving the `save_athlete_goal` tool, RAG context retrieval, and all other chat service functionality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `app/services/langchain_chat_service.py`

**Function**: `_create_tools()`

**Specific Changes**:

1. **Add Imports**: Import the existing data retrieval tools at the top of the file
   ```python
   from app.ai.tools.get_athlete_goals import get_athlete_goals
   from app.ai.tools.get_recent_activities import get_recent_activities
   from app.ai.tools.get_weekly_metrics import get_weekly_metrics
   ```

2. **Add Athlete Context**: Add a default athlete ID constant or instance variable
   ```python
   # In __init__ or as class constant
   self.default_athlete_id = 1  # For single-athlete MVP
   ```

3. **Create Wrapper Tools**: Create wrapper functions that inject the athlete_id context
   ```python
   @langchain_tool
   def get_my_goals() -> List[Dict[str, Any]]:
       """Retrieve your active fitness goals."""
       return get_athlete_goals.invoke({"athlete_id": self.default_athlete_id})
   
   @langchain_tool
   def get_my_recent_activities(days_back: int) -> List[Dict[str, Any]]:
       """Retrieve your recent Strava activities. Specify how many days back to look (max 365)."""
       return get_recent_activities.invoke({
           "athlete_id": self.default_athlete_id,
           "days_back": days_back
       })
   
   @langchain_tool
   def get_my_weekly_metrics(week_id: str) -> Optional[Dict[str, Any]]:
       """Retrieve your weekly body metrics. Provide week_id in format YYYY-WW (e.g., '2024-W15')."""
       return get_weekly_metrics.invoke({
           "athlete_id": self.default_athlete_id,
           "week_id": week_id
       })
   ```

4. **Return All Tools**: Modify the return statement to include all tools
   ```python
   return [save_athlete_goal, get_my_goals, get_my_recent_activities, get_my_weekly_metrics]
   ```

5. **Update Tool Count Log**: The initialization log will automatically show 4 tools instead of 1

### Alternative Approach (Simpler)

Instead of creating wrapper tools, we could directly return the imported tools and let the LLM provide the athlete_id. However, this requires the LLM to know the athlete_id, which it doesn't have context for. The wrapper approach is cleaner for the single-athlete MVP case.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, demonstrate the bug on unfixed code by showing that data retrieval questions fail, then verify the fix works correctly and preserves existing behavior.

### Exploratory Fault Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm that the agent cannot answer data-driven questions.

**Test Plan**: Send chat messages asking about activities, metrics, and goals to the unfixed chat service. Observe that the agent responds with generic questions instead of retrieving data. Inspect the tool list to confirm only `save_athlete_goal` is available.

**Test Cases**:
1. **Progress Question Test**: Send "How am I progressing with my training?" (will fail - agent asks for manual info)
2. **Activity Question Test**: Send "What activities did I do this week?" (will fail - agent cannot retrieve activities)
3. **Metrics Question Test**: Send "What's my current weight?" (will fail - agent cannot retrieve metrics)
4. **Goals Question Test**: Send "What are my goals?" (will fail - agent cannot retrieve goals)
5. **Tool List Inspection**: Check `len(service.tools)` equals 1 and only contains `save_athlete_goal`

**Expected Counterexamples**:
- Agent responds with "Can you tell me about your recent workouts?" instead of retrieving activities
- Agent responds with "What's your current weight?" instead of retrieving metrics
- Tool list contains only 1 tool instead of 4

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (data retrieval questions), the fixed function provides data retrieval tools.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  tools := _create_tools_fixed()
  ASSERT "get_recent_activities" IN [t.name for t in tools]
  ASSERT "get_athlete_goals" IN [t.name for t in tools]
  ASSERT "get_weekly_metrics" IN [t.name for t in tools]
  ASSERT len(tools) >= 4
END FOR
```

**Test Cases**:
1. **Tool List Verification**: Check that `_create_tools()` returns 4 tools
2. **Tool Names Verification**: Verify tool names include all data retrieval tools
3. **Tool Invocation Test**: Call each tool wrapper and verify it returns data
4. **Integration Test**: Send data retrieval questions and verify agent calls appropriate tools

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (non-data-retrieval interactions), the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT get_chat_response_original(input) = get_chat_response_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-data-retrieval inputs

**Test Plan**: Test goal-setting conversations, general advice questions, and RAG-based responses on both unfixed and fixed code. Verify identical behavior.

**Test Cases**:
1. **Goal Setting Preservation**: Send "I want to lose 10 pounds" and verify `save_athlete_goal` is called correctly
2. **General Advice Preservation**: Send "What's a good workout routine?" and verify response doesn't change
3. **RAG Context Preservation**: Send questions that trigger RAG retrieval and verify context is still included
4. **Tool Execution Preservation**: Verify tool execution flow in `get_chat_response()` works identically

### Unit Tests

- Test `_create_tools()` returns 4 tools with correct names
- Test each tool wrapper invokes the underlying tool with correct athlete_id
- Test tool wrappers handle errors gracefully
- Test that `save_athlete_goal` still works after adding new tools

### Property-Based Tests

- Generate random data retrieval questions and verify tools are available
- Generate random goal-setting conversations and verify behavior is preserved
- Generate random week_id values and verify `get_my_weekly_metrics` validates correctly
- Generate random days_back values and verify `get_my_recent_activities` validates correctly

### Integration Tests

- Test full conversation flow: ask about progress → agent calls `get_recent_activities` → agent provides specific feedback
- Test full conversation flow: ask about goals → agent calls `get_my_goals` → agent lists actual goals
- Test full conversation flow: ask about weight → agent calls `get_my_weekly_metrics` → agent provides current weight
- Test that tool results are properly formatted as evidence cards
- Test that tool invocations are logged by the telemetry system

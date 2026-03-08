# Design Document: LM Studio Data Retrieval Parity

## Overview

This design document specifies the fix for the LM Studio data retrieval parity bug. The bug prevents LM Studio users from accessing data retrieval tools because of conditional service selection logic that routes them to a separate LMStudioChatService instead of the unified LangChainChatService.

## Bug Condition Specification

### Fault Condition

The bug occurs when the application routes LM Studio users to a service without data retrieval tools.

**isBugCondition(input):**
```
input.llm_type == "lm-studio" AND
input.service_used == "LMStudioChatService" AND
NOT has_data_retrieval_tools(input.service_used)
```

**Concrete Failing Cases:**
- LLM_TYPE="lm-studio" → routes to LMStudioChatService → lacks save_athlete_goal, get_my_goals, get_my_recent_activities, get_my_weekly_metrics

### Expected Behavior Properties

When the bug condition is satisfied, the system should exhibit the following correct behavior:

**expectedBehavior(result):**
```
result.service_used == "LangChainChatService" AND
has_all_tools(result.service_used, [
  "save_athlete_goal",
  "get_my_goals", 
  "get_my_recent_activities",
  "get_my_weekly_metrics"
]) AND
result.behavior == result_for_other_providers(["ollama", "openai"])
```

**Properties:**
1. LM Studio users receive LangChainChatService
2. All 4 data retrieval tools are available
3. Behavior is identical to Ollama and OpenAI providers
4. No conditional routing based on LLM_TYPE

## Preservation Requirements

The fix must preserve existing behavior for non-buggy cases (Ollama and OpenAI providers).

**Non-Bug Condition:**
```
¬isBugCondition(input) ≡ input.llm_type IN ["ollama", "openai"]
```

**Preservation Properties:**

For all inputs where `input.llm_type IN ["ollama", "openai"]`:

1. **Service Selection Preserved:**
   ```
   F(input).service_used == "LangChainChatService" 
   ⟹ F'(input).service_used == "LangChainChatService"
   ```

2. **Tool Availability Preserved:**
   ```
   has_all_tools(F(input), ["save_athlete_goal", "get_my_goals", 
                            "get_my_recent_activities", "get_my_weekly_metrics"])
   ⟹ has_all_tools(F'(input), ["save_athlete_goal", "get_my_goals",
                                "get_my_recent_activities", "get_my_weekly_metrics"])
   ```

3. **Response Format Preserved:**
   ```
   F(input).response_format == F'(input).response_format
   ```

4. **ChatOpenAI Compatibility Preserved:**
   ```
   F(input).supports_openai_compatible_endpoints == true
   ⟹ F'(input).supports_openai_compatible_endpoints == true
   ```

## Implementation Strategy

### Root Cause

The conditional logic in `app/api/chat.py` (lines 23-28) routes LM Studio to a separate service:

```python
if settings.LLM_TYPE == "lm-studio":
    from app.services.lmstudio_chat_service import LMStudioChatService as ChatService
else:
    from app.services.langchain_chat_service import LangChainChatService as ChatService
```

This creates a bifurcation where LM Studio users get a different service implementation without data retrieval tools.

### Solution

Remove the conditional logic and always use LangChainChatService for all providers. LangChain's ChatOpenAI already supports LM Studio's OpenAI-compatible endpoint, making the separate service unnecessary.

**Changes Required:**

1. **app/api/chat.py:**
   - Remove conditional import logic (lines 23-28)
   - Always import LangChainChatService
   - Simplify to single service path

2. **app/services/lmstudio_chat_service.py:**
   - Can be deprecated or removed (not required for this fix)
   - No longer referenced after chat.py changes

### Validation Strategy

**Fix Checking (Property 1: Fault Condition → Expected Behavior):**
- Test that LM Studio users receive LangChainChatService
- Verify all 4 data retrieval tools are available
- Confirm behavior matches Ollama/OpenAI

**Preservation Checking (Property 2: Preservation):**
- Test that Ollama users still receive LangChainChatService with all tools
- Test that OpenAI users still receive LangChainChatService with all tools
- Verify response format and structure unchanged
- Confirm ChatOpenAI still supports OpenAI-compatible endpoints

## Requirements Traceability

| Requirement | Design Section | Validation |
|-------------|----------------|------------|
| 1.1 | Fault Condition | Property 1 test |
| 1.2 | Fault Condition | Property 1 test |
| 1.3 | Root Cause | Property 1 test |
| 2.1 | Expected Behavior | Property 1 test |
| 2.2 | Expected Behavior | Property 1 test |
| 2.3 | Implementation Strategy | Property 1 test |
| 3.1 | Preservation Requirements | Property 2 test |
| 3.2 | Preservation Requirements | Property 2 test |
| 3.3 | Preservation Requirements | Property 2 test |
| 3.4 | Preservation Requirements | Property 2 test |
| 3.5 | Preservation Requirements | Property 2 test |

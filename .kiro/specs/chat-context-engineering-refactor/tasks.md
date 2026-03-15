# Tasks: Chat Context Engineering Refactor

## Phase 0: Architecture Baseline

- [x] 0.1 Create Architecture Documentation
  - [x] 0.1.1 Write 2-4 page architecture document
  - [x] 0.1.2 Document component responsibility map (ChatMessageHandler, ChatSessionService, ChatAgent, ChatContextBuilder, ToolOrchestrator, LLMAdapter)
  - [x] 0.1.3 Create current vs target sequence diagrams
  - [x] 0.1.4 Define runtime context model with 8 layers
  - [x] 0.1.5 Document migration strategy with backward compatibility plan
  - [x] 0.1.6 Include feature flag approach

- [x] 0.2 Establish Source of Truth Agreements
  - [x] 0.2.1 Document session lifecycle ownership (ChatSessionService)
  - [x] 0.2.2 Document runtime context ownership (ChatContextBuilder)
  - [x] 0.2.3 Document tool execution ownership (ToolOrchestrator)
  - [x] 0.2.4 Document model invocation ownership (LLMAdapter)
  - [x] 0.2.5 Get team approval on responsibility boundaries

- [x] 0.3 Create Phase 0 Exit Criteria Checklist
  - [x] 0.3.1 Verify all responsibilities documented
  - [x] 0.3.2 Verify source of truth agreements signed off
  - [x] 0.3.3 Verify migration strategy approved
  - [x] 0.3.4 Verify no overlapping responsibilities identified
## Phase 1: Extract ChatSessionService

- [x] 1.1 Create ChatSessionService
  - [x] 1.1.1 Create `chat_session_service.py`
  - [x] 1.1.2 Implement `__init__(db, rag_engine)`
  - [x] 1.1.3 Implement `create_session(athlete_id, title)` → session_id
  - [x] 1.1.4 Implement `load_session(session_id)` → List[ChatMessage]
  - [x] 1.1.5 Implement `get_active_buffer(session_id)` → List[ChatMessage]
  - [x] 1.1.6 Implement `append_messages(session_id, user_msg, assistant_msg)`
  - [x] 1.1.7 Implement `persist_session(session_id, eval_score)`
  - [x] 1.1.8 Implement `clear_buffer(session_id)`
  - [x] 1.1.9 Implement `delete_session(session_id)`
  - [x] 1.1.10 Add `active_buffers: Dict[int, List[ChatMessage]]` state management

- [x] 1.2 Refactor ChatMessageHandler to Use ChatSessionService
  - [x] 1.2.1 Add ChatSessionService dependency to `ChatMessageHandler.__init__`
  - [x] 1.2.2 Replace direct session creation with `session_service.create_session()`
  - [x] 1.2.3 Replace direct message loading with `session_service.load_session()`
  - [x] 1.2.4 Replace `active_session_messages` with `session_service.get_active_buffer()`
  - [x] 1.2.5 Replace `_update_active_buffer` with `session_service.append_messages()`
  - [x] 1.2.6 Replace `persist_session` with `session_service.persist_session()`
  - [x] 1.2.7 Remove `load_session_messages()` method
  - [x] 1.2.8 Remove `clear_active_buffer()` method
  - [x] 1.2.9 Remove `persist_session()` method

- [x] 1.3 Update API Endpoints to Use ChatSessionService
  - [x] 1.3.1 Update `chat.py` to inject ChatSessionService
  - [x] 1.3.2 Update create_session endpoint to use service
  - [x] 1.3.3 Update delete_session endpoint to use service
  - [x] 1.3.4 Update persist_session endpoint to use service
  - [x] 1.3.5 Verify streaming endpoints work with new service

- [x] 1.4 Write Tests for ChatSessionService
  - [x] 1.4.1 Test `test_create_session_success`
  - [x] 1.4.2 Test `test_load_session_with_messages`
  - [x] 1.4.3 Test `test_load_session_not_found`
  - [x] 1.4.4 Test `test_append_messages_to_buffer`
  - [x] 1.4.5 Test `test_get_active_buffer_empty`
  - [x] 1.4.6 Test `test_get_active_buffer_with_messages`
  - [x] 1.4.7 Test `test_persist_session_to_db_and_vector_store`
  - [x] 1.4.8 Test `test_clear_buffer`
  - [x] 1.4.9 Test `test_delete_session_removes_all_data`
  - [x] 1.4.10 Test `test_multiple_sessions_isolated_buffers`

- [x] 1.5 Integration Testing for Phase 1
  - [x] 1.5.1 Test session creation through API
  - [x] 1.5.2 Test session switching doesn't leak state
  - [x] 1.5.3 Test streaming persistence works
  - [x] 1.5.4 Test concurrent session access
  - [x] 1.5.5 Verify no regression in UI session operations

- [x] 1.6 Phase 1 Exit Criteria Validation
  - [x] 1.6.1 Verify ChatMessageHandler doesn't contain session lifecycle logic
  - [x] 1.6.2 Verify UI can list/load/create/stream sessions
  - [x] 1.6.3 Verify all session tests pass
  - [x] 1.6.4 Verify no regression in session switching
  - [x] 1.6.5 Verify no regression in streaming persistence
## Phase 2: Move Context Composition to CE Path

- [x] 2.1 Create Versioned Prompt Templates
  - [x] 2.1.1 Create `coach_chat_v1.0.0.j2`
  - [x] 2.1.2 Define AI coach persona
  - [x] 2.1.3 Define behavioral constraints
  - [x] 2.1.4 Define communication style
  - [x] 2.1.5 Define tool usage guidelines
  - [x] 2.1.6 Create `chat_response_v1.0.0.j2`
  - [x] 2.1.7 Define response objective
  - [x] 2.1.8 Define input description
  - [x] 2.1.9 Define analytical focus
  - [x] 2.1.10 Define output guidelines
  - [x] 2.1.11 Add runtime parameter placeholders

- [x] 2.2 Implement Dynamic History Selection
  - [x] 2.2.1 Add `select_relevant_history()` method to ChatContextBuilder
  - [x] 2.2.2 Implement last_n_turns policy (default: 5)
  - [x] 2.2.3 Implement relevance-based selection using embeddings
  - [x] 2.2.4 Implement token-aware trimming (oldest first)
  - [x] 2.2.5 Add configuration for selection policy
  - [x] 2.2.6 Test history selection with various conversation lengths
  - [x] 2.2.7 Test token budget enforcement during history selection

- [x] 2.3 Implement Athlete Behavior Summary
  - [x] 2.3.1 Create `athlete_behavior_summary.py`
  - [x] 2.3.2 Implement `generate_summary(athlete_id, db)` → str
  - [x] 2.3.3 Query recent activity patterns (last 30 days)
  - [x] 2.3.4 Extract training preferences from history
  - [x] 2.3.5 Identify recent trends (volume, intensity)
  - [x] 2.3.6 Extract past feedback from evaluations
  - [x] 2.3.7 Condense to 150-200 tokens
  - [x] 2.3.8 Add caching mechanism (update weekly)
  - [x] 2.3.9 Test summary generation with various athlete profiles

- [x] 2.4 Activate ChatContextBuilder in Runtime
  - [x] 2.4.1 Update ChatMessageHandler to use ChatContextBuilder
  - [x] 2.4.2 Remove `_retrieve_context()` method
  - [x] 2.4.3 Remove `_build_conversation()` method
  - [x] 2.4.4 Remove `_get_system_prompt()` method
  - [x] 2.4.5 Add ChatContextBuilder initialization
  - [x] 2.4.6 Wire `ChatContextBuilder.gather_data()` into handle_message flow
  - [x] 2.4.7 Add SystemInstructionsLoader for prompt loading
  - [x] 2.4.8 Add TaskInstructionsLoader for task prompts
  - [x] 2.4.9 Add DomainKnowledgeLoader for domain data

- [x] 2.5 Implement Intent-Aware Retrieval in ChatContextBuilder
  - [x] 2.5.1 Update `gather_data()` to use IntentRouter
  - [x] 2.5.2 Implement intent classification before retrieval
  - [x] 2.5.3 Apply intent-specific retrieval policies (recent_performance: 14 days)
  - [x] 2.5.4 Apply intent-specific retrieval policies (trend_analysis: 90 days)
  - [x] 2.5.5 Apply intent-specific retrieval policies (goal_progress: goals + related activities)
  - [x] 2.5.6 Apply intent-specific retrieval policies (recovery_status: 7 days with effort)
  - [x] 2.5.7 Apply intent-specific retrieval policies (training_plan: plan-specific data)
  - [x] 2.5.8 Apply intent-specific retrieval policies (comparison: comparative data)
  - [x] 2.5.9 Apply intent-specific retrieval policies (general: broad retrieval)
  - [x] 2.5.10 Generate evidence cards for all retrieved data
  - [x] 2.5.11 Limit retrieved records to fit token budget

- [x] 2.6 Implement Token Budget Enforcement
  - [x] 2.6.1 Add token counting to ChatContextBuilder
  - [x] 2.6.2 Implement ContextBudgetExceeded exception
  - [x] 2.6.3 Add layer-by-layer token tracking
  - [x] 2.6.4 Implement automatic trimming when budget exceeded (trim oldest history first)
  - [x] 2.6.5 Implement automatic trimming when budget exceeded (trim lowest-relevance evidence second)
  - [x] 2.6.6 Never trim system/task instructions or athlete summary
  - [x] 2.6.7 Test budget enforcement with various context sizes

- [x] 2.7 Write Tests for Phase 2
  - [x] 2.7.1 Test `test_prompt_template_loading`
  - [x] 2.7.2 Test `test_dynamic_history_selection_last_n`
  - [x] 2.7.3 Test `test_dynamic_history_selection_relevance`
  - [x] 2.7.4 Test `test_athlete_behavior_summary_generation`
  - [x] 2.7.5 Test `test_intent_classification_and_retrieval`
  - [x] 2.7.6 Test `test_token_budget_enforcement`
  - [x] 2.7.7 Test `test_context_builder_full_pipeline`
  - [x] 2.7.8 Test `test_evidence_card_generation`

- [x] 2.8 Integration Testing for Phase 2
  - [x] 2.8.1 Test chat responses maintain relevance
  - [x] 2.8.2 Test reduced prompt pollution (no full session dump)
  - [x] 2.8.3 Test conversation continuity preserved
  - [x] 2.8.4 Test athlete personalization visible in responses
  - [x] 2.8.5 Test intent-aware retrieval returns appropriate data

- [x] 2.9 Phase 2 Exit Criteria Validation
  - [x] 2.9.1 Verify chat doesn't send full session history by default
  - [x] 2.9.2 Verify context built by ChatContextBuilder not handler
  - [x] 2.9.3 Verify athlete behavior summary included as separate layer
  - [x] 2.9.4 Verify irrelevant old turns not in prompt
  - [x] 2.9.5 Verify UI doesn't require changes
  - [x] 2.9.6 Verify token budget enforced (2400 tokens)

## Phase 2: Bug Fixes (Post-Integration Testing)

- [x] 2.10 Fix Domain Knowledge Serialization Issue
  - [x] 2.10.1 Analyze TrainingZone and DomainKnowledge serialization requirements
  - [x] 2.10.2 Add `to_dict()` method to TrainingZone dataclass
  - [x] 2.10.3 Add `to_dict()` method to DomainKnowledge dataclass
  - [x] 2.10.4 Update DomainKnowledgeLoader to support dict conversion
  - [x] 2.10.5 Update ChatContextBuilder to handle both object and dict formats
  - [x] 2.10.6 Update `_count_dict_tokens()` to handle nested custom objects gracefully
  - [x] 2.10.7 Test domain knowledge serialization with all data types
  - [x] 2.10.8 Verify integration tests pass after fix

- [x] 2.11 Fix Athlete Behavior Summary Database Coupling
  - [x] 2.11.1 Add caching mechanism to AthleteBehaviorSummary
  - [x] 2.11.2 Implement cache invalidation strategy (weekly refresh)
  - [x] 2.11.3 Add mock-friendly interface for testing
  - [x] 2.11.4 Update integration tests to use cached summaries
  - [x] 2.11.5 Test behavior summary generation with cache
  - [x] 2.11.6 Verify integration tests pass after fix

- [x] 2.12 Verify All Phase 2 Integration Tests Pass
  - [x] 2.12.1 Run test_chat_responses_maintain_relevance
  - [x] 2.12.2 Run test_no_full_session_dump_in_context
  - [x] 2.12.3 Run test_conversation_continuity_preserved
  - [x] 2.12.4 Run test_athlete_personalization_in_context
  - [x] 2.12.5 Run test_intent_aware_retrieval_returns_appropriate_data
  - [x] 2.12.6 Run test_token_budget_enforced_in_integration
  - [x] 2.12.7 Run test_end_to_end_ce_flow
  - [x] 2.12.8 Verify all 8/8 integration tests pass

## Phase 3: Introduce ChatAgent

- [x] 3.1 Create ChatAgent
  - [x] 3.1.1 Create `chat_agent.py`
  - [x] 3.1.2 Implement `__init__(context_builder, tool_orchestrator, llm_adapter)`
  - [x] 3.1.3 Implement `execute(user_message, session_id, user_id, conversation_history)` → Dict
  - [x] 3.1.4 Request context from ChatContextBuilder
  - [x] 3.1.5 Invoke LLMAdapter for initial response
  - [x] 3.1.6 Check for tool calls
  - [x] 3.1.7 Delegate to ToolOrchestrator if tools needed
  - [x] 3.1.8 Return final response with metadata
  - [x] 3.1.9 Add latency tracking
  - [x] 3.1.10 Add metadata collection (tokens, model used, iterations)

- [x] 3.2 Refactor ChatMessageHandler as Thin Coordinator
  - [x] 3.2.1 Add ChatAgent dependency to `ChatMessageHandler.__init__`
  - [x] 3.2.2 Replace handle_message logic with agent delegation
  - [x] 3.2.3 Remove `_orchestrate_tools()` method
  - [x] 3.2.4 Remove direct LLM invocation logic
  - [x] 3.2.5 Keep only: session coordination, agent invocation, response return
  - [x] 3.2.6 Verify handler is < 100 lines

- [x] 3.3 Define ChatAgent-SessionService Contract
  - [x] 3.3.1 Document input contract: conversation_history format
  - [x] 3.3.2 Document output contract: response + metadata format
  - [x] 3.3.3 Document error handling contract
  - [x] 3.3.4 Add type hints for all interfaces
  - [x] 3.3.5 Add docstrings with examples

- [x] 3.4 Write Tests for ChatAgent
  - [x] 3.4.1 Test `test_agent_execute_simple_query`
  - [x] 3.4.2 Test `test_agent_execute_with_tool_calls`
  - [x] 3.4.3 Test `test_agent_receives_session_context`
  - [x] 3.4.4 Test `test_agent_returns_metadata`
  - [x] 3.4.5 Test `test_agent_handles_llm_errors`
  - [x] 3.4.6 Test `test_agent_tracks_latency`

- [ ] 3.5 Integration Testing for Phase 3
  - [ ] 3.5.1 Test chat request → agent execution end-to-end
  - [ ] 3.5.2 Test agent receives session-linked context
  - [ ] 3.5.3 Test agent returns response + metadata for persistence
  - [ ] 3.5.4 Test clean orchestration boundaries
  - [ ] 3.5.5 Test easier testing with isolated agent

- [ ] 3.6 Phase 3 Exit Criteria Validation
  - [ ] 3.6.1 Verify handler doesn't have reasoning/runtime ownership
  - [ ] 3.6.2 Verify agent is primary execution entry point
  - [ ] 3.6.3 Verify flow is: handler → session service → agent → session service
  - [ ] 3.6.4 Verify clean orchestration boundaries
  - [ ] 3.6.5 Verify no duplicated logic between handler and agent
## Phase 4: Extract ToolOrchestrator

- [x] 4.1 Create ToolOrchestrator
  - [x] 4.1.1 Create `tool_orchestrator.py`
  - [x] 4.1.2 Implement `__init__(llm_adapter, tool_registry, max_iterations=5)`
  - [x] 4.1.3 Implement `orchestrate(conversation, tool_definitions, user_id)` → Dict
  - [x] 4.1.4 Implement iterative tool loop (max 5 iterations)
  - [x] 4.1.5 Execute tools sequentially
  - [x] 4.1.6 Pass tool results to subsequent calls
  - [x] 4.1.7 Append tool results to conversation
  - [x] 4.1.8 Handle tool failures gracefully
  - [x] 4.1.9 Log all tool invocations
  - [x] 4.1.10 Add termination condition detection
  - [x] 4.1.11 Add iteration limit enforcement

- [x] 4.2 Implement ReAct Pattern
  - [x] 4.2.1 Add reasoning step logging
  - [x] 4.2.2 Add action step logging
  - [x] 4.2.3 Add observation step logging
  - [x] 4.2.4 Implement Think → Act → Observe → Repeat loop
  - [x] 4.2.5 Add debug logging for transparency

- [x] 4.3 Implement Tool Execution Policy
  - [x] 4.3.1 Add configurable max_iterations (default: 5)
  - [x] 4.3.2 Add configurable failure behavior (fail_fast, retry, skip)
  - [x] 4.3.3 Implement tool invocation logging
  - [x] 4.3.4 Implement user_id scoping enforcement
  - [x] 4.3.5 Implement parameter validation before execution

- [x] 4.4 Handle Tool Failures
  - [x] 4.4.1 Implement try-catch around tool execution
  - [x] 4.4.2 Return structured error responses
  - [x] 4.4.3 Allow LLM to see errors and retry
  - [x] 4.4.4 Implement failure recovery strategies
  - [x] 4.4.5 Log all tool failures with details

- [x] 4.5 Update ChatAgent to Use ToolOrchestrator
  - [x] 4.5.1 Remove `_orchestrate_tools()` method from ChatMessageHandler (if still there)
  - [x] 4.5.2 Add ToolOrchestrator to ChatAgent dependencies
  - [x] 4.5.3 Delegate tool orchestration to ToolOrchestrator
  - [x] 4.5.4 Pass conversation and tool definitions to orchestrator
  - [x] 4.5.5 Receive and return orchestrator results

- [ ] 4.6 Write Tests for ToolOrchestrator
  - [ ] 4.6.1 Test `test_orchestrate_zero_tools`
  - [ ] 4.6.2 Test `test_orchestrate_one_tool`
  - [ ] 4.6.3 Test `test_orchestrate_sequential_chain`
  - [ ] 4.6.4 Test `test_orchestrate_dependent_results`
  - [ ] 4.6.5 Test `test_orchestrate_max_iterations_reached`
  - [ ] 4.6.6 Test `test_orchestrate_tool_failure_recovery`
  - [ ] 4.6.7 Test `test_orchestrate_iteration_limit_enforced`
  - [ ] 4.6.8 Test `test_orchestrate_user_id_scoping`

- [ ] 4.7 Integration Testing for Phase 4
  - [ ] 4.7.1 Test complex queries with multiple tools
  - [ ] 4.7.2 Test recovery from tool errors
  - [ ] 4.7.3 Test no infinite loops
  - [ ] 4.7.4 Test streaming compatibility with tool calls
  - [ ] 4.7.5 Test tool result passing between calls

- [ ] 4.8 Phase 4 Exit Criteria Validation
  - [ ] 4.8.1 Verify handler doesn't contain tool loop
  - [ ] 4.8.2 Verify agent uses ToolOrchestrator exclusively
  - [ ] 4.8.3 Verify multi-step tool-assisted execution works end-to-end
  - [ ] 4.8.4 Verify iteration limits enforced
  - [ ] 4.8.5 Verify tool failures handled gracefully
## Phase 5: Switch Chat to Shared LLMAdapter

- [x] 5.1 Update ChatAgent to Use LLMAdapter
  - [x] 5.1.1 Replace direct LLMClient calls with LLMAdapter
  - [x] 5.1.2 Pass Context object to `LLMAdapter.invoke()`
  - [x] 5.1.3 Define ChatResponseContract (Pydantic schema)
  - [x] 5.1.4 Handle LLMResponse with metadata
  - [x] 5.1.5 Remove direct model invocation code

- [x] 5.2 Implement Streaming Support in LLMAdapter
  - [x] 5.2.1 Add `stream()` method to LLMAdapter
  - [x] 5.2.2 Support streaming with tool calls
  - [x] 5.2.3 Emit telemetry after stream completes
  - [x] 5.2.4 Handle errors without breaking stream
  - [x] 5.2.5 Test streaming compatibility

- [x] 5.3 Add Telemetry Events for Chat
  - [x] 5.3.1 Emit telemetry for retrieval latency
  - [x] 5.3.2 Emit telemetry for model latency
  - [x] 5.3.3 Emit telemetry for total latency
  - [x] 5.3.4 Emit telemetry for tokens in/out
  - [x] 5.3.5 Emit telemetry for model used (primary/fallback)
  - [x] 5.3.6 Emit telemetry for fallback usage
  - [x] 5.3.7 Write telemetry to `invocations.jsonl`

- [x] 5.4 Implement Telemetry Log Rotation
  - [x] 5.4.1 Add daily log rotation for invocations.jsonl
  - [x] 5.4.2 Implement log file size limits
  - [x] 5.4.3 Add log archival strategy
  - [x] 5.4.4 Test rotation doesn't lose data

- [ ] 5.5 Write Tests for Phase 5
  - [ ] 5.5.1 Test `test_chat_uses_llm_adapter`
  - [ ] 5.5.2 Test `test_primary_model_invocation`
  - [ ] 5.5.3 Test `test_fallback_on_timeout`
  - [ ] 5.5.4 Test `test_fallback_on_connection_error`
  - [ ] 5.5.5 Test `test_telemetry_emission`
  - [ ] 5.5.6 Test `test_streaming_with_adapter`
  - [ ] 5.5.7 Test `test_token_counting`

- [ ] 5.6 Integration Testing for Phase 5
  - [ ] 5.6.1 Test chat and evaluation use same invocation abstraction
  - [ ] 5.6.2 Test telemetry available for chat runtime
  - [ ] 5.6.3 Test no direct raw model invocation in handler
  - [ ] 5.6.4 Test fallback works end-to-end
  - [ ] 5.6.5 Test latency profile acceptable

- [ ] 5.7 Phase 5 Exit Criteria Validation
  - [ ] 5.7.1 Verify chat and evaluation use same invocation abstraction
  - [ ] 5.7.2 Verify telemetry available for chat runtime
  - [ ] 5.7.3 Verify no direct raw model invocation remains in handler
  - [ ] 5.7.4 Verify fallback working
  - [ ] 5.7.5 Verify same or better latency than legacy
  - [ ] 5.7.6 Verify same or better answer quality than legacy
## Phase 6: Hardening and Controlled Rollout

- [x] 6.1 Implement Feature Flag
  - [x] 6.1.1 Add USE_CE_CHAT_RUNTIME to Settings
  - [x] 6.1.2 Add LEGACY_CHAT_ENABLED to Settings
  - [x] 6.1.3 Add CE_CHAT_TOKEN_BUDGET to Settings
  - [x] 6.1.4 Add CE_CHAT_MAX_TOOL_ITERATIONS to Settings
  - [x] 6.1.5 Implement runtime selection in ChatMessageHandler
  - [x] 6.1.6 Add logging for which runtime is active

- [x] 6.2 Implement Dual Runtime Support
  - [x] 6.2.1 Add `_handle_ce()` method to ChatMessageHandler
  - [x] 6.2.2 Add `_handle_legacy()` method to ChatMessageHandler
  - [x] 6.2.3 Implement runtime selection based on feature flag
  - [x] 6.2.4 Ensure both paths work independently
  - [x] 6.2.5 Add runtime identifier to responses

- [x] 6.3 Create Side-by-Side Comparison Mode
  - [x] 6.3.1 Add ENABLE_RUNTIME_COMPARISON setting
  - [x] 6.3.2 Implement comparison mode that invokes both runtimes
  - [x] 6.3.3 Log differences in: latency, response quality, tool calls, tokens
  - [x] 6.3.4 Create comparison report format
  - [x] 6.3.5 Add comparison results to telemetry

- [x] 6.4 Create Rollout Configuration
  - [x] 6.4.1 Create rollout checklist document
  - [x] 6.4.2 Define pilot user group
  - [x] 6.4.3 Define success metrics
  - [x] 6.4.4 Define rollback procedure
  - [x] 6.4.5 Create monitoring dashboard requirements

- [x] 6.5 Conduct Quality Validation
  - [x] 6.5.1 Run automated tests on CE runtime
  - [x] 6.5.2 Measure p95 latency (target: < 3s simple, < 5s multi-tool)
  - [x] 6.5.3 Conduct human evaluation of response quality
  - [x] 6.5.4 Check for UI regressions
  - [x] 6.5.5 Validate tool calling reliability
  - [x] 6.5.6 Compare with legacy baseline

- [x] 6.6 Pilot Rollout
  - [x] 6.6.1 Enable CE runtime for pilot users (feature flag)
  - [x] 6.6.2 Monitor telemetry for pilot group
  - [x] 6.6.3 Collect user feedback
  - [x] 6.6.4 Identify and fix bugs
  - [x] 6.6.5 Iterate on quality issues

- [x] 6.7 Create Legacy Deprecation Plan
  - [x] 6.7.1 Document timeline for legacy removal
  - [x] 6.7.2 Identify all legacy code to remove
  - [x] 6.7.3 Define stability requirements (2 weeks stable)
  - [x] 6.7.4 Document rollback procedure
  - [x] 6.7.5 Create removal checklist

- [ ] 6.8 Write Tests for Phase 6
  - [ ] 6.8.1 Test `test_feature_flag_ce_runtime`
  - [ ] 6.8.2 Test `test_feature_flag_legacy_runtime`
  - [ ] 6.8.3 Test `test_runtime_selection`
  - [ ] 6.8.4 Test `test_comparison_mode`
  - [ ] 6.8.5 Test `test_telemetry_includes_runtime_identifier`

- [ ] 6.9 Full Integration Testing
  - [ ] 6.9.1 Test CE runtime end-to-end
  - [ ] 6.9.2 Test legacy runtime still works
  - [ ] 6.9.3 Test feature flag toggle
  - [ ] 6.9.4 Test comparison mode
  - [ ] 6.9.5 Test rollback procedure

- [ ] 6.10 Phase 6 Exit Criteria Validation
  - [ ] 6.10.1 Verify CE chat runtime stable
  - [ ] 6.10.2 Verify no critical UI regressions
  - [ ] 6.10.3 Verify acceptable latency (p95 < 3s simple, < 5s multi-tool)
  - [ ] 6.10.4 Verify acceptable answer quality (human eval)
  - [ ] 6.10.5 Verify legacy path ready for removal
  - [ ] 6.10.6 Verify 2 weeks of stable operation
## Cross-Phase Tasks

- [ ] X.1 Documentation
  - [ ] X.1.1 Update README with CE architecture overview
  - [ ] X.1.2 Document component responsibilities
  - [ ] X.1.3 Document configuration options
  - [ ] X.1.4 Document feature flags
  - [ ] X.1.5 Create migration guide for developers
  - [ ] X.1.6 Document telemetry format and usage

- [ ] X.2 Performance Monitoring
  - [ ] X.2.1 Set up latency monitoring
  - [ ] X.2.2 Set up token usage monitoring
  - [ ] X.2.3 Set up error rate monitoring
  - [ ] X.2.4 Set up fallback rate monitoring
  - [ ] X.2.5 Create performance dashboard

- [x] X.3 Backward Compatibility Testing
  - [x] X.3.1 Test existing sessions load correctly
  - [x] X.3.2 Test vector store embeddings compatible
  - [x] X.3.3 Test API contracts unchanged
  - [x] X.3.4 Test streaming endpoints work
  - [x] X.3.5 Test error responses consistent

- [-] X.4 Code Cleanupss 
  - [x] X.4.1 Remove deprecated methods after each phase
  - [x] X.4.2 Update imports after refactoring
  - [x] X.4.3 Remove unused dependencies
  - [x] X.4.4 Update type hints
  - [x] X.4.5 Run linter and fix issues

- [ ] X.5 Final Validation
  - [ ] X.5.1 Run full test suite
  - [ ] X.5.2 Verify 85% code coverage for new components
  - [ ] X.5.3 Conduct security review
  - [ ] X.5.4 Conduct performance review
  - [ ] X.5.5 Get stakeholder sign-off

---

## Summary by Phase

- **Phase 0**: 3 tasks, ~15 subtasks - Architecture Baseline
- **Phase 1**: 6 tasks, ~35 subtasks - Extract ChatSessionService
- **Phase 2**: 9 tasks, ~50 subtasks - Move Context Composition to CE Path
- **Phase 3**: 6 tasks, ~30 subtasks - Introduce ChatAgent
- **Phase 4**: 8 tasks, ~40 subtasks - Extract ToolOrchestrator
- **Phase 5**: 7 tasks, ~35 subtasks - Switch Chat to Shared LLMAdapter
- **Phase 6**: 10 tasks, ~40 subtasks - Hardening and Controlled Rollout
- **Cross-Phase**: 5 tasks, ~25 subtasks - Documentation, Monitoring, Cleanup

**Total**: 54 tasks, ~270 subtasks

---

## Validation Checklist by Phase

### After Phase 0
- [ ] All responsibilities documented
- [ ] Source of truth agreements signed off
- [ ] Migration strategy approved
- [ ] No overlapping responsibilities identified

### After Phase 1
- [ ] Sessions: creation, loading, persistence work
- [ ] Stream binding works
- [ ] No state leakage between sessions

### After Phase 2
- [ ] Responses maintain relevance
- [ ] Reduced prompt pollution (no full session dump)
- [ ] Continuity still intact
- [ ] Athlete personalization visible

### After Phase 3
- [ ] Clean orchestration boundaries
- [ ] Easier testing with isolated components
- [ ] No handler-owned reasoning

### After Phase 4
- [ ] Complex queries with multiple tools work
- [ ] Recovery from tool errors works
- [ ] No infinite loops
- [ ] Iteration limits enforced

### After Phase 5
- [ ] Telemetry working
- [ ] Fallback working
- [ ] Stable latency
- [ ] Same or better answer quality

### After Phase 6
- [ ] CE runtime stable
- [ ] No critical regressions
- [ ] Acceptable performance
- [ ] Ready for legacy removal
Requirements Document: Chat Context Engineering Refactor
Introduction
This specification defines requirements for migrating the chat system from its current ad-hoc implementation to the Context Engineering (CE) architecture, achieving parity with the evaluation system's structured approach to prompt management, context building, and LLM invocation.

Glossary
ChatMessageHandler: Current monolithic component handling session, context, tools, and LLM invocation
ChatSessionService: Proposed component for session lifecycle management
ChatAgent: Proposed runtime execution owner for chat flow
ChatContextBuilder: CE component for structured context assembly (exists but unused)
ToolOrchestrator: Proposed component for multi-step tool execution
LLMAdapter: Shared abstraction for model invocation with fallback
ReAct Pattern: Reasoning + Acting agent framework for tool calling
Athlete Behavior Summary: Condensed profile of athlete's training patterns and preferences
Dynamic History Selection: Context-aware conversation history filtering
Phase 0: Architecture Baseline
Requirement 0.1: Architecture Documentation
User Story: As a platform developer, I want clear architecture documentation, so that all team members understand the target design before code changes begin.

Acceptance Criteria:

THE Architecture_Document SHALL be 2-4 pages describing target component responsibilities
THE Architecture_Document SHALL include a responsibility map for: ChatMessageHandler, ChatSessionService, ChatAgent, ChatContextBuilder, ToolOrchestrator, LLMAdapter
THE Architecture_Document SHALL provide current vs target sequence diagrams
THE Architecture_Document SHALL define the runtime context model with layers: system instructions, task instructions, athlete behavior summary, structured athlete state, retrieved evidence, dynamic history, current user message
THE Architecture_Document SHALL include a migration strategy note covering backward compatibility and optional feature flags
Requirement 0.2: Source of Truth Agreement
User Story: As a platform developer, I want agreed-upon component ownership, so that we avoid overlapping responsibilities during refactor.

Acceptance Criteria:

THE Team SHALL agree which component is source of truth for session lifecycle
THE Team SHALL agree which component is source of truth for runtime context
THE Team SHALL agree which component is source of truth for tool execution
THE Team SHALL agree which component is source of truth for model invocation
THE Architecture_Document SHALL document these agreements explicitly
Phase 1: Extract ChatSessionService
Requirement 1.1: Session Lifecycle Extraction
User Story: As a platform developer, I want session management separated from message handling, so that UI/session concerns don't pollute chat runtime logic.

Acceptance Criteria:

THE ChatSessionService SHALL handle create/load session operations
THE ChatSessionService SHALL handle get session messages operations
THE ChatSessionService SHALL handle append user/assistant messages operations
THE ChatSessionService SHALL maintain the active in-memory message buffer
THE ChatSessionService SHALL handle clear buffer operations
THE ChatSessionService SHALL coordinate session persistence to database and vector store
THE ChatMessageHandler SHALL delegate all session operations to ChatSessionService
THE ChatMessageHandler SHALL NOT maintain session lifecycle logic directly
Requirement 1.2: Session State Isolation
User Story: As a platform developer, I want session state isolated in one component, so that we avoid duplicated state between handler and service.

Acceptance Criteria:

THE ChatSessionService SHALL be the single owner of active_session_messages buffer
THE ChatMessageHandler SHALL NOT duplicate session state
THE UI SHALL continue to support: list sessions, load session, create session, stream into session
WHEN switching sessions, THE system SHALL NOT exhibit regression in session loading
WHEN streaming responses, THE system SHALL NOT exhibit regression in persistence behavior
Phase 2: Move Context Composition to CE Path
Requirement 2.1: ChatContextBuilder Activation
User Story: As a platform developer, I want chat to use CE-based context assembly, so that we achieve consistency with evaluation system and eliminate manual prompt building.

Acceptance Criteria:

THE ChatContextBuilder SHALL be activated in the chat runtime path
THE ChatMessageHandler SHALL remove _retrieve_context method
THE ChatMessageHandler SHALL remove _build_conversation method
THE ChatMessageHandler SHALL remove hardcoded system prompt ownership
THE ChatContextBuilder SHALL use versioned prompt templates from app/ai/prompts/
THE ChatContextBuilder SHALL enforce token budget limits (2400 tokens for chat)
Requirement 2.2: Dynamic History Selection
User Story: As an athlete, I want relevant conversation history included in context, so that the AI maintains continuity without overwhelming the prompt with irrelevant old messages.

Acceptance Criteria:

THE ChatContextBuilder SHALL implement dynamic conversation history selection
THE ChatContextBuilder SHALL NOT send full session history by default
WHEN selecting history, THE ChatContextBuilder SHALL prioritize recent turns and contextually relevant past turns
WHEN history exceeds token budget, THE ChatContextBuilder SHALL trim oldest irrelevant turns first
THE history selection policy SHALL be configurable (e.g., last_n_turns, relevance_threshold)
Requirement 2.3: Athlete Behavior Summary Injection
User Story: As an athlete, I want the AI to remember my training patterns and preferences, so that advice is personalized without repeating my profile every message.

Acceptance Criteria:

THE ChatContextBuilder SHALL include athlete behavior summary as a separate context layer
THE athlete behavior summary SHALL be computed from: recent activity patterns, stated goals, training preferences, past feedback
THE athlete behavior summary SHALL be injected for all coaching-related requests
THE athlete behavior summary SHALL be condensed to fit within 200 tokens
THE athlete behavior summary SHALL update periodically (e.g., weekly) not per-message
Requirement 2.4: Intent-Aware Retrieval
User Story: As an athlete, I want the AI to retrieve relevant data based on my question type, so that responses are grounded in appropriate historical context.

Acceptance Criteria:

THE ChatContextBuilder SHALL use IntentRouter to classify user queries
THE ChatContextBuilder SHALL apply intent-specific retrieval policies (recent_performance: 14 days, trend_analysis: 90 days, etc.)
THE ChatContextBuilder SHALL generate evidence cards for retrieved data
THE ChatContextBuilder SHALL limit retrieved records to respect token budget
THE ChatContextBuilder SHALL format retrieved data as structured evidence cards with source IDs
Phase 3: Introduce ChatAgent
Requirement 3.1: Runtime Execution Owner
User Story: As a platform developer, I want a clear runtime owner for chat execution, so that orchestration logic is centralized and testable.

Acceptance Criteria:

THE ChatAgent SHALL be the primary execution entry point for chat requests
THE ChatAgent SHALL request context from ChatContextBuilder
THE ChatAgent SHALL invoke tool orchestration when needed
THE ChatAgent SHALL invoke LLM through the invocation layer
THE ChatAgent SHALL return final response with metadata for persistence
THE ChatMessageHandler SHALL become a thin coordinator delegating to ChatAgent
Requirement 3.2: Clean Orchestration Boundaries
User Story: As a platform developer, I want clear contracts between components, so that we avoid duplicated orchestration logic.

Acceptance Criteria:

THE ChatAgent SHALL have a clear contract with ChatSessionService for session-linked context
THE ChatAgent SHALL have a clear contract with ToolOrchestrator for tool execution
THE ChatAgent SHALL have a clear contract with LLMAdapter for model invocation
THE ChatMessageHandler SHALL NOT contain reasoning or runtime ownership logic
THE execution flow SHALL be: handler → session service → agent → session service
Phase 4: Extract ToolOrchestrator
Requirement 4.1: Multi-Step Tool Execution
User Story: As an athlete, I want the AI to chain multiple tool calls together, so that complex queries are answered with complete information gathering.

Acceptance Criteria:

THE ToolOrchestrator SHALL handle zero, one, or many tool calls per request
THE ToolOrchestrator SHALL support sequential tool chains where later tools use earlier results
THE ToolOrchestrator SHALL support dependent tool results (tool B uses output from tool A)
THE ToolOrchestrator SHALL implement bounded iterative execution (max_iterations configurable)
THE ToolOrchestrator SHALL handle tool failure gracefully with retry or fallback strategies
Requirement 4.2: ReAct Pattern Implementation
User Story: As a platform developer, I want structured ReAct-style execution, so that tool calling is reliable and transparent.

Acceptance Criteria:

THE ToolOrchestrator SHALL implement the ReAct pattern: Think → Act → Observe → Repeat
THE ToolOrchestrator SHALL log reasoning steps for debugging
THE ToolOrchestrator SHALL enforce iteration limits to prevent infinite loops
THE ToolOrchestrator SHALL append tool results to runtime context correctly
THE ToolOrchestrator SHALL support streaming responses with tool calls
Requirement 4.3: Tool Execution Policy
User Story: As a platform operator, I want configurable tool execution policies, so that we can control behavior and costs.

Acceptance Criteria:

THE ToolOrchestrator SHALL support configurable max_iterations (default: 5)
THE ToolOrchestrator SHALL support configurable failure behavior (fail_fast, retry, skip)
THE ToolOrchestrator SHALL log all tool invocations with: tool_name, parameters, result, latency
THE ToolOrchestrator SHALL enforce user_id scoping for all tool calls
THE ToolOrchestrator SHALL validate tool parameters against schemas before execution
Phase 5: Switch Chat to Shared LLMAdapter
Requirement 5.1: Unified Model Invocation
User Story: As a platform developer, I want chat and evaluation to use the same LLM invocation layer, so that we have consistent behavior and telemetry.

Acceptance Criteria:

THE ChatAgent SHALL invoke LLM through shared LLMAdapter (not direct client calls)
THE LLMAdapter SHALL provide model abstraction (Mixtral primary, Llama fallback)
THE LLMAdapter SHALL implement automatic fallback on timeout or connection errors
THE LLMAdapter SHALL count tokens for input and output
THE LLMAdapter SHALL provide consistent invocation interface for chat and evaluation
Requirement 5.2: Telemetry and Observability
User Story: As a platform operator, I want comprehensive telemetry for chat operations, so that I can monitor performance and debug issues.

Acceptance Criteria:

THE LLMAdapter SHALL emit telemetry events for: retrieval latency, model latency, total latency, tokens in/out, model used, fallback used
THE telemetry SHALL be written to app/ai/telemetry/invocations.jsonl
THE telemetry SHALL include: timestamp, operation_type, athlete_id, model_used, context_token_count, response_token_count, latency_ms, success_status
THE telemetry SHALL log errors with error type and message
THE telemetry logs SHALL rotate daily to prevent unbounded growth
Requirement 5.3: Streaming Compatibility
User Story: As an athlete, I want streaming responses to continue working, so that I get real-time feedback during long responses.

Acceptance Criteria:

THE LLMAdapter SHALL support streaming responses for chat
THE streaming path SHALL maintain compatibility with tool calling
THE streaming path SHALL emit telemetry after stream completes
THE streaming path SHALL handle errors gracefully without breaking the stream
THE UI SHALL continue to receive Server-Sent Events without regression
Phase 6: Hardening and Controlled Rollout
Requirement 6.1: Feature Flag Support
User Story: As a platform operator, I want to toggle between legacy and CE chat runtimes, so that we can roll out safely and roll back if needed.

Acceptance Criteria:

THE system SHALL support a feature flag: use_ce_chat_runtime (default: false)
WHEN use_ce_chat_runtime=false, THE system SHALL use legacy ChatMessageHandler path
WHEN use_ce_chat_runtime=true, THE system SHALL use new CE chat runtime path
THE feature flag SHALL be configurable via environment variable or config file
THE system SHALL log which runtime path is active on startup
Requirement 6.2: Side-by-Side Comparison
User Story: As a platform developer, I want to compare legacy and CE runtimes, so that we can validate quality before full migration.

Acceptance Criteria:

THE system SHALL support side-by-side comparison mode for testing
THE comparison mode SHALL invoke both runtimes and log differences
THE comparison SHALL measure: latency difference, response quality, tool call differences, token usage differences
THE comparison results SHALL be logged for analysis
THE comparison mode SHALL NOT be enabled in production
Requirement 6.3: Quality Validation
User Story: As a platform operator, I want validation that CE runtime maintains quality, so that we don't degrade user experience.

Acceptance Criteria:

THE CE runtime SHALL maintain acceptable latency (p95 < 3 seconds)
THE CE runtime SHALL maintain acceptable answer quality (human evaluation or automated metrics)
THE CE runtime SHALL NOT exhibit critical UI regressions
THE CE runtime SHALL maintain tool calling reliability (success rate >= legacy)
THE CE runtime SHALL be validated with pilot users before full rollout
Requirement 6.4: Legacy Path Deprecation
User Story: As a platform developer, I want a clear deprecation plan for legacy code, so that we can clean up after successful migration.

Acceptance Criteria:

THE deprecation plan SHALL specify timeline for legacy path removal
THE deprecation plan SHALL identify all legacy code to be removed
THE deprecation plan SHALL require CE runtime stability for 2 weeks before legacy removal
THE deprecation plan SHALL include rollback procedure if issues arise
THE legacy path SHALL be removed only after exit criteria met
Cross-Phase Requirements
Requirement 7.1: Backward Compatibility
User Story: As a platform operator, I want existing chat sessions to continue working, so that users don't lose conversation history.

Acceptance Criteria:

THE refactor SHALL maintain compatibility with existing chat session database records
THE refactor SHALL maintain compatibility with existing vector store embeddings
THE refactor SHALL maintain API endpoint contracts (request/response formats unchanged)
THE refactor SHALL support loading legacy session history into new runtime
THE refactor SHALL NOT require database migrations that break existing data
Requirement 7.2: Performance Targets
User Story: As an athlete, I want chat responses to remain fast, so that conversations feel natural.

Acceptance Criteria:

THE CE chat runtime SHALL achieve p95 latency < 3 seconds for simple queries
THE CE chat runtime SHALL achieve p95 latency < 5 seconds for multi-tool queries
THE context building SHALL complete in < 500ms
THE RAG retrieval SHALL complete in < 200ms for 20 records
THE system SHALL log performance warnings when targets are exceeded
Requirement 7.3: Testing Coverage
User Story: As a platform developer, I want comprehensive tests for each phase, so that we catch regressions early.

Acceptance Criteria:

THE refactor SHALL include unit tests for each new component (ChatSessionService, ChatAgent, ToolOrchestrator)
THE refactor SHALL include integration tests for end-to-end chat flow
THE refactor SHALL include tests for: session creation, message loading, buffer updates, persistence, context building, tool execution, model invocation
THE refactor SHALL achieve minimum 85% code coverage for new components
THE refactor SHALL include regression tests for critical user flows
Exit Criteria by Phase
Phase 1 Exit Criteria:

ChatSessionService handles all session lifecycle operations
ChatMessageHandler delegates session operations to service
All session tests pass
No regression in session switching or streaming persistence
Phase 2 Exit Criteria:

ChatContextBuilder is active in runtime path
Manual prompt building removed from handler
Dynamic history selection implemented
Athlete behavior summary included
Intent-aware retrieval working
Token budget enforced
Responses maintain relevance and continuity
Phase 3 Exit Criteria:

ChatAgent is primary execution entry point
Handler is thin coordinator
Clean orchestration boundaries established
Agent receives session-linked context
Agent returns response with metadata
Phase 4 Exit Criteria:

ToolOrchestrator handles all tool execution
Multi-step tool chains working
Iteration limits enforced
Tool failure handling implemented
No infinite loops
Streaming compatible with tool calls
Phase 5 Exit Criteria:

Chat uses shared LLMAdapter
Telemetry emitted for all invocations
Fallback working
Streaming compatible
Same or better latency than legacy
Same or better answer quality than legacy
Phase 6 Exit Criteria:

Feature flag implemented
Side-by-side comparison completed
Quality validation passed
No critical regressions
CE runtime stable for 2 weeks
Legacy path ready for removal
Implementation Notes
Critical Dependencies:

LangChain (already installed)
Existing Context Engineering components (app/ai/)
Existing RAG system with intent routing
Existing LLMAdapter with fallback
Migration Strategy:

Incremental phase-by-phase approach
Feature flag for safe rollout
Backward compatibility maintained throughout
Optional side-by-side comparison for validation
Risk Mitigation:

Comprehensive testing at each phase
Feature flag for quick rollback
Performance monitoring and alerting
Quality validation before full rollout
Clear exit criteria for each phase
What Must Stay Together:

Phase 2: ChatContextBuilder activation + dynamic history + athlete behavior + prompt ownership removal + token budget
Phase 4: Multi-step execution + sequential chaining + bounded iteration + tool failure handling
This requirements document provides a comprehensive foundation for the Chat Context Engineering Refactor, ensuring all stakeholders understand the scope, goals, and success criteria for each phase of the migration.
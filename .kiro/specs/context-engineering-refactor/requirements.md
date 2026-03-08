# Requirements Document: Context Engineering Refactor

## Introduction

This specification defines the requirements for implementing a comprehensive Context Engineering (CE) architecture for the Fitness Coaching Platform's AI subsystem. Context Engineering is a formal architecture for managing AI task data, behavioral rules, output contracts, and evidence traceability.

The refactor transforms the current ad-hoc AI implementation (string concatenation, embedded logic, flat prompts) into a structured, versioned, and testable system with clear separation of concerns across prompt layers, context building, LLM invocation, and output validation.

## Glossary

- **Context_Engineering_System**: The complete AI subsystem architecture managing prompts, context, invocations, and validation
- **System_Instructions_Layer**: Versioned persona definitions and behavioral constraints for the AI coach
- **Task_Instructions_Layer**: Per-invocation analytical objectives and output format specifications
- **Domain_Knowledge_Layer**: Sport science reference values and training zone definitions stored in YAML
- **RAG_System**: Retrieval-Augmented Generation system for fetching relevant athlete data
- **Intent_Router**: Component that classifies user queries into named intents for targeted retrieval
- **Evidence_Card**: Structured data object linking AI claims to source database records
- **Output_Contract**: Pydantic schema defining expected AI response structure with validation rules
- **Context_Validator**: Component enforcing token budgets and context completeness checks
- **LLM_Adapter**: Abstraction layer supporting multiple model backends (Mixtral, Llama)
- **Derived_Metrics_Engine**: Component computing calculated fields from raw activity data
- **Week_ID**: ISO week identifier used for temporal data grouping (format: YYYY-WW)
- **Confidence_Score**: Hybrid metric (70% system + 30% LLM) indicating AI response reliability
- **Invocation_Log**: Telemetry record capturing context size, model used, latency, and token counts

## Requirements

### Phase 1: Foundation Layer (Sprint 1)

#### Requirement 1.1: System Instructions Management

**User Story:** As a platform developer, I want versioned system instructions, so that AI behavior changes are traceable and rollback-capable

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL store system instructions in `app/ai/prompts/system/` as versioned Jinja2 templates
2. WHEN a system instruction template is loaded, THE Context_Engineering_System SHALL validate it contains required sections: persona, behavioral_constraints, output_format
3. THE Context_Engineering_System SHALL support multiple instruction versions with semantic versioning (v1.0.0, v1.1.0)
4. WHEN rendering system instructions, THE Context_Engineering_System SHALL inject configuration variables from `app/ai/config/coach_persona.yaml`
5. THE Context_Engineering_System SHALL log which system instruction version was used for each LLM invocation

#### Requirement 1.2: Task Instructions Management

**User Story:** As a platform developer, I want task-specific instruction templates, so that different AI operations have appropriate analytical objectives

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL store task instructions in `app/ai/prompts/tasks/` organized by operation type (weekly_eval, chat_response, goal_analysis)
2. WHEN a task instruction is requested, THE Context_Engineering_System SHALL load the template matching the operation type
3. THE Context_Engineering_System SHALL render task instructions with runtime parameters (athlete_id, week_id, query_text)
4. THE Context_Engineering_System SHALL validate task instructions contain required fields: objective, input_description, output_schema_reference
5. FOR ALL task instruction templates, THE Context_Engineering_System SHALL enforce a maximum rendered size of 800 tokens

#### Requirement 1.3: Domain Knowledge Layer

**User Story:** As a sports scientist, I want training zone definitions stored as data, so that reference values can be updated without code changes

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL load domain knowledge from `app/ai/config/domain_knowledge.yaml`
2. THE Domain_Knowledge_Layer SHALL include training zones (Z1-Z5) with heart rate percentages and RPE ranges
3. THE Domain_Knowledge_Layer SHALL include effort level definitions (easy, moderate, hard, max)
4. THE Domain_Knowledge_Layer SHALL include recovery guidelines with rest day recommendations
5. WHEN domain knowledge is requested, THE Context_Engineering_System SHALL return it as structured data (dict/dataclass)
6. THE Context_Engineering_System SHALL validate domain knowledge schema on application startup

### Phase 2: Context Building & RAG (Sprint 2)

#### Requirement 2.1: Intent-Aware RAG System

**User Story:** As an athlete, I want the AI to retrieve relevant data for my questions, so that responses are grounded in my actual training history

##### Acceptance Criteria

1. THE RAG_System SHALL classify incoming queries into one of seven intents: recent_performance, trend_analysis, goal_progress, recovery_status, training_plan, comparison, general
2. WHEN intent is recent_performance, THE RAG_System SHALL retrieve activities from the last 14 days
3. WHEN intent is trend_analysis, THE RAG_System SHALL retrieve activities from the last 90 days
4. WHEN intent is goal_progress, THE RAG_System SHALL retrieve the athlete's active goals and related activities
5. WHEN intent is recovery_status, THE RAG_System SHALL retrieve activities from the last 7 days with effort scores
6. THE RAG_System SHALL limit retrieved activities to 20 records per query to respect token budgets
7. THE RAG_System SHALL generate evidence cards for each retrieved activity linking claim to source record

#### Requirement 2.2: Context Builder Architecture

**User Story:** As a platform developer, I want typed context builders, so that LLM inputs are validated and consistent

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL provide a `ContextBuilder` base class in `app/ai/context/builder.py`
2. THE ContextBuilder SHALL implement methods: add_system_instructions(), add_task_instructions(), add_domain_knowledge(), add_retrieved_data(), add_conversation_history()
3. WHEN building context, THE ContextBuilder SHALL enforce layer ordering: system → task → domain → retrieved → conversation
4. THE ContextBuilder SHALL validate total context size does not exceed operation-specific token budgets (3200 for eval, 2400 for chat)
5. WHEN token budget is exceeded, THE ContextBuilder SHALL raise ContextBudgetExceeded exception with details
6. THE ContextBuilder SHALL return a structured Context object with typed fields for each layer

#### Requirement 2.3: Derived Metrics Engine

**User Story:** As a platform developer, I want calculated metrics computed before LLM invocation, so that the AI receives complete analytical data

##### Acceptance Criteria

1. THE Derived_Metrics_Engine SHALL compute weekly aggregates: total_distance, total_duration, total_elevation, activity_count, avg_heart_rate
2. THE Derived_Metrics_Engine SHALL compute effort distribution: percentage of activities in each effort level (easy/moderate/hard/max)
3. THE Derived_Metrics_Engine SHALL compute training load: sum of (duration × effort_multiplier) for the week
4. THE Derived_Metrics_Engine SHALL compute recovery metrics: rest_days_count, consecutive_training_days
5. WHEN computing metrics for a week, THE Derived_Metrics_Engine SHALL filter activities using StravaActivity.week_id field (not computed from start_date)
6. THE Derived_Metrics_Engine SHALL return metrics as a typed DerivedMetrics dataclass with all fields populated

### Phase 3: LLM Integration & Output Contracts (Sprint 3)

#### Requirement 3.1: LLM Adapter Layer

**User Story:** As a platform operator, I want model-agnostic LLM invocation, so that I can switch between Mixtral and Llama without code changes

##### Acceptance Criteria

1. THE LLM_Adapter SHALL support two model backends: Mixtral-8x7B-Instruct (primary) and Llama-3.1-8B-Instruct (fallback)
2. WHEN invoking the LLM, THE LLM_Adapter SHALL use Mixtral as the default model
3. IF Mixtral invocation fails with a timeout or connection error, THEN THE LLM_Adapter SHALL automatically retry with Llama
4. THE LLM_Adapter SHALL use LangChain's ChatOllama interface for all model invocations
5. THE LLM_Adapter SHALL configure models with temperature=0.7, top_p=0.9, and operation-specific max_tokens
6. THE LLM_Adapter SHALL log which model was used for each successful invocation
7. THE LLM_Adapter SHALL expose a unified invoke() method accepting Context and OutputContract parameters

#### Requirement 3.2: Output Contract Validation

**User Story:** As a platform developer, I want structured output validation, so that AI responses conform to expected schemas

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL define output contracts as Pydantic v2 models in `app/ai/contracts/`
2. THE Output_Contract SHALL include WeeklyEvalContract with fields: overall_assessment, strengths, areas_for_improvement, recommendations, confidence_score
3. THE Output_Contract SHALL include ChatResponseContract with fields: response_text, evidence_cards, confidence_score, follow_up_suggestions
4. WHEN the LLM returns a response, THE Context_Engineering_System SHALL parse it against the specified Output_Contract
5. IF parsing fails, THEN THE Context_Engineering_System SHALL raise OutputValidationError with details of schema violations
6. THE Context_Engineering_System SHALL use LangChain's with_structured_output() for schema enforcement during generation
7. THE Output_Contract SHALL validate confidence_score is between 0.0 and 1.0

#### Requirement 3.3: Confidence Scoring System

**User Story:** As an athlete, I want to know how reliable AI assessments are, so that I can make informed training decisions

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL compute hybrid confidence scores using 70% system metrics and 30% LLM self-assessment
2. THE Context_Engineering_System SHALL compute system confidence from: data_completeness (40%), data_recency (30%), retrieval_quality (30%)
3. WHEN computing data_completeness, THE Context_Engineering_System SHALL check for presence of heart rate, power, and effort data
4. WHEN computing data_recency, THE Context_Engineering_System SHALL score based on days since last activity (0-7 days = 1.0, 8-14 = 0.7, 15+ = 0.4)
5. WHEN computing retrieval_quality, THE Context_Engineering_System SHALL score based on number of evidence cards generated (5+ = 1.0, 3-4 = 0.7, 1-2 = 0.4)
6. THE Context_Engineering_System SHALL prompt the LLM to provide self-assessed confidence in its response
7. THE Context_Engineering_System SHALL combine system and LLM confidence using weighted average: (0.7 × system) + (0.3 × llm)

### Phase 4: Evidence & Telemetry (Sprint 4)

#### Requirement 4.1: Evidence Traceability

**User Story:** As an athlete, I want to see which activities support AI claims, so that I can verify assessments against my data

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL generate evidence cards for each claim in AI responses
2. THE Evidence_Card SHALL include fields: claim_text, source_type (activity/goal/metric), source_id, source_date, relevance_score
3. WHEN the RAG_System retrieves an activity, THE Context_Engineering_System SHALL create an evidence card linking it to the query
4. WHEN the LLM references specific data in its response, THE Context_Engineering_System SHALL associate relevant evidence cards
5. THE Context_Engineering_System SHALL store evidence cards in the evidence_data JSONB field of WeeklyEval records
6. THE Context_Engineering_System SHALL maintain backward compatibility with existing WeeklyEval records that lack evidence_data
7. FOR ALL evidence cards, THE Context_Engineering_System SHALL validate source_id references an existing database record

#### Requirement 4.2: Context Telemetry

**User Story:** As a platform operator, I want invocation telemetry, so that I can monitor AI performance and debug issues

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL log an invocation record for each LLM call
2. THE Invocation_Log SHALL include fields: timestamp, operation_type, athlete_id, model_used, context_token_count, response_token_count, latency_ms, success_status
3. WHEN an LLM invocation completes, THE Context_Engineering_System SHALL write the invocation log to `app/ai/telemetry/invocations.jsonl`
4. WHEN an LLM invocation fails, THE Context_Engineering_System SHALL log the error type and message
5. THE Context_Engineering_System SHALL compute context_token_count using tiktoken with cl100k_base encoding
6. THE Context_Engineering_System SHALL measure latency from context build start to response parse completion
7. THE Context_Engineering_System SHALL rotate invocation logs daily to prevent unbounded growth

### Phase 5: Tool Integration & Migration (Sprint 5)

#### Requirement 5.1: LangChain Tool Definitions

**User Story:** As a platform developer, I want the AI to access data through structured tools, so that data retrieval is auditable and controlled

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL define LangChain StructuredTools in `app/ai/tools/`
2. THE Context_Engineering_System SHALL provide a GetRecentActivities tool accepting athlete_id and days_back parameters
3. THE Context_Engineering_System SHALL provide a GetAthleteGoals tool accepting athlete_id parameter
4. THE Context_Engineering_System SHALL provide a GetWeeklyMetrics tool accepting athlete_id and week_id parameters
5. WHEN a tool is invoked, THE Context_Engineering_System SHALL validate parameters against Pydantic schemas
6. WHEN a tool is invoked, THE Context_Engineering_System SHALL log the tool name, parameters, and result count
7. THE Context_Engineering_System SHALL disable web search tools by default (require explicit intent-gating for future use)

#### Requirement 5.2: Week_ID Bug Fix

**User Story:** As a platform developer, I want activity queries to use the correct week_id field, so that weekly evaluations include all relevant activities

##### Acceptance Criteria

1. WHEN querying activities for a specific week, THE Context_Engineering_System SHALL filter using StravaActivity.week_id field
2. THE Context_Engineering_System SHALL NOT compute week_id from StravaActivity.start_date during queries
3. WHEN creating or updating StravaActivity records, THE Context_Engineering_System SHALL populate week_id using ISO week format (YYYY-WW)
4. THE Context_Engineering_System SHALL validate week_id format matches regex: `^\d{4}-W\d{2}$`
5. FOR ALL existing StravaActivity records with null week_id, THE Context_Engineering_System SHALL provide a migration script to backfill values
6. THE Context_Engineering_System SHALL create a database index on StravaActivity.week_id for query performance

#### Requirement 5.3: Service Layer Migration

**User Story:** As a platform developer, I want existing services migrated to CE architecture, so that all AI operations use the new system

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL refactor `app/services/evaluation_engine.py` to use ContextBuilder and LLM_Adapter
2. THE Context_Engineering_System SHALL refactor `app/services/langchain_eval_service.py` to use Output_Contract validation
3. THE Context_Engineering_System SHALL refactor `app/services/rag_service.py` to use Intent_Router and Evidence_Card generation
4. WHEN migrating services, THE Context_Engineering_System SHALL maintain existing API contracts (function signatures unchanged)
5. WHEN migrating services, THE Context_Engineering_System SHALL preserve existing WeeklyEval database schema compatibility
6. THE Context_Engineering_System SHALL remove deprecated prompt files from `app/prompts/` after migration validation
7. THE Context_Engineering_System SHALL update all service imports to reference `app/ai/` modules

#### Requirement 5.4: Testing & Validation

**User Story:** As a platform developer, I want comprehensive tests for CE components, so that the refactor is verified correct

##### Acceptance Criteria

1. THE Context_Engineering_System SHALL provide unit tests for ContextBuilder validating token budget enforcement
2. THE Context_Engineering_System SHALL provide unit tests for Derived_Metrics_Engine validating calculation correctness
3. THE Context_Engineering_System SHALL provide integration tests for LLM_Adapter validating model fallback behavior
4. THE Context_Engineering_System SHALL provide property tests for Output_Contract validation using round-trip serialization
5. THE Context_Engineering_System SHALL provide integration tests validating Week_ID bug fix with real database queries
6. THE Context_Engineering_System SHALL provide migration compatibility tests ensuring existing WeeklyEval records remain accessible
7. FOR ALL tests, THE Context_Engineering_System SHALL achieve minimum 85% code coverage for `app/ai/` modules

## Implementation Notes

### Critical Dependencies

- LangChain 1.2.10 (already installed)
- langchain_ollama (already installed)
- Pydantic 2.12.5 (already installed)
- Jinja2 (already installed)
- tiktoken (for token counting)
- FAISS (already installed, for RAG)

### Migration Strategy

The refactor follows a 5-sprint approach with each phase building on the previous:

1. Sprint 1: Foundation (prompts, config, domain knowledge)
2. Sprint 2: Context building and RAG
3. Sprint 3: LLM integration and output validation
4. Sprint 4: Evidence tracking and telemetry
5. Sprint 5: Tool integration and service migration

### Backward Compatibility

- Existing WeeklyEval records without evidence_data remain readable
- API endpoints maintain current request/response formats
- Database schema changes are additive only (new fields, indexes)
- Old prompt files remain until migration validation completes

### Performance Targets

- Weekly evaluation: < 5 seconds end-to-end
- Chat response: < 3 seconds end-to-end
- Context building: < 500ms
- Token budget: 3200 for eval, 2400 for chat
- RAG retrieval: < 200ms for 20 activities

### Security Considerations

- Web search tools disabled by default
- Tool invocations logged for audit trail
- Athlete data access controlled through existing auth layer
- No PII in telemetry logs (athlete_id only, no names/emails)

# Implementation Plan: Context Engineering Refactor

## Overview

This implementation plan transforms the Fitness Coaching Platform's AI subsystem from an ad-hoc implementation into a formal Context Engineering architecture. The refactor introduces structured prompt management, typed context building, intent-aware retrieval, output validation, evidence traceability, and comprehensive telemetry across 5 sprints.

## Implementation Approach

The implementation follows a 5-sprint structure with clear dependencies:
- Sprint 1: Foundation layer (prompts, config, domain knowledge)
- Sprint 2: Context building and RAG system
- Sprint 3: LLM integration and output contracts
- Sprint 4: Evidence tracking and telemetry
- Sprint 5: Tool integration and service migration

Token budgets: 3,200 tokens (evaluation), 2,400 tokens (chat)
Temperature: 0.1 for evaluation, 0.7 for chat
Confidence scoring: 70% system + 30% LLM
Test coverage target: 85% for app/ai/ modules

## Tasks

### Sprint 1: Foundation Layer

- [x] 1. Create app/ai/ module structure
  - Create app/ai/__init__.py with module exports
  - Create 9 subdirectories: contracts/, prompts/, config/, context/, retrieval/, derived/, adapter/, tools/, validators/, telemetry/
  - Create __init__.py files in each subdirectory
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Implement System Instructions Management
  - [x] 2.1 Create SystemInstructionsLoader class in app/ai/prompts/system_loader.py
    - Implement load(version: str) method to load and render Jinja2 templates
    - Implement list_versions() method to enumerate available versions
    - Validate templates contain required sections: persona, behavioral_constraints, output_format
    - _Requirements: 1.1.1, 1.1.2, 1.1.3_
  
  - [x] 2.2 Create coach_persona_v1.0.0.j2 template in app/ai/prompts/system/
    - Define AI coach persona with certifications and expertise
    - Specify behavioral constraints (data-driven, no medical advice, acknowledge gaps)
    - Define output format expectations
    - _Requirements: 1.1.1_
  
  - [x] 2.3 Create coach_persona.yaml config in app/ai/config/
    - Define coach_name, certifications, tone, max_recommendations
    - Implement configuration injection in SystemInstructionsLoader
    - _Requirements: 1.1.4_
  
  - [ ]* 2.4 Write unit tests for SystemInstructionsLoader
    - Test version loading and validation
    - Test configuration injection
    - Test error handling for missing templates
    - _Requirements: 5.4.1_

- [x] 3. Implement Task Instructions Management
  - [x] 3.1 Create TaskInstructionsLoader class in app/ai/prompts/task_loader.py
    - Implement load(operation: str, version: str, params: Dict) method
    - Implement validate_token_limit(rendered: str, max_tokens: int) method
    - Validate templates contain required fields: objective, input_description, output_schema_reference
    - _Requirements: 1.2.1, 1.2.2, 1.2.3, 1.2.4_
  
  - [x] 3.2 Create weekly_eval_v1.0.0.j2 template in app/ai/prompts/tasks/
    - Define analytical objectives for weekly evaluation
    - Specify input data description (activities, metrics, logs, goals)
    - Reference WeeklyEvalContract output schema
    - _Requirements: 1.2.1, 1.2.4_
  
  - [x] 3.3 Create chat_response_v1.0.0.j2 template in app/ai/prompts/tasks/
    - Define objectives for coach chat responses
    - Specify input data description (query, conversation history, retrieved data)
    - Reference ChatResponseContract output schema
    - _Requirements: 1.2.1, 1.2.4_
  
  - [ ]* 3.4 Write unit tests for TaskInstructionsLoader
    - Test template loading with runtime parameters
    - Test token limit validation (800 token max)
    - Test error handling for missing templates
    - _Requirements: 1.2.5, 5.4.1_

- [x] 4. Implement Domain Knowledge Layer
  - [x] 4.1 Create domain_knowledge.yaml in app/ai/config/
    - Define training zones (Z1-Z5) with HR percentages and RPE ranges
    - Define effort levels (easy, moderate, hard, max) with target percentages
    - Define recovery guidelines (rest days, consecutive training limits)
    - Define nutrition targets (protein, carbs, fat ranges)
    - _Requirements: 1.3.1, 1.3.2, 1.3.3, 1.3.4_
  
  - [x] 4.2 Create DomainKnowledgeLoader class in app/ai/config/domain_loader.py
    - Implement load() method returning DomainKnowledge dataclass
    - Implement validate_schema() method for startup validation
    - Define TrainingZone and DomainKnowledge dataclasses
    - _Requirements: 1.3.5, 1.3.6_
  
  - [ ]* 4.3 Write unit tests for DomainKnowledgeLoader
    - Test YAML loading and parsing
    - Test schema validation
    - Test error handling for malformed YAML
    - _Requirements: 1.3.6, 5.4.1_

- [x] 5. Checkpoint - Foundation Layer Complete
  - Ensure all tests pass, ask the user if questions arise.

### Sprint 2: Context Building & RAG

- [x] 6. Implement ContextBuilder Base Class
  - [x] 6.1 Create ContextBuilder base class in app/ai/context/builder.py
    - Define Context dataclass with typed layers (system, task, domain, retrieved, conversation)
    - Implement add_system_instructions(), add_task_instructions(), add_domain_knowledge() methods
    - Implement add_retrieved_data(), add_conversation_history() methods
    - Implement build() method with validation
    - _Requirements: 2.2.1, 2.2.2, 2.2.3_
  
  - [x] 6.2 Implement token counting with tiktoken
    - Add _count_tokens() method using cl100k_base encoding
    - Implement token budget validation in build() method
    - Define ContextBudgetExceeded exception with actual/budget details
    - _Requirements: 2.2.4, 2.2.5_
  
  - [x] 6.3 Implement Context.to_messages() method
    - Convert layered context to LangChain message format
    - Format task instructions, domain knowledge, and retrieved data
    - _Requirements: 2.2.6_
  
  - [ ]* 6.4 Write property test for ContextBuilder token budget enforcement
    - **Property 10: Token budget enforcement**
    - **Validates: Requirements 2.2.4, 2.2.5**
    - Test that contexts exceeding budget raise ContextBudgetExceeded
    - Test that contexts within budget build successfully
    - _Requirements: 5.4.1_

- [x] 7. Implement EvaluationContextBuilder
  - [x] 7.1 Create EvaluationContextBuilder class in app/ai/context/evaluation_context.py
    - Extend ContextBuilder with token_budget=3200
    - Implement gather_data(athlete_id, week_id, period_start, period_end) method
    - Query activities using StravaActivity.week_id field (fixes bug)
    - Query metrics, logs, and goals for the period
    - _Requirements: 2.2.1, 2.3.5_
  
  - [x] 7.2 Implement evidence card formatting methods
    - Implement _format_activity_card() for activities
    - Implement _format_metric_card() for weekly measurements
    - Implement _format_log_card() for daily logs
    - Implement _format_goal_card() for athlete goals
    - _Requirements: 2.1.7_
  
  - [ ]* 7.3 Write unit tests for EvaluationContextBuilder
    - Test data gathering with mocked database
    - Test evidence card formatting
    - Test week_id filtering (bug fix validation)
    - _Requirements: 5.4.5_

- [x] 8. Implement DerivedMetricsEngine
  - [x] 8.1 Create DerivedMetricsEngine class in app/ai/derived/metrics_engine.py
    - Define DerivedMetrics dataclass with all computed fields
    - Implement compute(activities, week_start, week_end) method
    - Compute volume metrics: total_distance, total_duration, total_elevation, activity_count
    - _Requirements: 2.3.1_
  
  - [x] 8.2 Implement effort distribution computation
    - Implement _compute_effort_distribution() method
    - Implement _classify_effort() using domain knowledge HR zones
    - Compute percentages for easy/moderate/hard/max effort levels
    - _Requirements: 2.3.2_
  
  - [x] 8.3 Implement training load and recovery metrics
    - Implement _compute_training_load() with effort multipliers
    - Implement _compute_recovery_metrics() for rest days and consecutive training days
    - Implement _compute_hr_metrics() for average HR and zone distribution
    - _Requirements: 2.3.3, 2.3.4_
  
  - [ ]* 8.4 Write property test for DerivedMetricsEngine calculation correctness
    - **Property 11: Derived metrics determinism**
    - **Validates: Requirements 2.3.1, 2.3.2, 2.3.3**
    - Test that identical inputs produce identical outputs
    - Test that metrics sum correctly (effort percentages = 100%)
    - _Requirements: 5.4.2_

- [x] 9. Implement Intent-Aware RAG System
  - [x] 9.1 Create IntentRouter class in app/ai/retrieval/intent_router.py
    - Define Intent enum with 7 intents: recent_performance, trend_analysis, goal_progress, recovery_status, training_plan, comparison, general
    - Implement classify(query: str) method using keyword matching
    - _Requirements: 2.1.1_
  
  - [x] 9.2 Create retrieval_policies.yaml in app/ai/config/
    - Define retrieval policy for each intent (days_back, max_records, data_types)
    - recent_performance: 14 days, 20 records
    - trend_analysis: 90 days, 20 records
    - goal_progress: active goals + related activities
    - recovery_status: 7 days with effort scores
    - _Requirements: 2.1.2, 2.1.3, 2.1.4, 2.1.5_
  
  - [x] 9.3 Create RAGRetriever class in app/ai/retrieval/rag_retriever.py
    - Implement retrieve(query: str, athlete_id: int, intent: Intent) method
    - Load retrieval policy for intent from YAML
    - Query database based on policy parameters
    - Limit results to 20 records per query
    - _Requirements: 2.1.6_
  
  - [x] 9.4 Implement evidence card generation in RAGRetriever
    - Generate evidence cards for each retrieved record
    - Include claim_text, source_type, source_id, source_date, relevance_score
    - _Requirements: 2.1.7_
  
  - [ ]* 9.5 Write unit tests for IntentRouter
    - Test intent classification for various query types
    - Test fallback to general intent for ambiguous queries
    - _Requirements: 5.4.1_
  
  - [ ]* 9.6 Write unit tests for RAGRetriever
    - Test retrieval with different intents
    - Test 20-record limit enforcement
    - Test evidence card generation
    - _Requirements: 5.4.1_

- [x] 10. Implement Week_ID Bug Fix
  - [x] 10.1 Create Alembic migration for week_id field
    - Add week_id column to strava_activities table (String, nullable)
    - Create index on week_id for query performance
    - _Requirements: 5.2.3, 5.2.6_
  
  - [x] 10.2 Create backfill script for existing activities
    - Query all StravaActivity records with null week_id
    - Compute week_id from start_date using ISO week format (YYYY-WW)
    - Update records in batches
    - _Requirements: 5.2.5_
  
  - [x] 10.3 Update StravaActivity model
    - Add week_id field to model definition
    - Add week_id format validation (regex: ^\d{4}-W\d{2}$)
    - Update create/update logic to populate week_id
    - _Requirements: 5.2.3, 5.2.4_
  
  - [ ]* 10.4 Write integration test for week_id filtering
    - **Property 15: Week_ID filtering correctness**
    - **Validates: Requirements 5.2.1, 5.2.2**
    - Test that queries use week_id field, not computed from start_date
    - Test that all activities for a week are retrieved
    - _Requirements: 5.4.5_

- [x] 11. Checkpoint - Context Building & RAG Complete
  - Ensure all tests pass, ask the user if questions arise.

### Sprint 3: LLM Integration & Output Contracts

- [x] 12. Define Output Contracts
  - [x] 12.1 Create WeeklyEvalContract in app/ai/contracts/evaluation_contract.py
    - Define Pydantic v2 model with fields: overall_assessment, strengths, areas_for_improvement, recommendations, confidence_score
    - Add field validators for confidence_score (0.0-1.0 range)
    - Add field validators for list lengths (strengths: 1-5, areas_for_improvement: 1-5, recommendations: max 5)
    - _Requirements: 3.2.2, 3.2.7_
  
  - [x] 12.2 Create ChatResponseContract in app/ai/contracts/chat_contract.py
    - Define Pydantic v2 model with fields: response_text, evidence_cards, confidence_score, follow_up_suggestions
    - Add field validators for confidence_score (0.0-1.0 range)
    - Add nested EvidenceCard model
    - _Requirements: 3.2.3, 3.2.7_
  
  - [x] 12.3 Create EvidenceCard model in app/ai/contracts/evidence_card.py
    - Define Pydantic v2 model with fields: claim_text, source_type, source_id, source_date, relevance_score
    - Add field validators for source_type enum (activity/goal/metric/log)
    - Add field validators for relevance_score (0.0-1.0 range)
    - _Requirements: 4.1.2_
  
  - [ ]* 12.4 Write property test for output contract validation
    - **Property 20: Output contract round-trip serialization**
    - **Validates: Requirements 3.2.4, 3.2.5**
    - Test that valid data serializes and deserializes correctly
    - Test that invalid data raises ValidationError
    - _Requirements: 5.4.4_

- [x] 13. Implement LLM Adapter Layer
  - [x] 13.1 Create LLMProviderAdapter interface in app/ai/adapter/llm_adapter.py
    - Define abstract base class with invoke(context: Context, contract: Type[BaseModel]) method
    - Define LLMConfig dataclass with model_name, temperature, max_tokens, top_p
    - Define LLMResponse dataclass with parsed_output, model_used, token_count, latency_ms
    - _Requirements: 3.1.7_
  
  - [x] 13.2 Create LangChainAdapter implementation in app/ai/adapter/langchain_adapter.py
    - Implement invoke() method using ChatOllama
    - Configure Mixtral-8x7B-Instruct as primary model
    - Configure Llama-3.1-8B-Instruct as fallback model
    - Use with_structured_output() for schema enforcement
    - _Requirements: 3.1.1, 3.1.2, 3.1.4, 3.2.6_
  
  - [x] 13.3 Implement automatic fallback logic
    - Catch timeout and connection errors from Mixtral
    - Automatically retry with Llama on failure
    - Log which model was used for each invocation
    - _Requirements: 3.1.3, 3.1.6_
  
  - [x] 13.4 Configure model parameters
    - Set temperature=0.7, top_p=0.9 for all invocations
    - Set max_tokens based on operation type (eval vs chat)
    - _Requirements: 3.1.5_
  
  - [ ]* 13.5 Write integration test for LLM adapter fallback
    - **Property 22: LLM fallback behavior**
    - **Validates: Requirements 3.1.2, 3.1.3**
    - Test that Mixtral is tried first
    - Test that Llama is used on Mixtral failure
    - Test that model_used is logged correctly
    - _Requirements: 5.4.3_

- [x] 14. Implement Output Validation
  - [x] 14.1 Create OutputValidator class in app/ai/validators/output_validator.py
    - Implement validate(response: str, contract: Type[BaseModel]) method
    - Parse LLM response against Pydantic schema
    - Raise OutputValidationError on schema violations with details
    - _Requirements: 3.2.4, 3.2.5_
  
  - [x] 14.2 Implement retry logic with guidance
    - Add retry_count parameter (max 3 attempts)
    - On validation failure, provide error details to LLM for correction
    - Re-invoke LLM with guidance message
    - _Requirements: 3.2.5_
  
  - [ ]* 14.3 Write unit tests for OutputValidator
    - Test successful validation
    - Test validation failure with detailed error messages
    - Test retry logic
    - _Requirements: 5.4.1_

- [x] 15. Implement Confidence Scoring System
  - [x] 15.1 Create ConfidenceScorer class in app/ai/derived/confidence_scorer.py
    - Implement compute_system_confidence(context: Context, metrics: DerivedMetrics) method
    - Compute data_completeness score (40% weight) based on HR, power, effort data presence
    - Compute data_recency score (30% weight) based on days since last activity
    - Compute retrieval_quality score (30% weight) based on evidence card count
    - _Requirements: 3.3.2, 3.3.3, 3.3.4, 3.3.5_
  
  - [x] 15.2 Implement hybrid confidence computation
    - Implement compute_hybrid_confidence(system_score: float, llm_score: float) method
    - Use weighted average: (0.7 × system) + (0.3 × llm)
    - _Requirements: 3.3.1, 3.3.7_
  
  - [x] 15.3 Update task instructions to request LLM self-assessment
    - Add confidence_score field to output schemas
    - Prompt LLM to assess its own confidence in the response
    - _Requirements: 3.3.6_
  
  - [ ]* 15.4 Write unit tests for ConfidenceScorer
    - Test system confidence computation with various data completeness levels
    - Test hybrid confidence calculation
    - Test edge cases (no data, perfect data)
    - _Requirements: 5.4.1_

- [x] 16. Create CompletenessScorer
  - [x] 16.1 Create CompletenessScorer class in app/ai/derived/completeness_scorer.py
    - Implement score(activities: List[StravaActivity]) method
    - Check for presence of HR data, power data, effort data
    - Return completeness score (0.0-1.0) based on data availability
    - _Requirements: 3.3.3_
  
  - [ ]* 16.2 Write unit tests for CompletenessScorer
    - Test scoring with complete data
    - Test scoring with partial data
    - Test scoring with no data
    - _Requirements: 5.4.1_

- [x] 17. Checkpoint - LLM Integration & Output Contracts Complete
  - Ensure all tests pass, ask the user if questions arise.

### Sprint 4: Evidence & Telemetry

- [x] 18. Implement Evidence Traceability
  - [x] 18.1 Update EvidenceCard model with validation
    - Add source_id validator to check database record existence
    - Add source_type enum validator (activity/goal/metric/log)
    - Add relevance_score range validator (0.0-1.0)
    - _Requirements: 4.1.2, 4.1.7_
  
  - [x] 18.2 Create EvidenceMapper class in app/ai/retrieval/evidence_mapper.py
    - Implement map_claims_to_evidence(response: BaseModel, retrieved_data: List[Dict]) method
    - Extract claims from LLM response text
    - Match claims to evidence cards based on content similarity
    - Associate relevant evidence cards with each claim
    - _Requirements: 4.1.4_
  
  - [x] 18.3 Update RAGRetriever to generate evidence cards
    - Generate evidence card for each retrieved activity
    - Include claim_text, source_type, source_id, source_date, relevance_score
    - _Requirements: 4.1.1, 4.1.3_
  
  - [x] 18.4 Update WeeklyEval model to store evidence_data
    - Verify evidence_data JSONB field exists in WeeklyEval model
    - Ensure backward compatibility with null evidence_data
    - _Requirements: 4.1.5, 4.1.6_
  
  - [ ]* 18.5 Write integration test for evidence traceability
    - **Property 27: Evidence source validation**
    - **Validates: Requirements 4.1.7**
    - Test that all evidence cards reference existing database records
    - Test that evidence cards are correctly associated with claims
    - _Requirements: 5.4.1_

- [x] 19. Implement Invocation Telemetry
  - [x] 19.1 Create InvocationLogger class in app/ai/telemetry/invocation_logger.py
    - Define InvocationLog dataclass with fields: timestamp, operation_type, athlete_id, model_used, context_token_count, response_token_count, latency_ms, success_status, error_message
    - Implement log(invocation: InvocationLog) method writing to JSONL
    - _Requirements: 4.2.1, 4.2.2_
  
  - [x] 19.2 Implement JSONL logging
    - Write invocation logs to app/ai/telemetry/invocations.jsonl
    - Append one JSON object per line
    - _Requirements: 4.2.3_
  
  - [x] 19.3 Implement log rotation
    - Add daily log rotation logic (30-day retention)
    - Archive old logs to invocations_YYYY-MM-DD.jsonl.gz
    - _Requirements: 4.2.7_
  
  - [x] 19.4 Integrate telemetry into LLM adapter
    - Measure latency from context build start to response parse completion
    - Count tokens using tiktoken (cl100k_base encoding)
    - Log success/failure status and error messages
    - _Requirements: 4.2.4, 4.2.5, 4.2.6_
  
  - [ ]* 19.5 Write unit tests for InvocationLogger
    - Test JSONL writing
    - Test log rotation
    - Test error logging
    - _Requirements: 5.4.1_

- [x] 20. Update WeeklyEval Persistence
  - [x] 20.1 Update EvaluationService to store evidence_data
    - Serialize evidence cards to JSON
    - Store in evidence_data JSONB field
    - _Requirements: 4.1.5_
  
  - [x] 20.2 Ensure backward compatibility
    - Handle null evidence_data in existing records
    - Provide default empty list when evidence_data is null
    - _Requirements: 4.1.6_
  
  - [ ]* 20.3 Write migration compatibility test
    - **Property 35: Backward compatibility**
    - **Validates: Requirements 4.1.6**
    - Test that existing WeeklyEval records without evidence_data remain accessible
    - Test that new records with evidence_data are stored correctly
    - _Requirements: 5.4.6_

- [x] 21. Checkpoint - Evidence & Telemetry Complete
  - Ensure all tests pass, ask the user if questions arise.

### Sprint 5: Tool Integration & Migration

- [x] 22. Implement LangChain Tools
  - [x] 22.1 Create GetRecentActivities tool in app/ai/tools/get_recent_activities.py
    - Define StructuredTool with athlete_id and days_back parameters
    - Implement Pydantic schema for parameter validation
    - Query StravaActivity records for the specified period
    - Return formatted activity list
    - _Requirements: 5.1.2_
  
  - [x] 22.2 Create GetAthleteGoals tool in app/ai/tools/get_athlete_goals.py
    - Define StructuredTool with athlete_id parameter
    - Implement Pydantic schema for parameter validation
    - Query active AthleteGoal records
    - Return formatted goal list
    - _Requirements: 5.1.3_
  
  - [x] 22.3 Create GetWeeklyMetrics tool in app/ai/tools/get_weekly_metrics.py
    - Define StructuredTool with athlete_id and week_id parameters
    - Implement Pydantic schema for parameter validation
    - Query WeeklyMeasurement records for the specified week
    - Return formatted metrics
    - _Requirements: 5.1.4_
  
  - [x] 22.4 Implement tool invocation logging
    - Log tool name, parameters, and result count for each invocation
    - _Requirements: 5.1.6_
  
  - [x] 22.5 Disable web search tools
    - Ensure web search tools are not included in tool list
    - Add configuration flag for future intent-gated web search
    - _Requirements: 5.1.7_
  
  - [ ]* 22.6 Write unit tests for LangChain tools
    - Test parameter validation
    - Test data retrieval
    - Test tool invocation logging
    - _Requirements: 5.4.1_

- [x] 23. Migrate EvaluationService
  - [x] 23.1 Refactor app/services/evaluation_engine.py to use ContextBuilder
    - Replace manual context assembly with EvaluationContextBuilder
    - Use DerivedMetricsEngine for metric computation
    - Maintain existing function signatures
    - _Requirements: 5.3.1, 5.3.4_
  
  - [x] 23.2 Integrate LLM adapter
    - Replace direct LLM calls with LLMProviderAdapter.invoke()
    - Use WeeklyEvalContract for output validation
    - _Requirements: 5.3.1_
  
  - [x] 23.3 Integrate evidence mapping
    - Use EvidenceMapper to link claims to source records
    - Store evidence_data in WeeklyEval records
    - _Requirements: 5.3.1_
  
  - [x] 23.4 Integrate telemetry logging
    - Use InvocationLogger to log all LLM invocations
    - _Requirements: 5.3.1_
  
  - [ ]* 23.5 Write integration test for migrated EvaluationService
    - Test end-to-end evaluation flow
    - Test that API contracts are preserved
    - Test that database schema compatibility is maintained
    - _Requirements: 5.3.4, 5.3.5_

- [x] 24. Migrate LangChainEvalService
  - [x] 24.1 Refactor app/services/langchain_eval_service.py to use Output Contracts
    - Replace manual output parsing with OutputValidator
    - Use WeeklyEvalContract for schema enforcement
    - Maintain existing function signatures
    - _Requirements: 5.3.2, 5.3.4_
  
  - [x] 24.2 Integrate confidence scoring
    - Use ConfidenceScorer to compute hybrid confidence
    - Include confidence_score in WeeklyEval records
    - _Requirements: 5.3.2_
  
  - [ ]* 24.3 Write integration test for migrated LangChainEvalService
    - Test output contract validation
    - Test confidence scoring
    - _Requirements: 5.4.1_

- [x] 25. Migrate RAGService
  - [x] 25.1 Refactor app/services/rag_service.py to use IntentRouter
    - Replace manual query classification with IntentRouter.classify()
    - Use retrieval_policies.yaml for intent-specific retrieval
    - Maintain existing function signatures
    - _Requirements: 5.3.3, 5.3.4_
  
  - [x] 25.2 Integrate RAGRetriever
    - Replace manual data retrieval with RAGRetriever.retrieve()
    - Use evidence card generation
    - _Requirements: 5.3.3_
  
  - [x] 25.3 Integrate ChatContextBuilder
    - Use ChatContextBuilder for context assembly (token_budget=2400)
    - Include conversation history in context
    - _Requirements: 5.3.3_
  
  - [ ]* 25.4 Write integration test for migrated RAGService
    - Test intent classification
    - Test retrieval with different intents
    - Test evidence card generation
    - _Requirements: 5.4.1_

- [x] 26. Update Module Imports
  - [x] 26.1 Update all service imports to reference app/ai/ modules
    - Update imports in app/services/evaluation_engine.py
    - Update imports in app/services/langchain_eval_service.py
    - Update imports in app/services/rag_service.py
    - Update imports in API route handlers
    - _Requirements: 5.3.7_
  
  - [x] 26.2 Remove deprecated prompt files
    - Delete old prompt files from app/prompts/ after migration validation
    - Ensure no references to old prompt files remain
    - _Requirements: 5.3.6_
  
  - [ ]* 26.3 Write import validation test
    - Test that all imports resolve correctly
    - Test that no deprecated modules are imported
    - _Requirements: 5.4.1_

- [-] 27. Write End-to-End Integration Tests
  - [ ]* 27.1 Write integration test for weekly evaluation pipeline
    - **Property 38: End-to-end evaluation correctness**
    - **Validates: Requirements 5.3.1, 5.3.4, 5.3.5**
    - Test complete flow from API request to database persistence
    - Test that all CE components work together correctly
    - Test that token budgets are respected
    - _Requirements: 5.4.1_
  
  - [ ]* 27.2 Write integration test for coach chat pipeline
    - **Property 39: End-to-end chat correctness**
    - **Validates: Requirements 5.3.3, 5.3.4**
    - Test complete flow from query to response with evidence
    - Test intent routing and retrieval
    - Test conversation history handling
    - _Requirements: 5.4.1_
  
  - [ ]* 27.3 Write property test for context token budget enforcement
    - **Property 40: Token budget enforcement across operations**
    - **Validates: Requirements 2.2.4, 2.2.5**
    - Test that evaluation contexts never exceed 3200 tokens
    - Test that chat contexts never exceed 2400 tokens
    - _Requirements: 5.4.1_
  
  - [ ]* 27.4 Write property test for evidence traceability
    - **Property 41: Evidence source integrity**
    - **Validates: Requirements 4.1.7**
    - Test that all evidence cards reference valid database records
    - Test that evidence cards are correctly linked to claims
    - _Requirements: 5.4.1_
  
  - [ ]* 27.5 Write property test for output contract compliance
    - **Property 42: Output schema compliance**
    - **Validates: Requirements 3.2.4, 3.2.5**
    - Test that all LLM responses conform to output contracts
    - Test that validation errors are handled correctly
    - _Requirements: 5.4.1_
  
  - [ ]* 27.6 Write property test for confidence score validity
    - **Property 43: Confidence score bounds**
    - **Validates: Requirements 3.3.1, 3.3.7**
    - Test that all confidence scores are between 0.0 and 1.0
    - Test that hybrid confidence calculation is correct
    - _Requirements: 5.4.1_

- [ ] 28. Verify Test Coverage
  - [ ]* 28.1 Run test coverage analysis for app/ai/ modules
    - Use pytest-cov to measure code coverage
    - Ensure minimum 85% coverage for all app/ai/ modules
    - Identify and test uncovered code paths
    - _Requirements: 5.4.7_
  
  - [ ]* 28.2 Generate coverage report
    - Generate HTML coverage report
    - Review coverage gaps and add tests as needed
    - _Requirements: 5.4.7_

- [ ] 29. Final Checkpoint - Context Engineering Refactor Complete
  - Ensure all tests pass, ask the user if questions arise.
  - Verify all 14 requirements are implemented
  - Verify all 43 correctness properties are validated
  - Confirm backward compatibility with existing data
  - Confirm API contracts are preserved

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at the end of each sprint
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows and component interactions
- The implementation uses Python with LangChain, Pydantic v2, SQLAlchemy, and FastAPI
- Token budgets: 3,200 tokens (evaluation), 2,400 tokens (chat)
- Confidence scoring: 70% system metrics + 30% LLM self-assessment
- Evidence cards link AI claims to source database records for verification
- Week_ID bug fix: use StravaActivity.week_id field instead of computed from start_date
- Backward compatibility: preserve API contracts, support null evidence_data
- Test coverage target: 85% for app/ai/ modules

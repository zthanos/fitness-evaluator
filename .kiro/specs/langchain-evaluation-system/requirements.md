# Requirements Document

## Introduction

This feature fixes critical data integration issues in the fitness evaluation system and enhances it with LangChain-based AI evaluation capabilities. The current system has a week_id mismatch that prevents activities from being included in evaluations, and uses basic LLM client calls instead of the more robust LangChain framework with tool calling support.

## Glossary

- **Evaluation_System**: The fitness evaluation subsystem that analyzes weekly performance data
- **Week_ID**: A unique identifier for a calendar week used to group related data
- **WeeklyMeasurement**: Database entity storing body metrics for a specific week (uses uuid4 primary key)
- **StravaActivity**: Database entity storing synchronized fitness activities (uses week_id foreign key)
- **Contract**: A structured data object containing all inputs for an evaluation (measurements, activities, logs, targets)
- **LangChain**: A framework for building LLM applications with tool calling and structured outputs
- **Tool_Calling**: LLM capability to invoke predefined functions with structured parameters
- **Evaluation_Service**: Service class that orchestrates the evaluation workflow
- **LLM_Client**: Current basic LLM integration without framework support
- **Idempotency**: Property where repeated evaluations with identical input produce identical output
- **Evidence_Map**: Traceability mapping from evaluation claims to source database records

## Requirements

### Requirement 1: Fix Week ID Mismatch

**User Story:** As a fitness coach, I want activities to be included in weekly evaluations, so that training analysis reflects actual workout data.

#### Acceptance Criteria

1. WHEN the Evaluation_System builds a Contract, THE Evaluation_System SHALL query StravaActivity records using the WeeklyMeasurement.id as week_id
2. WHEN the Strava_Sync_Service syncs activities for a week, THE Strava_Sync_Service SHALL assign the WeeklyMeasurement.id to StravaActivity.week_id
3. THE Evaluation_System SHALL include all StravaActivity records in the Contract.strava_aggregates field
4. FOR ALL weeks with synchronized activities, the Contract SHALL contain non-empty activity data
5. THE Evaluation_System SHALL maintain backward compatibility with existing WeeklyEval records

### Requirement 2: Integrate LangChain Framework

**User Story:** As a developer, I want evaluations to use LangChain instead of basic LLM calls, so that the system has consistent architecture and better reliability.

#### Acceptance Criteria

1. THE Evaluation_Service SHALL use LangChain for LLM interactions
2. THE Evaluation_Service SHALL support both Ollama and LM Studio backends through LangChain
3. THE Evaluation_Service SHALL use temperature=0.1 for consistent evaluation outputs
4. THE Evaluation_Service SHALL initialize LangChain with the same configuration pattern as Goal_Setting_Service
5. WHEN LangChain is unavailable, THE Evaluation_Service SHALL raise an ImportError with installation instructions

### Requirement 3: Structured Evaluation Output

**User Story:** As a fitness coach, I want evaluations to return structured, validated data, so that the UI can reliably display results.

#### Acceptance Criteria

1. THE Evaluation_Service SHALL use LangChain structured output parsing for EvalOutput schema
2. WHEN the LLM returns invalid JSON, THE Evaluation_Service SHALL retry with schema guidance
3. THE Evaluation_Service SHALL validate all EvalOutput fields against the Pydantic schema
4. THE Evaluation_Service SHALL include data_confidence score in every evaluation
5. IF validation fails after retries, THEN THE Evaluation_Service SHALL return a descriptive error with the validation failure details

### Requirement 4: Complete Data Contract

**User Story:** As a fitness coach, I want evaluations to consider all available data, so that recommendations are comprehensive and accurate.

#### Acceptance Criteria

1. THE Contract SHALL include WeeklyMeasurement data (weight, body_fat_pct, waist_cm, sleep_avg_hrs, rhr_bpm, energy_level_avg)
2. THE Contract SHALL include PlanTargets data (target_calories, target_protein_g, target_fasting_hrs, target_run_km_wk, target_strength_sessions, target_weight_kg)
3. THE Contract SHALL include DailyLog records for all seven days of the week
4. THE Contract SHALL include StravaActivity aggregates (run_km, ride_km, strength_sessions, heart_rate_data)
5. THE Contract SHALL include active AthleteGoal records for goal-oriented evaluation
6. WHEN any data source is empty, THE Contract SHALL include the field with null value

### Requirement 5: Evaluation Prompt Engineering

**User Story:** As a fitness coach, I want evaluations to provide actionable insights, so that athletes know what to improve.

#### Acceptance Criteria

1. THE Evaluation_System SHALL use a dedicated evaluation prompt template file
2. THE Evaluation_Prompt SHALL instruct the LLM to analyze nutrition adherence against targets
3. THE Evaluation_Prompt SHALL instruct the LLM to analyze training volume against targets
4. THE Evaluation_Prompt SHALL instruct the LLM to identify progress toward active goals
5. THE Evaluation_Prompt SHALL instruct the LLM to provide maximum 5 specific, actionable recommendations
6. THE Evaluation_Prompt SHALL instruct the LLM to calculate data_confidence based on completeness of input data

### Requirement 6: Maintain Idempotency

**User Story:** As a developer, I want identical input data to produce identical evaluations, so that the system is deterministic and cacheable.

#### Acceptance Criteria

1. THE Evaluation_Service SHALL compute SHA-256 hash of the Contract before evaluation
2. WHEN an evaluation exists with matching input_hash, THE Evaluation_Service SHALL return the cached result without calling the LLM
3. THE Evaluation_Service SHALL store input_hash with every WeeklyEval record
4. THE Evaluation_Service SHALL provide a refresh endpoint that bypasses the cache
5. THE Contract serialization SHALL use deterministic JSON encoding (sorted keys, consistent datetime format)

### Requirement 7: Evidence Traceability

**User Story:** As a fitness coach, I want to verify evaluation claims against source data, so that I can trust the AI recommendations.

#### Acceptance Criteria

1. THE Evaluation_Service SHALL collect evidence for each evaluation claim
2. THE Evidence_Map SHALL link evaluation statements to specific database record IDs
3. THE Evidence_Map SHALL include record type and primary key for each evidence item
4. THE Evaluation_Service SHALL store evidence_map_json with every WeeklyEval record
5. THE Evaluation_API SHALL return evidence_map in GET responses

### Requirement 8: Error Handling and Logging

**User Story:** As a developer, I want detailed error information when evaluations fail, so that I can diagnose and fix issues quickly.

#### Acceptance Criteria

1. WHEN LangChain initialization fails, THE Evaluation_Service SHALL log the error with backend configuration details
2. WHEN LLM invocation fails, THE Evaluation_Service SHALL log the request parameters and error response
3. WHEN schema validation fails, THE Evaluation_Service SHALL log the raw LLM response and validation errors
4. WHEN Contract building fails, THE Evaluation_Service SHALL log which data sources are missing
5. THE Evaluation_Service SHALL raise ValueError with descriptive messages for all validation failures

### Requirement 9: API Backward Compatibility

**User Story:** As a frontend developer, I want the evaluation API to maintain its current interface, so that existing UI code continues to work.

#### Acceptance Criteria

1. THE Evaluation_API SHALL maintain the POST /evaluate/{week_start} endpoint signature
2. THE Evaluation_API SHALL maintain the GET /evaluate/{week_start} endpoint signature
3. THE Evaluation_API SHALL maintain the POST /evaluate/{week_start}/refresh endpoint signature
4. THE Evaluation_API SHALL return the same response structure (week_start, week_id, evaluation, generated_at, input_hash)
5. THE Evaluation_API SHALL continue to accept week_start as a date parameter and derive week_id internally

### Requirement 10: Migration Strategy

**User Story:** As a developer, I want to migrate from the old system to LangChain without data loss, so that existing evaluations remain accessible.

#### Acceptance Criteria

1. THE Evaluation_Service SHALL read existing WeeklyEval records created by the old system
2. THE Evaluation_Service SHALL preserve all existing input_hash values
3. THE Evaluation_Service SHALL preserve all existing evidence_map_json values
4. WHEN re-evaluating a week, THE Evaluation_Service SHALL replace the old evaluation with the new LangChain-generated evaluation
5. THE Evaluation_Service SHALL not require database schema changes to WeeklyEval table

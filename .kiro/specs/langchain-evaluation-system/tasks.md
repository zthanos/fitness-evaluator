# Implementation Plan: LangChain Evaluation System

## Overview

This implementation refactors the fitness evaluation system to use LangChain for LLM interactions and fixes critical data integration issues. The work involves fixing the week_id mismatch, creating a new LangChainEvaluationService, updating the PromptEngine to include AthleteGoal data, and maintaining backward compatibility with existing APIs.

## Tasks

- [ ] 1. Create LangChainEvaluationService with structured output
  - [x] 1.1 Create app/services/langchain_eval_service.py with LangChain integration
    - Implement LangChainEvaluationService class with __init__ method
    - Support both ChatOllama and ChatOpenAI backends based on settings.LLM_TYPE
    - Configure temperature=0.1 for consistent outputs
    - Bind structured output schema using with_structured_output(EvalOutput)
    - Add import error handling with installation instructions if LangChain unavailable
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [x] 1.2 Implement generate_evaluation method with retry logic
    - Load evaluation prompt template from file
    - Build messages array with SystemMessage and HumanMessage
    - Implement 3-attempt retry loop for validation failures
    - Add schema guidance to messages on retry attempts
    - Return validated EvalOutput on success
    - Raise ValueError with descriptive message after 3 failed attempts
    - _Requirements: 3.1, 3.2, 3.3, 3.5_
  
  - [ ]* 1.3 Write property test for structured output validation
    - **Property 4: All evaluations include data_confidence score**
    - **Property 9: Schema validation rejects invalid outputs**
    - **Validates: Requirements 3.3, 3.4**
  
  - [ ]* 1.4 Write unit tests for LangChainEvaluationService
    - Test successful evaluation with valid contract
    - Test retry logic with invalid JSON responses
    - Test error handling for LangChain import failure
    - Test error handling for LLM backend unavailability
    - Test both Ollama and LM Studio backend initialization
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.5_

- [ ] 2. Fix week_id mismatch in PromptEngine
  - [x] 2.1 Update build_contract to use WeeklyMeasurement.id as week_id
    - Query WeeklyMeasurement using week_id parameter (UUID)
    - Raise ValueError if WeeklyMeasurement not found
    - Derive week_start and week_end from WeeklyMeasurement
    - Query StravaActivity using WeeklyMeasurement.id as week_id foreign key
    - Query DailyLog using date range [week_start, week_start + 7 days)
    - _Requirements: 1.1, 1.3, 4.3_
  
  - [x] 2.2 Add AthleteGoal data to contract
    - Query AthleteGoal records where status == GoalStatus.ACTIVE
    - Add active_goals field to contract with serialized goal data
    - Include goal_type, target_value, target_date, description, status, created_at
    - Handle empty active_goals with empty array
    - _Requirements: 4.5_
  
  - [x] 2.3 Implement deterministic contract serialization
    - Create hash_contract function using SHA-256
    - Serialize contract to JSON with sorted keys
    - Use consistent datetime format (ISO 8601 strings)
    - Ensure hash is deterministic across multiple calls
    - _Requirements: 6.1, 6.5_
  
  - [ ]* 2.4 Write property test for contract data completeness
    - **Property 1: Contract includes activities using correct week_id**
    - **Property 2: Contract contains all required data fields**
    - **Property 3: Contract includes all daily logs for the week**
    - **Validates: Requirements 1.1, 1.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**
  
  - [ ]* 2.5 Write property test for contract hashing determinism
    - **Property 6: Contract hashing is deterministic**
    - **Validates: Requirements 6.5**
  
  - [ ]* 2.6 Write unit tests for PromptEngine updates
    - Test build_contract with complete data (7 daily logs, Strava activities, goals)
    - Test build_contract with partial data (3 daily logs, no Strava activities)
    - Test build_contract with no data (empty contract with null values)
    - Test ValueError raised when WeeklyMeasurement not found
    - Test contract includes all required fields
    - Test hash_contract produces consistent results
    - _Requirements: 1.1, 1.3, 1.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.5_

- [ ] 3. Update Strava sync service to use correct week_id
  - [x] 3.1 Update Strava sync to assign WeeklyMeasurement.id to StravaActivity.week_id
    - Locate Strava sync service code
    - When syncing activities for a week, look up WeeklyMeasurement by week_start
    - Assign WeeklyMeasurement.id to StravaActivity.week_id field
    - Ensure all new StravaActivity records use correct week_id
    - _Requirements: 1.2_
  
  - [ ]* 3.2 Write unit tests for Strava sync week_id assignment
    - Test StravaActivity.week_id matches WeeklyMeasurement.id
    - Test activities are queryable using WeeklyMeasurement.id
    - _Requirements: 1.2, 1.3_

- [ ] 4. Create evaluation prompt template
  - [x] 4.1 Create app/prompts/evaluation_prompt.txt with comprehensive instructions
    - Instruct LLM to analyze nutrition adherence against targets
    - Instruct LLM to analyze training volume against targets
    - Instruct LLM to identify progress toward active goals
    - Instruct LLM to provide maximum 5 specific, actionable recommendations
    - Instruct LLM to calculate data_confidence based on input completeness
    - Include EvalOutput schema structure in prompt
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  
  - [ ]* 4.2 Write unit test for prompt template loading
    - Test prompt file exists and is readable
    - Test prompt contains required instruction sections
    - _Requirements: 5.1_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Update EvaluationService to use LangChain
  - [x] 6.1 Refactor evaluate_week to use LangChainEvaluationService
    - Initialize LangChainEvaluationService instance
    - Build contract using PromptEngine.build_contract
    - Compute contract hash using hash_contract
    - Check for existing WeeklyEval with matching input_hash (cache hit)
    - If cache hit, return existing evaluation without LLM call
    - If cache miss, call LangChainEvaluationService.generate_evaluation
    - Store result in WeeklyEval with input_hash
    - _Requirements: 2.1, 6.1, 6.2, 6.3_
  
  - [x] 6.2 Implement evidence collection and storage
    - Create EvidenceCollector class or functions
    - Map evaluation claims to source database record IDs
    - Build evidence_map with record types and primary keys
    - Store evidence_map_json in WeeklyEval record
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [x] 6.3 Add comprehensive error handling and logging
    - Log LangChain initialization errors with backend details
    - Log LLM invocation errors with request parameters and contract hash
    - Log schema validation errors with raw response and validation details
    - Log contract building errors with missing data sources
    - Raise ValueError with descriptive messages for all validation failures
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [ ]* 6.4 Write property test for evaluation storage
    - **Property 7: Contract hash is stored with evaluations**
    - **Property 8: Evidence map is stored with evaluations**
    - **Validates: Requirements 6.1, 6.3, 7.1, 7.2, 7.3, 7.4**
  
  - [ ]* 6.5 Write unit tests for EvaluationService refactoring
    - Test evaluate_week with cache hit (idempotency)
    - Test evaluate_week with cache miss (new evaluation)
    - Test evidence_map is stored with evaluation
    - Test input_hash is stored with evaluation
    - Test error handling for LangChain failures
    - Test error handling for contract building failures
    - _Requirements: 2.1, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 7. Update Evaluation API for backward compatibility
  - [x] 7.1 Update POST /evaluate/{week_start} endpoint
    - Look up WeeklyMeasurement by week_start to get week_id
    - Raise HTTPException 404 if WeeklyMeasurement not found
    - Call EvaluationService.evaluate_week with week_id
    - Return response with week_start, week_id, evaluation, generated_at, input_hash
    - Maintain existing response structure for backward compatibility
    - _Requirements: 9.1, 9.4, 9.5_
  
  - [x] 7.2 Update GET /evaluate/{week_start} endpoint
    - Look up WeeklyMeasurement by week_start to get week_id
    - Query WeeklyEval by week_id
    - Return response with evidence_map included
    - Maintain existing response structure
    - _Requirements: 9.2, 9.4, 7.5_
  
  - [x] 7.3 Update POST /evaluate/{week_start}/refresh endpoint
    - Look up WeeklyMeasurement by week_start to get week_id
    - Call EvaluationService.evaluate_week with cache bypass flag
    - Return response with updated evaluation
    - Maintain existing response structure
    - _Requirements: 9.3, 9.4, 6.4_
  
  - [ ]* 7.4 Write property test for API response structure
    - **Property 10: API responses maintain required structure**
    - **Property 11: ValueError raised for validation failures**
    - **Validates: Requirements 9.4, 8.5**
  
  - [ ]* 7.5 Write integration tests for API endpoints
    - Test POST /evaluate/{week_start} with complete data
    - Test POST /evaluate/{week_start} with partial data
    - Test POST /evaluate/{week_start} with missing WeeklyMeasurement (404)
    - Test GET /evaluate/{week_start} returns cached evaluation
    - Test GET /evaluate/{week_start} includes evidence_map
    - Test POST /evaluate/{week_start}/refresh bypasses cache
    - Test API maintains backward compatible response structure
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 7.5, 6.4_

- [ ] 8. Ensure migration compatibility
  - [x] 8.1 Verify existing WeeklyEval records are readable
    - Test reading WeeklyEval records created by old system
    - Verify input_hash values are preserved
    - Verify evidence_map_json values are preserved (if present)
    - Ensure no database schema changes required
    - _Requirements: 10.1, 10.2, 10.3, 10.5_
  
  - [x] 8.2 Test re-evaluation of existing weeks
    - Test re-evaluating a week replaces old evaluation with new one
    - Verify new evaluation uses LangChain
    - Verify new evaluation has updated input_hash
    - Verify new evaluation has evidence_map
    - _Requirements: 10.4_
  
  - [ ]* 8.3 Write unit tests for migration scenarios
    - Test reading old WeeklyEval records
    - Test re-evaluating old weeks with new system
    - Test backward compatibility with existing data
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 9. Add property test for recommendations limit
  - [ ]* 9.1 Write property test for recommendations constraint
    - **Property 5: All evaluations have at most 5 recommendations**
    - **Validates: Requirements 5.5**

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at reasonable breaks
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples, edge cases, and integration points
- The implementation maintains backward compatibility with existing API signatures
- No database schema changes are required for migration

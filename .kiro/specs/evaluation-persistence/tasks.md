# Implementation Plan: Evaluation Persistence

## Overview

This implementation adds database persistence for evaluation reports in the fitness platform. The approach follows these steps: create the database model, add a migration, update API endpoints to use database storage instead of in-memory storage, implement the re-evaluation endpoint, add frontend UI for re-evaluation, and verify backward compatibility. The implementation uses Python with FastAPI, SQLAlchemy, and Hypothesis for property-based testing.

## Tasks

- [ ] 1. Create Evaluation database model
  - [x] 1.1 Create app/models/evaluation.py with Evaluation model
    - Define all fields: id, athlete_id, period dates, scores, JSON arrays, timestamps
    - Use TimestampMixin for created_at and updated_at
    - Add to_dict() method for API serialization
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12, 1.13, 1.14_
  
  - [ ]* 1.2 Write unit tests for Evaluation model
    - Test model creation with all fields
    - Test JSON field serialization/deserialization
    - Test to_dict() method output
    - Test timestamp auto-generation
    - _Requirements: 1.1-1.14_

- [ ] 2. Create database migration for evaluations table
  - [x] 2.1 Generate Alembic migration script
    - Create alembic/versions/009_add_evaluations_table.py
    - Add upgrade function to create evaluations table with all columns
    - Add indexes on athlete_id and created_at
    - Add check constraint for period_type values
    - Add downgrade function to drop table and indexes
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [ ]* 2.2 Test migration up and down
    - Test upgrade creates table and indexes correctly
    - Test downgrade removes table cleanly
    - Verify schema matches model definition
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 3. Update API endpoints to use database storage
  - [x] 3.1 Modify POST /api/evaluations/generate to save to database
    - Replace in-memory store with database save
    - Add transaction commit after save
    - Add rollback on database errors
    - Remove evaluations_store dictionary
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [ ]* 3.2 Write property test for evaluation persistence round-trip
    - **Property 1: Evaluation Persistence Round-Trip**
    - **Validates: Requirements 2.1, 2.5, 3.1, 3.9**
    - Generate random evaluation data, save to DB, retrieve by ID, verify equivalence
  
  - [ ]* 3.3 Write property test for database transaction rollback
    - **Property 2: Database Transaction Rollback on Failure**
    - **Validates: Requirements 2.3**
    - Simulate database failures, verify rollback and no partial data
  
  - [x] 3.4 Modify GET /api/evaluations to query from database
    - Replace in-memory store with database query
    - Implement athlete_id filtering
    - Implement date_from and date_to filtering
    - Implement score_min and score_max filtering
    - Implement sorting by created_at DESC
    - Implement limit parameter
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_
  
  - [ ]* 3.5 Write property tests for filtering and sorting
    - **Property 3: Athlete ID Filtering** - Validates: Requirements 3.2
    - **Property 4: Date From Filtering** - Validates: Requirements 3.3
    - **Property 5: Date To Filtering** - Validates: Requirements 3.4
    - **Property 6: Score Minimum Filtering** - Validates: Requirements 3.5
    - **Property 7: Score Maximum Filtering** - Validates: Requirements 3.6
    - **Property 8: Descending Created-At Sort Order** - Validates: Requirements 3.7
    - **Property 9: Limit Parameter Enforcement** - Validates: Requirements 3.8
    - Generate random evaluation sets, apply filters, verify correct results
  
  - [x] 3.6 Modify GET /api/evaluations/{id} to query from database
    - Replace in-memory store with database query by ID
    - Return 404 if evaluation not found
    - _Requirements: 3.9, 3.10_
  
  - [ ]* 3.7 Write property test for non-existent evaluation 404
    - **Property 10: Non-Existent Evaluation Returns 404**
    - **Validates: Requirements 3.10**
    - Generate random non-existent IDs, verify 404 response

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement re-evaluation endpoint
  - [x] 5.1 Create POST /api/evaluations/{id}/re-evaluate endpoint
    - Retrieve original evaluation by ID
    - Return 404 if not found
    - Extract period_start, period_end, period_type, athlete_id from original
    - Call EvaluationEngine with same parameters
    - Generate new UUID for new evaluation
    - Save new evaluation to database
    - Return new evaluation in response
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  
  - [ ]* 5.2 Write property test for re-evaluation creates new evaluation
    - **Property 11: Re-Evaluation Creates New Evaluation with Same Parameters**
    - **Validates: Requirements 4.4, 4.5, 4.6, 4.7**
    - Create evaluation, re-evaluate, verify new ID and same parameters
  
  - [ ]* 5.3 Write property test for re-evaluate non-existent returns 404
    - **Property 12: Re-Evaluate Non-Existent Returns 404**
    - **Validates: Requirements 4.3**
    - Generate random non-existent IDs, verify 404 response
  
  - [ ]* 5.4 Write unit tests for re-evaluation endpoint
    - Test successful re-evaluation flow
    - Test 404 for non-existent evaluation
    - Test error handling for generation failures
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 6. Add re-evaluate button to frontend
  - [x] 6.1 Add re-evaluate button to evaluation-detail.html
    - Add button in Actions card
    - Add click handler to call re-evaluate endpoint
    - Implement button state management (disabled during request)
    - Implement redirect to new evaluation on success
    - Implement error toast on failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ]* 6.2 Write integration test for re-evaluate button flow
    - Test button click triggers API call
    - Test redirect on success
    - Test error handling on failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 7. Verify backward compatibility
  - [x] 7.1 Run existing evaluation tests against new implementation
    - Run test_eval_service_refactor.py
    - Run test_evaluation_score_bounds.py
    - Verify all tests pass without modification
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [ ]* 7.2 Write property tests for backward compatibility
    - **Property 13: Backward Compatible Request/Response Schemas** - Validates: Requirements 7.1
    - **Property 14: Backward Compatible Status Codes** - Validates: Requirements 7.2
    - Test existing endpoints with same requests, verify same responses
  
  - [ ]* 7.3 Write integration tests for frontend compatibility
    - Test evaluation list page loads and displays data
    - Test evaluation detail page loads and displays data
    - Test evaluation generation from frontend
    - _Requirements: 7.3_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property-based tests use Hypothesis library with 100+ iterations per property
- All database operations use SQLAlchemy session management via get_db() dependency
- EvaluationEngine service remains unchanged throughout implementation
- Frontend uses vanilla JavaScript with fetch API for re-evaluation
- Migration script follows Alembic conventions and existing migration patterns

# Requirements Document

## Introduction

This document specifies requirements for implementing database persistence for evaluations in the fitness platform. Currently, evaluations are stored in memory and lost when the server restarts. This feature will add database storage, enable evaluation history across restarts, and provide re-evaluation capabilities from the detail page.

## Glossary

- **Evaluation**: A structured performance report containing scores, strengths, improvements, tips, and recommendations for a specific time period
- **Evaluation_API**: The FastAPI router handling evaluation endpoints at /api/evaluations
- **Evaluation_Model**: The SQLAlchemy database model for storing evaluation data
- **Evaluation_Service**: The service layer component that generates evaluations using the EvaluationEngine
- **Re_Evaluation**: The process of regenerating an evaluation report using the same parameters (period_start, period_end, period_type) as a previous evaluation
- **Database_Session**: SQLAlchemy session for database operations
- **In_Memory_Store**: The current evaluations_store dictionary that holds evaluations temporarily

## Requirements

### Requirement 1: Database Model for Evaluations

**User Story:** As a developer, I want a database model for evaluations, so that evaluation data persists across server restarts.

#### Acceptance Criteria

1. THE Evaluation_Model SHALL store the evaluation ID as a string primary key
2. THE Evaluation_Model SHALL store the athlete_id as an integer foreign key
3. THE Evaluation_Model SHALL store period_start as a date field
4. THE Evaluation_Model SHALL store period_end as a date field
5. THE Evaluation_Model SHALL store period_type as a string field
6. THE Evaluation_Model SHALL store overall_score as an integer field
7. THE Evaluation_Model SHALL store strengths as a JSON array field
8. THE Evaluation_Model SHALL store improvements as a JSON array field
9. THE Evaluation_Model SHALL store tips as a JSON array field
10. THE Evaluation_Model SHALL store recommended_exercises as a JSON array field
11. THE Evaluation_Model SHALL store goal_alignment as a text field
12. THE Evaluation_Model SHALL store confidence_score as a float field
13. THE Evaluation_Model SHALL include created_at and updated_at timestamp fields using TimestampMixin
14. THE Evaluation_Model SHALL follow the existing model patterns in app/models/

### Requirement 2: Persist Evaluations to Database

**User Story:** As a user, I want my evaluations saved to the database, so that I can access them after server restarts.

#### Acceptance Criteria

1. WHEN an evaluation is generated, THE Evaluation_API SHALL save it to the database using the Evaluation_Model
2. WHEN an evaluation is saved, THE Evaluation_API SHALL commit the database transaction
3. IF the database save fails, THEN THE Evaluation_API SHALL rollback the transaction and return an error
4. THE Evaluation_API SHALL remove the in_memory_store dictionary after database persistence is implemented
5. FOR ALL saved evaluations, retrieving them from the database SHALL return data equivalent to what was saved (round-trip property)

### Requirement 3: Retrieve Evaluations from Database

**User Story:** As a user, I want to view my evaluation history from the database, so that I can see all past evaluations even after restarts.

#### Acceptance Criteria

1. WHEN the GET /api/evaluations endpoint is called, THE Evaluation_API SHALL query evaluations from the database
2. WHEN retrieving evaluations, THE Evaluation_API SHALL filter by athlete_id
3. WHEN date_from filter is provided, THE Evaluation_API SHALL return only evaluations where period_start is greater than or equal to date_from
4. WHEN date_to filter is provided, THE Evaluation_API SHALL return only evaluations where period_end is less than or equal to date_to
5. WHEN score_min filter is provided, THE Evaluation_API SHALL return only evaluations where overall_score is greater than or equal to score_min
6. WHEN score_max filter is provided, THE Evaluation_API SHALL return only evaluations where overall_score is less than or equal to score_max
7. THE Evaluation_API SHALL sort evaluations by created_at in descending order (newest first)
8. THE Evaluation_API SHALL apply the limit parameter to restrict the number of results
9. WHEN the GET /api/evaluations/{id} endpoint is called, THE Evaluation_API SHALL retrieve the evaluation from the database by ID
10. IF an evaluation ID does not exist, THEN THE Evaluation_API SHALL return a 404 error

### Requirement 4: Re-Evaluation Endpoint

**User Story:** As a user, I want to re-evaluate from the evaluation detail page, so that I can generate an updated evaluation with the same parameters.

#### Acceptance Criteria

1. THE Evaluation_API SHALL provide a POST /api/evaluations/{id}/re-evaluate endpoint
2. WHEN the re-evaluate endpoint is called, THE Evaluation_API SHALL retrieve the original evaluation by ID
3. IF the original evaluation does not exist, THEN THE Evaluation_API SHALL return a 404 error
4. WHEN re-evaluating, THE Evaluation_API SHALL use the same period_start, period_end, period_type, and athlete_id as the original evaluation
5. WHEN re-evaluating, THE Evaluation_API SHALL generate a new evaluation with a new ID
6. WHEN re-evaluating, THE Evaluation_API SHALL save the new evaluation to the database
7. THE Evaluation_API SHALL return the newly generated evaluation in the response

### Requirement 5: Re-Evaluation UI Button

**User Story:** As a user, I want a re-evaluate button on the evaluation detail page, so that I can easily regenerate evaluations.

#### Acceptance Criteria

1. THE evaluation-detail.html page SHALL display a "Re-evaluate" button in the Actions card
2. WHEN the re-evaluate button is clicked, THE page SHALL call the POST /api/evaluations/{id}/re-evaluate endpoint
3. WHILE the re-evaluation is in progress, THE button SHALL display "Re-evaluating..." and be disabled
4. WHEN re-evaluation succeeds, THE page SHALL redirect to the new evaluation detail page
5. IF re-evaluation fails, THEN THE page SHALL display an error message and re-enable the button

### Requirement 6: Database Migration

**User Story:** As a developer, I want a database migration for the evaluations table, so that the schema is properly versioned and applied.

#### Acceptance Criteria

1. THE system SHALL include an Alembic migration script that creates the evaluations table
2. THE migration script SHALL create all columns defined in the Evaluation_Model
3. THE migration script SHALL create appropriate indexes for athlete_id and created_at fields
4. THE migration script SHALL include a downgrade function to drop the evaluations table

### Requirement 7: Backward Compatibility

**User Story:** As a developer, I want the changes to maintain backward compatibility, so that existing functionality continues to work.

#### Acceptance Criteria

1. THE Evaluation_API SHALL maintain the same request and response schemas for all existing endpoints
2. THE Evaluation_API SHALL maintain the same HTTP status codes for success and error cases
3. THE frontend pages SHALL continue to work without modifications to their API calls
4. THE EvaluationEngine service SHALL remain unchanged in its interface and behavior

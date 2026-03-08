# Design Document: Evaluation Persistence

## Overview

This design implements database persistence for evaluation reports in the fitness platform. Currently, evaluations are stored in an in-memory dictionary (`evaluations_store`) that loses data on server restart. This design adds a SQLAlchemy model for evaluations, migrates the API endpoints to use database storage, and implements a re-evaluation feature accessible from the evaluation detail page.

The implementation maintains backward compatibility with existing API contracts while adding persistence and new functionality. The design follows established patterns in the codebase for models (TimestampMixin, JSON fields), API endpoints (FastAPI with dependency injection), and frontend interactions (vanilla JavaScript with fetch API).

## Architecture

### System Components

The evaluation persistence feature spans three architectural layers:

1. **Data Layer**: SQLAlchemy ORM model for the `evaluations` table with SQLite backend
2. **API Layer**: FastAPI router endpoints for CRUD operations and re-evaluation
3. **Frontend Layer**: JavaScript enhancements to the evaluation detail page for re-evaluation UI

### Data Flow

**Evaluation Generation Flow:**
```
User Request → API Endpoint → EvaluationEngine → Database Save → Response
```

**Evaluation Retrieval Flow:**
```
User Request → API Endpoint → Database Query → Response
```

**Re-Evaluation Flow:**
```
User Click → Frontend JS → POST /api/evaluations/{id}/re-evaluate → 
Fetch Original → Generate New → Save to DB → Redirect to New Detail Page
```

### Integration Points

- **Database**: SQLAlchemy session management via `get_db()` dependency
- **EvaluationEngine**: Existing service remains unchanged, generates evaluation reports
- **Frontend**: Existing pages continue to work with same API contracts
- **Migrations**: Alembic migration system for schema versioning

## Components and Interfaces

### Database Model: Evaluation

**File**: `app/models/evaluation.py`

**Purpose**: Persist evaluation reports with all metadata and generated content.

**Schema**:
```python
class Evaluation(Base, TimestampMixin):
    __tablename__ = 'evaluations'
    
    # Primary key
    id: str = Column(String(36), primary_key=True)
    
    # Metadata
    athlete_id: int = Column(Integer, nullable=False)
    period_start: date = Column(Date, nullable=False)
    period_end: date = Column(Date, nullable=False)
    period_type: str = Column(String(20), nullable=False)
    
    # Evaluation content
    overall_score: int = Column(Integer, nullable=False)
    strengths: list = Column(JSON, nullable=False)
    improvements: list = Column(JSON, nullable=False)
    tips: list = Column(JSON, nullable=False)
    recommended_exercises: list = Column(JSON, nullable=False)
    goal_alignment: str = Column(Text, nullable=False)
    confidence_score: float = Column(Float, nullable=False)
    
    # Timestamps (from TimestampMixin)
    # created_at: datetime
    # updated_at: datetime
```

**Indexes**:
- `idx_evaluations_athlete_id`: For filtering by athlete
- `idx_evaluations_created_at`: For sorting by generation time

**Methods**:
- `to_dict()`: Convert model to dictionary for API responses

### API Endpoints

**File**: `app/api/evaluations.py`

#### Modified Endpoints

**POST /api/evaluations/generate**
- **Changes**: Save to database instead of in-memory store
- **Process**: Generate evaluation → Create Evaluation model → Commit to DB → Return response
- **Error Handling**: Rollback on database errors

**GET /api/evaluations**
- **Changes**: Query from database instead of in-memory store
- **Process**: Build SQLAlchemy query with filters → Execute → Convert to response models
- **Filters**: athlete_id, date_from, date_to, score_min, score_max, limit
- **Sorting**: Order by created_at DESC

**GET /api/evaluations/{id}**
- **Changes**: Query from database instead of in-memory store
- **Process**: Query by ID → Return 404 if not found → Convert to response model

#### New Endpoint

**POST /api/evaluations/{id}/re-evaluate**
- **Purpose**: Generate a new evaluation using the same parameters as an existing one
- **Request**: No body required, ID in path
- **Response**: New evaluation with new ID
- **Process**:
  1. Query original evaluation by ID
  2. Return 404 if not found
  3. Extract period_start, period_end, period_type, athlete_id
  4. Call EvaluationEngine with same parameters
  5. Generate new UUID for new evaluation
  6. Save new evaluation to database
  7. Return new evaluation response

**Error Cases**:
- 404: Original evaluation not found
- 400: Invalid evaluation data
- 500: Database or generation errors

### Frontend Changes

**File**: `public/evaluation-detail.html`

**New UI Element**: Re-evaluate button in the Actions card

**Button Behavior**:
- Initial state: "Re-evaluate" button enabled
- On click: Disable button, change text to "Re-evaluating..."
- On success: Redirect to new evaluation detail page
- On error: Show error toast, re-enable button

**JavaScript Implementation**:
```javascript
async function reEvaluate() {
    const button = event.target;
    const originalText = button.textContent;
    
    try {
        button.disabled = true;
        button.textContent = 'Re-evaluating...';
        
        const response = await fetch(
            `/api/evaluations/${currentEvaluation.id}/re-evaluate`,
            { method: 'POST' }
        );
        
        if (!response.ok) {
            throw new Error('Re-evaluation failed');
        }
        
        const newEval = await response.json();
        window.location.href = `evaluation-detail.html?id=${newEval.id}`;
        
    } catch (error) {
        console.error('Re-evaluation error:', error);
        showError('Failed to re-evaluate. Please try again.');
        button.disabled = false;
        button.textContent = originalText;
    }
}
```

### Database Migration

**File**: `alembic/versions/009_add_evaluations_table.py`

**Revision**: 009
**Revises**: 008

**Upgrade**:
- Create `evaluations` table with all columns
- Create indexes on `athlete_id` and `created_at`
- Add check constraint for `period_type` values

**Downgrade**:
- Drop indexes
- Drop `evaluations` table

## Data Models

### Evaluation Model Details

**Field Specifications**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String(36) | Primary Key | UUID as string |
| athlete_id | Integer | NOT NULL | Foreign key to athlete |
| period_start | Date | NOT NULL | Start of evaluation period |
| period_end | Date | NOT NULL | End of evaluation period |
| period_type | String(20) | NOT NULL, CHECK | 'weekly', 'bi-weekly', or 'monthly' |
| overall_score | Integer | NOT NULL | Score 0-100 |
| strengths | JSON | NOT NULL | Array of strings |
| improvements | JSON | NOT NULL | Array of strings |
| tips | JSON | NOT NULL | Array of strings |
| recommended_exercises | JSON | NOT NULL | Array of strings |
| goal_alignment | Text | NOT NULL | Goal progress assessment |
| confidence_score | Float | NOT NULL | 0.0-1.0 data confidence |
| created_at | DateTime | NOT NULL | Auto-generated timestamp |
| updated_at | DateTime | NOT NULL | Auto-updated timestamp |

**JSON Field Structure**:
- All JSON fields store arrays of strings
- Empty arrays are valid (e.g., no improvements identified)
- Frontend handles empty arrays gracefully

**Timestamp Behavior**:
- `created_at`: Set once on insert to current UTC time
- `updated_at`: Set on insert and updated on every modification
- Both use `TimestampMixin` pattern from `app/models/base.py`

### Schema Validation

**Pydantic Schemas** (existing, no changes):
- `EvaluationRequest`: Input validation for generation
- `EvaluationResponse`: Output serialization for API
- `EvaluationReport`: LLM output validation

**Database Constraints**:
- Check constraint: `period_type IN ('weekly', 'bi-weekly', 'monthly')`
- Foreign key: `athlete_id` references athletes (future enhancement)
- Indexes: Composite queries on athlete_id + created_at


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Evaluation Persistence Round-Trip

*For any* valid evaluation data (athlete_id, period dates, scores, lists, etc.), if we save it to the database and then retrieve it by ID, the retrieved data should be equivalent to what was saved.

**Validates: Requirements 2.1, 2.5, 3.1, 3.9**

### Property 2: Database Transaction Rollback on Failure

*For any* database save operation that fails, the system should rollback the transaction and return an appropriate error response without leaving partial data in the database.

**Validates: Requirements 2.3**

### Property 3: Athlete ID Filtering

*For any* set of evaluations with different athlete_ids, querying the GET /api/evaluations endpoint with a specific athlete_id filter should return only evaluations belonging to that athlete.

**Validates: Requirements 3.2**

### Property 4: Date From Filtering

*For any* date_from filter value, all evaluations returned by GET /api/evaluations should have period_start >= date_from.

**Validates: Requirements 3.3**

### Property 5: Date To Filtering

*For any* date_to filter value, all evaluations returned by GET /api/evaluations should have period_end <= date_to.

**Validates: Requirements 3.4**

### Property 6: Score Minimum Filtering

*For any* score_min filter value, all evaluations returned by GET /api/evaluations should have overall_score >= score_min.

**Validates: Requirements 3.5**

### Property 7: Score Maximum Filtering

*For any* score_max filter value, all evaluations returned by GET /api/evaluations should have overall_score <= score_max.

**Validates: Requirements 3.6**

### Property 8: Descending Created-At Sort Order

*For any* set of evaluations returned by GET /api/evaluations, the list should be sorted by created_at in descending order (newest first), meaning for all adjacent pairs (eval_i, eval_i+1), eval_i.created_at >= eval_i+1.created_at.

**Validates: Requirements 3.7**

### Property 9: Limit Parameter Enforcement

*For any* limit parameter value L, the number of evaluations returned by GET /api/evaluations should be <= L.

**Validates: Requirements 3.8**

### Property 10: Non-Existent Evaluation Returns 404

*For any* evaluation ID that does not exist in the database, calling GET /api/evaluations/{id} should return a 404 status code.

**Validates: Requirements 3.10**

### Property 11: Re-Evaluation Creates New Evaluation with Same Parameters

*For any* existing evaluation, calling POST /api/evaluations/{id}/re-evaluate should produce a new evaluation that:
- Has a different ID from the original
- Has the same period_start, period_end, period_type, and athlete_id as the original
- Is saved to the database and retrievable by its new ID
- Is returned in the API response

**Validates: Requirements 4.4, 4.5, 4.6, 4.7**

### Property 12: Re-Evaluate Non-Existent Returns 404

*For any* evaluation ID that does not exist in the database, calling POST /api/evaluations/{id}/re-evaluate should return a 404 status code.

**Validates: Requirements 4.3**

### Property 13: Backward Compatible Request/Response Schemas

*For any* valid request to existing endpoints (POST /generate, GET /, GET /{id}) that worked before the database migration, the same request should work after migration with the same response schema structure.

**Validates: Requirements 7.1**

### Property 14: Backward Compatible Status Codes

*For any* request to existing endpoints, the HTTP status codes for success (200, 201) and error cases (400, 404, 500) should remain the same as before the database migration.

**Validates: Requirements 7.2**

## Error Handling

### Database Errors

**Connection Failures**:
- Symptom: SQLAlchemy raises connection errors
- Response: HTTP 500 with message "Database connection failed"
- Recovery: Automatic retry via connection pool, log error for monitoring

**Transaction Failures**:
- Symptom: Commit fails due to constraint violations or deadlocks
- Response: Rollback transaction, HTTP 500 with message "Failed to save evaluation"
- Recovery: Session rollback ensures clean state for next request

**Query Failures**:
- Symptom: Query raises exception (malformed query, database corruption)
- Response: HTTP 500 with message "Failed to retrieve evaluations"
- Recovery: Log error, return empty result set or error response

### Validation Errors

**Invalid Evaluation ID**:
- Symptom: ID not found in database
- Response: HTTP 404 with message "Evaluation {id} not found"
- User Action: Verify ID or return to evaluation list

**Invalid Filter Parameters**:
- Symptom: score_min > score_max, date_from > date_to
- Response: HTTP 400 with descriptive validation error
- User Action: Correct filter parameters

**Invalid Period Type**:
- Symptom: period_type not in ['weekly', 'bi-weekly', 'monthly']
- Response: HTTP 400 with message "period_type must be 'weekly', 'bi-weekly', or 'monthly'"
- User Action: Use valid period type

### Frontend Errors

**Re-Evaluation Failure**:
- Symptom: API returns error status
- Response: Display error toast, re-enable button
- User Action: Retry or contact support

**Network Errors**:
- Symptom: Fetch fails due to network issues
- Response: Display error toast "Network error, please try again"
- User Action: Check connection and retry

**Timeout Errors**:
- Symptom: Request takes too long (>30s)
- Response: Display error toast "Request timed out"
- User Action: Retry with shorter time period

### Error Logging

All errors should be logged with:
- Timestamp
- Request ID (for tracing)
- User/Athlete ID
- Error type and message
- Stack trace (for 500 errors)

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests**: Focus on specific examples, edge cases, and integration points
- Example: Test re-evaluation with a specific known evaluation
- Example: Test empty filter results
- Edge case: Test evaluation with empty arrays (no strengths, no tips)
- Edge case: Test boundary scores (0, 100)
- Integration: Test database session lifecycle

**Property-Based Tests**: Verify universal properties across all inputs
- Generate random evaluation data and verify round-trip persistence
- Generate random filter combinations and verify correct filtering
- Generate random evaluation sets and verify sort order
- Test with 100+ iterations per property to catch edge cases

### Property-Based Testing Configuration

**Library**: Hypothesis (Python property-based testing library)

**Configuration**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)
@given(
    athlete_id=st.integers(min_value=1, max_value=1000),
    period_start=st.dates(),
    period_end=st.dates(),
    overall_score=st.integers(min_value=0, max_value=100),
    # ... other fields
)
def test_evaluation_persistence_round_trip(...):
    # Test implementation
    pass
```

**Test Tags**: Each property test must include a comment referencing the design property:
```python
# Feature: evaluation-persistence, Property 1: Evaluation Persistence Round-Trip
def test_evaluation_persistence_round_trip(...):
    pass
```

**Minimum Iterations**: 100 per property test (configurable via `max_examples`)

### Test Coverage Requirements

**Database Layer**:
- Model creation and field validation
- JSON field serialization/deserialization
- Timestamp auto-generation
- Index usage verification

**API Layer**:
- All endpoint success paths
- All error conditions (404, 400, 500)
- Filter combinations
- Sort order verification
- Re-evaluation flow

**Frontend Layer**:
- Button state transitions
- API call verification
- Error handling
- Redirect behavior

**Integration Tests**:
- End-to-end evaluation generation and retrieval
- Re-evaluation full flow
- Database migration up/down
- Backward compatibility with existing data

### Test Data Strategies

**Hypothesis Strategies** for property-based tests:

```python
# Evaluation data strategy
evaluation_data = st.fixed_dictionaries({
    'athlete_id': st.integers(min_value=1, max_value=1000),
    'period_start': st.dates(min_value=date(2020, 1, 1)),
    'period_end': st.dates(min_value=date(2020, 1, 1)),
    'period_type': st.sampled_from(['weekly', 'bi-weekly', 'monthly']),
    'overall_score': st.integers(min_value=0, max_value=100),
    'strengths': st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=10),
    'improvements': st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=10),
    'tips': st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=10),
    'recommended_exercises': st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=10),
    'goal_alignment': st.text(min_size=10, max_size=500),
    'confidence_score': st.floats(min_value=0.0, max_value=1.0),
})
```

**Edge Cases to Cover**:
- Empty arrays for strengths, improvements, tips, recommended_exercises
- Boundary scores: 0, 100
- Boundary confidence: 0.0, 1.0
- Same-day periods (period_start == period_end)
- Very long text in goal_alignment
- Special characters in text fields
- Large result sets (test pagination)
- Concurrent requests (test transaction isolation)

### Backward Compatibility Testing

**Approach**: Run existing evaluation tests against new implementation

**Verification**:
1. All existing unit tests pass without modification
2. API contracts remain unchanged (request/response schemas)
3. Status codes match previous behavior
4. Frontend pages work without changes
5. Existing evaluation data (if any) remains accessible

**Test Suite**:
- Re-run all tests in `test_eval_service_refactor.py`
- Re-run all tests in `test_evaluation_score_bounds.py`
- Verify frontend pages load and function correctly
- Test with sample data from previous implementation

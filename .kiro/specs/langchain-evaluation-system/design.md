# Design Document: LangChain Evaluation System

## Overview

This design refactors the fitness evaluation system to use LangChain for LLM interactions and fixes critical data integration issues. The current system has a week_id mismatch preventing activities from being included in evaluations, and uses basic LLM client calls instead of the more robust LangChain framework.

The refactored system will:
- Fix the week_id mismatch by using WeeklyMeasurement.id consistently
- Replace basic LLM calls with LangChain's structured output capabilities
- Add AthleteGoal data to evaluation contracts for goal-oriented feedback
- Maintain backward compatibility with existing API signatures and database records
- Provide deterministic evaluations through contract hashing and caching

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│  Evaluation API │
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  EvaluationService      │
│  - evaluate_week()      │
│  - get_evaluation()     │
└────────┬────────────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌──────────────────┐  ┌────────────────────┐
│  PromptEngine    │  │  LangChainService  │
│  - build_contract│  │  - structured_call │
│  - hash_contract │  │  - with_retry      │
└──────────────────┘  └────────────────────┘
         │                  │
         ▼                  ▼
┌──────────────────┐  ┌────────────────────┐
│  Database        │  │  LLM Backend       │
│  - WeeklyEval    │  │  (Ollama/LM Studio)│
│  - DailyLog      │  └────────────────────┘
│  - StravaActivity│
│  - AthleteGoal   │
└──────────────────┘
```

### Component Responsibilities


**Evaluation API** (`app/api/evaluate.py`)
- Maintains existing endpoint signatures for backward compatibility
- Converts week_start dates to week_id using WeeklyMeasurement lookup
- Delegates evaluation logic to EvaluationService
- Returns structured responses with evaluation data and metadata

**EvaluationService** (`app/services/eval_service.py`)
- Orchestrates the evaluation workflow
- Implements idempotency through contract hashing
- Manages WeeklyEval record lifecycle (create/update/retrieve)
- Coordinates between PromptEngine, LangChainService, and EvidenceCollector

**PromptEngine** (`app/services/prompt_engine.py`)
- Builds evaluation contracts from database entities
- Queries WeeklyMeasurement, PlanTargets, DailyLog, StravaActivity, AthleteGoal
- Uses WeeklyMeasurement.id as the canonical week_id for all queries
- Computes SHA-256 hash of contracts for idempotency
- Ensures deterministic JSON serialization (sorted keys, consistent datetime format)

**LangChainEvaluationService** (`app/services/langchain_eval_service.py` - new)
- Wraps LangChain LLM interactions
- Initializes ChatOllama or ChatOpenAI based on configuration
- Uses structured output parsing with EvalOutput Pydantic schema
- Implements retry logic for invalid JSON responses
- Configures temperature=0.1 for consistent outputs

**EvidenceCollector** (`app/services/evidence_collector.py`)
- Maps evaluation claims to source database records
- Builds evidence_map with record types and primary keys
- Provides traceability for AI-generated insights

### Data Flow

1. **Request**: Client calls POST /evaluate/{week_start}
2. **Week ID Resolution**: API looks up WeeklyMeasurement by week_start to get week_id (UUID)
3. **Contract Building**: PromptEngine queries all data sources using week_id
4. **Hash Check**: Service computes contract hash and checks for cached evaluation
5. **LLM Call** (if not cached): LangChainService sends contract to LLM with structured output
6. **Validation**: Response is validated against EvalOutput Pydantic schema
7. **Evidence Collection**: EvidenceCollector maps claims to source records
8. **Storage**: WeeklyEval record is created/updated with results
9. **Response**: API returns evaluation with metadata

## Components and Interfaces

### LangChainEvaluationService

```python
class LangChainEvaluationService:
    """LangChain-based evaluation service with structured output."""
    
    def __init__(self):
        """Initialize LangChain with Ollama or LM Studio backend."""
        settings = get_settings()
        
        if settings.LLM_TYPE.lower() in ["lm-studio", "openai"]:
            self.llm = ChatOpenAI(
                base_url=settings.llm_base_url,
                api_key="lm-studio",
                model=settings.OLLAMA_MODEL,
                temperature=0.1
            )
        else:
            self.llm = ChatOllama(
                base_url=settings.llm_base_url,
                model=settings.OLLAMA_MODEL,
                temperature=0.1
            )
        
        # Bind structured output schema
        self.llm_with_structure = self.llm.with_structured_output(EvalOutput)
    
    async def generate_evaluation(self, contract: dict) -> EvalOutput:
        """Generate evaluation with structured output parsing."""
        prompt = self._load_prompt_template()
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps(contract, indent=2, default=str))
        ]
        
        # Retry logic for invalid responses
        for attempt in range(3):
            try:
                result = await self.llm_with_structure.ainvoke(messages)
                return result
            except ValidationError as e:
                if attempt == 2:
                    raise ValueError(f"Validation failed after 3 attempts: {e}")
                # Add schema guidance for retry
                messages.append(AIMessage(content="Schema validation failed"))
                messages.append(HumanMessage(content=f"Please ensure response matches: {EvalOutput.model_json_schema()}"))
```

### Enhanced PromptEngine

```python
def build_contract(week_id: str, db: Session) -> dict:
    """Build evaluation contract with all data sources."""
    
    # 1. Load WeeklyMeasurement using week_id (UUID)
    weekly_measurement = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == week_id
    ).first()
    
    if not weekly_measurement:
        raise ValueError(f"No WeeklyMeasurement found for week_id: {week_id}")
    
    week_start = weekly_measurement.week_start
    week_end = week_start + timedelta(days=7)
    
    # 2. Load active PlanTargets
    plan_targets = db.query(PlanTargets).filter(
        PlanTargets.effective_from <= week_start
    ).order_by(PlanTargets.effective_from.desc()).first()
    
    # 3. Load DailyLog records for the week
    daily_logs = db.query(DailyLog).filter(
        DailyLog.log_date >= week_start,
        DailyLog.log_date < week_end
    ).order_by(DailyLog.log_date).all()
    
    # 4. Load StravaActivity aggregates using week_id
    strava_aggregates = compute_weekly_aggregates(week_id, db)
    
    # 5. Load active AthleteGoal records (NEW)
    active_goals = db.query(AthleteGoal).filter(
        AthleteGoal.status == GoalStatus.ACTIVE.value
    ).all()
    
    # Build contract with all fields
    contract = {
        "week": {
            "start": str(week_start),
            "end": str(week_end)
        },
        "targets": _serialize_targets(plan_targets),
        "measurements": _serialize_measurements(weekly_measurement),
        "daily_logs": _serialize_daily_logs(daily_logs),
        "strava_aggregates": strava_aggregates,
        "active_goals": _serialize_goals(active_goals)  # NEW
    }
    
    return contract
```

### Week ID Resolution in API

```python
@router.post("/{week_start}")
async def evaluate_week(week_start: date, db: Session = Depends(get_db)):
    """Evaluate week with week_id resolution."""
    
    # Look up WeeklyMeasurement to get week_id
    weekly_measurement = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.week_start == week_start
    ).first()
    
    if not weekly_measurement:
        raise HTTPException(
            status_code=404,
            detail=f"No WeeklyMeasurement found for week starting {week_start}"
        )
    
    week_id = weekly_measurement.id
    
    # Proceed with evaluation using week_id
    eval_service = EvaluationService(db)
    weekly_eval = await eval_service.evaluate_week(week_id)
    
    return {
        "week_start": week_start,
        "week_id": str(week_id),
        "evaluation": weekly_eval.parsed_output_json,
        "generated_at": weekly_eval.generated_at,
        "input_hash": weekly_eval.input_hash
    }
```

## Data Models

### Contract Structure

```python
{
    "week": {
        "start": "2024-01-01",  # ISO date string
        "end": "2024-01-08"
    },
    "targets": {
        "effective_from": "2024-01-01",
        "target_calories": 2000,
        "target_protein_g": 150,
        "target_fasting_hrs": 16,
        "target_run_km_wk": 30,
        "target_strength_sessions": 3,
        "target_weight_kg": 75,
        "notes": "Maintenance phase"
    },
    "measurements": {
        "weight_kg": 76.5,
        "weight_prev_kg": 77.0,
        "body_fat_pct": 15.2,
        "waist_cm": 82,
        "waist_prev_cm": 83,
        "sleep_avg_hrs": 7.5,
        "rhr_bpm": 52,
        "energy_level_avg": 8.0
    },
    "daily_logs": [
        {
            "id": "uuid",
            "log_date": "2024-01-01",
            "fasting_hours": 16,
            "calories_in": 1950,
            "protein_g": 145,
            "carbs_g": 200,
            "fat_g": 65,
            "adherence_score": 9,
            "notes": "Good day"
        }
        // ... 7 days total
    ],
    "strava_aggregates": {
        "run_km": 32.5,
        "ride_km": 0,
        "strength_sessions": 3,
        "total_moving_time_min": 420,
        "total_calories": 2800,
        "total_elevation_m": 450,
        "session_counts": {"Run": 4, "WeightTraining": 3},
        "heart_rate_data": {
            "avg_hr_weekly": 145,
            "max_hr_overall": 178,
            "activities_with_hr": 7,
            "hr_by_activity": [...]
        }
    },
    "active_goals": [
        {
            "id": "uuid",
            "goal_type": "weight_loss",
            "target_value": 75.0,
            "target_date": "2024-03-01",
            "description": "Lose 5kg by March",
            "status": "active",
            "created_at": "2024-01-01"
        }
    ]
}
```

### EvalOutput Schema (Existing)

```python
class EvalOutput(BaseModel):
    overall_score: int = Field(..., ge=1, le=10)
    summary: str = Field(..., min_length=50, max_length=500)
    wins: List[str] = Field(..., min_length=1)
    misses: List[str]
    nutrition_analysis: NutritionAnalysis
    training_analysis: TrainingAnalysis
    recommendations: List[Recommendation] = Field(..., max_length=5)
    data_confidence: float = Field(..., ge=0.0, le=1.0)
```

### Evidence Map Structure

```python
{
    "week_id": "uuid",
    "overall_score": {
        "value": 8,
        "based_on": ["nutrition_analysis", "training_analysis", "data_confidence"]
    },
    "nutrition_analysis": {
        "avg_daily_calories": 1975,
        "avg_protein_g": 148,
        "avg_adherence_score": 8.5,
        "source_records": ["daily_log_uuid_1", "daily_log_uuid_2", ...]
    },
    "training_analysis": {
        "total_run_km": 32.5,
        "strength_sessions": 3,
        "total_active_minutes": 420,
        "source_records": ["strava_activity_uuid_1", "strava_activity_uuid_2", ...]
    },
    "goal_progress": {
        "goals_evaluated": ["goal_uuid_1"],
        "source_records": ["goal_uuid_1", "weekly_measurement_uuid"]
    }
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Contract includes activities using correct week_id

*For any* WeeklyMeasurement with associated StravaActivity records, when building a contract using that WeeklyMeasurement.id, the contract's strava_aggregates field should include data from all StravaActivity records where week_id matches the WeeklyMeasurement.id.

**Validates: Requirements 1.1, 1.4**

### Property 2: Contract contains all required data fields

*For any* week_id, when building a contract, the contract should contain all required top-level fields (week, targets, measurements, daily_logs, strava_aggregates, active_goals) with either populated data or null values.

**Validates: Requirements 4.1, 4.2, 4.4, 4.5, 4.6**

### Property 3: Contract includes all daily logs for the week

*For any* week with DailyLog records, when building a contract, the contract's daily_logs array should contain exactly the DailyLog records where log_date falls within [week_start, week_start + 7 days).

**Validates: Requirements 4.3**

### Property 4: All evaluations include data_confidence score

*For any* evaluation output, the EvalOutput should contain a data_confidence field with a value between 0.0 and 1.0 inclusive.

**Validates: Requirements 3.4**

### Property 5: All evaluations have at most 5 recommendations

*For any* evaluation output, the recommendations array should contain at most 5 items.

**Validates: Requirements 5.5**

### Property 6: Contract hashing is deterministic

*For any* contract, serializing and hashing the contract twice should produce identical hash values.

**Validates: Requirements 6.5**

### Property 7: Contract hash is stored with evaluations

*For any* completed evaluation, the WeeklyEval record should contain a non-null input_hash field computed from the contract.

**Validates: Requirements 6.1, 6.3**

### Property 8: Evidence map is stored with evaluations

*For any* completed evaluation, the WeeklyEval record should contain an evidence_map_json field with record types and primary keys linking evaluation claims to source data.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

### Property 9: Schema validation rejects invalid outputs

*For any* data that violates the EvalOutput schema constraints (e.g., overall_score outside 1-10 range, summary too short/long, data_confidence outside 0.0-1.0), validation should fail and raise an error.

**Validates: Requirements 3.3**

### Property 10: API responses maintain required structure

*For any* successful evaluation API response, the response should contain all required fields: week_start, week_id, evaluation, generated_at, and input_hash.

**Validates: Requirements 9.4**

### Property 11: ValueError raised for validation failures

*For any* validation failure (invalid contract, invalid LLM response, missing data), the service should raise a ValueError with a descriptive error message.

**Validates: Requirements 8.5**

## Error Handling

### LangChain Initialization Errors

```python
try:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

if not LANGCHAIN_AVAILABLE:
    raise ImportError(
        "LangChain is not available. Install with: "
        "uv pip install langchain-core langchain-ollama langchain-openai"
    )
```

**Logging**: Log backend type, endpoint URL, model name, and error details.

### LLM Invocation Errors

```python
try:
    result = await self.llm_with_structure.ainvoke(messages)
except Exception as e:
    logger.error(
        f"LLM invocation failed: {e}",
        extra={
            "backend": self.settings.LLM_TYPE,
            "model": self.settings.OLLAMA_MODEL,
            "endpoint": self.settings.llm_base_url,
            "contract_hash": hash_contract(contract)
        }
    )
    raise ValueError(f"LLM evaluation failed: {str(e)}")
```

**Logging**: Log request parameters, contract hash, error response, and retry attempts.

### Schema Validation Errors

```python
for attempt in range(3):
    try:
        result = await self.llm_with_structure.ainvoke(messages)
        return result
    except ValidationError as e:
        logger.warning(
            f"Validation failed (attempt {attempt + 1}/3): {e}",
            extra={
                "raw_response": str(result) if 'result' in locals() else None,
                "validation_errors": e.errors()
            }
        )
        if attempt == 2:
            raise ValueError(
                f"Validation failed after 3 attempts. "
                f"Errors: {e.errors()}"
            )
```

**Logging**: Log raw LLM response, validation errors, and retry attempts.

### Contract Building Errors

```python
def build_contract(week_id: str, db: Session) -> dict:
    weekly_measurement = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == week_id
    ).first()
    
    if not weekly_measurement:
        logger.error(
            f"Contract building failed: No WeeklyMeasurement found",
            extra={"week_id": week_id}
        )
        raise ValueError(f"No WeeklyMeasurement found for week_id: {week_id}")
    
    # Log data source availability
    logger.info(
        "Building contract",
        extra={
            "week_id": week_id,
            "has_targets": plan_targets is not None,
            "daily_logs_count": len(daily_logs),
            "has_strava_data": bool(strava_aggregates),
            "active_goals_count": len(active_goals)
        }
    )
```

**Logging**: Log which data sources are missing or empty.

### Error Response Format

All API errors return consistent structure:

```python
{
    "detail": "Descriptive error message",
    "error_type": "ValidationError|ValueError|HTTPException",
    "context": {
        "week_id": "uuid",
        "week_start": "2024-01-01",
        "missing_data": ["targets", "strava_activities"]
    }
}
```

## Testing Strategy

### Dual Testing Approach

The testing strategy combines unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, error conditions, and integration points
- **Property tests**: Verify universal properties across all inputs through randomization

Both approaches are complementary and necessary. Unit tests catch concrete bugs in specific scenarios, while property tests verify general correctness across a wide input space.

### Property-Based Testing Configuration

**Library**: Use `hypothesis` for Python property-based testing

**Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: langchain-evaluation-system, Property {number}: {property_text}`

**Example Property Test**:

```python
from hypothesis import given, strategies as st
import pytest

# Feature: langchain-evaluation-system, Property 6: Contract hashing is deterministic
@given(
    week_id=st.uuids(),
    weight=st.floats(min_value=50, max_value=150),
    calories=st.integers(min_value=1000, max_value=4000)
)
@pytest.mark.property_test
def test_contract_hashing_deterministic(week_id, weight, calories, db_session):
    """For any contract, hashing twice produces identical results."""
    # Create test data
    measurement = create_weekly_measurement(week_id, weight)
    daily_log = create_daily_log(week_id, calories)
    
    # Build contract twice
    contract1 = build_contract(str(week_id), db_session)
    contract2 = build_contract(str(week_id), db_session)
    
    # Hash should be identical
    hash1 = hash_contract(contract1)
    hash2 = hash_contract(contract2)
    
    assert hash1 == hash2
```

### Unit Testing Focus Areas

**Specific Examples**:
- Evaluate a week with complete data (7 daily logs, Strava activities, goals)
- Evaluate a week with partial data (3 daily logs, no Strava activities)
- Evaluate a week with no data (empty contract)

**Edge Cases**:
- Week with exactly 5 recommendations (boundary test)
- Week with data_confidence = 0.0 and 1.0 (boundary test)
- Week with overall_score = 1 and 10 (boundary test)
- Empty strava_aggregates with null values
- Missing WeeklyMeasurement for week_start

**Error Conditions**:
- LangChain import failure
- LLM backend unavailable
- Invalid JSON response from LLM
- Schema validation failure after retries
- Missing week_id in database

**Integration Points**:
- API endpoint calls with database setup
- LangChain initialization with different backends (Ollama, LM Studio)
- Evidence collection with real database records
- Cache hit/miss behavior with idempotency

### Test Data Generators

```python
# Hypothesis strategies for property tests
@st.composite
def weekly_measurement_strategy(draw):
    return WeeklyMeasurement(
        id=str(draw(st.uuids())),
        week_start=draw(st.dates(min_value=date(2024, 1, 1))),
        weight_kg=draw(st.floats(min_value=50, max_value=150)),
        body_fat_pct=draw(st.floats(min_value=5, max_value=40)),
        sleep_avg_hrs=draw(st.floats(min_value=4, max_value=12)),
        rhr_bpm=draw(st.integers(min_value=40, max_value=100)),
        energy_level_avg=draw(st.floats(min_value=1, max_value=10))
    )

@st.composite
def daily_log_strategy(draw, week_id):
    return DailyLog(
        id=str(draw(st.uuids())),
        log_date=draw(st.dates()),
        fasting_hours=draw(st.floats(min_value=0, max_value=24)),
        calories_in=draw(st.integers(min_value=0, max_value=5000)),
        protein_g=draw(st.integers(min_value=0, max_value=300)),
        adherence_score=draw(st.integers(min_value=1, max_value=10))
    )
```

### Test Coverage Goals

- **Line coverage**: >90% for all service modules
- **Branch coverage**: >85% for error handling paths
- **Property tests**: All 11 correctness properties implemented
- **Integration tests**: All 3 API endpoints with database


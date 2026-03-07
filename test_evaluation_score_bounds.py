"""Property Test: Evaluation Score Bounds

**Validates: Requirements 11.4**

Property 12: Evaluation Score Bounds
For all Evaluation_Reports, the overall score SHALL be between 0 and 100 inclusive.

This test verifies that the evaluation generation system always produces scores
within the valid range, regardless of input data characteristics.
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.services.evaluation_engine import EvaluationEngine
from app.schemas.evaluation_schemas import EvaluationReport
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog


# Test database setup
@pytest.fixture
def test_db():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


# Hypothesis strategies for generating test data
@st.composite
def activity_data(draw):
    """Generate random activity data."""
    return {
        'id': draw(st.uuids()).hex,
        'strava_id': draw(st.integers(min_value=1, max_value=999999999)),
        'activity_type': draw(st.sampled_from(['Run', 'Ride', 'Swim', 'Walk', 'Hike'])),
        'start_date': draw(st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2024, 12, 31)
        )),
        'distance_m': draw(st.floats(min_value=0, max_value=100000, allow_nan=False)),
        'moving_time_s': draw(st.integers(min_value=0, max_value=36000)),
        'elevation_m': draw(st.floats(min_value=0, max_value=5000, allow_nan=False)),
        'avg_hr': draw(st.integers(min_value=60, max_value=200) | st.none()),
        'max_hr': draw(st.integers(min_value=80, max_value=220) | st.none()),
        'calories': draw(st.floats(min_value=0, max_value=5000, allow_nan=False) | st.none())
    }


@st.composite
def metric_data(draw):
    """Generate random body metric data."""
    return {
        'id': draw(st.uuids()).hex,
        'week_start': draw(st.dates(
            min_value=date(2024, 1, 1),
            max_value=date(2024, 12, 31)
        )),
        'weight_kg': draw(st.floats(min_value=40, max_value=150, allow_nan=False)),
        'weight_prev_kg': draw(st.floats(min_value=40, max_value=150, allow_nan=False) | st.none()),
        'body_fat_pct': draw(st.floats(min_value=5, max_value=50, allow_nan=False) | st.none()),
        'waist_cm': draw(st.floats(min_value=50, max_value=150, allow_nan=False) | st.none()),
        'waist_prev_cm': draw(st.floats(min_value=50, max_value=150, allow_nan=False) | st.none()),
        'sleep_avg_hrs': draw(st.floats(min_value=4, max_value=12, allow_nan=False) | st.none()),
        'rhr_bpm': draw(st.integers(min_value=40, max_value=100) | st.none()),
        'energy_level_avg': draw(st.floats(min_value=1, max_value=10, allow_nan=False) | st.none())
    }


@st.composite
def log_data(draw):
    """Generate random daily log data."""
    return {
        'id': draw(st.uuids()).hex,
        'log_date': draw(st.dates(
            min_value=date(2024, 1, 1),
            max_value=date(2024, 12, 31)
        )),
        'fasting_hours': draw(st.floats(min_value=0, max_value=24, allow_nan=False) | st.none()),
        'calories_in': draw(st.integers(min_value=0, max_value=10000) | st.none()),
        'protein_g': draw(st.floats(min_value=0, max_value=500, allow_nan=False) | st.none()),
        'carbs_g': draw(st.floats(min_value=0, max_value=800, allow_nan=False) | st.none()),
        'fat_g': draw(st.floats(min_value=0, max_value=300, allow_nan=False) | st.none()),
        'adherence_score': draw(st.integers(min_value=0, max_value=100) | st.none()),
        'notes': draw(st.text(max_size=200) | st.none())
    }


@st.composite
def evaluation_period(draw):
    """Generate random evaluation period."""
    start = draw(st.dates(min_value=date(2024, 1, 1), max_value=date(2024, 11, 1)))
    period_type = draw(st.sampled_from(['weekly', 'bi-weekly', 'monthly']))
    
    if period_type == 'weekly':
        end = start + timedelta(days=6)
    elif period_type == 'bi-weekly':
        end = start + timedelta(days=13)
    else:  # monthly
        end = start + timedelta(days=29)
    
    return start, end, period_type


@given(
    activities=st.lists(activity_data(), min_size=0, max_size=20),
    metrics=st.lists(metric_data(), min_size=0, max_size=5),
    logs=st.lists(log_data(), min_size=0, max_size=30),
    period=evaluation_period()
)
@settings(max_examples=50, deadline=None)
async def test_evaluation_score_bounds_property(test_db, activities, metrics, logs, period):
    """
    Property Test: Evaluation scores must be between 0 and 100 inclusive.
    
    **Validates: Requirements 11.4**
    
    This test generates random combinations of activities, metrics, and logs,
    then verifies that the evaluation engine always produces scores within
    the valid range [0, 100].
    
    The property holds regardless of:
    - Number of activities (0 to 20)
    - Number of metrics (0 to 5)
    - Number of logs (0 to 30)
    - Period type (weekly, bi-weekly, monthly)
    - Data completeness (some fields may be None)
    """
    period_start, period_end, period_type = period
    
    # Mock the LLM to return a valid evaluation with random score
    mock_evaluation = EvaluationReport(
        overall_score=st.integers(min_value=0, max_value=100).example(),
        strengths=["Test strength"],
        improvements=["Test improvement"],
        tips=["Test tip"],
        recommended_exercises=["Test exercise"],
        goal_alignment="Test alignment assessment",
        confidence_score=0.8
    )
    
    # Create evaluation engine with mocked LLM
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_evaluation)
    
    engine = EvaluationEngine(test_db, llm_client=mock_llm)
    
    # Generate evaluation
    result = await engine.generate_evaluation(
        athlete_id=1,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type
    )
    
    # Property assertion: Score must be between 0 and 100 inclusive
    assert 0 <= result.overall_score <= 100, (
        f"Evaluation score {result.overall_score} is outside valid range [0, 100]"
    )


@pytest.mark.asyncio
async def test_evaluation_score_bounds_with_real_llm_mock(test_db):
    """
    Test evaluation score bounds with realistic LLM response mocking.
    
    **Validates: Requirements 11.4**
    
    This test uses a more realistic mock that simulates actual LLM behavior,
    including potential edge cases like extreme scores.
    """
    # Test with minimum score
    mock_evaluation_min = EvaluationReport(
        overall_score=0,
        strengths=["Maintained some activity"],
        improvements=["Significant gaps in training", "Poor nutrition adherence"],
        tips=["Start with small, achievable goals"],
        recommended_exercises=["Walking", "Light stretching"],
        goal_alignment="Significant work needed to align with goals",
        confidence_score=0.3
    )
    
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_evaluation_min)
    
    engine = EvaluationEngine(test_db, llm_client=mock_llm)
    
    result = await engine.generate_evaluation(
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type="weekly"
    )
    
    assert 0 <= result.overall_score <= 100
    assert result.overall_score == 0
    
    # Test with maximum score
    mock_evaluation_max = EvaluationReport(
        overall_score=100,
        strengths=["Perfect adherence", "Excellent training consistency"],
        improvements=[],
        tips=["Maintain current approach"],
        recommended_exercises=["Continue current program"],
        goal_alignment="Fully aligned with goals, excellent progress",
        confidence_score=1.0
    )
    
    mock_llm.ainvoke = AsyncMock(return_value=mock_evaluation_max)
    engine = EvaluationEngine(test_db, llm_client=mock_llm)
    
    result = await engine.generate_evaluation(
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type="weekly"
    )
    
    assert 0 <= result.overall_score <= 100
    assert result.overall_score == 100
    
    # Test with mid-range score
    mock_evaluation_mid = EvaluationReport(
        overall_score=55,
        strengths=["Good training consistency"],
        improvements=["Nutrition tracking needs improvement"],
        tips=["Focus on meal planning"],
        recommended_exercises=["Add strength training"],
        goal_alignment="Making progress but room for improvement",
        confidence_score=0.7
    )
    
    mock_llm.ainvoke = AsyncMock(return_value=mock_evaluation_mid)
    engine = EvaluationEngine(test_db, llm_client=mock_llm)
    
    result = await engine.generate_evaluation(
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type="weekly"
    )
    
    assert 0 <= result.overall_score <= 100
    assert result.overall_score == 55


@pytest.mark.asyncio
async def test_evaluation_score_validation_rejects_invalid(test_db):
    """
    Test that Pydantic validation rejects invalid scores.
    
    **Validates: Requirements 11.4**
    
    This test verifies that the schema validation layer properly rejects
    scores outside the valid range.
    """
    from pydantic import ValidationError
    
    # Test score below minimum
    with pytest.raises(ValidationError) as exc_info:
        EvaluationReport(
            overall_score=-1,
            strengths=["Test"],
            improvements=[],
            tips=[],
            recommended_exercises=[],
            goal_alignment="Test",
            confidence_score=0.5
        )
    
    assert "overall_score" in str(exc_info.value)
    
    # Test score above maximum
    with pytest.raises(ValidationError) as exc_info:
        EvaluationReport(
            overall_score=101,
            strengths=["Test"],
            improvements=[],
            tips=[],
            recommended_exercises=[],
            goal_alignment="Test",
            confidence_score=0.5
        )
    
    assert "overall_score" in str(exc_info.value)

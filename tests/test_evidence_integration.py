"""
Integration test for evidence collection in evaluation workflow
Tests that evidence_map_json is properly stored and retrieved through the full evaluation flow

Validates Requirement 7.4: Store evidence_map_json with every WeeklyEval record
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.models.strava_activity import StravaActivity
from app.models.athlete_goal import AthleteGoal, GoalStatus
from app.services.eval_service import EvaluationService
from app.schemas.eval_output import EvalOutput, NutritionAnalysis, TrainingAnalysis, Recommendation
from sqlalchemy.orm import Session


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_eval_output():
    """Create a mock EvalOutput for testing."""
    return EvalOutput(
        overall_score=8,
        summary="Good week with solid nutrition adherence and training volume.",
        wins=["Met protein targets", "Completed all strength sessions"],
        misses=["Missed one run session"],
        nutrition_analysis=NutritionAnalysis(
            avg_daily_calories=2000,
            avg_protein_g=150,
            avg_adherence_score=8.5,
            commentary="Excellent protein intake and calorie control."
        ),
        training_analysis=TrainingAnalysis(
            total_run_km=25.0,
            strength_sessions=3,
            total_active_minutes=300,
            commentary="Good training volume, slightly below run target."
        ),
        recommendations=[
            Recommendation(
                area="Training",
                action="Add one more run session next week",
                priority=1
            )
        ],
        data_confidence=0.95
    )


def test_evidence_stored_in_weekly_eval(db_session: Session, mock_eval_output):
    """
    Test that evidence_map_json is stored with WeeklyEval record.
    
    Validates Requirement 7.4: Store evidence_map_json with every WeeklyEval record
    """
    # Create WeeklyMeasurement
    week_start = date.today()
    measurement = WeeklyMeasurement(
        week_start=week_start,
        weight_kg=75.0,
        body_fat_pct=15.0,
        waist_cm=85.0,
        sleep_avg_hrs=7.5,
        rhr_bpm=60,
        energy_level_avg=8.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(measurement)
    db_session.commit()
    db_session.refresh(measurement)
    
    week_id = str(measurement.id)
    
    # Create DailyLog records
    for i in range(3):
        log = DailyLog(
            log_date=week_start + timedelta(days=i),
            fasting_hours=16.0,
            calories_in=2000,
            protein_g=150,
            carbs_g=200,
            fat_g=70,
            adherence_score=85,
            notes="Good day",
            week_id=week_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(log)
    db_session.commit()
    
    # Create StravaActivity records
    for i in range(2):
        activity = StravaActivity(
            strava_id=2000 + i,
            activity_type="Run",
            start_date=datetime.now(),
            moving_time_s=3600,
            distance_m=10000,
            elevation_m=100,
            avg_hr=150,
            max_hr=170,
            calories=500,
            raw_json='{"test": "data"}',
            week_id=week_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(activity)
    db_session.commit()
    
    # Create AthleteGoal
    goal = AthleteGoal(
        goal_type="weight_loss",
        target_value=70.0,
        target_date=date.today() + timedelta(days=90),
        description="Lose 5kg in 3 months",
        status=GoalStatus.ACTIVE.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(goal)
    db_session.commit()
    
    # Mock LangChainEvaluationService
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Create evaluation service and evaluate
        eval_service = EvaluationService(db_session)
        import asyncio
        weekly_eval = asyncio.run(eval_service.evaluate_week(week_id))
        
        # Verify evidence_map_json is stored
        assert weekly_eval.evidence_map_json is not None
        
        # Verify evidence_map structure
        evidence = weekly_eval.evidence_map_json
        assert evidence["week_id"] == week_id
        
        # Verify nutrition_analysis evidence
        assert "nutrition_analysis" in evidence
        assert evidence["nutrition_analysis"]["record_type"] == "daily_log"
        assert len(evidence["nutrition_analysis"]["source_records"]) == 3
        
        # Verify training_analysis evidence
        assert "training_analysis" in evidence
        assert evidence["training_analysis"]["record_type"] == "strava_activity"
        assert len(evidence["training_analysis"]["source_records"]) == 2
        
        # Verify goal_progress evidence
        assert "goal_progress" in evidence
        assert evidence["goal_progress"]["record_type"] == "athlete_goal"
        assert len(evidence["goal_progress"]["goals_evaluated"]) == 1
        
        # Verify measurements evidence
        assert "measurements" in evidence
        assert evidence["measurements"]["record_type"] == "weekly_measurement"
        assert str(measurement.id) in evidence["measurements"]["source_records"]


def test_evidence_retrieved_from_database(db_session: Session, mock_eval_output):
    """
    Test that evidence_map_json is retrieved when fetching WeeklyEval from database.
    
    Validates Requirement 7.5: Evidence_map is returned in GET responses
    """
    # Create WeeklyMeasurement
    week_start = date.today()
    measurement = WeeklyMeasurement(
        week_start=week_start,
        weight_kg=75.0,
        body_fat_pct=15.0,
        waist_cm=85.0,
        sleep_avg_hrs=7.5,
        rhr_bpm=60,
        energy_level_avg=8.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(measurement)
    db_session.commit()
    db_session.refresh(measurement)
    
    week_id = str(measurement.id)
    
    # Mock LangChainEvaluationService
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Create evaluation
        eval_service = EvaluationService(db_session)
        import asyncio
        asyncio.run(eval_service.evaluate_week(week_id))
    
    # Retrieve evaluation from database
    eval_service = EvaluationService(db_session)
    retrieved_eval = eval_service.get_evaluation(week_id)
    
    # Verify evidence_map_json is retrieved
    assert retrieved_eval is not None
    assert retrieved_eval.evidence_map_json is not None
    assert retrieved_eval.evidence_map_json["week_id"] == week_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

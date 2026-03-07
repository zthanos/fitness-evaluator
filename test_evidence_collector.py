"""
Test evidence collection and storage
Tests Task 6.2: Implement evidence collection and storage

Validates Requirements:
- 7.1: Collect evidence for each evaluation claim
- 7.2: Link evaluation statements to specific database record IDs
- 7.3: Include record type and primary key for each evidence item
- 7.4: Store evidence_map_json with every WeeklyEval record
"""

import pytest
from datetime import date, datetime, timedelta
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.models.strava_activity import StravaActivity
from app.models.athlete_goal import AthleteGoal, GoalStatus
from app.services.evidence_collector import collect_evidence
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


def test_collect_evidence_with_complete_data(db_session: Session, mock_eval_output):
    """
    Test evidence collection with complete data (daily logs, activities, goals).
    
    Validates:
    - 7.1: Evidence is collected for each evaluation claim
    - 7.2: Evidence links to specific database record IDs
    - 7.3: Evidence includes record type and primary key for each item
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
    
    # Create DailyLog records (3 days)
    daily_log_ids = []
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
        db_session.refresh(log)
        daily_log_ids.append(str(log.id))
    
    # Create StravaActivity records (2 activities)
    activity_ids = []
    for i in range(2):
        activity = StravaActivity(
            strava_id=1000 + i,
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
        db_session.refresh(activity)
        activity_ids.append(str(activity.id))
    
    # Create AthleteGoal record
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
    db_session.refresh(goal)
    goal_id = str(goal.id)
    
    # Collect evidence
    evidence = collect_evidence(mock_eval_output, week_id, db_session)
    
    # Validate evidence structure
    assert evidence is not None
    assert evidence["week_id"] == week_id
    
    # Validate overall_score evidence
    assert "overall_score" in evidence
    assert evidence["overall_score"]["value"] == 8
    assert "based_on" in evidence["overall_score"]
    
    # Validate nutrition_analysis evidence (Requirement 7.2, 7.3)
    assert "nutrition_analysis" in evidence
    assert evidence["nutrition_analysis"]["record_type"] == "daily_log"
    assert "source_records" in evidence["nutrition_analysis"]
    assert len(evidence["nutrition_analysis"]["source_records"]) == 3
    assert all(log_id in evidence["nutrition_analysis"]["source_records"] for log_id in daily_log_ids)
    
    # Validate training_analysis evidence (Requirement 7.2, 7.3)
    assert "training_analysis" in evidence
    assert evidence["training_analysis"]["record_type"] == "strava_activity"
    assert "source_records" in evidence["training_analysis"]
    assert len(evidence["training_analysis"]["source_records"]) == 2
    assert all(activity_id in evidence["training_analysis"]["source_records"] for activity_id in activity_ids)
    
    # Validate goal_progress evidence (Requirement 7.2, 7.3)
    assert "goal_progress" in evidence
    assert evidence["goal_progress"]["record_type"] == "athlete_goal"
    assert "goals_evaluated" in evidence["goal_progress"]
    assert goal_id in evidence["goal_progress"]["goals_evaluated"]
    assert "source_records" in evidence["goal_progress"]
    assert goal_id in evidence["goal_progress"]["source_records"]
    assert str(measurement.id) in evidence["goal_progress"]["source_records"]
    
    # Validate measurements evidence (Requirement 7.2, 7.3)
    assert "measurements" in evidence
    assert evidence["measurements"]["record_type"] == "weekly_measurement"
    assert "source_records" in evidence["measurements"]
    assert str(measurement.id) in evidence["measurements"]["source_records"]


def test_collect_evidence_with_partial_data(db_session: Session, mock_eval_output):
    """
    Test evidence collection with partial data (no activities, no goals).
    
    Validates:
    - Evidence collection handles missing data gracefully
    - Empty source_records arrays are included for missing data
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
    
    # Create only 1 DailyLog record
    log = DailyLog(
        log_date=week_start,
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
    db_session.refresh(log)
    
    # No StravaActivity or AthleteGoal records
    
    # Collect evidence
    evidence = collect_evidence(mock_eval_output, week_id, db_session)
    
    # Validate evidence structure
    assert evidence is not None
    assert evidence["week_id"] == week_id
    
    # Validate nutrition_analysis has 1 record
    assert len(evidence["nutrition_analysis"]["source_records"]) == 1
    assert str(log.id) in evidence["nutrition_analysis"]["source_records"]
    
    # Validate training_analysis has empty source_records
    assert len(evidence["training_analysis"]["source_records"]) == 0
    
    # Validate goal_progress has empty goals_evaluated
    assert len(evidence["goal_progress"]["goals_evaluated"]) == 0


def test_collect_evidence_raises_error_for_missing_measurement(db_session: Session, mock_eval_output):
    """
    Test that collect_evidence raises ValueError when WeeklyMeasurement not found.
    
    Validates:
    - Error handling for missing WeeklyMeasurement
    """
    # Use a non-existent week_id
    fake_week_id = "00000000-0000-0000-0000-000000000000"
    
    # Attempt to collect evidence
    with pytest.raises(ValueError, match="No WeeklyMeasurement found"):
        collect_evidence(mock_eval_output, fake_week_id, db_session)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test AthleteGoal integration in contract building
Tests Requirement: 4.5 - Contract includes active AthleteGoal records
"""

import pytest
from datetime import date, datetime, timedelta
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.athlete_goal import AthleteGoal, GoalStatus, GoalType
from app.services.prompt_engine import build_contract
from sqlalchemy.orm import Session


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_contract_includes_active_goals(db_session: Session):
    """
    Test that build_contract includes active AthleteGoal records.
    
    Validates Requirement 4.5: Contract includes active AthleteGoal records
    """
    # Create a WeeklyMeasurement
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
    
    # Create active goals
    goal1 = AthleteGoal(
        goal_type=GoalType.WEIGHT_LOSS.value,
        target_value=70.0,
        target_date=date.today() + timedelta(days=90),
        description="Lose 5kg in 3 months",
        status=GoalStatus.ACTIVE.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    goal2 = AthleteGoal(
        goal_type=GoalType.PERFORMANCE.value,
        target_value=None,
        target_date=date.today() + timedelta(days=60),
        description="Run 5K under 25 minutes",
        status=GoalStatus.ACTIVE.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    # Create a completed goal (should not be included)
    goal3 = AthleteGoal(
        goal_type=GoalType.STRENGTH.value,
        target_value=100.0,
        target_date=date.today() - timedelta(days=30),
        description="Bench press 100kg",
        status=GoalStatus.COMPLETED.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    db_session.add_all([goal1, goal2, goal3])
    db_session.commit()
    
    # Build contract
    contract = build_contract(str(measurement.id), db_session)
    
    # Verify active_goals field exists
    assert "active_goals" in contract, "Contract should include active_goals field"
    
    # Verify only active goals are included
    active_goals = contract["active_goals"]
    assert len(active_goals) >= 2, f"Expected at least 2 active goals, got {len(active_goals)}"
    
    # Verify goal structure - find our test goals
    goal_descriptions = [g["description"] for g in active_goals]
    assert "Lose 5kg in 3 months" in goal_descriptions
    assert "Run 5K under 25 minutes" in goal_descriptions
    assert "Bench press 100kg" not in goal_descriptions  # Completed goal should not be included
    
    # Verify required fields are present
    for goal in active_goals:
        assert "id" in goal
        assert "goal_type" in goal
        assert "target_value" in goal
        assert "target_date" in goal
        assert "description" in goal
        assert "status" in goal
        assert "created_at" in goal
        assert goal["status"] == GoalStatus.ACTIVE.value


def test_contract_with_no_active_goals(db_session: Session):
    """
    Test that build_contract handles empty active_goals correctly.
    
    Validates Requirement 4.5: Handle empty active_goals with empty array
    """
    # Create a WeeklyMeasurement
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
    
    # Build contract without any goals
    contract = build_contract(str(measurement.id), db_session)
    
    # Verify active_goals field exists and is empty
    assert "active_goals" in contract, "Contract should include active_goals field"
    assert contract["active_goals"] == [], "active_goals should be an empty array when no active goals exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

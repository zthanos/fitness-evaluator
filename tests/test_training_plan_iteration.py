"""
Unit tests for Training Plan iteration support.

Tests iterate_plan and update_plan methods.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from app.models.base import Base
from app.models import Athlete
from app.schemas import TrainingSession, TrainingWeek, TrainingPlan
from app.services.training_plan_engine import TrainingPlanEngine


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def engine(db_session):
    """Create a TrainingPlanEngine instance."""
    return TrainingPlanEngine(db=db_session)


@pytest.fixture
def athlete(db_session):
    """Create a test athlete."""
    athlete = Athlete(name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    return athlete


@pytest.fixture
def sample_plan(athlete):
    """Create a sample training plan dataclass."""
    session1 = TrainingSession(
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy",
        description="Easy pace, focus on form"
    )
    
    session2 = TrainingSession(
        day_of_week=3,
        session_type="tempo_run",
        duration_minutes=60,
        intensity="moderate",
        description="Tempo intervals"
    )
    
    week1 = TrainingWeek(
        week_number=1,
        focus="Base building",
        volume_target=5.0,
        sessions=[session1, session2]
    )
    
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Marathon Training",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="draft",
        weeks=[week1]
    )
    
    return plan


def test_update_plan_preserves_id_and_created_at(engine, sample_plan):
    """Test that update_plan preserves plan ID and created_at."""
    # Save initial plan
    plan_id = engine.save_plan(sample_plan)
    
    # Retrieve plan to get created_at
    original_plan = engine.get_plan(plan_id, sample_plan.user_id)
    original_created_at = original_plan.created_at
    
    # Modify the plan
    original_plan.title = "Updated Marathon Training"
    original_plan.status = "active"
    
    # Update the plan
    updated_id = engine.update_plan(original_plan)
    
    # Verify ID is the same
    assert updated_id == plan_id
    
    # Retrieve updated plan
    updated_plan = engine.get_plan(plan_id, sample_plan.user_id)
    
    # Verify changes were applied
    assert updated_plan.title == "Updated Marathon Training"
    assert updated_plan.status == "active"
    
    # Verify ID and created_at are preserved
    assert updated_plan.id == plan_id
    assert updated_plan.created_at == original_created_at


def test_update_plan_with_new_weeks(engine, sample_plan):
    """Test updating a plan with different weeks."""
    # Save initial plan
    plan_id = engine.save_plan(sample_plan)
    
    # Retrieve plan
    original_plan = engine.get_plan(plan_id, sample_plan.user_id)
    
    # Add a new week
    new_session = TrainingSession(
        day_of_week=2,
        session_type="interval",
        duration_minutes=50,
        intensity="hard",
        description="Speed work"
    )
    
    new_week = TrainingWeek(
        week_number=2,
        focus="Intensity",
        volume_target=6.0,
        sessions=[new_session]
    )
    
    original_plan.weeks.append(new_week)
    
    # Update the plan
    engine.update_plan(original_plan)
    
    # Retrieve updated plan
    updated_plan = engine.get_plan(plan_id, sample_plan.user_id)
    
    # Verify new week was added
    assert len(updated_plan.weeks) == 2
    assert updated_plan.weeks[1].week_number == 2
    assert updated_plan.weeks[1].focus == "Intensity"


def test_update_plan_with_user_scoping(engine, sample_plan, db_session):
    """Test that update_plan enforces user_id scoping."""
    # Save plan for user 1
    plan_id = engine.save_plan(sample_plan)
    
    # Create another athlete
    athlete2 = Athlete(name="Other Athlete", email="other@example.com")
    db_session.add(athlete2)
    db_session.commit()
    
    # Retrieve plan
    plan = engine.get_plan(plan_id, sample_plan.user_id)
    
    # Try to update with wrong user_id
    plan.user_id = athlete2.id
    plan.title = "Hacked Plan"
    
    # Should raise ValueError (plan not found for this user)
    with pytest.raises(ValueError, match="Plan not found"):
        engine.update_plan(plan)


def test_update_plan_without_id_raises_error(engine, sample_plan):
    """Test that update_plan raises error if plan has no ID."""
    # Try to update a plan without an ID
    with pytest.raises(ValueError, match="Cannot update plan without an ID"):
        engine.update_plan(sample_plan)


def test_update_plan_replaces_all_weeks(engine, sample_plan):
    """Test that update_plan replaces all weeks and sessions."""
    # Save initial plan with 1 week
    plan_id = engine.save_plan(sample_plan)
    
    # Retrieve plan
    plan = engine.get_plan(plan_id, sample_plan.user_id)
    assert len(plan.weeks) == 1
    assert len(plan.weeks[0].sessions) == 2
    
    # Replace with completely different weeks
    new_session = TrainingSession(
        day_of_week=5,
        session_type="long_run",
        duration_minutes=120,
        intensity="easy",
        description="Long slow distance"
    )
    
    new_week = TrainingWeek(
        week_number=1,
        focus="Endurance",
        volume_target=10.0,
        sessions=[new_session]
    )
    
    plan.weeks = [new_week]
    
    # Update the plan
    engine.update_plan(plan)
    
    # Retrieve updated plan
    updated_plan = engine.get_plan(plan_id, sample_plan.user_id)
    
    # Verify old weeks/sessions are gone
    assert len(updated_plan.weeks) == 1
    assert len(updated_plan.weeks[0].sessions) == 1
    assert updated_plan.weeks[0].focus == "Endurance"
    assert updated_plan.weeks[0].sessions[0].session_type == "long_run"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

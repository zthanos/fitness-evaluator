"""
Unit tests for Training Plan goal linking.

Tests that plans can be linked to goals and goal information is accessible.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from app.models.base import Base
from app.models import Athlete, AthleteGoal
from app.schemas import TrainingPlan
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
def goal(db_session, athlete):
    """Create a test goal."""
    goal = AthleteGoal(
        athlete_id=str(athlete.id),
        goal_type="performance",
        target_value=240.0,  # 4 hours in minutes
        target_date=date(2024, 6, 1),
        description="Run a sub-4 hour marathon",
        status="active"
    )
    db_session.add(goal)
    db_session.commit()
    return goal


def test_save_plan_with_goal_id(engine, athlete, goal):
    """Test saving a plan with a goal_id."""
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Marathon Training",
        sport="running",
        goal_id=goal.id,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="draft",
        weeks=[]
    )
    
    # Save plan
    plan_id = engine.save_plan(plan)
    
    # Retrieve plan
    retrieved_plan = engine.get_plan(plan_id, athlete.id)
    
    # Verify goal_id is preserved
    assert retrieved_plan.goal_id == goal.id


def test_get_plan_includes_goal_id(engine, athlete, goal):
    """Test that get_plan returns the goal_id."""
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Cycling Plan",
        sport="cycling",
        goal_id=goal.id,
        start_date=date(2024, 2, 1),
        end_date=date(2024, 5, 1),
        status="active",
        weeks=[]
    )
    
    plan_id = engine.save_plan(plan)
    retrieved_plan = engine.get_plan(plan_id, athlete.id)
    
    assert retrieved_plan.goal_id == goal.id


def test_save_plan_without_goal_id(engine, athlete):
    """Test saving a plan without a goal_id."""
    plan = TrainingPlan(
        user_id=athlete.id,
        title="General Fitness",
        sport="running",
        goal_id=None,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="draft",
        weeks=[]
    )
    
    # Save plan
    plan_id = engine.save_plan(plan)
    
    # Retrieve plan
    retrieved_plan = engine.get_plan(plan_id, athlete.id)
    
    # Verify goal_id is None
    assert retrieved_plan.goal_id is None


def test_goal_deletion_sets_null(engine, athlete, goal, db_session):
    """Test that deleting a goal sets goal_id to NULL in plans."""
    # Create plan linked to goal
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Marathon Training",
        sport="running",
        goal_id=goal.id,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="draft",
        weeks=[]
    )
    
    plan_id = engine.save_plan(plan)
    
    # Verify goal_id is set
    retrieved_plan = engine.get_plan(plan_id, athlete.id)
    assert retrieved_plan.goal_id == goal.id
    
    # Delete the goal
    db_session.delete(goal)
    db_session.commit()
    
    # Retrieve plan again
    retrieved_plan = engine.get_plan(plan_id, athlete.id)
    
    # Verify goal_id is now None (SET NULL on delete)
    assert retrieved_plan.goal_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

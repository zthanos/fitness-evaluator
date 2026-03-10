"""
Test training plan schema creation and relationships.

This test verifies:
1. All tables can be created successfully
2. Foreign key relationships are correct
3. Indexes are created
4. Constraints are enforced
"""
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime
from app.models.base import Base
from app.models import (
    TrainingPlan, 
    TrainingPlanWeek, 
    TrainingPlanSession,
    FaissMetadata,
    Athlete,
    AthleteGoal,
    StravaActivity
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_tables_created(db_session):
    """Test that all training plan tables are created."""
    inspector = inspect(db_session.bind)
    tables = inspector.get_table_names()
    
    assert 'training_plans' in tables
    assert 'training_plan_weeks' in tables
    assert 'training_plan_sessions' in tables
    assert 'faiss_metadata' in tables


def test_training_plan_columns(db_session):
    """Test that training_plans table has all required columns."""
    inspector = inspect(db_session.bind)
    columns = {col['name']: col for col in inspector.get_columns('training_plans')}
    
    assert 'id' in columns
    assert 'user_id' in columns
    assert 'title' in columns
    assert 'sport' in columns
    assert 'goal_id' in columns
    assert 'start_date' in columns
    assert 'end_date' in columns
    assert 'status' in columns
    assert 'created_at' in columns
    assert 'updated_at' in columns


def test_training_plan_week_columns(db_session):
    """Test that training_plan_weeks table has all required columns."""
    inspector = inspect(db_session.bind)
    columns = {col['name']: col for col in inspector.get_columns('training_plan_weeks')}
    
    assert 'id' in columns
    assert 'plan_id' in columns
    assert 'week_number' in columns
    assert 'focus' in columns
    assert 'volume_target' in columns


def test_training_plan_session_columns(db_session):
    """Test that training_plan_sessions table has all required columns."""
    inspector = inspect(db_session.bind)
    columns = {col['name']: col for col in inspector.get_columns('training_plan_sessions')}
    
    assert 'id' in columns
    assert 'week_id' in columns
    assert 'day_of_week' in columns
    assert 'session_type' in columns
    assert 'duration_minutes' in columns
    assert 'intensity' in columns
    assert 'description' in columns
    assert 'completed' in columns
    assert 'matched_activity_id' in columns


def test_faiss_metadata_user_id_column(db_session):
    """Test that faiss_metadata table has user_id column."""
    inspector = inspect(db_session.bind)
    columns = {col['name']: col for col in inspector.get_columns('faiss_metadata')}
    
    assert 'user_id' in columns


def test_indexes_created(db_session):
    """Test that all required indexes are created."""
    inspector = inspect(db_session.bind)
    
    # Training plans indexes
    plan_indexes = {idx['name']: idx for idx in inspector.get_indexes('training_plans')}
    assert 'idx_training_plans_user_id' in plan_indexes
    assert 'idx_training_plans_status' in plan_indexes
    
    # Training plan weeks indexes
    week_indexes = {idx['name']: idx for idx in inspector.get_indexes('training_plan_weeks')}
    assert 'idx_training_plan_weeks_plan_id' in week_indexes
    
    # Training plan sessions indexes
    session_indexes = {idx['name']: idx for idx in inspector.get_indexes('training_plan_sessions')}
    assert 'idx_training_plan_sessions_week_id' in session_indexes
    assert 'idx_training_plan_sessions_completed' in session_indexes
    assert 'idx_training_plan_sessions_matched_activity' in session_indexes
    
    # Faiss metadata indexes (SQLAlchemy uses ix_ prefix for column indexes)
    faiss_indexes = {idx['name']: idx for idx in inspector.get_indexes('faiss_metadata')}
    assert 'ix_faiss_metadata_user_id' in faiss_indexes


def test_foreign_keys(db_session):
    """Test that foreign key relationships are defined."""
    inspector = inspect(db_session.bind)
    
    # Training plans foreign keys
    plan_fks = inspector.get_foreign_keys('training_plans')
    fk_columns = [fk['constrained_columns'][0] for fk in plan_fks]
    assert 'user_id' in fk_columns
    assert 'goal_id' in fk_columns
    
    # Training plan weeks foreign keys
    week_fks = inspector.get_foreign_keys('training_plan_weeks')
    fk_columns = [fk['constrained_columns'][0] for fk in week_fks]
    assert 'plan_id' in fk_columns
    
    # Training plan sessions foreign keys
    session_fks = inspector.get_foreign_keys('training_plan_sessions')
    fk_columns = [fk['constrained_columns'][0] for fk in session_fks]
    assert 'week_id' in fk_columns
    assert 'matched_activity_id' in fk_columns


def test_create_training_plan(db_session):
    """Test creating a complete training plan with weeks and sessions."""
    # Create an athlete first
    athlete = Athlete(
        name="Test Athlete",
        email="test@example.com"
    )
    db_session.add(athlete)
    db_session.commit()
    
    # Create a training plan
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Marathon Training",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active"
    )
    db_session.add(plan)
    db_session.commit()
    
    # Create a week
    week = TrainingPlanWeek(
        plan_id=plan.id,
        week_number=1,
        focus="Base building",
        volume_target=30.0
    )
    db_session.add(week)
    db_session.commit()
    
    # Create a session
    session = TrainingPlanSession(
        week_id=week.id,
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy",
        description="Easy pace, focus on form",
        completed=False
    )
    db_session.add(session)
    db_session.commit()
    
    # Verify relationships
    assert len(plan.weeks) == 1
    assert plan.weeks[0].week_number == 1
    assert len(plan.weeks[0].sessions) == 1
    assert plan.weeks[0].sessions[0].session_type == "easy_run"


def test_day_of_week_constraint(db_session):
    """Test that day_of_week constraint is enforced."""
    # Create an athlete and plan
    athlete = Athlete(name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Test Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        status="active"
    )
    db_session.add(plan)
    db_session.commit()
    
    week = TrainingPlanWeek(
        plan_id=plan.id,
        week_number=1,
        focus="Test"
    )
    db_session.add(week)
    db_session.commit()
    
    # Try to create a session with invalid day_of_week
    session = TrainingPlanSession(
        week_id=week.id,
        day_of_week=8,  # Invalid: should be 1-7
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy"
    )
    db_session.add(session)
    
    with pytest.raises(Exception):  # SQLite will raise an IntegrityError
        db_session.commit()


def test_cascade_delete(db_session):
    """Test that cascade delete works correctly."""
    # Create an athlete and plan with weeks and sessions
    athlete = Athlete(name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Test Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        status="active"
    )
    db_session.add(plan)
    db_session.commit()
    
    week = TrainingPlanWeek(
        plan_id=plan.id,
        week_number=1,
        focus="Test"
    )
    db_session.add(week)
    db_session.commit()
    
    session = TrainingPlanSession(
        week_id=week.id,
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy"
    )
    db_session.add(session)
    db_session.commit()
    
    plan_id = plan.id
    week_id = week.id
    session_id = session.id
    
    # Delete the plan
    db_session.delete(plan)
    db_session.commit()
    
    # Verify that weeks and sessions are also deleted
    assert db_session.query(TrainingPlan).filter_by(id=plan_id).first() is None
    assert db_session.query(TrainingPlanWeek).filter_by(id=week_id).first() is None
    assert db_session.query(TrainingPlanSession).filter_by(id=session_id).first() is None


def test_unique_constraint_plan_week(db_session):
    """Test that unique constraint on (plan_id, week_number) is enforced."""
    # Create an athlete and plan
    athlete = Athlete(name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    
    plan = TrainingPlan(
        user_id=athlete.id,
        title="Test Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        status="active"
    )
    db_session.add(plan)
    db_session.commit()
    
    # Create first week
    week1 = TrainingPlanWeek(
        plan_id=plan.id,
        week_number=1,
        focus="Test"
    )
    db_session.add(week1)
    db_session.commit()
    
    # Try to create another week with the same week_number
    week2 = TrainingPlanWeek(
        plan_id=plan.id,
        week_number=1,  # Duplicate
        focus="Test 2"
    )
    db_session.add(week2)
    
    with pytest.raises(Exception):  # SQLite will raise an IntegrityError
        db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

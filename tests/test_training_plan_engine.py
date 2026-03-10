"""
Unit tests for TrainingPlanEngine.

Tests save_plan, get_plan, and list_plans methods with user_id scoping.
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


def test_save_plan(engine, sample_plan):
    """Test saving a training plan to the database."""
    # Save plan
    plan_id = engine.save_plan(sample_plan)
    
    # Verify plan was saved
    assert plan_id is not None
    assert len(plan_id) == 36  # UUID length
    
    # Verify we can retrieve it
    retrieved_plan = engine.get_plan(plan_id, sample_plan.user_id)
    assert retrieved_plan is not None
    assert retrieved_plan.title == "Marathon Training"
    assert retrieved_plan.sport == "running"
    assert len(retrieved_plan.weeks) == 1
    assert len(retrieved_plan.weeks[0].sessions) == 2


def test_get_plan_with_user_scoping(engine, sample_plan, db_session):
    """Test that get_plan enforces user_id scoping."""
    # Save plan for user 1
    plan_id = engine.save_plan(sample_plan)
    
    # Create another athlete
    athlete2 = Athlete(name="Other Athlete", email="other@example.com")
    db_session.add(athlete2)
    db_session.commit()
    
    # Try to retrieve plan with wrong user_id
    retrieved_plan = engine.get_plan(plan_id, athlete2.id)
    
    # Should return None (not found)
    assert retrieved_plan is None
    
    # Should work with correct user_id
    retrieved_plan = engine.get_plan(plan_id, sample_plan.user_id)
    assert retrieved_plan is not None


def test_list_plans(engine, athlete, db_session):
    """Test listing all plans for a user."""
    # Create multiple plans
    plan1 = TrainingPlan(
        user_id=athlete.id,
        title="Plan 1",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active",
        weeks=[]
    )
    
    plan2 = TrainingPlan(
        user_id=athlete.id,
        title="Plan 2",
        sport="cycling",
        start_date=date(2024, 5, 1),
        end_date=date(2024, 8, 1),
        status="draft",
        weeks=[]
    )
    
    # Save plans
    engine.save_plan(plan1)
    engine.save_plan(plan2)
    
    # List plans
    plans = engine.list_plans(athlete.id)
    
    # Verify both plans are returned
    assert len(plans) == 2
    titles = [p.title for p in plans]
    assert "Plan 1" in titles
    assert "Plan 2" in titles


def test_list_plans_with_user_scoping(engine, athlete, db_session):
    """Test that list_plans only returns plans for the specified user."""
    # Create plan for athlete 1
    plan1 = TrainingPlan(
        user_id=athlete.id,
        title="Athlete 1 Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active",
        weeks=[]
    )
    engine.save_plan(plan1)
    
    # Create another athlete with a plan
    athlete2 = Athlete(name="Other Athlete", email="other@example.com")
    db_session.add(athlete2)
    db_session.commit()
    
    plan2 = TrainingPlan(
        user_id=athlete2.id,
        title="Athlete 2 Plan",
        sport="cycling",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active",
        weeks=[]
    )
    engine.save_plan(plan2)
    
    # List plans for athlete 1
    plans = engine.list_plans(athlete.id)
    
    # Should only return athlete 1's plan
    assert len(plans) == 1
    assert plans[0].title == "Athlete 1 Plan"
    
    # List plans for athlete 2
    plans2 = engine.list_plans(athlete2.id)
    
    # Should only return athlete 2's plan
    assert len(plans2) == 1
    assert plans2[0].title == "Athlete 2 Plan"


def test_save_plan_preserves_relationships(engine, sample_plan):
    """Test that saving a plan preserves all relationships."""
    # Save plan
    plan_id = engine.save_plan(sample_plan)
    
    # Retrieve plan
    retrieved_plan = engine.get_plan(plan_id, sample_plan.user_id)
    
    # Verify all data is preserved
    assert retrieved_plan.title == sample_plan.title
    assert retrieved_plan.sport == sample_plan.sport
    assert retrieved_plan.start_date == sample_plan.start_date
    assert retrieved_plan.end_date == sample_plan.end_date
    assert retrieved_plan.status == sample_plan.status
    
    # Verify weeks
    assert len(retrieved_plan.weeks) == len(sample_plan.weeks)
    for i, week in enumerate(retrieved_plan.weeks):
        original_week = sample_plan.weeks[i]
        assert week.week_number == original_week.week_number
        assert week.focus == original_week.focus
        assert week.volume_target == original_week.volume_target
        
        # Verify sessions
        assert len(week.sessions) == len(original_week.sessions)
        for j, session in enumerate(week.sessions):
            original_session = original_week.sessions[j]
            assert session.day_of_week == original_session.day_of_week
            assert session.session_type == original_session.session_type
            assert session.duration_minutes == original_session.duration_minutes
            assert session.intensity == original_session.intensity
            assert session.description == original_session.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_build_generation_prompt_with_activities(engine, athlete):
    """Test that generation prompt includes activity data."""
    recent_activities = [
        {
            "date": "2024-01-15T10:00:00",
            "activity_type": "Run",
            "duration_min": 45.0,
            "distance_km": 7.5,
            "avg_hr": 145
        },
        {
            "date": "2024-01-13T09:00:00",
            "activity_type": "Run",
            "duration_min": 60.0,
            "distance_km": 10.0,
            "avg_hr": 150
        }
    ]
    
    weekly_metrics = [
        {
            "week_id": "2024-W02",
            "weight_kg": 70.5,
            "rhr_bpm": 55,
            "sleep_avg_hrs": 7.5
        }
    ]
    
    prompt = engine._build_generation_prompt(
        sport="running",
        duration_weeks=12,
        goal_description="Run a sub-4 hour marathon",
        recent_activities=recent_activities,
        weekly_metrics=weekly_metrics,
        start_date=date(2024, 2, 1)
    )
    
    # Verify prompt includes key information
    assert "12-week running training plan" in prompt
    assert "2024-02-01" in prompt
    assert "sub-4 hour marathon" in prompt
    assert "Recent Training History" in prompt
    assert "Total activities: 2" in prompt
    assert "Recent Body Metrics" in prompt
    assert "Weight: 70.5 kg" in prompt
    assert "Resting HR: 55 bpm" in prompt


def test_build_generation_prompt_without_activities(engine, athlete):
    """Test that generation prompt handles missing activity data."""
    prompt = engine._build_generation_prompt(
        sport="cycling",
        duration_weeks=8,
        goal_description=None,
        recent_activities=[],
        weekly_metrics=[],
        start_date=date(2024, 3, 1)
    )
    
    # Verify prompt handles missing data gracefully
    assert "8-week cycling training plan" in prompt
    assert "2024-03-01" in prompt
    assert "No recent training history available" in prompt
    assert "beginner-friendly plan" in prompt

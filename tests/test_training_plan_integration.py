"""
Integration test for training plan models and dataclasses.

This test verifies that SQLAlchemy models and dataclasses work together correctly.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from app.models.base import Base
from app.models import TrainingPlan as TrainingPlanModel
from app.models import TrainingPlanWeek as TrainingPlanWeekModel
from app.models import TrainingPlanSession as TrainingPlanSessionModel
from app.models import Athlete
from app.schemas import TrainingSession, TrainingWeek, TrainingPlan


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_dataclass_to_model_conversion(db_session):
    """Test converting dataclass to SQLAlchemy model."""
    # Create an athlete
    athlete = Athlete(name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    
    # Create dataclass instances
    session_dc = TrainingSession(
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=45,
        intensity="easy",
        description="Easy pace, focus on form"
    )
    
    week_dc = TrainingWeek(
        week_number=1,
        focus="Base building",
        volume_target=5.0,
        sessions=[session_dc]
    )
    
    plan_dc = TrainingPlan(
        user_id=athlete.id,
        title="Marathon Training",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="active",
        weeks=[week_dc]
    )
    
    # Validate dataclass
    assert plan_dc.validate() is True
    
    # Convert to SQLAlchemy models
    plan_model = TrainingPlanModel(
        user_id=plan_dc.user_id,
        title=plan_dc.title,
        sport=plan_dc.sport,
        start_date=plan_dc.start_date,
        end_date=plan_dc.end_date,
        status=plan_dc.status
    )
    db_session.add(plan_model)
    db_session.flush()
    
    for week_dc in plan_dc.weeks:
        week_model = TrainingPlanWeekModel(
            plan_id=plan_model.id,
            week_number=week_dc.week_number,
            focus=week_dc.focus,
            volume_target=week_dc.volume_target
        )
        db_session.add(week_model)
        db_session.flush()
        
        for session_dc in week_dc.sessions:
            session_model = TrainingPlanSessionModel(
                week_id=week_model.id,
                day_of_week=session_dc.day_of_week,
                session_type=session_dc.session_type,
                duration_minutes=session_dc.duration_minutes,
                intensity=session_dc.intensity,
                description=session_dc.description,
                completed=session_dc.completed,
                matched_activity_id=session_dc.matched_activity_id
            )
            db_session.add(session_model)
    
    db_session.commit()
    
    # Verify data was saved correctly
    saved_plan = db_session.query(TrainingPlanModel).filter_by(id=plan_model.id).first()
    assert saved_plan is not None
    assert saved_plan.title == "Marathon Training"
    assert len(saved_plan.weeks) == 1
    assert saved_plan.weeks[0].week_number == 1
    assert len(saved_plan.weeks[0].sessions) == 1
    assert saved_plan.weeks[0].sessions[0].session_type == "easy_run"


def test_model_to_dataclass_conversion(db_session):
    """Test converting SQLAlchemy model to dataclass."""
    # Create an athlete
    athlete = Athlete(name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    
    # Create SQLAlchemy models
    plan_model = TrainingPlanModel(
        user_id=athlete.id,
        title="Cycling Plan",
        sport="cycling",
        start_date=date(2024, 2, 1),
        end_date=date(2024, 5, 1),
        status="draft"
    )
    db_session.add(plan_model)
    db_session.flush()
    
    week_model = TrainingPlanWeekModel(
        plan_id=plan_model.id,
        week_number=1,
        focus="Endurance",
        volume_target=8.0
    )
    db_session.add(week_model)
    db_session.flush()
    
    session_model = TrainingPlanSessionModel(
        week_id=week_model.id,
        day_of_week=2,
        session_type="easy_ride",
        duration_minutes=90,
        intensity="easy",
        description="Long easy ride"
    )
    db_session.add(session_model)
    db_session.commit()
    
    # Convert to dataclasses
    sessions_dc = [
        TrainingSession(
            day_of_week=s.day_of_week,
            session_type=s.session_type,
            duration_minutes=s.duration_minutes,
            intensity=s.intensity,
            description=s.description,
            completed=s.completed,
            matched_activity_id=s.matched_activity_id
        )
        for s in week_model.sessions
    ]
    
    weeks_dc = [
        TrainingWeek(
            week_number=w.week_number,
            focus=w.focus,
            volume_target=w.volume_target,
            sessions=[
                TrainingSession(
                    day_of_week=s.day_of_week,
                    session_type=s.session_type,
                    duration_minutes=s.duration_minutes,
                    intensity=s.intensity,
                    description=s.description,
                    completed=s.completed,
                    matched_activity_id=s.matched_activity_id
                )
                for s in w.sessions
            ]
        )
        for w in plan_model.weeks
    ]
    
    plan_dc = TrainingPlan(
        id=plan_model.id,
        user_id=plan_model.user_id,
        title=plan_model.title,
        sport=plan_model.sport,
        goal_id=plan_model.goal_id,
        start_date=plan_model.start_date,
        end_date=plan_model.end_date,
        status=plan_model.status,
        weeks=weeks_dc,
        created_at=plan_model.created_at,
        updated_at=plan_model.updated_at
    )
    
    # Validate dataclass
    assert plan_dc.validate() is True
    assert plan_dc.title == "Cycling Plan"
    assert plan_dc.sport == "cycling"
    assert len(plan_dc.weeks) == 1
    assert plan_dc.weeks[0].week_number == 1
    assert len(plan_dc.weeks[0].sessions) == 1
    assert plan_dc.weeks[0].sessions[0].session_type == "easy_ride"


def test_validation_consistency(db_session):
    """Test that validation works consistently between models and dataclasses."""
    # Create an athlete
    athlete = Athlete(name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    
    # Test invalid session_type in dataclass
    session_dc = TrainingSession(
        day_of_week=1,
        session_type="invalid_type",
        duration_minutes=45,
        intensity="easy",
        description="Test"
    )
    
    with pytest.raises(ValueError, match="Invalid session_type"):
        session_dc.validate()
    
    # Test invalid intensity in dataclass
    session_dc2 = TrainingSession(
        day_of_week=1,
        session_type="easy_run",
        duration_minutes=45,
        intensity="super_hard",
        description="Test"
    )
    
    with pytest.raises(ValueError, match="Invalid intensity"):
        session_dc2.validate()
    
    # Test invalid status in dataclass
    plan_dc = TrainingPlan(
        user_id=athlete.id,
        title="Test Plan",
        sport="running",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
        status="invalid_status"
    )
    
    with pytest.raises(ValueError, match="Invalid status"):
        plan_dc.validate()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

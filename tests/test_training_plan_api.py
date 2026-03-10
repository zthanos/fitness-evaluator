"""Tests for Training Plan API endpoints.

Tests the three main endpoints:
1. GET /api/training-plans - List all plans
2. GET /api/training-plans/{plan_id} - Get plan details
3. GET /api/training-plans/{plan_id}/adherence - Get adherence time series
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime, timedelta
from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.training_plan import TrainingPlan
from app.models.training_plan_week import TrainingPlanWeek
from app.models.training_plan_session import TrainingPlanSession
from app.models.athlete import Athlete
from app.models.athlete_goal import AthleteGoal
import uuid


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_training_plan_api.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_athlete(db_session):
    """Create a sample athlete for testing."""
    athlete = Athlete(id=1, name="Test Athlete", email="test@example.com")
    db_session.add(athlete)
    db_session.commit()
    return athlete


@pytest.fixture
def sample_goal(db_session, sample_athlete):
    """Create a sample goal for testing."""
    goal = AthleteGoal(
        id=str(uuid.uuid4()),
        athlete_id=sample_athlete.id,
        goal_type="performance",
        description="Run a sub-4 hour marathon",
        status="active"
    )
    db_session.add(goal)
    db_session.commit()
    return goal


@pytest.fixture
def sample_plan(db_session, sample_athlete, sample_goal):
    """Create a sample training plan with weeks and sessions."""
    plan = TrainingPlan(
        id=str(uuid.uuid4()),
        user_id=sample_athlete.id,
        title="Marathon Training",
        sport="running",
        goal_id=sample_goal.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(weeks=4),
        status="active"
    )
    db_session.add(plan)
    db_session.flush()
    
    # Add 2 weeks with sessions
    for week_num in range(1, 3):
        week = TrainingPlanWeek(
            id=str(uuid.uuid4()),
            plan_id=plan.id,
            week_number=week_num,
            focus=f"Week {week_num} focus",
            volume_target=10.0
        )
        db_session.add(week)
        db_session.flush()
        
        # Add 3 sessions per week
        for day in range(1, 4):
            session = TrainingPlanSession(
                id=str(uuid.uuid4()),
                week_id=week.id,
                day_of_week=day,
                session_type="easy_run",
                duration_minutes=45,
                intensity="easy",
                description="Easy run",
                completed=(week_num == 1 and day <= 2)  # First 2 sessions of week 1 completed
            )
            db_session.add(session)
    
    db_session.commit()
    db_session.refresh(plan)
    return plan


def test_list_training_plans_empty(db_session, sample_athlete):
    """Test listing plans when none exist."""
    response = client.get(f"/api/training-plans?user_id={sample_athlete.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) == 0


def test_list_training_plans(db_session, sample_plan):
    """Test listing plans with adherence calculation."""
    response = client.get(f"/api/training-plans?user_id={sample_plan.user_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) == 1
    
    plan = data["plans"][0]
    assert plan["id"] == sample_plan.id
    assert plan["title"] == "Marathon Training"
    assert plan["sport"] == "running"
    assert plan["status"] == "active"
    assert plan["total_sessions"] == 6
    assert plan["completed_sessions"] == 2
    # 2 out of 6 sessions completed = 33.3%
    assert abs(plan["adherence_percentage"] - 33.3) < 0.1


def test_list_training_plans_with_status_filter(db_session, sample_plan):
    """Test filtering plans by status."""
    response = client.get(f"/api/training-plans?user_id={sample_plan.user_id}&status=active")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["plans"]) == 1
    
    # Test with different status
    response = client.get(f"/api/training-plans?user_id={sample_plan.user_id}&status=completed")
    assert response.status_code == 200
    data = response.json()
    assert len(data["plans"]) == 0


def test_list_training_plans_invalid_status(db_session, sample_athlete):
    """Test invalid status filter."""
    response = client.get(f"/api/training-plans?user_id={sample_athlete.id}&status=invalid")
    
    assert response.status_code == 400
    assert "Invalid status" in response.json()["detail"]


def test_get_training_plan_details(db_session, sample_plan):
    """Test getting detailed plan with weeks and sessions."""
    response = client.get(f"/api/training-plans/{sample_plan.id}?user_id={sample_plan.user_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert "plan" in data
    
    plan = data["plan"]
    assert plan["id"] == sample_plan.id
    assert plan["title"] == "Marathon Training"
    assert plan["sport"] == "running"
    assert plan["status"] == "active"
    
    # Check goal information
    assert plan["goal"] is not None
    assert plan["goal"]["description"] == "Run a sub-4 hour marathon"
    
    # Check weeks
    assert len(plan["weeks"]) == 2
    week1 = plan["weeks"][0]
    assert week1["week_number"] == 1
    assert week1["focus"] == "Week 1 focus"
    assert len(week1["sessions"]) == 3
    
    # Check adherence calculation
    # Week 1: 2/3 completed = 66.7%
    assert abs(week1["adherence"] - 66.7) < 0.1
    # Overall: 2/6 completed = 33.3%
    assert abs(plan["overall_adherence"] - 33.3) < 0.1


def test_get_training_plan_not_found(db_session, sample_athlete):
    """Test getting non-existent plan."""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/training-plans/{fake_id}?user_id={sample_athlete.id}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_training_plan_wrong_user(db_session, sample_plan):
    """Test user scoping - cannot access other user's plans."""
    wrong_user_id = 999
    response = client.get(f"/api/training-plans/{sample_plan.id}?user_id={wrong_user_id}")
    
    assert response.status_code == 404
    assert "not found or access denied" in response.json()["detail"]


def test_get_adherence_time_series(db_session, sample_plan):
    """Test getting adherence time series for charting."""
    response = client.get(f"/api/training-plans/{sample_plan.id}/adherence?user_id={sample_plan.user_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "adherence_by_week" in data
    assert "overall_adherence" in data
    
    # Check weekly adherence
    adherence_by_week = data["adherence_by_week"]
    assert len(adherence_by_week) == 2
    
    # Week 1: 2/3 completed = 66.7%
    assert adherence_by_week[0]["week"] == 1
    assert abs(adherence_by_week[0]["adherence"] - 66.7) < 0.1
    
    # Week 2: 0/3 completed = 0%
    assert adherence_by_week[1]["week"] == 2
    assert adherence_by_week[1]["adherence"] == 0.0
    
    # Overall: 2/6 completed = 33.3%
    assert abs(data["overall_adherence"] - 33.3) < 0.1


def test_get_adherence_not_found(db_session, sample_athlete):
    """Test getting adherence for non-existent plan."""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/training-plans/{fake_id}/adherence?user_id={sample_athlete.id}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_adherence_wrong_user(db_session, sample_plan):
    """Test user scoping for adherence endpoint."""
    wrong_user_id = 999
    response = client.get(f"/api/training-plans/{sample_plan.id}/adherence?user_id={wrong_user_id}")
    
    assert response.status_code == 404
    assert "not found or access denied" in response.json()["detail"]

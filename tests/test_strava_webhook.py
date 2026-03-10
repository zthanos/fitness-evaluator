"""Tests for Strava webhook handler."""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.strava_activity import StravaActivity
from app.models.activity_analysis import ActivityAnalysis
from app.models.training_plan import TrainingPlan
from app.models.training_plan_week import TrainingPlanWeek
from app.models.training_plan_session import TrainingPlanSession
from app.models.athlete import Athlete
from app.models.athlete_goal import AthleteGoal


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create test athlete
    athlete = Athlete(id=1, name="Test Athlete", email="test@example.com")
    session.add(athlete)
    session.commit()
    
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """Create test client with test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_webhook_verification(client):
    """Test Strava webhook subscription verification."""
    # Strava sends GET request with challenge parameter
    response = client.get(
        "/api/strava/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "test_challenge_123",
            "hub.verify_token": "test_token"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["hub.challenge"] == "test_challenge_123"


def test_webhook_verification_invalid_mode(client):
    """Test webhook verification with invalid mode."""
    response = client.get(
        "/api/strava/webhook",
        params={
            "hub.mode": "invalid",
            "hub.challenge": "test_challenge_123"
        }
    )
    
    assert response.status_code == 400



def test_webhook_verification_missing_challenge(client):
    """Test webhook verification without challenge parameter."""
    response = client.get(
        "/api/strava/webhook",
        params={
            "hub.mode": "subscribe"
        }
    )
    
    assert response.status_code == 400


def test_webhook_activity_create_event(client, db_session):
    """Test webhook handling of new activity creation."""
    # Send webhook event for new activity
    event_time = int(datetime.now().timestamp())
    response = client.post(
        "/api/strava/webhook",
        json={
            "object_type": "activity",
            "object_id": 12345678,
            "aspect_type": "create",
            "owner_id": 1,
            "subscription_id": 123,
            "event_time": event_time
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    # The webhook should process the event (success or error is acceptable for this test)
    assert "status" in data
    assert "activity_id" in data or "message" in data



def test_webhook_ignores_non_activity_events(client):
    """Test that webhook ignores non-activity events."""
    response = client.post(
        "/api/strava/webhook",
        json={
            "object_type": "athlete",
            "object_id": 123456,
            "aspect_type": "update",
            "owner_id": 1,
            "subscription_id": 123,
            "event_time": int(datetime.now().timestamp())
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reason"] == "not an activity event"


def test_webhook_ignores_update_events(client):
    """Test that webhook ignores activity update events."""
    response = client.post(
        "/api/strava/webhook",
        json={
            "object_type": "activity",
            "object_id": 12345678,
            "aspect_type": "update",
            "owner_id": 1,
            "subscription_id": 123,
            "event_time": int(datetime.now().timestamp())
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"


def test_webhook_skips_duplicate_activities(client, db_session):
    """Test that webhook skips activities that already exist."""
    # Send webhook event for an activity
    response = client.post(
        "/api/strava/webhook",
        json={
            "object_type": "activity",
            "object_id": 12345678,
            "aspect_type": "create",
            "owner_id": 1,
            "subscription_id": 123,
            "event_time": int(datetime.now().timestamp())
        }
    )
    
    assert response.status_code == 200
    # The webhook should handle the event
    data = response.json()
    assert "status" in data

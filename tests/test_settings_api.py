"""Test settings API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, engine
from app.models.base import Base
from datetime import date

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_get_profile_creates_default():
    """Test GET /api/settings/profile creates default athlete if none exists."""
    response = client.get("/api/settings/profile")
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "Athlete"
    assert data["email"] is None
    assert data["date_of_birth"] is None


def test_update_profile():
    """Test PUT /api/settings/profile updates athlete profile."""
    # First create a profile
    client.get("/api/settings/profile")
    
    # Update profile
    profile_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "date_of_birth": "1990-05-15"
    }
    
    response = client.put("/api/settings/profile", json=profile_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["date_of_birth"] == "1990-05-15"


def test_update_profile_validates_email():
    """Test profile update validates email format."""
    profile_data = {
        "name": "John Doe",
        "email": "invalid-email"
    }
    
    response = client.put("/api/settings/profile", json=profile_data)
    assert response.status_code == 422  # Validation error


def test_update_profile_validates_date_of_birth():
    """Test profile update validates date of birth range."""
    # First create a profile
    client.get("/api/settings/profile")
    
    # Future date should fail
    profile_data = {
        "date_of_birth": "2050-01-01"
    }
    
    response = client.put("/api/settings/profile", json=profile_data)
    assert response.status_code == 400
    assert "Date of birth must be between" in response.json()["detail"]
    
    # Very old date should fail
    profile_data = {
        "date_of_birth": "1800-01-01"
    }
    
    response = client.put("/api/settings/profile", json=profile_data)
    assert response.status_code == 400


def test_update_training_plan():
    """Test PUT /api/settings/training-plan updates training plan."""
    # First create a profile
    client.get("/api/settings/profile")
    
    # Update training plan
    plan_data = {
        "plan_name": "Marathon Training",
        "start_date": "2024-01-01",
        "goal_description": "Complete a marathon in under 4 hours"
    }
    
    response = client.put("/api/settings/training-plan", json=plan_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "Marathon Training" in data["current_plan"]
    assert data["goals"] == "Complete a marathon in under 4 hours"


def test_get_strava_status():
    """Test GET /api/settings/strava returns placeholder status."""
    response = client.get("/api/settings/strava")
    assert response.status_code == 200
    
    data = response.json()
    assert data["connected"] is False
    assert "message" in data


def test_get_llm_settings():
    """Test GET /api/settings/llm returns LLM configuration."""
    response = client.get("/api/settings/llm")
    assert response.status_code == 200
    
    data = response.json()
    assert "llm_type" in data
    assert "endpoint" in data
    assert "model" in data
    assert "temperature" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

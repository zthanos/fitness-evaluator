"""Test dashboard API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_dashboard.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_dashboard_stats_endpoint():
    """Test that dashboard stats endpoint returns expected structure."""
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_activities" in data
    assert "current_weight" in data
    assert "weekly_adherence_avg" in data
    assert "latest_evaluation_score" in data
    assert "latest_evaluation_date" in data
    
    # With empty database, should return zeros/nulls
    assert data["total_activities"] == 0
    assert data["current_weight"] is None
    assert data["weekly_adherence_avg"] is None


def test_activity_volume_chart_endpoint():
    """Test that activity volume chart endpoint returns expected structure."""
    response = client.get("/api/dashboard/charts/activity-volume")
    assert response.status_code == 200
    
    data = response.json()
    assert "data_points" in data
    assert isinstance(data["data_points"], list)


def test_weight_trend_chart_endpoint():
    """Test that weight trend chart endpoint returns expected structure."""
    response = client.get("/api/dashboard/charts/weight-trend")
    assert response.status_code == 200
    
    data = response.json()
    assert "data_points" in data
    assert isinstance(data["data_points"], list)


def test_recent_activities_endpoint():
    """Test that recent activities endpoint returns expected structure."""
    response = client.get("/api/dashboard/recent/activities")
    assert response.status_code == 200
    
    data = response.json()
    assert "activities" in data
    assert isinstance(data["activities"], list)


def test_recent_logs_endpoint():
    """Test that recent logs endpoint returns expected structure."""
    response = client.get("/api/dashboard/recent/logs")
    assert response.status_code == 200
    
    data = response.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)


def test_latest_evaluation_endpoint():
    """Test that latest evaluation endpoint returns expected structure."""
    response = client.get("/api/dashboard/latest-evaluation")
    assert response.status_code == 200
    
    data = response.json()
    assert "score" in data
    assert "top_strengths" in data
    assert "top_improvements" in data
    assert "period_start" in data
    assert "period_end" in data
    assert "period_type" in data
    assert "generated_at" in data
    assert "evaluation_id" in data
    
    # With empty database, should return nulls
    assert data["score"] is None
    assert data["top_strengths"] == []
    assert data["top_improvements"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

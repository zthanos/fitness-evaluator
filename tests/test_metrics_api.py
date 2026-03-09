"""
Test suite for metrics API endpoints.

Tests Requirements: 5.4, 5.5, 5.6
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from app.main import create_app
from app.database import get_db, engine
from app.models.base import Base
from sqlalchemy.orm import Session

# Create test client
app = create_app()
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_metric_success(setup_database):
    """Test creating a new body metric record."""
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 75.5,
        "body_fat_pct": 18.5,
        "measurements": {
            "waist_cm": 85.0
        }
    }
    
    response = client.post("/api/metrics", json=metric_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "id" in data
    assert data["measurement_date"] == "2024-01-15"
    assert data["weight"] == 75.5
    assert data["body_fat_pct"] == 18.5
    assert data["measurements"]["waist_cm"] == 85.0
    assert "created_at" in data
    assert "updated_at" in data


def test_create_metric_validation_weight_too_low(setup_database):
    """Test weight validation - below minimum (Requirement 5.2)."""
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 25.0,  # Below minimum of 30
    }
    
    response = client.post("/api/metrics", json=metric_data)
    
    assert response.status_code == 422  # Validation error


def test_create_metric_validation_weight_too_high(setup_database):
    """Test weight validation - above maximum (Requirement 5.2)."""
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 350.0,  # Above maximum of 300
    }
    
    response = client.post("/api/metrics", json=metric_data)
    
    assert response.status_code == 422  # Validation error


def test_create_metric_validation_body_fat_too_low(setup_database):
    """Test body fat validation - below minimum (Requirement 5.3)."""
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 75.0,
        "body_fat_pct": 2.0,  # Below minimum of 3
    }
    
    response = client.post("/api/metrics", json=metric_data)
    
    assert response.status_code == 422  # Validation error


def test_create_metric_validation_body_fat_too_high(setup_database):
    """Test body fat validation - above maximum (Requirement 5.3)."""
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 75.0,
        "body_fat_pct": 65.0,  # Above maximum of 60
    }
    
    response = client.post("/api/metrics", json=metric_data)
    
    assert response.status_code == 422  # Validation error


def test_create_metric_duplicate_date(setup_database):
    """Test that duplicate dates are rejected."""
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 75.5,
    }
    
    # Create first metric
    response1 = client.post("/api/metrics", json=metric_data)
    assert response1.status_code == 200
    
    # Try to create duplicate
    response2 = client.post("/api/metrics", json=metric_data)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]


def test_get_metrics_history(setup_database):
    """Test retrieving metrics history (Requirement 5.4, 5.5)."""
    # Create multiple metrics
    dates = ["2024-01-10", "2024-01-15", "2024-01-20"]
    for date in dates:
        metric_data = {
            "measurement_date": date,
            "weight": 75.0,
        }
        client.post("/api/metrics", json=metric_data)
    
    # Get all metrics
    response = client.get("/api/metrics")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    
    # Verify ordering (most recent first)
    assert data[0]["measurement_date"] == "2024-01-20"
    assert data[1]["measurement_date"] == "2024-01-15"
    assert data[2]["measurement_date"] == "2024-01-10"


def test_get_metrics_with_date_filter(setup_database):
    """Test retrieving metrics with date range filter."""
    # Create multiple metrics
    dates = ["2024-01-10", "2024-01-15", "2024-01-20", "2024-01-25"]
    for date in dates:
        metric_data = {
            "measurement_date": date,
            "weight": 75.0,
        }
        client.post("/api/metrics", json=metric_data)
    
    # Get metrics in date range
    response = client.get("/api/metrics?date_from=2024-01-15&date_to=2024-01-20")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["measurement_date"] == "2024-01-20"
    assert data[1]["measurement_date"] == "2024-01-15"


def test_update_metric_within_24_hours(setup_database):
    """Test updating a metric within 24 hours (Requirement 5.6)."""
    # Create metric
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 75.5,
        "body_fat_pct": 18.5,
    }
    
    create_response = client.post("/api/metrics", json=metric_data)
    assert create_response.status_code == 200
    metric_id = create_response.json()["id"]
    
    # Update metric
    update_data = {
        "weight": 74.8,
        "body_fat_pct": 18.2,
    }
    
    update_response = client.put(f"/api/metrics/{metric_id}", json=update_data)
    
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["weight"] == 74.8
    assert data["body_fat_pct"] == 18.2


def test_update_metric_not_found(setup_database):
    """Test updating a non-existent metric."""
    update_data = {
        "weight": 74.8,
    }
    
    response = client.put("/api/metrics/nonexistent-id", json=update_data)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_specific_metric(setup_database):
    """Test retrieving a specific metric by ID."""
    # Create metric
    metric_data = {
        "measurement_date": "2024-01-15",
        "weight": 75.5,
    }
    
    create_response = client.post("/api/metrics", json=metric_data)
    assert create_response.status_code == 200
    metric_id = create_response.json()["id"]
    
    # Get specific metric
    response = client.get(f"/api/metrics/{metric_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == metric_id
    assert data["weight"] == 75.5


def test_get_specific_metric_not_found(setup_database):
    """Test retrieving a non-existent metric."""
    response = client.get("/api/metrics/nonexistent-id")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

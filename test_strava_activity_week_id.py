"""
Unit tests for StravaActivity week_id validation and auto-population.

Tests the week_id field validation, computation, and automatic population
as specified in Task 10.3 of the Context Engineering Refactor spec.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.strava_activity import StravaActivity


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_week_id_format_validation_valid():
    """Test that valid week_id formats are accepted."""
    valid_week_ids = [
        "2024-W01",
        "2024-W15",
        "2024-W52",
        "2023-W01",
        "2025-W26"
    ]
    
    for week_id in valid_week_ids:
        activity = StravaActivity(
            strava_id=12345,
            activity_type="Run",
            start_date=datetime(2024, 4, 15, 10, 0, 0),
            raw_json="{}",
            week_id=week_id
        )
        # Should not raise an exception
        assert activity.week_id == week_id


def test_week_id_format_validation_invalid():
    """Test that invalid week_id formats are rejected."""
    invalid_week_ids = [
        "2024-W1",      # Missing leading zero
        "2024-W100",    # Week number too large
        "24-W15",       # Year too short
        "2024W15",      # Missing hyphen
        "2024-15",      # Missing 'W'
        "W15-2024",     # Wrong order
        "2024-W",       # Missing week number
        "invalid"       # Completely invalid
    ]
    
    for week_id in invalid_week_ids:
        with pytest.raises(ValueError, match="week_id must match format YYYY-WW"):
            activity = StravaActivity(
                strava_id=12345,
                activity_type="Run",
                start_date=datetime(2024, 4, 15, 10, 0, 0),
                raw_json="{}",
                week_id=week_id
            )


def test_compute_week_id_static_method():
    """Test the compute_week_id static method."""
    test_cases = [
        (datetime(2024, 1, 1), "2024-W01"),   # New Year's Day
        (datetime(2024, 4, 15), "2024-W16"),  # Mid-April
        (datetime(2024, 12, 31), "2025-W01"), # End of year (ISO week belongs to next year)
        (datetime(2023, 1, 1), "2022-W52"),   # Start of year (ISO week belongs to previous year)
        (datetime(2024, 6, 15), "2024-W24"),  # Mid-June
    ]
    
    for start_date, expected_week_id in test_cases:
        result = StravaActivity.compute_week_id(start_date)
        assert result == expected_week_id, f"Expected {expected_week_id} for {start_date}, got {result}"


def test_auto_populate_week_id_on_insert(db_session):
    """Test that week_id is automatically populated when inserting a new activity."""
    activity = StravaActivity(
        strava_id=12345,
        activity_type="Run",
        start_date=datetime(2024, 4, 15, 10, 0, 0),
        raw_json="{}"
        # Note: week_id is NOT set
    )
    
    db_session.add(activity)
    db_session.flush()  # Trigger the before_insert event
    
    # week_id should be automatically populated
    assert activity.week_id == "2024-W16"


def test_auto_populate_week_id_on_update(db_session):
    """Test that week_id is automatically populated when updating an activity."""
    # Create activity with week_id
    activity = StravaActivity(
        strava_id=12345,
        activity_type="Run",
        start_date=datetime(2024, 4, 15, 10, 0, 0),
        raw_json="{}",
        week_id="2024-W16"
    )
    
    db_session.add(activity)
    db_session.commit()
    
    # Update start_date and clear week_id
    activity.start_date = datetime(2024, 6, 15, 10, 0, 0)
    activity.week_id = None
    
    db_session.commit()  # Trigger the before_update event
    
    # week_id should be automatically populated based on new start_date
    assert activity.week_id == "2024-W24"


def test_manual_week_id_not_overridden(db_session):
    """Test that manually set week_id is not overridden by auto-population."""
    activity = StravaActivity(
        strava_id=12345,
        activity_type="Run",
        start_date=datetime(2024, 4, 15, 10, 0, 0),
        raw_json="{}",
        week_id="2024-W20"  # Manually set to a different week
    )
    
    db_session.add(activity)
    db_session.flush()
    
    # Manual week_id should be preserved
    assert activity.week_id == "2024-W20"


def test_populate_week_id_method():
    """Test the populate_week_id instance method."""
    activity = StravaActivity(
        strava_id=12345,
        activity_type="Run",
        start_date=datetime(2024, 4, 15, 10, 0, 0),
        raw_json="{}"
    )
    
    # Initially no week_id
    assert activity.week_id is None
    
    # Call populate_week_id
    activity.populate_week_id()
    
    # week_id should now be set
    assert activity.week_id == "2024-W16"


def test_populate_week_id_does_not_override_existing(db_session):
    """Test that populate_week_id does not override an existing week_id."""
    activity = StravaActivity(
        strava_id=12345,
        activity_type="Run",
        start_date=datetime(2024, 4, 15, 10, 0, 0),
        raw_json="{}",
        week_id="2024-W20"
    )
    
    # Call populate_week_id
    activity.populate_week_id()
    
    # Existing week_id should be preserved
    assert activity.week_id == "2024-W20"


def test_week_id_nullable(db_session):
    """Test that week_id can be null (for backward compatibility)."""
    activity = StravaActivity(
        strava_id=12345,
        activity_type="Run",
        start_date=datetime(2024, 4, 15, 10, 0, 0),
        raw_json="{}",
        week_id=None
    )
    
    # Should not raise an exception
    assert activity.week_id is None

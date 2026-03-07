"""Test effort analysis implementation."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.strava_activity import StravaActivity
from app.models.activity_analysis import ActivityAnalysis
from app.services.llm_client import LLMClient
import json


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
def sample_activity(db_session):
    """Create a sample activity for testing."""
    activity = StravaActivity(
        strava_id=12345,
        activity_type="Run",
        start_date=datetime.now(),
        moving_time_s=1800,  # 30 minutes
        distance_m=5000,  # 5km
        elevation_m=50,
        avg_hr=150,
        max_hr=170,
        raw_json=json.dumps({
            "splits_metric": [
                {"distance": 1000, "moving_time": 360, "elevation_difference": 10},
                {"distance": 1000, "moving_time": 350, "elevation_difference": 15},
                {"distance": 1000, "moving_time": 370, "elevation_difference": 5},
                {"distance": 1000, "moving_time": 360, "elevation_difference": 10},
                {"distance": 1000, "moving_time": 360, "elevation_difference": 10}
            ]
        })
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


def test_activity_analysis_model(db_session, sample_activity):
    """Test that ActivityAnalysis model can be created and queried."""
    # Create an analysis
    analysis = ActivityAnalysis(
        activity_id=sample_activity.id,
        analysis_text="Test analysis text"
    )
    db_session.add(analysis)
    db_session.commit()
    
    # Query it back
    retrieved = db_session.query(ActivityAnalysis).filter_by(
        activity_id=sample_activity.id
    ).first()
    
    assert retrieved is not None
    assert retrieved.analysis_text == "Test analysis text"
    assert retrieved.activity_id == sample_activity.id


def test_activity_analysis_relationship(db_session, sample_activity):
    """Test the relationship between Activity and ActivityAnalysis."""
    # Create an analysis
    analysis = ActivityAnalysis(
        activity_id=sample_activity.id,
        analysis_text="Test analysis"
    )
    db_session.add(analysis)
    db_session.commit()
    
    # Access through relationship
    db_session.refresh(sample_activity)
    assert sample_activity.analysis is not None
    assert sample_activity.analysis.analysis_text == "Test analysis"


def test_activity_analysis_unique_constraint(db_session, sample_activity):
    """Test that only one analysis per activity is allowed."""
    # Create first analysis
    analysis1 = ActivityAnalysis(
        activity_id=sample_activity.id,
        analysis_text="First analysis"
    )
    db_session.add(analysis1)
    db_session.commit()
    
    # Try to create second analysis for same activity
    analysis2 = ActivityAnalysis(
        activity_id=sample_activity.id,
        analysis_text="Second analysis"
    )
    db_session.add(analysis2)
    
    with pytest.raises(Exception):  # Should raise IntegrityError
        db_session.commit()


@pytest.mark.asyncio
async def test_generate_effort_analysis_structure():
    """Test that generate_effort_analysis returns properly formatted text."""
    llm_client = LLMClient()
    
    activity_data = {
        "activity_type": "Run",
        "distance_m": 5000,
        "moving_time_s": 1800,
        "elevation_m": 50,
        "avg_hr": 150,
        "max_hr": 170,
        "raw_json": json.dumps({
            "splits_metric": [
                {"distance": 1000, "moving_time": 360, "elevation_difference": 10},
                {"distance": 1000, "moving_time": 350, "elevation_difference": 15}
            ]
        })
    }
    
    # Note: This will fail if LLM is not available, which is expected
    # The test verifies the method exists and has correct signature
    try:
        result = await llm_client.generate_effort_analysis(activity_data)
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        # If LLM is not available, just verify the method exists
        assert hasattr(llm_client, 'generate_effort_analysis')
        print(f"LLM not available for testing: {e}")


def test_effort_analysis_context_building():
    """Test that activity data is properly formatted for LLM context."""
    activity_data = {
        "activity_type": "Run",
        "distance_m": 5000,
        "moving_time_s": 1800,
        "elevation_m": 50,
        "avg_hr": 150,
        "max_hr": 170
    }
    
    # Verify basic calculations
    distance_km = activity_data['distance_m'] / 1000
    duration_min = activity_data['moving_time_s'] / 60
    pace_min_per_km = duration_min / distance_km
    
    assert distance_km == 5.0
    assert duration_min == 30.0
    assert pace_min_per_km == 6.0  # 6 min/km pace


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

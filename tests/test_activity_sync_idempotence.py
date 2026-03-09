"""
Property-based test for Strava activity sync idempotence.

**Property 17: Activity Sync Idempotence**
**Validates: Requirements 20.6**

For any Strava Activity_Record A, syncing A multiple times SHALL result in exactly one record 
in the database with the same Strava activity ID.
"""
import pytest
import os
from hypothesis import given, strategies as st, settings
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.services.strava_client import StravaClient
from app.models.base import Base
from app.models.strava_activity import StravaActivity
from app.models.strava_token import StravaToken
from app.models.athlete import Athlete


# Strategy for generating activity data
activity_strategy = st.fixed_dictionaries({
    'id': st.integers(min_value=1000000, max_value=9999999999),
    'type': st.sampled_from(['Run', 'Ride', 'Swim', 'WeightTraining', 'Walk']),
    'start_date': st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2024, 12, 31)
    ).map(lambda dt: dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')),
    'moving_time': st.integers(min_value=60, max_value=36000),
    'distance': st.floats(min_value=100, max_value=100000),
    'total_elevation_gain': st.floats(min_value=0, max_value=5000),
    'average_heartrate': st.one_of(st.none(), st.integers(min_value=60, max_value=200)),
    'max_heartrate': st.one_of(st.none(), st.integers(min_value=80, max_value=220)),
    'calories': st.one_of(st.none(), st.floats(min_value=50, max_value=5000)),
})


def create_test_db():
    """Create a test database with schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    return TestSessionLocal(), engine


def setup_test_client(db):
    """Set up test client with encryption key and athlete."""
    # Set up test encryption key
    test_key = Fernet.generate_key().decode()
    os.environ['STRAVA_ENCRYPTION_KEY'] = test_key
    os.environ['STRAVA_CLIENT_ID'] = 'test_client_id'
    os.environ['STRAVA_CLIENT_SECRET'] = 'test_client_secret'
    
    # Create test athlete
    athlete = Athlete(id=1, name="Test Athlete", email="test@example.com")
    db.add(athlete)
    
    # Create test token
    client = StravaClient(db)
    token = StravaToken(
        athlete_id=1,
        access_token_encrypted=client._encrypt_token("test_access_token"),
        refresh_token_encrypted=client._encrypt_token("test_refresh_token"),
        expires_at=datetime(2025, 12, 31, tzinfo=timezone.utc)
    )
    db.add(token)
    db.commit()
    
    return client


@given(activity_data=activity_strategy, sync_count=st.integers(min_value=2, max_value=5))
@settings(max_examples=50)
def test_activity_sync_idempotence(activity_data, sync_count):
    """
    Property 17: Activity Sync Idempotence
    
    For any Strava Activity_Record A, syncing A multiple times SHALL result in 
    exactly one record in the database with the same Strava activity ID.
    
    This property ensures that:
    1. Duplicate activities are not created
    2. The same activity synced multiple times results in one database record
    3. Activity data is properly deduplicated by strava_id
    
    Requirements: 20.6
    """
    db, engine = create_test_db()
    client = setup_test_client(db)
    
    try:
        # Mock the get_activities method to return the same activity multiple times
        async def mock_get_activities(athlete_id, after=None):
            return [activity_data]
        
        # Patch the get_activities method
        with patch.object(client, 'get_activities', new=mock_get_activities):
            # Sync the same activity multiple times
            for i in range(sync_count):
                # Use asyncio to run the async method
                import asyncio
                synced_count = asyncio.run(client.sync_activities(athlete_id=1))
                
                # First sync should add the activity, subsequent syncs should find it exists
                if i == 0:
                    assert synced_count == 1, f"First sync should add 1 activity, got {synced_count}"
                else:
                    assert synced_count == 0, f"Subsequent sync {i+1} should add 0 activities, got {synced_count}"
        
        # Verify only one activity exists in database
        activities = db.query(StravaActivity).filter(
            StravaActivity.strava_id == activity_data['id']
        ).all()
        
        assert len(activities) == 1, (
            f"Expected exactly 1 activity after {sync_count} syncs, "
            f"found {len(activities)} activities"
        )
        
        # Verify the activity has correct data
        activity = activities[0]
        assert activity.strava_id == activity_data['id']
        assert activity.activity_type == activity_data['type']
        assert activity.athlete_id == 1
        
    finally:
        db.close()
        engine.dispose()


@given(activities=st.lists(activity_strategy, min_size=1, max_size=10, unique_by=lambda x: x['id']))
@settings(max_examples=30)
def test_multiple_activities_sync_idempotence(activities):
    """
    Extended property: Multiple different activities synced multiple times
    should each appear exactly once.
    
    This ensures idempotence works correctly with multiple activities.
    """
    db, engine = create_test_db()
    client = setup_test_client(db)
    
    try:
        # Mock the get_activities method to return all activities
        async def mock_get_activities(athlete_id, after=None):
            return activities
        
        with patch.object(client, 'get_activities', new=mock_get_activities):
            # Sync twice
            import asyncio
            first_sync = asyncio.run(client.sync_activities(athlete_id=1))
            second_sync = asyncio.run(client.sync_activities(athlete_id=1))
            
            # First sync should add all activities
            assert first_sync == len(activities), (
                f"First sync should add {len(activities)} activities, got {first_sync}"
            )
            
            # Second sync should add no new activities
            assert second_sync == 0, (
                f"Second sync should add 0 activities, got {second_sync}"
            )
        
        # Verify each activity appears exactly once
        for activity_data in activities:
            count = db.query(StravaActivity).filter(
                StravaActivity.strava_id == activity_data['id']
            ).count()
            
            assert count == 1, (
                f"Activity {activity_data['id']} should appear exactly once, "
                f"found {count} times"
            )
        
        # Verify total count matches
        total_count = db.query(StravaActivity).count()
        assert total_count == len(activities), (
            f"Expected {len(activities)} total activities, found {total_count}"
        )
        
    finally:
        db.close()
        engine.dispose()


def test_sync_with_existing_activity():
    """
    Edge case: Syncing when an activity already exists in the database.
    """
    db, engine = create_test_db()
    client = setup_test_client(db)
    
    try:
        # Create an existing activity
        existing_activity = StravaActivity(
            athlete_id=1,
            strava_id=12345,
            activity_type="Run",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            moving_time_s=3600,
            distance_m=10000,
            elevation_m=100,
            raw_json="{}"
        )
        db.add(existing_activity)
        db.commit()
        
        # Mock sync with the same activity
        activity_data = {
            'id': 12345,
            'type': 'Run',
            'start_date': '2024-01-01T00:00:00Z',
            'moving_time': 3600,
            'distance': 10000,
            'total_elevation_gain': 100,
            'average_heartrate': None,
            'max_heartrate': None,
            'calories': None,
        }
        
        async def mock_get_activities(athlete_id, after=None):
            return [activity_data]
        
        with patch.object(client, 'get_activities', new=mock_get_activities):
            import asyncio
            synced_count = asyncio.run(client.sync_activities(athlete_id=1))
            
            # Should not add a new activity
            assert synced_count == 0, f"Should not add duplicate, got {synced_count}"
        
        # Verify still only one activity
        count = db.query(StravaActivity).filter(
            StravaActivity.strava_id == 12345
        ).count()
        assert count == 1, f"Should have exactly 1 activity, found {count}"
        
    finally:
        db.close()
        engine.dispose()


def test_sync_empty_activities():
    """
    Edge case: Syncing when Strava returns no activities.
    """
    db, engine = create_test_db()
    client = setup_test_client(db)
    
    try:
        # Mock sync with no activities
        async def mock_get_activities(athlete_id, after=None):
            return []
        
        with patch.object(client, 'get_activities', new=mock_get_activities):
            import asyncio
            synced_count = asyncio.run(client.sync_activities(athlete_id=1))
            
            assert synced_count == 0, f"Should sync 0 activities, got {synced_count}"
        
        # Verify no activities in database
        count = db.query(StravaActivity).count()
        assert count == 0, f"Should have 0 activities, found {count}"
        
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

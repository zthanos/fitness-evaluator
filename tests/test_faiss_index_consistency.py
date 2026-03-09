"""Property Test: FAISS Index Consistency

Property 5: For any record R added to the FAISS_Index with vector V, searching for V 
SHALL return R as the top result with similarity score >= 0.99.

**Validates: Requirements 16**

This test uses property-based testing to verify that the FAISS index correctly stores 
and retrieves vectors, ensuring that exact matches are always returned with high similarity.
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.services.rag_service import RAGSystem
from datetime import datetime, date
import tempfile
import os
import numpy as np


@pytest.fixture
def test_db():
    """Create a test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def rag_system(test_db):
    """Create a RAG system with temporary index."""
    import uuid
    temp_dir = tempfile.mkdtemp(suffix=f"_{uuid.uuid4().hex[:8]}")
    index_path = os.path.join(temp_dir, "test_index.bin")
    
    rag = RAGSystem(test_db, index_path=index_path)
    yield rag
    
    # Cleanup
    if os.path.exists(index_path):
        os.remove(index_path)
    try:
        os.rmdir(temp_dir)
    except:
        pass


# Property 5: FAISS Index Consistency
@given(
    activity_type=st.sampled_from(['Run', 'Ride', 'Swim', 'Walk', 'Hike']),
    distance_m=st.floats(min_value=100, max_value=50000),
    moving_time_s=st.integers(min_value=60, max_value=10800),
    elevation_m=st.floats(min_value=0, max_value=2000)
)
@settings(
    max_examples=10,
    deadline=10000,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_faiss_index_consistency_activity(test_db, rag_system, activity_type, distance_m, moving_time_s, elevation_m):
    """
    Property 5: FAISS Index Consistency
    
    For any activity record added to the FAISS index, searching for its exact embedding
    SHALL return the activity as the top result with similarity score >= 0.99.
    
    This property ensures that:
    1. FAISS index correctly stores vectors
    2. Exact vector matches are returned with high similarity
    3. The metadata mapping is consistent
    
    **Validates: Requirements 16**
    """
    # Create test activity with unique strava_id
    import time
    unique_id = abs(hash((activity_type, distance_m, moving_time_s, elevation_m, time.time())))
    activity = StravaActivity(
        id=f"test-activity-{unique_id}",
        strava_id=unique_id,
        activity_type=activity_type,
        start_date=datetime.now(),
        distance_m=distance_m,
        moving_time_s=moving_time_s,
        elevation_m=elevation_m,
        raw_json="{}"  # Required field
    )
    test_db.add(activity)
    test_db.commit()
    
    # Index the activity
    rag_system.index_activity(activity)
    test_db.commit()
    
    # Get the embedding text that was indexed
    from app.models.faiss_metadata import FaissMetadata
    metadata = test_db.query(FaissMetadata).filter(
        FaissMetadata.record_type == 'activity',
        FaissMetadata.record_id == str(activity.id)
    ).first()
    
    assert metadata is not None, "Metadata should be stored in database"
    
    # Search for the exact text
    results = rag_system.search(metadata.embedding_text, top_k=1)
    
    # Property: The indexed activity should be returned as top result
    assert len(results) >= 1, "Search should return at least one result"
    
    top_result = results[0]
    assert top_result['record_type'] == 'activity', "Top result should be an activity"
    assert top_result['record_id'] == str(activity.id), "Top result should be the indexed activity"
    
    # Property: Similarity score should be >= 0.99 for exact match
    assert top_result['similarity'] >= 0.99, \
        f"Exact match similarity should be >= 0.99, got {top_result['similarity']}"


@given(
    weight_kg=st.floats(min_value=40, max_value=150),
    body_fat_pct=st.floats(min_value=5, max_value=40),
    days_offset=st.integers(min_value=0, max_value=365)
)
@settings(
    max_examples=10,
    deadline=10000,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_faiss_index_consistency_metric(test_db, rag_system, weight_kg, body_fat_pct, days_offset):
    """
    Test FAISS index consistency for body metrics.
    
    Verifies that indexed metrics can be retrieved with high similarity.
    """
    # Create test metric with unique date
    from datetime import timedelta
    metric = WeeklyMeasurement(
        id=f"test-metric-{hash((weight_kg, body_fat_pct, days_offset))}",
        week_start=date.today() - timedelta(days=days_offset),
        weight_kg=weight_kg,
        body_fat_pct=body_fat_pct
    )
    test_db.add(metric)
    test_db.commit()
    
    # Index the metric
    rag_system.index_metric(metric)
    test_db.commit()
    
    # Get the embedding text
    from app.models.faiss_metadata import FaissMetadata
    metadata = test_db.query(FaissMetadata).filter(
        FaissMetadata.record_type == 'metric',
        FaissMetadata.record_id == str(metric.id)
    ).first()
    
    assert metadata is not None
    
    # Search for the exact text
    results = rag_system.search(metadata.embedding_text, top_k=1)
    
    # Verify top result
    assert len(results) >= 1
    top_result = results[0]
    assert top_result['record_type'] == 'metric'
    assert top_result['record_id'] == str(metric.id)
    assert top_result['similarity'] >= 0.99


@given(
    calories=st.integers(min_value=1000, max_value=4000),
    protein_g=st.floats(min_value=50, max_value=300),
    carbs_g=st.floats(min_value=100, max_value=500),
    fat_g=st.floats(min_value=30, max_value=150),
    days_offset=st.integers(min_value=0, max_value=365)
)
@settings(
    max_examples=10,
    deadline=10000,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_faiss_index_consistency_log(test_db, rag_system, calories, protein_g, carbs_g, fat_g, days_offset):
    """
    Test FAISS index consistency for daily logs.
    
    Verifies that indexed logs can be retrieved with high similarity.
    """
    # Create test log with unique date
    from datetime import timedelta
    log = DailyLog(
        id=f"test-log-{hash((calories, protein_g, days_offset))}",
        log_date=date.today() - timedelta(days=days_offset),
        calories_in=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g
    )
    test_db.add(log)
    test_db.commit()
    
    # Index the log
    rag_system.index_log(log)
    test_db.commit()
    
    # Get the embedding text
    from app.models.faiss_metadata import FaissMetadata
    metadata = test_db.query(FaissMetadata).filter(
        FaissMetadata.record_type == 'log',
        FaissMetadata.record_id == str(log.id)
    ).first()
    
    assert metadata is not None
    
    # Search for the exact text
    results = rag_system.search(metadata.embedding_text, top_k=1)
    
    # Verify top result
    assert len(results) >= 1
    top_result = results[0]
    assert top_result['record_type'] == 'log'
    assert top_result['record_id'] == str(log.id)
    assert top_result['similarity'] >= 0.99


def test_multiple_records_consistency(test_db, rag_system):
    """
    Test that multiple records can be indexed and retrieved correctly.
    
    This ensures that the index maintains consistency when multiple vectors are added.
    """
    # Create multiple activities
    activities = []
    for i in range(5):
        activity = StravaActivity(
            id=f"multi-test-{i}",
            strava_id=1000 + i,
            activity_type='Run',
            start_date=datetime.now(),
            distance_m=5000 + i * 1000,
            moving_time_s=1500 + i * 100,
            elevation_m=50 + i * 10,
            raw_json="{}"  # Required field
        )
        test_db.add(activity)
        activities.append(activity)
    
    test_db.commit()
    
    # Index all activities
    for activity in activities:
        rag_system.index_activity(activity)
    
    test_db.commit()
    
    # Verify each activity can be retrieved
    from app.models.faiss_metadata import FaissMetadata
    for activity in activities:
        metadata = test_db.query(FaissMetadata).filter(
            FaissMetadata.record_type == 'activity',
            FaissMetadata.record_id == str(activity.id)
        ).first()
        
        assert metadata is not None
        
        # Search for this specific activity
        results = rag_system.search(metadata.embedding_text, top_k=1)
        
        assert len(results) >= 1
        assert results[0]['record_id'] == str(activity.id)
        assert results[0]['similarity'] >= 0.99


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

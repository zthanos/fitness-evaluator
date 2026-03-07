"""Test RAG Integration

Tests the RAG system integration with chat service.
Validates Requirements 15 (RAG Context Retrieval) and 29 (LLM Prompt Engineering).

Note: Updated to use Ollama's nomic-embed-text model (768 dimensions) instead of 
sentence-transformers all-MiniLM-L6-v2 (384 dimensions).
"""
import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.services.rag_service import RAGSystem
import os
import tempfile


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
    # Use temporary file for index
    temp_dir = tempfile.mkdtemp()
    index_path = os.path.join(temp_dir, "test_index.bin")
    
    rag = RAGSystem(test_db, index_path=index_path)
    yield rag
    
    # Cleanup
    if os.path.exists(index_path):
        os.remove(index_path)
    metadata_path = index_path.replace(".bin", "_metadata.pkl")
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
    os.rmdir(temp_dir)


def test_rag_system_initialization(rag_system):
    """Test RAG system initializes correctly."""
    assert rag_system is not None
    assert rag_system.index is not None
    assert rag_system.EMBEDDING_DIM == 768
    assert rag_system.MODEL_NAME == "nomic-embed-text"


def test_embedding_generation(rag_system):
    """Test embedding generation produces correct dimensions."""
    text = "Running 5km in 25 minutes"
    embedding = rag_system.generate_embedding(text)
    
    # Validate embedding dimension (Requirement 15.6, 28.2)
    assert embedding.shape == (768,)
    assert embedding.dtype == 'float32'


def test_index_activity(test_db, rag_system):
    """Test indexing a Strava activity."""
    # Create test activity
    activity = StravaActivity(
        id="test-activity-1",
        strava_id=12345,
        name="Morning Run",
        type="Run",
        start_date=datetime.now(),
        distance_m=5000,
        moving_time_s=1500,
        elevation_m=50
    )
    test_db.add(activity)
    test_db.commit()
    
    # Index activity
    rag_system.index_activity(activity)
    
    # Verify index has one vector
    assert rag_system.index.ntotal == 1
    assert len(rag_system.metadata) == 1
    
    # Verify metadata
    record_type, record_id, text = rag_system.metadata[0]
    assert record_type == 'activity'
    assert record_id == 'test-activity-1'
    assert 'Morning Run' in text
    assert 'Run' in text


def test_index_metric(test_db, rag_system):
    """Test indexing a body metric."""
    # Create test metric
    metric = WeeklyMeasurement(
        id="test-metric-1",
        week_start_date=date.today(),
        weight_kg=75.5,
        body_fat_pct=15.0
    )
    test_db.add(metric)
    test_db.commit()
    
    # Index metric
    rag_system.index_metric(metric)
    
    # Verify index
    assert rag_system.index.ntotal == 1
    assert len(rag_system.metadata) == 1
    
    # Verify metadata
    record_type, record_id, text = rag_system.metadata[0]
    assert record_type == 'metric'
    assert '75.5 kg' in text


def test_index_daily_log(test_db, rag_system):
    """Test indexing a daily log."""
    # Create test log
    log = DailyLog(
        id="test-log-1",
        date=date.today(),
        calories=2000,
        protein_g=150,
        carbs_g=200,
        fats_g=70,
        adherence_score=85,
        mood="Good"
    )
    test_db.add(log)
    test_db.commit()
    
    # Index log
    rag_system.index_log(log)
    
    # Verify index
    assert rag_system.index.ntotal == 1
    assert len(rag_system.metadata) == 1
    
    # Verify metadata
    record_type, record_id, text = rag_system.metadata[0]
    assert record_type == 'log'
    assert '2000' in text
    assert 'Good' in text


def test_semantic_search(test_db, rag_system):
    """Test semantic search retrieves relevant records."""
    # Create multiple activities
    activities = [
        StravaActivity(
            id="run-1",
            strava_id=1,
            name="Morning Run",
            type="Run",
            start_date=datetime.now(),
            distance_m=5000,
            moving_time_s=1500
        ),
        StravaActivity(
            id="bike-1",
            strava_id=2,
            name="Evening Bike Ride",
            type="Ride",
            start_date=datetime.now(),
            distance_m=20000,
            moving_time_s=3600
        ),
        StravaActivity(
            id="run-2",
            strava_id=3,
            name="Long Run",
            type="Run",
            start_date=datetime.now(),
            distance_m=15000,
            moving_time_s=5400
        )
    ]
    
    for activity in activities:
        test_db.add(activity)
        rag_system.index_activity(activity)
    
    test_db.commit()
    
    # Search for running activities
    results = rag_system.search("running workout", top_k=3)
    
    # Validate results (Requirement 15.2, 15.3)
    assert len(results) > 0
    assert len(results) <= 3
    
    # Check result structure
    for result in results:
        assert 'record_type' in result
        assert 'record_id' in result
        assert 'text' in result
        assert 'similarity' in result
        assert result['record_type'] == 'activity'
    
    # Verify relevance ordering (Property 16: Semantic Search Relevance Ordering)
    similarities = [r['similarity'] for r in results]
    assert similarities == sorted(similarities, reverse=True), "Results should be ordered by similarity"


def test_search_empty_index(rag_system):
    """Test search on empty index returns empty results."""
    results = rag_system.search("test query", top_k=5)
    assert results == []


def test_search_top_k_limit(test_db, rag_system):
    """Test search respects top_k limit."""
    # Create 10 activities
    for i in range(10):
        activity = StravaActivity(
            id=f"activity-{i}",
            strava_id=i,
            name=f"Run {i}",
            type="Run",
            start_date=datetime.now(),
            distance_m=5000,
            moving_time_s=1500
        )
        test_db.add(activity)
        rag_system.index_activity(activity)
    
    test_db.commit()
    
    # Search with top_k=5 (Requirement 15.2)
    results = rag_system.search("running", top_k=5)
    
    assert len(results) == 5


def test_index_persistence(test_db):
    """Test index can be saved and loaded."""
    # Create temporary index
    temp_dir = tempfile.mkdtemp()
    index_path = os.path.join(temp_dir, "persist_test.bin")
    
    # Create RAG system and add data
    rag1 = RAGSystem(test_db, index_path=index_path)
    
    activity = StravaActivity(
        id="persist-1",
        strava_id=999,
        name="Test Activity",
        type="Run",
        start_date=datetime.now(),
        distance_m=5000,
        moving_time_s=1500
    )
    test_db.add(activity)
    test_db.commit()
    
    rag1.index_activity(activity)
    rag1.save_index()
    
    # Create new RAG system and load index
    rag2 = RAGSystem(test_db, index_path=index_path)
    
    # Verify index was loaded
    assert rag2.index.ntotal == 1
    assert len(rag2.metadata) == 1
    
    # Verify search works
    results = rag2.search("test activity", top_k=1)
    assert len(results) == 1
    assert results[0]['record_id'] == 'persist-1'
    
    # Cleanup
    os.remove(index_path)
    metadata_path = index_path.replace(".bin", "_metadata.pkl")
    os.remove(metadata_path)
    os.rmdir(temp_dir)


def test_format_activity_text(test_db, rag_system):
    """Test activity text formatting."""
    activity = StravaActivity(
        id="format-test",
        strava_id=123,
        name="Test Run",
        type="Run",
        start_date=datetime(2024, 1, 15, 8, 0, 0),
        distance_m=5000,
        moving_time_s=1500,
        elevation_m=100
    )
    
    text = rag_system._format_activity_text(activity)
    
    # Verify all key information is included (Requirement 28.3)
    assert "Test Run" in text
    assert "Run" in text
    assert "2024-01-15" in text
    assert "5.00 km" in text
    assert "25 minutes" in text
    assert "100 m" in text


def test_format_metric_text(test_db, rag_system):
    """Test metric text formatting."""
    metric = WeeklyMeasurement(
        id="metric-format",
        week_start_date=date(2024, 1, 15),
        weight_kg=75.5,
        body_fat_pct=15.2,
        chest_cm=100.0,
        waist_cm=85.0
    )
    
    text = rag_system._format_metric_text(metric)
    
    # Verify all key information is included (Requirement 28.4)
    assert "2024-01-15" in text
    assert "75.5 kg" in text
    assert "15.2%" in text
    assert "Chest: 100.0 cm" in text
    assert "Waist: 85.0 cm" in text


def test_format_log_text(test_db, rag_system):
    """Test daily log text formatting."""
    log = DailyLog(
        id="log-format",
        date=date(2024, 1, 15),
        calories=2000,
        protein_g=150,
        carbs_g=200,
        fats_g=70,
        adherence_score=85,
        mood="Energetic"
    )
    
    text = rag_system._format_log_text(log)
    
    # Verify all key information is included (Requirement 28.5)
    assert "2024-01-15" in text
    assert "2000" in text
    assert "150g" in text
    assert "200g" in text
    assert "70g" in text
    assert "85/100" in text
    assert "Energetic" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

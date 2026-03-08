"""
Test RAGRetriever evidence card generation.

This test verifies that RAGRetriever generates evidence cards correctly
according to requirements 4.1.1 and 4.1.3.

Requirements:
- 4.1.1: Generate evidence cards for each claim in AI responses
- 4.1.3: When the RAG_System retrieves an activity, create an evidence card linking it to the query
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.models.athlete_goal import AthleteGoal
from app.ai.retrieval.rag_retriever import RAGRetriever
from app.ai.retrieval.intent_router import Intent


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
def sample_activities(db_session):
    """Create sample activities for testing."""
    activities = []
    for i in range(3):
        activity = StravaActivity(
            strava_id=1000 + i,  # Required field
            athlete_id=1,
            activity_type="Run",
            start_date=datetime.now() - timedelta(days=i),
            distance_m=5000 + (i * 1000),
            moving_time_s=1800 + (i * 300),
            elevation_m=100 + (i * 50),
            avg_hr=150 + i,
            max_hr=180 + i,
            calories=300 + (i * 50),
            raw_json="{}",  # Required field
            week_id=f"2024-W{15 - i}"
        )
        db_session.add(activity)
        activities.append(activity)
    
    db_session.commit()
    return activities


def test_retrieve_generates_evidence_cards_by_default(db_session, sample_activities):
    """
    Test that RAGRetriever generates evidence cards by default.
    
    Validates: Requirement 4.1.3 - When the RAG_System retrieves an activity,
    create an evidence card linking it to the query.
    """
    retriever = RAGRetriever(db_session)
    
    # Retrieve activities (should generate evidence cards by default)
    results = retriever.retrieve(
        query="Show me my recent runs",
        athlete_id=1,
        intent=Intent.RECENT_PERFORMANCE
    )
    
    # Verify evidence cards were generated
    assert len(results) > 0, "Should retrieve at least one result"
    
    # Check that results are evidence cards (have required fields)
    for card in results:
        assert "claim_text" in card, "Evidence card should have claim_text"
        assert "source_type" in card, "Evidence card should have source_type"
        assert "source_id" in card, "Evidence card should have source_id"
        assert "source_date" in card, "Evidence card should have source_date"
        assert "relevance_score" in card, "Evidence card should have relevance_score"


def test_evidence_card_has_all_required_fields(db_session, sample_activities):
    """
    Test that evidence cards include all required fields.
    
    Validates: Requirement 4.1.2 - Evidence_Card SHALL include fields:
    claim_text, source_type, source_id, source_date, relevance_score
    """
    retriever = RAGRetriever(db_session)
    
    results = retriever.retrieve(
        query="Show me my recent runs",
        athlete_id=1,
        intent=Intent.RECENT_PERFORMANCE
    )
    
    assert len(results) > 0, "Should retrieve at least one result"
    
    # Verify first evidence card has all required fields
    card = results[0]
    
    # Check field presence
    assert "claim_text" in card
    assert "source_type" in card
    assert "source_id" in card
    assert "source_date" in card
    assert "relevance_score" in card
    
    # Check field types
    assert isinstance(card["claim_text"], str)
    assert isinstance(card["source_type"], str)
    assert isinstance(card["source_id"], (int, str))  # Can be int or string (UUID)
    assert isinstance(card["source_date"], str)
    assert isinstance(card["relevance_score"], float)
    
    # Check field values
    assert card["source_type"] == "activity"
    assert card["source_id"]  # Should not be empty
    assert 0.0 <= card["relevance_score"] <= 1.0


def test_evidence_card_claim_text_is_descriptive(db_session, sample_activities):
    """
    Test that evidence card claim_text is descriptive and includes activity details.
    """
    retriever = RAGRetriever(db_session)
    
    results = retriever.retrieve(
        query="Show me my recent runs",
        athlete_id=1,
        intent=Intent.RECENT_PERFORMANCE
    )
    
    assert len(results) > 0
    
    card = results[0]
    claim_text = card["claim_text"]
    
    # Claim text should include activity type
    assert "Run" in claim_text
    
    # Claim text should include date
    assert "on" in claim_text
    
    # Claim text should include distance or duration
    assert "km" in claim_text or "min" in claim_text


def test_retrieve_without_evidence_cards(db_session, sample_activities):
    """
    Test that RAGRetriever can retrieve raw data without evidence cards.
    
    This tests the flexibility of the implementation - evidence cards
    can be disabled if needed for specific use cases.
    """
    retriever = RAGRetriever(db_session)
    
    # Retrieve without evidence cards
    results = retriever.retrieve(
        query="Show me my recent runs",
        athlete_id=1,
        intent=Intent.RECENT_PERFORMANCE,
        generate_cards=False
    )
    
    assert len(results) > 0
    
    # Results should be raw activity data (not evidence cards)
    for record in results:
        assert "type" in record
        assert "id" in record
        # Should NOT have evidence card fields
        assert "claim_text" not in record
        assert "relevance_score" not in record


def test_evidence_cards_for_multiple_data_types(db_session):
    """
    Test that evidence cards are generated for different data types.
    
    Validates that evidence cards work for activities, metrics, logs, and goals.
    """
    # Add different types of data
    activity = StravaActivity(
        strava_id=2000,  # Required field
        athlete_id=1,
        activity_type="Run",
        start_date=datetime.now(),
        distance_m=5000,
        moving_time_s=1800,
        raw_json="{}",  # Required field
        week_id="2024-W15"
    )
    db_session.add(activity)
    
    metric = WeeklyMeasurement(
        id=1,
        week_start=datetime.now().date(),
        weight_kg=70.0,
        rhr_bpm=60
    )
    db_session.add(metric)
    
    log = DailyLog(
        id=1,
        log_date=datetime.now().date(),
        calories_in=2000,
        protein_g=150
    )
    db_session.add(log)
    
    goal = AthleteGoal(
        athlete_id="1",
        goal_type="Marathon",
        target_value=240.0,  # 4 hours in minutes
        description="Complete a marathon in under 4 hours",
        status="active"
    )
    db_session.add(goal)
    
    db_session.commit()
    
    retriever = RAGRetriever(db_session)
    
    # Retrieve with goal_progress intent (includes multiple data types)
    results = retriever.retrieve(
        query="How am I progressing toward my goals?",
        athlete_id=1,
        intent=Intent.GOAL_PROGRESS
    )
    
    # Should have evidence cards for different types
    source_types = {card["source_type"] for card in results}
    
    # At least activities and goals should be present
    assert "activity" in source_types
    assert "goal" in source_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

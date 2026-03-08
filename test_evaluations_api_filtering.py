"""
Test suite for GET /api/evaluations endpoint filtering, sorting, and limit functionality.

This test verifies that task 3.4 requirements are correctly implemented:
- Database query instead of in-memory store
- athlete_id filtering
- date_from and date_to filtering
- score_min and score_max filtering
- Sorting by created_at DESC
- Limit parameter

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8
"""
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import uuid

from app.main import app
from app.database import get_db
from app.models.evaluation import Evaluation

client = TestClient(app)


@pytest.fixture
def db_session():
    """Create a test database session."""
    from app.database import SessionLocal, engine
    from app.models.base import Base
    
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_evaluations(db_session: Session):
    """Create sample evaluations for testing."""
    evaluations = []
    
    # Create evaluations with different attributes for filtering tests
    test_data = [
        # athlete_id, period_start, period_end, overall_score, created_at_offset (days ago)
        (1, date(2024, 1, 1), date(2024, 1, 7), 85, 10),
        (1, date(2024, 1, 8), date(2024, 1, 14), 75, 9),
        (1, date(2024, 1, 15), date(2024, 1, 21), 90, 8),
        (1, date(2024, 1, 22), date(2024, 1, 28), 65, 7),
        (1, date(2024, 2, 1), date(2024, 2, 7), 80, 6),
        (2, date(2024, 1, 1), date(2024, 1, 7), 70, 5),  # Different athlete
        (2, date(2024, 1, 8), date(2024, 1, 14), 95, 4),  # Different athlete
    ]
    
    for athlete_id, period_start, period_end, score, days_ago in test_data:
        eval_id = str(uuid.uuid4())
        created_at = datetime.utcnow() - timedelta(days=days_ago)
        
        evaluation = Evaluation(
            id=eval_id,
            athlete_id=athlete_id,
            period_start=period_start,
            period_end=period_end,
            period_type='weekly',
            overall_score=score,
            strengths=['Strength 1', 'Strength 2'],
            improvements=['Improvement 1'],
            tips=['Tip 1', 'Tip 2'],
            recommended_exercises=['Exercise 1'],
            goal_alignment='Good progress',
            confidence_score=0.85,
            created_at=created_at,
            updated_at=created_at
        )
        db_session.add(evaluation)
        evaluations.append(evaluation)
    
    db_session.commit()
    return evaluations


def override_get_db(db_session):
    """Override the get_db dependency."""
    def _override():
        try:
            yield db_session
        finally:
            pass
    return _override


def test_get_evaluations_athlete_id_filtering(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations filters by athlete_id correctly.
    
    Requirement 3.2: WHEN retrieving evaluations, THE Evaluation_API SHALL filter by athlete_id
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Test athlete 1 - should get 5 evaluations
    response = client.get("/api/evaluations?athlete_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    assert all(eval['athlete_id'] == 1 for eval in data)
    
    # Test athlete 2 - should get 2 evaluations
    response = client.get("/api/evaluations?athlete_id=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(eval['athlete_id'] == 2 for eval in data)
    
    app.dependency_overrides.clear()


def test_get_evaluations_date_from_filtering(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations filters by date_from correctly.
    
    Requirement 3.3: WHEN date_from filter is provided, THE Evaluation_API SHALL return 
    only evaluations where period_start is greater than or equal to date_from
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Filter for evaluations starting from 2024-01-15 or later
    response = client.get("/api/evaluations?athlete_id=1&date_from=2024-01-15")
    assert response.status_code == 200
    data = response.json()
    
    # Should get 3 evaluations (Jan 15, Jan 22, Feb 1)
    assert len(data) == 3
    for eval in data:
        period_start = date.fromisoformat(eval['period_start'])
        assert period_start >= date(2024, 1, 15)
    
    app.dependency_overrides.clear()


def test_get_evaluations_date_to_filtering(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations filters by date_to correctly.
    
    Requirement 3.4: WHEN date_to filter is provided, THE Evaluation_API SHALL return 
    only evaluations where period_end is less than or equal to date_to
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Filter for evaluations ending on or before 2024-01-21
    response = client.get("/api/evaluations?athlete_id=1&date_to=2024-01-21")
    assert response.status_code == 200
    data = response.json()
    
    # Should get 3 evaluations (Jan 7, Jan 14, Jan 21)
    assert len(data) == 3
    for eval in data:
        period_end = date.fromisoformat(eval['period_end'])
        assert period_end <= date(2024, 1, 21)
    
    app.dependency_overrides.clear()


def test_get_evaluations_date_range_filtering(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations filters by both date_from and date_to correctly.
    
    Requirements 3.3, 3.4: Combined date range filtering
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Filter for evaluations in January 2024 (starting from Jan 8, ending by Jan 28)
    response = client.get("/api/evaluations?athlete_id=1&date_from=2024-01-08&date_to=2024-01-28")
    assert response.status_code == 200
    data = response.json()
    
    # Should get 3 evaluations (Jan 8-14, Jan 15-21, Jan 22-28)
    assert len(data) == 3
    for eval in data:
        period_start = date.fromisoformat(eval['period_start'])
        period_end = date.fromisoformat(eval['period_end'])
        assert period_start >= date(2024, 1, 8)
        assert period_end <= date(2024, 1, 28)
    
    app.dependency_overrides.clear()


def test_get_evaluations_score_min_filtering(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations filters by score_min correctly.
    
    Requirement 3.5: WHEN score_min filter is provided, THE Evaluation_API SHALL return 
    only evaluations where overall_score is greater than or equal to score_min
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Filter for evaluations with score >= 80
    response = client.get("/api/evaluations?athlete_id=1&score_min=80")
    assert response.status_code == 200
    data = response.json()
    
    # Should get 3 evaluations (scores: 85, 90, 80)
    assert len(data) == 3
    for eval in data:
        assert eval['overall_score'] >= 80
    
    app.dependency_overrides.clear()


def test_get_evaluations_score_max_filtering(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations filters by score_max correctly.
    
    Requirement 3.6: WHEN score_max filter is provided, THE Evaluation_API SHALL return 
    only evaluations where overall_score is less than or equal to score_max
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Filter for evaluations with score <= 75
    response = client.get("/api/evaluations?athlete_id=1&score_max=75")
    assert response.status_code == 200
    data = response.json()
    
    # Should get 2 evaluations (scores: 75, 65)
    assert len(data) == 2
    for eval in data:
        assert eval['overall_score'] <= 75
    
    app.dependency_overrides.clear()


def test_get_evaluations_score_range_filtering(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations filters by both score_min and score_max correctly.
    
    Requirements 3.5, 3.6: Combined score range filtering
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Filter for evaluations with score between 75 and 85 (inclusive)
    response = client.get("/api/evaluations?athlete_id=1&score_min=75&score_max=85")
    assert response.status_code == 200
    data = response.json()
    
    # Should get 3 evaluations (scores: 85, 75, 80)
    assert len(data) == 3
    for eval in data:
        assert 75 <= eval['overall_score'] <= 85
    
    app.dependency_overrides.clear()


def test_get_evaluations_sorting_by_created_at_desc(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations sorts by created_at in descending order (newest first).
    
    Requirement 3.7: THE Evaluation_API SHALL sort evaluations by created_at in descending order
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    response = client.get("/api/evaluations?athlete_id=1")
    assert response.status_code == 200
    data = response.json()
    
    # Verify we have multiple evaluations
    assert len(data) >= 2
    
    # Verify sorting: each evaluation should have generated_at >= next evaluation's generated_at
    # Note: generated_at is the field name in the response schema (maps to created_at in DB)
    for i in range(len(data) - 1):
        current_created = datetime.fromisoformat(data[i]['generated_at'].replace('Z', '+00:00'))
        next_created = datetime.fromisoformat(data[i + 1]['generated_at'].replace('Z', '+00:00'))
        assert current_created >= next_created, \
            f"Evaluations not sorted correctly: {current_created} should be >= {next_created}"
    
    app.dependency_overrides.clear()


def test_get_evaluations_limit_parameter(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations respects the limit parameter.
    
    Requirement 3.8: THE Evaluation_API SHALL apply the limit parameter to restrict the number of results
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Test limit=2
    response = client.get("/api/evaluations?athlete_id=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Test limit=3
    response = client.get("/api/evaluations?athlete_id=1&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    
    # Test default limit (should get all 5 for athlete 1)
    response = client.get("/api/evaluations?athlete_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    
    app.dependency_overrides.clear()


def test_get_evaluations_combined_filters(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations correctly applies multiple filters simultaneously.
    
    Requirements 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8: Combined filtering
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Complex filter: athlete_id=1, date range in January, score >= 75, limit=2
    response = client.get(
        "/api/evaluations?athlete_id=1&date_from=2024-01-01&date_to=2024-01-31"
        "&score_min=75&limit=2"
    )
    assert response.status_code == 200
    data = response.json()
    
    # Should get 2 evaluations (limited) that match all criteria
    assert len(data) == 2
    for eval in data:
        assert eval['athlete_id'] == 1
        period_start = date.fromisoformat(eval['period_start'])
        period_end = date.fromisoformat(eval['period_end'])
        assert date(2024, 1, 1) <= period_start
        assert period_end <= date(2024, 1, 31)
        assert eval['overall_score'] >= 75
    
    # Verify sorting (newest first)
    # Note: generated_at is the field name in the response schema (maps to created_at in DB)
    if len(data) >= 2:
        created_0 = datetime.fromisoformat(data[0]['generated_at'].replace('Z', '+00:00'))
        created_1 = datetime.fromisoformat(data[1]['generated_at'].replace('Z', '+00:00'))
        assert created_0 >= created_1
    
    app.dependency_overrides.clear()


def test_get_evaluations_empty_results(db_session: Session, sample_evaluations):
    """
    Test that GET /api/evaluations returns empty list when no evaluations match filters.
    
    Requirement 3.1: Query from database with proper filtering
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Filter that matches no evaluations
    response = client.get("/api/evaluations?athlete_id=1&score_min=95")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0
    assert isinstance(data, list)
    
    app.dependency_overrides.clear()


def test_get_evaluations_database_query_not_memory(db_session: Session):
    """
    Test that GET /api/evaluations queries from database, not in-memory store.
    
    Requirement 3.1: WHEN the GET /api/evaluations endpoint is called, 
    THE Evaluation_API SHALL query evaluations from the database
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create an evaluation directly in the database
    eval_id = str(uuid.uuid4())
    evaluation = Evaluation(
        id=eval_id,
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type='weekly',
        overall_score=88,
        strengths=['Test strength'],
        improvements=['Test improvement'],
        tips=['Test tip'],
        recommended_exercises=['Test exercise'],
        goal_alignment='Test alignment',
        confidence_score=0.9
    )
    db_session.add(evaluation)
    db_session.commit()
    
    # Query via API - should retrieve from database
    response = client.get("/api/evaluations?athlete_id=1")
    assert response.status_code == 200
    data = response.json()
    
    # Verify the evaluation is returned
    assert len(data) == 1
    assert data[0]['id'] == eval_id
    assert data[0]['overall_score'] == 88
    
    app.dependency_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test suite for GET /api/evaluations/{id} endpoint.

This test verifies that task 3.6 requirements are correctly implemented:
- Database query by ID instead of in-memory store
- Returns 404 if evaluation not found

Requirements: 3.9, 3.10
"""
import pytest
from datetime import date, datetime
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


def override_get_db(db_session):
    """Override the get_db dependency."""
    def _override():
        try:
            yield db_session
        finally:
            pass
    return _override


def test_get_evaluation_by_id_success(db_session: Session):
    """
    Test that GET /api/evaluations/{id} retrieves evaluation from database by ID.
    
    Requirement 3.9: WHEN the GET /api/evaluations/{id} endpoint is called, 
    THE Evaluation_API SHALL retrieve the evaluation from the database by ID
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
        strengths=['Strength 1', 'Strength 2'],
        improvements=['Improvement 1'],
        tips=['Tip 1', 'Tip 2'],
        recommended_exercises=['Exercise 1', 'Exercise 2'],
        goal_alignment='Good progress towards goals',
        confidence_score=0.9
    )
    db_session.add(evaluation)
    db_session.commit()
    
    # Query via API - should retrieve from database
    response = client.get(f"/api/evaluations/{eval_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data['id'] == eval_id
    assert data['athlete_id'] == 1
    assert data['period_start'] == '2024-01-01'
    assert data['period_end'] == '2024-01-07'
    assert data['period_type'] == 'weekly'
    assert data['overall_score'] == 88
    assert data['strengths'] == ['Strength 1', 'Strength 2']
    assert data['improvements'] == ['Improvement 1']
    assert data['tips'] == ['Tip 1', 'Tip 2']
    assert data['recommended_exercises'] == ['Exercise 1', 'Exercise 2']
    assert data['goal_alignment'] == 'Good progress towards goals'
    assert data['confidence_score'] == 0.9
    
    app.dependency_overrides.clear()


def test_get_evaluation_by_id_not_found(db_session: Session):
    """
    Test that GET /api/evaluations/{id} returns 404 if evaluation not found.
    
    Requirement 3.10: IF an evaluation ID does not exist, 
    THEN THE Evaluation_API SHALL return a 404 error
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Use a random UUID that doesn't exist in the database
    non_existent_id = str(uuid.uuid4())
    
    # Query via API - should return 404
    response = client.get(f"/api/evaluations/{non_existent_id}")
    assert response.status_code == 404
    
    data = response.json()
    assert 'detail' in data
    assert non_existent_id in data['detail']
    assert 'not found' in data['detail'].lower()
    
    app.dependency_overrides.clear()


def test_get_evaluation_by_id_database_query_not_memory(db_session: Session):
    """
    Test that GET /api/evaluations/{id} queries from database, not in-memory store.
    
    This test ensures the endpoint uses database persistence, not the old in-memory store.
    
    Requirement 3.9: Query from database by ID
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create multiple evaluations in the database
    eval_ids = []
    for i in range(3):
        eval_id = str(uuid.uuid4())
        evaluation = Evaluation(
            id=eval_id,
            athlete_id=1,
            period_start=date(2024, 1, 1 + i * 7),
            period_end=date(2024, 1, 7 + i * 7),
            period_type='weekly',
            overall_score=80 + i,
            strengths=[f'Strength {i}'],
            improvements=[f'Improvement {i}'],
            tips=[f'Tip {i}'],
            recommended_exercises=[f'Exercise {i}'],
            goal_alignment=f'Alignment {i}',
            confidence_score=0.8 + i * 0.05
        )
        db_session.add(evaluation)
        eval_ids.append(eval_id)
    
    db_session.commit()
    
    # Query each evaluation by ID - should retrieve correct one from database
    for i, eval_id in enumerate(eval_ids):
        response = client.get(f"/api/evaluations/{eval_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data['id'] == eval_id
        assert data['overall_score'] == 80 + i
        assert data['strengths'] == [f'Strength {i}']
        assert data['goal_alignment'] == f'Alignment {i}'
    
    app.dependency_overrides.clear()


def test_get_evaluation_by_id_with_empty_arrays(db_session: Session):
    """
    Test that GET /api/evaluations/{id} correctly handles evaluations with empty arrays.
    
    Edge case: Evaluation with no strengths, improvements, tips, or recommended exercises.
    
    Requirement 3.9: Query from database by ID
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create an evaluation with empty arrays
    eval_id = str(uuid.uuid4())
    evaluation = Evaluation(
        id=eval_id,
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type='weekly',
        overall_score=50,
        strengths=[],
        improvements=[],
        tips=[],
        recommended_exercises=[],
        goal_alignment='Needs more data',
        confidence_score=0.3
    )
    db_session.add(evaluation)
    db_session.commit()
    
    # Query via API
    response = client.get(f"/api/evaluations/{eval_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data['id'] == eval_id
    assert data['strengths'] == []
    assert data['improvements'] == []
    assert data['tips'] == []
    assert data['recommended_exercises'] == []
    
    app.dependency_overrides.clear()


def test_get_evaluation_by_id_boundary_scores(db_session: Session):
    """
    Test that GET /api/evaluations/{id} correctly handles boundary score values.
    
    Edge case: Scores at boundaries (0 and 100).
    
    Requirement 3.9: Query from database by ID
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Test score = 0
    eval_id_0 = str(uuid.uuid4())
    evaluation_0 = Evaluation(
        id=eval_id_0,
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type='weekly',
        overall_score=0,
        strengths=[],
        improvements=['Everything needs work'],
        tips=['Start with basics'],
        recommended_exercises=['Basic exercise'],
        goal_alignment='Far from goals',
        confidence_score=0.5
    )
    db_session.add(evaluation_0)
    
    # Test score = 100
    eval_id_100 = str(uuid.uuid4())
    evaluation_100 = Evaluation(
        id=eval_id_100,
        athlete_id=1,
        period_start=date(2024, 1, 8),
        period_end=date(2024, 1, 14),
        period_type='weekly',
        overall_score=100,
        strengths=['Perfect performance'],
        improvements=[],
        tips=['Keep it up'],
        recommended_exercises=['Advanced exercise'],
        goal_alignment='Goals exceeded',
        confidence_score=1.0
    )
    db_session.add(evaluation_100)
    db_session.commit()
    
    # Query score = 0
    response = client.get(f"/api/evaluations/{eval_id_0}")
    assert response.status_code == 200
    data = response.json()
    assert data['overall_score'] == 0
    
    # Query score = 100
    response = client.get(f"/api/evaluations/{eval_id_100}")
    assert response.status_code == 200
    data = response.json()
    assert data['overall_score'] == 100
    
    app.dependency_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

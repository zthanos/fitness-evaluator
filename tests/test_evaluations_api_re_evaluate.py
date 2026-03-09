"""
Test suite for POST /api/evaluations/{id}/re-evaluate endpoint.

This test verifies that task 5.1 requirements are correctly implemented:
- Retrieve original evaluation by ID
- Return 404 if not found
- Extract period_start, period_end, period_type, athlete_id from original
- Call EvaluationEngine with same parameters
- Generate new UUID for new evaluation
- Save new evaluation to database
- Return new evaluation in response

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""
import pytest
from datetime import date, datetime
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import uuid
from unittest.mock import AsyncMock, patch

from app.main import app
from app.database import get_db
from app.models.evaluation import Evaluation
from app.schemas.evaluation_schemas import EvaluationReport

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


def create_mock_evaluation_report():
    """Create a mock evaluation report for testing."""
    return EvaluationReport(
        overall_score=85,
        strengths=['New strength 1', 'New strength 2'],
        improvements=['New improvement 1'],
        tips=['New tip 1', 'New tip 2'],
        recommended_exercises=['New exercise 1', 'New exercise 2'],
        goal_alignment='Updated progress towards goals',
        confidence_score=0.92
    )


def test_re_evaluate_success(db_session: Session):
    """
    Test that POST /api/evaluations/{id}/re-evaluate successfully creates a new evaluation.
    
    Requirements:
    - 4.2: Retrieve original evaluation by ID
    - 4.4: Use same period_start, period_end, period_type, athlete_id
    - 4.5: Generate new evaluation with new ID
    - 4.6: Save new evaluation to database
    - 4.7: Return newly generated evaluation
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create an original evaluation in the database
    original_id = str(uuid.uuid4())
    original_evaluation = Evaluation(
        id=original_id,
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type='weekly',
        overall_score=88,
        strengths=['Original strength 1', 'Original strength 2'],
        improvements=['Original improvement 1'],
        tips=['Original tip 1', 'Original tip 2'],
        recommended_exercises=['Original exercise 1', 'Original exercise 2'],
        goal_alignment='Original goal alignment',
        confidence_score=0.9
    )
    db_session.add(original_evaluation)
    db_session.commit()
    
    # Mock the EvaluationEngine to avoid actual LLM calls
    mock_report = create_mock_evaluation_report()
    
    with patch('app.api.evaluations.EvaluationEngine') as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_report)
        
        # Call re-evaluate endpoint
        response = client.post(f"/api/evaluations/{original_id}/re-evaluate")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify new evaluation has different ID
        assert data['id'] != original_id
        
        # Verify same parameters as original
        assert data['athlete_id'] == 1
        assert data['period_start'] == '2024-01-01'
        assert data['period_end'] == '2024-01-07'
        assert data['period_type'] == 'weekly'
        
        # Verify new evaluation content from mock
        assert data['overall_score'] == 85
        assert data['strengths'] == ['New strength 1', 'New strength 2']
        assert data['improvements'] == ['New improvement 1']
        assert data['tips'] == ['New tip 1', 'New tip 2']
        assert data['recommended_exercises'] == ['New exercise 1', 'New exercise 2']
        assert data['goal_alignment'] == 'Updated progress towards goals'
        assert data['confidence_score'] == 0.92
        
        # Verify EvaluationEngine was called with correct parameters
        mock_instance.generate_evaluation.assert_called_once_with(
            athlete_id=1,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            period_type='weekly'
        )
    
    # Verify new evaluation was saved to database
    new_eval_id = data['id']
    saved_evaluation = db_session.query(Evaluation).filter(Evaluation.id == new_eval_id).first()
    assert saved_evaluation is not None
    assert saved_evaluation.athlete_id == 1
    assert saved_evaluation.period_start == date(2024, 1, 1)
    assert saved_evaluation.period_end == date(2024, 1, 7)
    assert saved_evaluation.period_type == 'weekly'
    
    # Verify original evaluation still exists
    original_still_exists = db_session.query(Evaluation).filter(Evaluation.id == original_id).first()
    assert original_still_exists is not None
    
    app.dependency_overrides.clear()


def test_re_evaluate_not_found(db_session: Session):
    """
    Test that POST /api/evaluations/{id}/re-evaluate returns 404 if original not found.
    
    Requirement 4.3: IF the original evaluation does not exist, 
    THEN THE Evaluation_API SHALL return a 404 error
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Use a random UUID that doesn't exist in the database
    non_existent_id = str(uuid.uuid4())
    
    # Call re-evaluate endpoint - should return 404
    response = client.post(f"/api/evaluations/{non_existent_id}/re-evaluate")
    assert response.status_code == 404
    
    data = response.json()
    assert 'detail' in data
    assert non_existent_id in data['detail']
    assert 'not found' in data['detail'].lower()
    
    app.dependency_overrides.clear()


def test_re_evaluate_preserves_all_parameters(db_session: Session):
    """
    Test that re-evaluate preserves all parameters from original evaluation.
    
    Requirement 4.4: Use same period_start, period_end, period_type, athlete_id
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create original evaluation with specific parameters
    original_id = str(uuid.uuid4())
    original_evaluation = Evaluation(
        id=original_id,
        athlete_id=42,  # Non-default athlete ID
        period_start=date(2024, 3, 15),
        period_end=date(2024, 3, 28),
        period_type='bi-weekly',
        overall_score=75,
        strengths=['Strength'],
        improvements=['Improvement'],
        tips=['Tip'],
        recommended_exercises=['Exercise'],
        goal_alignment='Alignment',
        confidence_score=0.85
    )
    db_session.add(original_evaluation)
    db_session.commit()
    
    # Mock the EvaluationEngine
    mock_report = create_mock_evaluation_report()
    
    with patch('app.api.evaluations.EvaluationEngine') as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_report)
        
        # Call re-evaluate endpoint
        response = client.post(f"/api/evaluations/{original_id}/re-evaluate")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all parameters match original
        assert data['athlete_id'] == 42
        assert data['period_start'] == '2024-03-15'
        assert data['period_end'] == '2024-03-28'
        assert data['period_type'] == 'bi-weekly'
        
        # Verify EvaluationEngine was called with exact parameters
        mock_instance.generate_evaluation.assert_called_once_with(
            athlete_id=42,
            period_start=date(2024, 3, 15),
            period_end=date(2024, 3, 28),
            period_type='bi-weekly'
        )
    
    app.dependency_overrides.clear()


def test_re_evaluate_generates_unique_id(db_session: Session):
    """
    Test that re-evaluate generates a unique ID for the new evaluation.
    
    Requirement 4.5: Generate new evaluation with new ID
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create original evaluation
    original_id = str(uuid.uuid4())
    original_evaluation = Evaluation(
        id=original_id,
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type='weekly',
        overall_score=80,
        strengths=['Strength'],
        improvements=['Improvement'],
        tips=['Tip'],
        recommended_exercises=['Exercise'],
        goal_alignment='Alignment',
        confidence_score=0.8
    )
    db_session.add(original_evaluation)
    db_session.commit()
    
    # Mock the EvaluationEngine
    mock_report = create_mock_evaluation_report()
    
    with patch('app.api.evaluations.EvaluationEngine') as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_report)
        
        # Call re-evaluate multiple times
        response1 = client.post(f"/api/evaluations/{original_id}/re-evaluate")
        response2 = client.post(f"/api/evaluations/{original_id}/re-evaluate")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Verify all IDs are unique
        assert data1['id'] != original_id
        assert data2['id'] != original_id
        assert data1['id'] != data2['id']
        
        # Verify all evaluations exist in database
        eval1 = db_session.query(Evaluation).filter(Evaluation.id == data1['id']).first()
        eval2 = db_session.query(Evaluation).filter(Evaluation.id == data2['id']).first()
        original = db_session.query(Evaluation).filter(Evaluation.id == original_id).first()
        
        assert eval1 is not None
        assert eval2 is not None
        assert original is not None
    
    app.dependency_overrides.clear()


def test_re_evaluate_with_monthly_period(db_session: Session):
    """
    Test re-evaluate with monthly period type.
    
    Requirement 4.4: Use same period_type
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create original evaluation with monthly period
    original_id = str(uuid.uuid4())
    original_evaluation = Evaluation(
        id=original_id,
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        period_type='monthly',
        overall_score=90,
        strengths=['Strength'],
        improvements=['Improvement'],
        tips=['Tip'],
        recommended_exercises=['Exercise'],
        goal_alignment='Alignment',
        confidence_score=0.95
    )
    db_session.add(original_evaluation)
    db_session.commit()
    
    # Mock the EvaluationEngine
    mock_report = create_mock_evaluation_report()
    
    with patch('app.api.evaluations.EvaluationEngine') as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_report)
        
        # Call re-evaluate endpoint
        response = client.post(f"/api/evaluations/{original_id}/re-evaluate")
        assert response.status_code == 200
        
        data = response.json()
        assert data['period_type'] == 'monthly'
        
        # Verify EvaluationEngine was called with monthly period
        mock_instance.generate_evaluation.assert_called_once_with(
            athlete_id=1,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_type='monthly'
        )
    
    app.dependency_overrides.clear()


def test_re_evaluate_database_save_failure(db_session: Session):
    """
    Test that re-evaluate handles database save failures gracefully.
    
    Verifies error handling when database commit fails.
    """
    app.dependency_overrides[get_db] = override_get_db(db_session)
    
    # Create original evaluation
    original_id = str(uuid.uuid4())
    original_evaluation = Evaluation(
        id=original_id,
        athlete_id=1,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        period_type='weekly',
        overall_score=80,
        strengths=['Strength'],
        improvements=['Improvement'],
        tips=['Tip'],
        recommended_exercises=['Exercise'],
        goal_alignment='Alignment',
        confidence_score=0.8
    )
    db_session.add(original_evaluation)
    db_session.commit()
    
    # Mock the EvaluationEngine
    mock_report = create_mock_evaluation_report()
    
    with patch('app.api.evaluations.EvaluationEngine') as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_report)
        
        # Mock db.commit to raise an exception
        with patch.object(db_session, 'commit', side_effect=Exception('Database error')):
            response = client.post(f"/api/evaluations/{original_id}/re-evaluate")
            
            # Should return 500 error
            assert response.status_code == 500
            data = response.json()
            assert 'detail' in data
            assert 'Failed to save evaluation' in data['detail']
    
    app.dependency_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

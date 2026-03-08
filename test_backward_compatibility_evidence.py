"""
Test backward compatibility for evidence_data in WeeklyEval records.

Validates Requirement 4.1.6: Maintain backward compatibility with existing 
WeeklyEval records that lack evidence_data.

This test ensures that:
1. Old records with null evidence_map_json can be read without errors
2. The evidence_cards property returns an empty list for null evidence_map_json
3. New records with evidence_map_json work correctly
4. The API layer handles both old and new records gracefully
"""

import pytest
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_eval import WeeklyEval
from app.models.weekly_measurement import WeeklyMeasurement
from app.services.eval_service import EvaluationService


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_old_record_with_null_evidence_map_json(db_session: Session):
    """
    Test that old WeeklyEval records with null evidence_map_json are readable.
    
    Validates Requirement 4.1.6: Handle null evidence_data in existing records
    """
    # Create a WeeklyMeasurement
    measurement = WeeklyMeasurement(
        week_start=date(2024, 1, 1),
        weight_kg=70.0,
        body_fat_pct=15.0,
        waist_cm=80.0,
        rhr_bpm=60,
        sleep_avg_hrs=7.5
    )
    db_session.add(measurement)
    db_session.commit()
    
    week_id = str(measurement.id)
    
    # Create an old WeeklyEval record without evidence_map_json (simulating old system)
    old_eval = WeeklyEval(
        week_id=week_id,
        input_hash="old_hash_123",
        llm_model="mixtral-8x7b-instruct",
        raw_llm_response='{"overall_score": 85}',
        parsed_output_json={
            "overall_score": 85,
            "summary": "Old evaluation without evidence tracking"
        },
        generated_at=datetime(2024, 1, 8, 10, 0, 0),
        evidence_map_json=None  # Old system didn't have evidence tracking
    )
    db_session.add(old_eval)
    db_session.commit()
    
    # Read the old evaluation
    eval_service = EvaluationService(db_session)
    retrieved_eval = eval_service.get_evaluation(week_id)
    
    # Verify the old record is readable
    assert retrieved_eval is not None
    assert retrieved_eval.week_id == week_id
    assert retrieved_eval.input_hash == "old_hash_123"
    assert retrieved_eval.evidence_map_json is None
    
    # Verify evidence_cards property returns empty list for backward compatibility
    assert retrieved_eval.evidence_cards == []
    assert isinstance(retrieved_eval.evidence_cards, list)


def test_new_record_with_evidence_map_json(db_session: Session):
    """
    Test that new WeeklyEval records with evidence_map_json work correctly.
    
    Validates Requirement 4.1.6: New records with evidence_data are stored correctly
    """
    # Create a WeeklyMeasurement
    measurement = WeeklyMeasurement(
        week_start=date(2024, 1, 8),
        weight_kg=70.0,
        body_fat_pct=15.0,
        waist_cm=80.0,
        rhr_bpm=60,
        sleep_avg_hrs=7.5
    )
    db_session.add(measurement)
    db_session.commit()
    
    week_id = str(measurement.id)
    
    # Create a new WeeklyEval record with evidence_map_json
    evidence_cards = [
        {
            "claim_text": "You completed 5 runs this week",
            "source_type": "activity",
            "source_id": "activity_123",
            "source_date": "2024-01-08",
            "relevance_score": 0.95
        },
        {
            "claim_text": "Your average heart rate was 145 bpm",
            "source_type": "activity",
            "source_id": "activity_124",
            "source_date": "2024-01-09",
            "relevance_score": 0.90
        }
    ]
    
    new_eval = WeeklyEval(
        week_id=week_id,
        input_hash="new_hash_456",
        llm_model="mixtral-8x7b-instruct",
        raw_llm_response='{"overall_score": 90}',
        parsed_output_json={
            "overall_score": 90,
            "summary": "New evaluation with evidence tracking"
        },
        generated_at=datetime(2024, 1, 15, 10, 0, 0),
        evidence_map_json={"evidence_cards": evidence_cards}
    )
    db_session.add(new_eval)
    db_session.commit()
    
    # Read the new evaluation
    eval_service = EvaluationService(db_session)
    retrieved_eval = eval_service.get_evaluation(week_id)
    
    # Verify the new record is readable
    assert retrieved_eval is not None
    assert retrieved_eval.week_id == week_id
    assert retrieved_eval.input_hash == "new_hash_456"
    assert retrieved_eval.evidence_map_json is not None
    
    # Verify evidence_cards property returns the evidence cards
    assert retrieved_eval.evidence_cards == evidence_cards
    assert len(retrieved_eval.evidence_cards) == 2
    assert retrieved_eval.evidence_cards[0]["claim_text"] == "You completed 5 runs this week"


def test_empty_evidence_map_json(db_session: Session):
    """
    Test that WeeklyEval records with empty evidence_map_json work correctly.
    
    Validates Requirement 4.1.6: Provide default empty list when evidence_data is null
    """
    # Create a WeeklyMeasurement
    measurement = WeeklyMeasurement(
        week_start=date(2024, 1, 15),
        weight_kg=70.0,
        body_fat_pct=15.0,
        waist_cm=80.0,
        rhr_bpm=60,
        sleep_avg_hrs=7.5
    )
    db_session.add(measurement)
    db_session.commit()
    
    week_id = str(measurement.id)
    
    # Create a WeeklyEval record with empty evidence_map_json
    eval_with_empty = WeeklyEval(
        week_id=week_id,
        input_hash="empty_hash_789",
        llm_model="mixtral-8x7b-instruct",
        raw_llm_response='{"overall_score": 80}',
        parsed_output_json={
            "overall_score": 80,
            "summary": "Evaluation with empty evidence"
        },
        generated_at=datetime(2024, 1, 22, 10, 0, 0),
        evidence_map_json={"evidence_cards": []}
    )
    db_session.add(eval_with_empty)
    db_session.commit()
    
    # Read the evaluation
    eval_service = EvaluationService(db_session)
    retrieved_eval = eval_service.get_evaluation(week_id)
    
    # Verify the record is readable
    assert retrieved_eval is not None
    assert retrieved_eval.week_id == week_id
    assert retrieved_eval.evidence_map_json is not None
    
    # Verify evidence_cards property returns empty list
    assert retrieved_eval.evidence_cards == []
    assert isinstance(retrieved_eval.evidence_cards, list)


def test_malformed_evidence_map_json(db_session: Session):
    """
    Test that WeeklyEval records with malformed evidence_map_json are handled gracefully.
    
    Validates Requirement 4.1.6: Provide default empty list when evidence_data is malformed
    """
    # Create a WeeklyMeasurement
    measurement = WeeklyMeasurement(
        week_start=date(2024, 1, 22),
        weight_kg=70.0,
        body_fat_pct=15.0,
        waist_cm=80.0,
        rhr_bpm=60,
        sleep_avg_hrs=7.5
    )
    db_session.add(measurement)
    db_session.commit()
    
    week_id = str(measurement.id)
    
    # Create a WeeklyEval record with malformed evidence_map_json (missing evidence_cards key)
    eval_malformed = WeeklyEval(
        week_id=week_id,
        input_hash="malformed_hash_999",
        llm_model="mixtral-8x7b-instruct",
        raw_llm_response='{"overall_score": 75}',
        parsed_output_json={
            "overall_score": 75,
            "summary": "Evaluation with malformed evidence"
        },
        generated_at=datetime(2024, 1, 29, 10, 0, 0),
        evidence_map_json={"some_other_key": "value"}  # Missing evidence_cards key
    )
    db_session.add(eval_malformed)
    db_session.commit()
    
    # Read the evaluation
    eval_service = EvaluationService(db_session)
    retrieved_eval = eval_service.get_evaluation(week_id)
    
    # Verify the record is readable
    assert retrieved_eval is not None
    assert retrieved_eval.week_id == week_id
    assert retrieved_eval.evidence_map_json is not None
    
    # Verify evidence_cards property returns empty list for malformed data
    assert retrieved_eval.evidence_cards == []
    assert isinstance(retrieved_eval.evidence_cards, list)


def test_mixed_old_and_new_records(db_session: Session):
    """
    Test that a mix of old and new WeeklyEval records can coexist.
    
    Validates Requirement 4.1.6: Backward compatibility with existing records
    """
    # Create WeeklyMeasurements
    measurement1 = WeeklyMeasurement(
        week_start=date(2024, 1, 1),
        weight_kg=70.0,
        body_fat_pct=15.0,
        waist_cm=80.0,
        rhr_bpm=60,
        sleep_avg_hrs=7.5
    )
    measurement2 = WeeklyMeasurement(
        week_start=date(2024, 1, 8),
        weight_kg=70.0,
        body_fat_pct=15.0,
        waist_cm=80.0,
        rhr_bpm=60,
        sleep_avg_hrs=7.5
    )
    db_session.add_all([measurement1, measurement2])
    db_session.commit()
    
    week_id1 = str(measurement1.id)
    week_id2 = str(measurement2.id)
    
    # Create an old record without evidence
    old_eval = WeeklyEval(
        week_id=week_id1,
        input_hash="old_hash",
        llm_model="mixtral-8x7b-instruct",
        raw_llm_response='{"overall_score": 85}',
        parsed_output_json={"overall_score": 85},
        generated_at=datetime(2024, 1, 8, 10, 0, 0),
        evidence_map_json=None
    )
    
    # Create a new record with evidence
    new_eval = WeeklyEval(
        week_id=week_id2,
        input_hash="new_hash",
        llm_model="mixtral-8x7b-instruct",
        raw_llm_response='{"overall_score": 90}',
        parsed_output_json={"overall_score": 90},
        generated_at=datetime(2024, 1, 15, 10, 0, 0),
        evidence_map_json={"evidence_cards": [{"claim_text": "test"}]}
    )
    
    db_session.add_all([old_eval, new_eval])
    db_session.commit()
    
    # Retrieve both evaluations
    eval_service = EvaluationService(db_session)
    retrieved_old = eval_service.get_evaluation(week_id1)
    retrieved_new = eval_service.get_evaluation(week_id2)
    
    # Verify both are readable
    assert retrieved_old is not None
    assert retrieved_new is not None
    
    # Verify old record has empty evidence_cards
    assert retrieved_old.evidence_cards == []
    
    # Verify new record has evidence_cards
    assert len(retrieved_new.evidence_cards) == 1
    assert retrieved_new.evidence_cards[0]["claim_text"] == "test"

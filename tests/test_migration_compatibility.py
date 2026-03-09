"""
Test migration compatibility for existing WeeklyEval records
Tests Task 8.1: Verify existing WeeklyEval records are readable

Validates Requirements:
- 10.1: Read existing WeeklyEval records created by old system
- 10.2: Preserve all existing input_hash values
- 10.3: Preserve all existing evidence_map_json values
- 10.5: No database schema changes required
"""

import pytest
from datetime import date, datetime
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.weekly_eval import WeeklyEval
from app.services.eval_service import EvaluationService
from sqlalchemy.orm import Session
import uuid


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_read_old_weekly_eval_with_input_hash(db_session: Session):
    """
    Test reading WeeklyEval records created by old system with input_hash.
    
    Validates Requirement 10.1: Read existing WeeklyEval records
    Validates Requirement 10.2: Preserve all existing input_hash values
    """
    # Create a WeeklyMeasurement (needed for week_id reference)
    week_start = date(2024, 1, 1)
    measurement = WeeklyMeasurement(
        week_start=week_start,
        weight_kg=75.0,
        body_fat_pct=15.0,
        waist_cm=85.0,
        sleep_avg_hrs=7.5,
        rhr_bpm=60,
        energy_level_avg=8.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(measurement)
    db_session.commit()
    db_session.refresh(measurement)
    
    week_id = str(measurement.id)
    
    # Simulate an old WeeklyEval record created by the old system
    old_input_hash = "abc123def456old_system_hash"
    old_eval = WeeklyEval(
        week_id=week_id,
        input_hash=old_input_hash,
        llm_model="old-model-v1",
        raw_llm_response='{"overall_score": 7, "summary": "Old system evaluation"}',
        parsed_output_json={
            "overall_score": 7,
            "summary": "Old system evaluation",
            "wins": ["Good adherence"],
            "misses": [],
            "nutrition_analysis": {
                "avg_daily_calories": 2000,
                "avg_protein_g": 150,
                "avg_adherence_score": 8.0,
                "commentary": "Good nutrition"
            },
            "training_analysis": {
                "total_run_km": 20.0,
                "strength_sessions": 2,
                "total_active_minutes": 240,
                "commentary": "Decent training"
            },
            "recommendations": [],
            "data_confidence": 0.8
        },
        generated_at=datetime(2024, 1, 8, 10, 0, 0),
        evidence_map_json=None,  # Old system didn't have evidence maps
        created_at=datetime(2024, 1, 8, 10, 0, 0),
        updated_at=datetime(2024, 1, 8, 10, 0, 0),
    )
    db_session.add(old_eval)
    db_session.commit()
    db_session.refresh(old_eval)
    
    # Read the old evaluation using EvaluationService
    eval_service = EvaluationService(db_session)
    retrieved_eval = eval_service.get_evaluation(week_id)
    
    # Verify the old record is readable
    assert retrieved_eval is not None
    assert retrieved_eval.week_id == week_id
    
    # Verify input_hash is preserved
    assert retrieved_eval.input_hash == old_input_hash
    
    # Verify parsed_output_json is readable
    assert retrieved_eval.parsed_output_json is not None
    assert retrieved_eval.parsed_output_json['overall_score'] == 7
    assert retrieved_eval.parsed_output_json['summary'] == "Old system evaluation"
    
    # Verify evidence_map_json is None (old system didn't have it)
    assert retrieved_eval.evidence_map_json is None


def test_read_old_weekly_eval_with_evidence_map(db_session: Session):
    """
    Test reading WeeklyEval records with evidence_map_json preserved.
    
    Validates Requirement 10.3: Preserve all existing evidence_map_json values
    """
    # Create a WeeklyMeasurement
    week_start = date(2024, 1, 15)
    measurement = WeeklyMeasurement(
        week_start=week_start,
        weight_kg=76.0,
        body_fat_pct=16.0,
        waist_cm=86.0,
        sleep_avg_hrs=7.0,
        rhr_bpm=62,
        energy_level_avg=7.5,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(measurement)
    db_session.commit()
    db_session.refresh(measurement)
    
    week_id = str(measurement.id)
    
    # Simulate a WeeklyEval record with evidence_map_json
    old_evidence_map = {
        "week_id": week_id,
        "nutrition_analysis": {
            "source_records": ["daily_log_1", "daily_log_2"]
        },
        "training_analysis": {
            "source_records": ["strava_activity_1", "strava_activity_2"]
        }
    }
    
    old_eval = WeeklyEval(
        week_id=week_id,
        input_hash="def789ghi012with_evidence",
        llm_model="old-model-v2",
        raw_llm_response='{"overall_score": 8}',
        parsed_output_json={
            "overall_score": 8,
            "summary": "Good week with evidence tracking",
            "wins": ["Met all targets"],
            "misses": [],
            "nutrition_analysis": {
                "avg_daily_calories": 2100,
                "avg_protein_g": 155,
                "avg_adherence_score": 9.0,
                "commentary": "Excellent"
            },
            "training_analysis": {
                "total_run_km": 30.0,
                "strength_sessions": 3,
                "total_active_minutes": 360,
                "commentary": "Great training"
            },
            "recommendations": [],
            "data_confidence": 0.9
        },
        generated_at=datetime(2024, 1, 22, 10, 0, 0),
        evidence_map_json=old_evidence_map,
        created_at=datetime(2024, 1, 22, 10, 0, 0),
        updated_at=datetime(2024, 1, 22, 10, 0, 0),
    )
    db_session.add(old_eval)
    db_session.commit()
    db_session.refresh(old_eval)
    
    # Read the evaluation
    eval_service = EvaluationService(db_session)
    retrieved_eval = eval_service.get_evaluation(week_id)
    
    # Verify the record is readable
    assert retrieved_eval is not None
    assert retrieved_eval.week_id == week_id
    
    # Verify evidence_map_json is preserved
    assert retrieved_eval.evidence_map_json is not None
    assert retrieved_eval.evidence_map_json == old_evidence_map
    assert "nutrition_analysis" in retrieved_eval.evidence_map_json
    assert "training_analysis" in retrieved_eval.evidence_map_json


def test_no_schema_changes_required(db_session: Session):
    """
    Test that no database schema changes are required for migration.
    
    Validates Requirement 10.5: No database schema changes required
    """
    # Create a WeeklyMeasurement
    week_start = date(2024, 2, 1)
    measurement = WeeklyMeasurement(
        week_start=week_start,
        weight_kg=74.0,
        body_fat_pct=14.5,
        waist_cm=84.0,
        sleep_avg_hrs=8.0,
        rhr_bpm=58,
        energy_level_avg=8.5,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(measurement)
    db_session.commit()
    db_session.refresh(measurement)
    
    week_id = str(measurement.id)
    
    # Create a WeeklyEval with all fields that existed in old system
    old_eval = WeeklyEval(
        id=str(uuid.uuid4()),
        week_id=week_id,
        input_hash="schema_test_hash",
        llm_model="test-model",
        raw_llm_response='{"test": "data"}',
        parsed_output_json={"test": "data"},
        generated_at=datetime.utcnow(),
        evidence_map_json={"test": "evidence"},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    # This should work without any schema changes
    db_session.add(old_eval)
    db_session.commit()
    db_session.refresh(old_eval)
    
    # Verify all fields are accessible
    assert old_eval.id is not None
    assert old_eval.week_id == week_id
    assert old_eval.input_hash == "schema_test_hash"
    assert old_eval.llm_model == "test-model"
    assert old_eval.raw_llm_response == '{"test": "data"}'
    assert old_eval.parsed_output_json == {"test": "data"}
    assert old_eval.generated_at is not None
    assert old_eval.evidence_map_json == {"test": "evidence"}
    assert old_eval.created_at is not None
    assert old_eval.updated_at is not None


def test_read_multiple_old_evaluations(db_session: Session):
    """
    Test reading multiple old WeeklyEval records.
    
    Validates Requirement 10.1: Read existing WeeklyEval records
    """
    # Create multiple WeeklyMeasurements and evaluations
    evaluations = []
    for i in range(3):
        week_start = date(2024, 1, 1 + (i * 7))
        measurement = WeeklyMeasurement(
            week_start=week_start,
            weight_kg=75.0 - i,
            body_fat_pct=15.0,
            waist_cm=85.0,
            sleep_avg_hrs=7.5,
            rhr_bpm=60,
            energy_level_avg=8.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(measurement)
        db_session.commit()
        db_session.refresh(measurement)
        
        week_id = str(measurement.id)
        
        old_eval = WeeklyEval(
            week_id=week_id,
            input_hash=f"hash_{i}",
            llm_model="old-model",
            raw_llm_response=f'{{"overall_score": {7 + i}}}',
            parsed_output_json={
                "overall_score": 7 + i,
                "summary": f"Week {i} evaluation",
                "wins": [],
                "misses": [],
                "nutrition_analysis": {
                    "avg_daily_calories": 2000,
                    "avg_protein_g": 150,
                    "avg_adherence_score": 8.0,
                    "commentary": "Good"
                },
                "training_analysis": {
                    "total_run_km": 20.0,
                    "strength_sessions": 2,
                    "total_active_minutes": 240,
                    "commentary": "Good"
                },
                "recommendations": [],
                "data_confidence": 0.8
            },
            generated_at=datetime.utcnow(),
            evidence_map_json=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(old_eval)
        db_session.commit()
        evaluations.append((week_id, f"hash_{i}"))
    
    # Read all evaluations
    eval_service = EvaluationService(db_session)
    for week_id, expected_hash in evaluations:
        retrieved_eval = eval_service.get_evaluation(week_id)
        assert retrieved_eval is not None
        assert retrieved_eval.week_id == week_id
        assert retrieved_eval.input_hash == expected_hash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

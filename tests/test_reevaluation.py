"""
Test re-evaluation of existing weeks
Tests Task 8.2: Test re-evaluation of existing weeks

Validates Requirements:
- 10.4: Re-evaluating a week replaces old evaluation with new one
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.weekly_eval import WeeklyEval
from app.models.daily_log import DailyLog
from app.models.plan_targets import PlanTargets
from app.services.eval_service import EvaluationService
from app.schemas.eval_output import EvalOutput, NutritionAnalysis, TrainingAnalysis, Recommendation
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


@pytest.fixture
def mock_eval_output():
    """Create a mock EvalOutput for testing."""
    return EvalOutput(
        overall_score=8,
        summary="Good week with solid nutrition adherence and training volume.",
        wins=["Met protein targets", "Completed all strength sessions"],
        misses=["Missed one run session"],
        nutrition_analysis=NutritionAnalysis(
            avg_daily_calories=2000,
            avg_protein_g=150,
            avg_adherence_score=8.5,
            commentary="Excellent protein intake and calorie control."
        ),
        training_analysis=TrainingAnalysis(
            total_run_km=25.0,
            strength_sessions=3,
            total_active_minutes=300,
            commentary="Good training volume, slightly below run target."
        ),
        recommendations=[
            Recommendation(
                area="Training",
                action="Add one more run session next week",
                priority=1
            )
        ],
        data_confidence=0.95
    )


@pytest.mark.asyncio
async def test_reevaluation_replaces_old_evaluation(db_session: Session, mock_eval_output):
    """
    Test that re-evaluating a week replaces the old evaluation with a new one.
    
    Validates Requirement 10.4: Re-evaluating a week replaces old evaluation
    """
    # Create a WeeklyMeasurement
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
    
    # Create PlanTargets for the week
    plan_targets = PlanTargets(
        effective_from=week_start - timedelta(days=7),
        target_calories=2000,
        target_protein_g=150,
        target_fasting_hrs=16,
        target_run_km_wk=30,
        target_strength_sessions=3,
        target_weight_kg=75,
        notes="Test targets",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(plan_targets)
    
    # Create some DailyLog records for the week
    for i in range(7):
        daily_log = DailyLog(
            log_date=week_start + timedelta(days=i),
            fasting_hours=16.0,
            calories_in=2000,
            protein_g=150,
            carbs_g=200,
            fat_g=70,
            adherence_score=8,
            notes=f"Day {i+1}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(daily_log)
    
    db_session.commit()
    
    # Create an old evaluation (simulating old system)
    old_input_hash = "old_system_hash_12345"
    old_eval = WeeklyEval(
        week_id=week_id,
        input_hash=old_input_hash,
        llm_model="old-model-v1",
        raw_llm_response='{"overall_score": 7, "summary": "Old system evaluation"}',
        parsed_output_json={
            "overall_score": 7,
            "summary": "Old system evaluation from legacy code",
            "wins": ["Good adherence"],
            "misses": ["Could improve training"],
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
    
    old_eval_id = old_eval.id
    old_generated_at = old_eval.generated_at
    
    # Verify old evaluation exists
    assert old_eval.input_hash == old_input_hash
    assert old_eval.evidence_map_json is None
    assert old_eval.parsed_output_json['summary'] == "Old system evaluation from legacy code"
    
    # Mock LangChainEvaluationService
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Re-evaluate the week using the new LangChain system with force_refresh=True
        eval_service = EvaluationService(db_session)
        new_eval = await eval_service.evaluate_week(week_id, force_refresh=True)
        
        # Verify LangChain was called
        mock_langchain.assert_called_once()
        mock_instance.generate_evaluation.assert_called_once()
    
    # Verify the evaluation was replaced (same week_id, but updated)
    assert new_eval.week_id == week_id
    
    # Verify new evaluation uses LangChain (has different characteristics)
    # The new system should have:
    # 1. Updated input_hash (different from old system)
    assert new_eval.input_hash != old_input_hash, "New evaluation should have different input_hash"
    
    # 2. Evidence map (new system feature)
    assert new_eval.evidence_map_json is not None, "New evaluation should have evidence_map"
    assert isinstance(new_eval.evidence_map_json, dict), "Evidence map should be a dictionary"
    
    # 3. Updated generated_at timestamp
    assert new_eval.generated_at > old_generated_at, "New evaluation should have newer timestamp"
    
    # 4. Valid EvalOutput structure from LangChain
    assert 'overall_score' in new_eval.parsed_output_json
    assert 'summary' in new_eval.parsed_output_json
    assert 'data_confidence' in new_eval.parsed_output_json
    assert 'wins' in new_eval.parsed_output_json
    assert 'misses' in new_eval.parsed_output_json
    assert 'nutrition_analysis' in new_eval.parsed_output_json
    assert 'training_analysis' in new_eval.parsed_output_json
    assert 'recommendations' in new_eval.parsed_output_json
    
    # Verify data_confidence is within valid range (0.0-1.0)
    assert 0.0 <= new_eval.parsed_output_json['data_confidence'] <= 1.0
    
    # Verify overall_score is within valid range (1-10)
    assert 1 <= new_eval.parsed_output_json['overall_score'] <= 10
    
    # Verify only one evaluation exists for this week_id
    all_evals = db_session.query(WeeklyEval).filter(WeeklyEval.week_id == week_id).all()
    assert len(all_evals) == 1, "Should only have one evaluation per week_id"
    
    # Verify it's the new evaluation (by checking evidence_map presence)
    assert all_evals[0].evidence_map_json is not None


@pytest.mark.asyncio
async def test_reevaluation_with_changed_data(db_session: Session, mock_eval_output):
    """
    Test that re-evaluating a week with changed data produces a new input_hash.
    
    Validates Requirement 10.4: Re-evaluating with different data updates input_hash
    """
    # Create a WeeklyMeasurement
    week_start = date(2024, 2, 1)
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
    
    # Create PlanTargets
    plan_targets = PlanTargets(
        effective_from=week_start - timedelta(days=7),
        target_calories=2100,
        target_protein_g=160,
        target_fasting_hrs=16,
        target_run_km_wk=35,
        target_strength_sessions=3,
        target_weight_kg=75,
        notes="Test targets",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(plan_targets)
    
    # Create initial DailyLog records (only 3 days)
    for i in range(3):
        daily_log = DailyLog(
            log_date=week_start + timedelta(days=i),
            fasting_hours=15.0,
            calories_in=1900,
            protein_g=140,
            carbs_g=180,
            fat_g=65,
            adherence_score=7,
            notes=f"Initial day {i+1}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(daily_log)
    
    db_session.commit()
    
    # Mock LangChainEvaluationService for first evaluation
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # First evaluation with partial data
        eval_service = EvaluationService(db_session)
        first_eval = await eval_service.evaluate_week(week_id)
    
    first_input_hash = first_eval.input_hash
    first_generated_at = first_eval.generated_at
    
    # Verify first evaluation
    assert first_eval.input_hash is not None
    assert first_eval.evidence_map_json is not None
    
    # Add more DailyLog records (complete the week)
    for i in range(3, 7):
        daily_log = DailyLog(
            log_date=week_start + timedelta(days=i),
            fasting_hours=16.5,
            calories_in=2100,
            protein_g=160,
            carbs_g=200,
            fat_g=75,
            adherence_score=9,
            notes=f"Added day {i+1}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(daily_log)
    
    db_session.commit()
    
    # Mock LangChainEvaluationService for second evaluation
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Re-evaluate with complete data (force_refresh=True to bypass cache)
        second_eval = await eval_service.evaluate_week(week_id, force_refresh=True)
    
    # Verify the evaluation was updated
    assert second_eval.week_id == week_id
    
    # Verify input_hash changed (because data changed)
    assert second_eval.input_hash != first_input_hash, "Input hash should change when data changes"
    
    # Verify new evaluation has evidence_map
    assert second_eval.evidence_map_json is not None
    
    # Verify generated_at was updated
    assert second_eval.generated_at > first_generated_at
    
    # Verify only one evaluation exists
    all_evals = db_session.query(WeeklyEval).filter(WeeklyEval.week_id == week_id).all()
    assert len(all_evals) == 1


@pytest.mark.asyncio
async def test_reevaluation_preserves_week_id(db_session: Session, mock_eval_output):
    """
    Test that re-evaluation preserves the week_id relationship.
    
    Validates Requirement 10.4: Re-evaluation maintains week_id consistency
    """
    # Create a WeeklyMeasurement
    week_start = date(2024, 3, 1)
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
    
    # Create minimal data
    plan_targets = PlanTargets(
        effective_from=week_start - timedelta(days=7),
        target_calories=2000,
        target_protein_g=150,
        target_fasting_hrs=16,
        target_run_km_wk=30,
        target_strength_sessions=3,
        target_weight_kg=74,
        notes="Test",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(plan_targets)
    db_session.commit()
    
    # Create old evaluation
    old_eval = WeeklyEval(
        week_id=week_id,
        input_hash="old_hash",
        llm_model="old-model",
        raw_llm_response='{"test": "data"}',
        parsed_output_json={
            "overall_score": 8,
            "summary": "Old evaluation",
            "wins": [],
            "misses": [],
            "nutrition_analysis": {
                "avg_daily_calories": 2000,
                "avg_protein_g": 150,
                "avg_adherence_score": 8.0,
                "commentary": "Good"
            },
            "training_analysis": {
                "total_run_km": 25.0,
                "strength_sessions": 3,
                "total_active_minutes": 300,
                "commentary": "Good"
            },
            "recommendations": [],
            "data_confidence": 0.7
        },
        generated_at=datetime.utcnow(),
        evidence_map_json=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(old_eval)
    db_session.commit()
    
    # Mock LangChainEvaluationService
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Re-evaluate
        eval_service = EvaluationService(db_session)
        new_eval = await eval_service.evaluate_week(week_id, force_refresh=True)
    
    # Verify week_id is preserved
    assert new_eval.week_id == week_id
    
    # Verify we can still look up by week_id
    retrieved_eval = eval_service.get_evaluation(week_id)
    assert retrieved_eval is not None
    assert retrieved_eval.week_id == week_id
    
    # Verify the evaluation is the new one (has evidence_map)
    assert retrieved_eval.evidence_map_json is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test EvaluationService refactoring with LangChain integration
Tests Task 6.1: Refactor evaluate_week to use LangChainEvaluationService
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.weekly_eval import WeeklyEval
from app.services.eval_service import EvaluationService
from app.schemas.eval_output import EvalOutput, NutritionAnalysis, TrainingAnalysis, Recommendation
from sqlalchemy.orm import Session


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


def test_evaluate_week_cache_miss(db_session: Session, mock_eval_output):
    """
    Test that evaluate_week generates new evaluation on cache miss.
    
    Validates:
    - Contract is built using PromptEngine.build_contract
    - Contract hash is computed using hash_contract
    - LangChainEvaluationService.generate_evaluation is called on cache miss
    - Result is stored in WeeklyEval with input_hash
    """
    # Create a WeeklyMeasurement
    week_start = date.today()
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
    
    # Mock LangChainEvaluationService
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Create evaluation service and evaluate
        eval_service = EvaluationService(db_session)
        import asyncio
        weekly_eval = asyncio.run(eval_service.evaluate_week(week_id))
        
        # Verify LangChain was called
        mock_langchain.assert_called_once()
        mock_instance.generate_evaluation.assert_called_once()
        
        # Verify result was stored
        assert weekly_eval is not None
        assert weekly_eval.week_id == week_id
        assert weekly_eval.input_hash is not None
        assert weekly_eval.parsed_output_json is not None
        assert weekly_eval.evidence_map_json is not None
        
        # Verify evaluation data
        assert weekly_eval.parsed_output_json['overall_score'] == 8
        assert weekly_eval.parsed_output_json['data_confidence'] == 0.95


def test_evaluate_week_cache_hit(db_session: Session, mock_eval_output):
    """
    Test that evaluate_week returns cached evaluation on cache hit.
    
    Validates:
    - Existing WeeklyEval with matching input_hash is returned
    - LangChainEvaluationService is NOT called on cache hit
    """
    # Create a WeeklyMeasurement
    week_start = date.today()
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
    
    # First evaluation (cache miss)
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        eval_service = EvaluationService(db_session)
        import asyncio
        first_eval = asyncio.run(eval_service.evaluate_week(week_id))
        
        # Verify LangChain was called once
        assert mock_instance.generate_evaluation.call_count == 1
        first_input_hash = first_eval.input_hash
    
    # Second evaluation (cache hit)
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        eval_service = EvaluationService(db_session)
        import asyncio
        second_eval = asyncio.run(eval_service.evaluate_week(week_id))
        
        # Verify LangChain was NOT called (cache hit)
        mock_instance.generate_evaluation.assert_not_called()
        
        # Verify same evaluation was returned
        assert second_eval.id == first_eval.id
        assert second_eval.input_hash == first_input_hash


def test_evaluate_week_force_refresh(db_session: Session, mock_eval_output):
    """
    Test that evaluate_week bypasses cache when force_refresh=True.
    
    Validates:
    - force_refresh=True bypasses cache
    - LangChainEvaluationService is called even with existing evaluation
    """
    # Create a WeeklyMeasurement
    week_start = date.today()
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
    
    # First evaluation
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        eval_service = EvaluationService(db_session)
        import asyncio
        first_eval = asyncio.run(eval_service.evaluate_week(week_id))
        
        assert mock_instance.generate_evaluation.call_count == 1
    
    # Force refresh
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        eval_service = EvaluationService(db_session)
        import asyncio
        refreshed_eval = asyncio.run(eval_service.evaluate_week(week_id, force_refresh=True))
        
        # Verify LangChain was called (cache bypassed)
        mock_instance.generate_evaluation.assert_called_once()
        
        # Verify evaluation was updated
        assert refreshed_eval.week_id == week_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

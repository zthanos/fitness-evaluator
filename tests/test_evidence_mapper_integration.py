"""
Test EvidenceMapper integration with EvaluationService
Tests Task 20.1: Update EvaluationService to store evidence_data
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.database import get_db, engine
from app.models.base import Base
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.weekly_eval import WeeklyEval
from app.models.strava_activity import StravaActivity
from app.models.daily_log import DailyLog
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
    """Create a mock EvalOutput with claims that reference activities and nutrition."""
    return EvalOutput(
        overall_score=8,
        summary="Good week with solid nutrition adherence and training volume.",
        wins=[
            "Completed 3 run sessions with good heart rate control",
            "Met protein targets consistently"
        ],
        misses=["Missed one strength session"],
        nutrition_analysis=NutritionAnalysis(
            avg_daily_calories=2000,
            avg_protein_g=150,
            avg_adherence_score=8.5,
            commentary="Excellent protein intake and calorie control throughout the week."
        ),
        training_analysis=TrainingAnalysis(
            total_run_km=25.0,
            strength_sessions=2,
            total_active_minutes=300,
            commentary="Good training volume with consistent running distance."
        ),
        recommendations=[
            Recommendation(
                area="Training",
                action="Add one more strength session next week to balance your training",
                priority=1
            ),
            Recommendation(
                area="Nutrition",
                action="Continue maintaining high protein intake for recovery",
                priority=2
            )
        ],
        data_confidence=0.95
    )


def test_evidence_mapper_generates_evidence_cards(db_session: Session, mock_eval_output):
    """
    Test that EvidenceMapper generates evidence cards from evaluation claims.
    
    Validates:
    - Evidence cards are generated using EvidenceMapper
    - Evidence cards link claims to source records (activities, logs, metrics)
    - Evidence cards are stored in evidence_map_json field
    - Evidence cards have required fields: claim_text, source_type, source_id, source_date, relevance_score
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
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db_session.add(measurement)
    db_session.commit()
    db_session.refresh(measurement)
    
    week_id = str(measurement.id)
    
    # Calculate ISO week_id for activities
    iso_calendar = week_start.isocalendar()
    iso_week_id = f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"
    
    # Create some activities for the week
    activity1 = StravaActivity(
        week_id=iso_week_id,
        strava_id=1001,
        start_date=week_start,
        activity_type="Run",
        distance_m=5000,
        moving_time_s=1800,
        elevation_m=50,
        avg_hr=145,
        max_hr=165,
        raw_json="{}",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    activity2 = StravaActivity(
        week_id=iso_week_id,
        strava_id=1002,
        start_date=week_start + timedelta(days=2),
        activity_type="Run",
        distance_m=10000,
        moving_time_s=3600,
        elevation_m=100,
        avg_hr=150,
        max_hr=170,
        raw_json="{}",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    activity3 = StravaActivity(
        week_id=iso_week_id,
        strava_id=1003,
        start_date=week_start + timedelta(days=4),
        activity_type="Run",
        distance_m=10000,
        moving_time_s=3600,
        elevation_m=80,
        avg_hr=148,
        max_hr=168,
        raw_json="{}",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db_session.add_all([activity1, activity2, activity3])
    
    # Create some daily logs
    for i in range(7):
        log = DailyLog(
            log_date=week_start + timedelta(days=i),
            calories_in=2000,
            protein_g=150,
            carbs_g=200,
            fat_g=70,
            adherence_score=8.5,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db_session.add(log)
    
    db_session.commit()
    
    # Mock LangChainEvaluationService
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Create evaluation service and evaluate
        eval_service = EvaluationService(db_session)
        import asyncio
        weekly_eval = asyncio.run(eval_service.evaluate_week(week_id))
        
        # Verify evidence_map_json was populated
        assert weekly_eval.evidence_map_json is not None
        assert "evidence_cards" in weekly_eval.evidence_map_json
        
        evidence_cards = weekly_eval.evidence_map_json["evidence_cards"]
        
        # Debug: Print what we got
        print(f"\nDebug: Evidence cards count: {len(evidence_cards)}")
        print(f"Debug: Mock eval output wins: {mock_eval_output.wins}")
        print(f"Debug: Mock eval output recommendations: {[r.action for r in mock_eval_output.recommendations]}")
        
        # Verify evidence cards were generated
        assert len(evidence_cards) > 0, "Evidence cards should be generated"
        
        # Verify evidence card structure
        for card in evidence_cards:
            assert "claim_text" in card, "Evidence card should have claim_text"
            assert "source_type" in card, "Evidence card should have source_type"
            assert "source_id" in card, "Evidence card should have source_id"
            assert "source_date" in card, "Evidence card should have source_date"
            assert "relevance_score" in card, "Evidence card should have relevance_score"
            
            # Verify source_type is valid
            assert card["source_type"] in ["activity", "log", "metric"], \
                f"Invalid source_type: {card['source_type']}"
            
            # Verify relevance_score is in valid range
            assert 0.0 <= card["relevance_score"] <= 1.0, \
                f"Invalid relevance_score: {card['relevance_score']}"
        
        # Verify that activity-related claims are linked to activities
        activity_cards = [c for c in evidence_cards if c["source_type"] == "activity"]
        assert len(activity_cards) > 0, "Should have evidence cards linked to activities"
        
        # Verify that nutrition-related claims are linked to logs
        log_cards = [c for c in evidence_cards if c["source_type"] == "log"]
        assert len(log_cards) > 0, "Should have evidence cards linked to logs"
        
        print(f"\nGenerated {len(evidence_cards)} evidence cards:")
        print(f"  - {len(activity_cards)} activity cards")
        print(f"  - {len(log_cards)} log cards")
        print(f"  - {len([c for c in evidence_cards if c['source_type'] == 'metric'])} metric cards")


def test_evidence_mapper_backward_compatibility(db_session: Session, mock_eval_output):
    """
    Test that evidence collection handles missing WeeklyMeasurement gracefully.
    
    Validates:
    - If WeeklyMeasurement is not found, evidence_map_json is set to empty array
    - Evaluation still completes successfully
    """
    # Use a non-existent week_id
    week_id = "non-existent-week-id"
    
    # Mock LangChainEvaluationService
    with patch('app.services.eval_service.LangChainEvaluationService') as mock_langchain:
        mock_instance = MagicMock()
        mock_instance.generate_evaluation = AsyncMock(return_value=mock_eval_output)
        mock_langchain.return_value = mock_instance
        
        # Mock build_contract to avoid database errors
        with patch('app.services.eval_service.build_contract') as mock_build:
            mock_build.return_value = {"test": "contract"}
            
            # Create evaluation service and evaluate
            eval_service = EvaluationService(db_session)
            import asyncio
            weekly_eval = asyncio.run(eval_service.evaluate_week(week_id))
            
            # Verify evidence_map_json is empty but present
            assert weekly_eval.evidence_map_json is not None
            assert "evidence_cards" in weekly_eval.evidence_map_json
            assert weekly_eval.evidence_map_json["evidence_cards"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

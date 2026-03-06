# app/services/evidence_collector.py
from sqlalchemy.orm import Session
from app.schemas.eval_output import EvalOutput


def collect_evidence(eval_data: EvalOutput, week_id: str, db: Session) -> dict:
    """
    Collect evidence for traceability of the evaluation.
    
    Maps evaluation outputs to the source data that informed them.
    This provides transparency and allows users to understand how
    the AI arrived at its conclusions.
    
    Args:
        eval_data: The parsed evaluation output from the LLM
        week_id: The string UUID of the week being evaluated
        db: Database session for querying source data
    
    Returns:
        Dictionary mapping evaluation components to their evidence sources
    """
    evidence = {
        "week_id": str(week_id),
        "overall_score": {
            "value": eval_data.overall_score,
            "based_on": ["nutrition_analysis", "training_analysis", "data_confidence"]
        },
        "nutrition_analysis": {
            "avg_daily_calories": eval_data.nutrition_analysis.avg_daily_calories,
            "avg_protein_g": eval_data.nutrition_analysis.avg_protein_g,
            "avg_adherence_score": eval_data.nutrition_analysis.avg_adherence_score,
            "source": "daily_logs"
        },
        "training_analysis": {
            "total_run_km": eval_data.training_analysis.total_run_km,
            "strength_sessions": eval_data.training_analysis.strength_sessions,
            "total_active_minutes": eval_data.training_analysis.total_active_minutes,
            "source": "strava_activities"
        },
        "recommendations_count": len(eval_data.recommendations),
        "data_confidence": eval_data.data_confidence
    }
    
    return evidence

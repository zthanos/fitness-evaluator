# app/services/evidence_collector.py
from sqlalchemy.orm import Session
from app.schemas.eval_output import EvalOutput
from app.models.daily_log import DailyLog
from app.models.strava_activity import StravaActivity
from app.models.athlete_goal import AthleteGoal, GoalStatus
from app.models.weekly_measurement import WeeklyMeasurement
from datetime import timedelta


def collect_evidence(eval_data: EvalOutput, week_id: str, db: Session) -> dict:
    """
    Collect evidence for traceability of the evaluation.
    
    Maps evaluation outputs to the source data that informed them.
    This provides transparency and allows users to understand how
    the AI arrived at its conclusions.
    
    Requirements:
    - 7.1: Collect evidence for each evaluation claim
    - 7.2: Link evaluation statements to specific database record IDs
    - 7.3: Include record type and primary key for each evidence item
    - 7.4: Store evidence_map_json with every WeeklyEval record
    
    Args:
        eval_data: The parsed evaluation output from the LLM
        week_id: The string UUID of the week being evaluated
        db: Database session for querying source data
    
    Returns:
        Dictionary mapping evaluation components to their evidence sources
        with record types and primary keys
    """
    # Get the WeeklyMeasurement to derive week_start
    weekly_measurement = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == week_id
    ).first()
    
    if not weekly_measurement:
        raise ValueError(f"No WeeklyMeasurement found for week_id: {week_id}")
    
    week_start = weekly_measurement.week_start
    week_end = week_start + timedelta(days=7)
    
    # Query DailyLog records for the week
    daily_logs = db.query(DailyLog).filter(
        DailyLog.log_date >= week_start,
        DailyLog.log_date < week_end
    ).all()
    
    # Query StravaActivity records for the week
    strava_activities = db.query(StravaActivity).filter(
        StravaActivity.week_id == week_id
    ).all()
    
    # Query active AthleteGoal records
    active_goals = db.query(AthleteGoal).filter(
        AthleteGoal.status == GoalStatus.ACTIVE.value
    ).all()
    
    # Build evidence map with record types and primary keys
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
            "record_type": "daily_log",
            "source_records": [str(log.id) for log in daily_logs]
        },
        "training_analysis": {
            "total_run_km": eval_data.training_analysis.total_run_km,
            "strength_sessions": eval_data.training_analysis.strength_sessions,
            "total_active_minutes": eval_data.training_analysis.total_active_minutes,
            "record_type": "strava_activity",
            "source_records": [str(activity.id) for activity in strava_activities]
        },
        "goal_progress": {
            "goals_evaluated": [str(goal.id) for goal in active_goals],
            "record_type": "athlete_goal",
            "source_records": [str(goal.id) for goal in active_goals] + [str(weekly_measurement.id)]
        },
        "measurements": {
            "record_type": "weekly_measurement",
            "source_records": [str(weekly_measurement.id)]
        },
        "recommendations_count": len(eval_data.recommendations),
        "data_confidence": eval_data.data_confidence
    }
    
    return evidence

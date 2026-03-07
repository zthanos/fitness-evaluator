# app/services/prompt_engine.py
import hashlib, json, logging
from datetime import timedelta
from sqlalchemy.orm import Session
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.plan_targets import PlanTargets
from app.models.daily_log import DailyLog
from app.models.strava_activity import StravaActivity
from app.models.athlete_goal import AthleteGoal, GoalStatus
from app.services.strava_service import compute_weekly_aggregates

logger = logging.getLogger(__name__)


def build_contract(week_id: str, db: Session) -> dict:
    """
    Gather all data for the week and return a structured dict (the Contract).
    Keys must always be present even if values are None.
    
    Args:
        week_id: UUID of the WeeklyMeasurement record
        db: Database session
        
    Returns:
        Contract dictionary with all data sources
        
    Raises:
        ValueError: If WeeklyMeasurement not found for the given week_id
    """
    logger.info(f"Building contract for week_id={week_id}")
    
    # 1. Load WeeklyMeasurement using week_id (UUID)
    weekly_measurement = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == week_id
    ).first()
    
    if not weekly_measurement:
        logger.error(
            "Contract building failed: No WeeklyMeasurement found",
            extra={
                "week_id": week_id,
                "missing_data": ["weekly_measurement"]
            }
        )
        raise ValueError(f"No WeeklyMeasurement found for week_id: {week_id}")
    
    # Derive week_start and week_end from WeeklyMeasurement
    week_start = weekly_measurement.week_start
    week_end = week_start + timedelta(days=7)
    
    # 2. Load active PlanTargets (latest effective_from <= week_start)
    plan_targets = db.query(PlanTargets).filter(
        PlanTargets.effective_from <= week_start
    ).order_by(PlanTargets.effective_from.desc()).first()
    
    # 3. Load all DailyLog rows for the week using date range [week_start, week_start + 7 days)
    daily_logs = db.query(DailyLog).filter(
        DailyLog.log_date >= week_start,
        DailyLog.log_date < week_end
    ).order_by(DailyLog.log_date).all()
    
    # 4. Query StravaActivity using WeeklyMeasurement.id as week_id foreign key
    strava_aggregates = compute_weekly_aggregates(week_id, db)
    
    # 5. Load active AthleteGoal records
    active_goals = db.query(AthleteGoal).filter(
        AthleteGoal.status == GoalStatus.ACTIVE.value
    ).all()
    
    # Log data source availability
    missing_data = []
    if not plan_targets:
        missing_data.append("plan_targets")
    if not daily_logs:
        missing_data.append("daily_logs")
    if not strava_aggregates or all(v == 0 or v is None for v in strava_aggregates.values() if isinstance(v, (int, float))):
        missing_data.append("strava_aggregates")
    if not active_goals:
        missing_data.append("active_goals")
    
    logger.info(
        "Contract data sources loaded",
        extra={
            "week_id": week_id,
            "week_start": str(week_start),
            "has_targets": plan_targets is not None,
            "daily_logs_count": len(daily_logs),
            "has_strava_data": bool(strava_aggregates and any(v != 0 and v is not None for v in strava_aggregates.values() if isinstance(v, (int, float)))),
            "active_goals_count": len(active_goals),
            "missing_data": missing_data if missing_data else None
        }
    )
    
    # Build and return the contract
    contract = {
        "week": {
            "start": str(week_start),
            "end": str(week_end)
        },
        "targets": {
            "effective_from": str(plan_targets.effective_from) if plan_targets else None,
            "target_calories": plan_targets.target_calories if plan_targets else None,
            "target_protein_g": plan_targets.target_protein_g if plan_targets else None,
            "target_fasting_hrs": plan_targets.target_fasting_hrs if plan_targets else None,
            "target_run_km_wk": plan_targets.target_run_km_wk if plan_targets else None,
            "target_strength_sessions": plan_targets.target_strength_sessions if plan_targets else None,
            "target_weight_kg": plan_targets.target_weight_kg if plan_targets else None,
            "notes": plan_targets.notes if plan_targets else None
        } if plan_targets else {
            "effective_from": None,
            "target_calories": None,
            "target_protein_g": None,
            "target_fasting_hrs": None,
            "target_run_km_wk": None,
            "target_strength_sessions": None,
            "target_weight_kg": None,
            "notes": None
        },
        "measurements": {
            "weight_kg": weekly_measurement.weight_kg,
            "weight_prev_kg": weekly_measurement.weight_prev_kg,
            "body_fat_pct": weekly_measurement.body_fat_pct,
            "waist_cm": weekly_measurement.waist_cm,
            "waist_prev_cm": weekly_measurement.waist_prev_cm,
            "sleep_avg_hrs": weekly_measurement.sleep_avg_hrs,
            "rhr_bpm": weekly_measurement.rhr_bpm,
            "energy_level_avg": weekly_measurement.energy_level_avg
        },
        "daily_logs": [
            {
                "id": str(log.id),
                "log_date": str(log.log_date),
                "fasting_hours": log.fasting_hours,
                "calories_in": log.calories_in,
                "protein_g": log.protein_g,
                "carbs_g": log.carbs_g,
                "fat_g": log.fat_g,
                "adherence_score": log.adherence_score,
                "notes": log.notes
            }
            for log in daily_logs
        ],
        "strava_aggregates": strava_aggregates,
        "active_goals": [
            {
                "id": str(goal.id),
                "goal_type": goal.goal_type,
                "target_value": goal.target_value,
                "target_date": str(goal.target_date) if goal.target_date else None,
                "description": goal.description,
                "status": goal.status,
                "created_at": str(goal.created_at) if goal.created_at else None
            }
            for goal in active_goals
        ]
    }
    
    logger.info(f"Contract built successfully for week_id={week_id}")
    return contract


def hash_contract(contract: dict) -> str:
    """
    SHA-256 of the deterministically serialized contract.
    """
    serialized = json.dumps(contract, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()

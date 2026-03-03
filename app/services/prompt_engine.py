# app/services/prompt_engine.py
import hashlib, json
from datetime import timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.plan_targets import PlanTargets
from app.models.daily_log import DailyLog
from app.models.strava_activity import StravaActivity
from app.services.strava_service import compute_weekly_aggregates


def build_contract(week_id: UUID, db: Session) -> dict:
    """
    Gather all data for the week and return a structured dict (the Contract).
    Keys must always be present even if values are None.
    """
    # 1. Load WeeklyMeasurement
    weekly_measurement = db.query(WeeklyMeasurement).filter(WeeklyMeasurement.id == week_id).first()
    
    # 2. Load active PlanTargets (latest effective_from <= week_start)
    if weekly_measurement:
        week_start = weekly_measurement.week_start
        plan_targets = db.query(PlanTargets).filter(
            PlanTargets.effective_from <= week_start
        ).order_by(PlanTargets.effective_from.desc()).first()
    else:
        plan_targets = None
    
    # 3. Load all DailyLog rows for the week (ordered by log_date)
    daily_logs = []
    if weekly_measurement:
        # Get the start and end dates for the week
        week_start = weekly_measurement.week_start
        week_end = week_start + timedelta(days=7)
        
        daily_logs = db.query(DailyLog).filter(
            DailyLog.log_date >= week_start,
            DailyLog.log_date < week_end
        ).order_by(DailyLog.log_date).all()
    
    # 4. Call compute_weekly_aggregates(week_id, db)
    strava_aggregates = compute_weekly_aggregates(week_id, db) if weekly_measurement else {}
    
    # Build and return the contract
    contract = {
        "week": {
            "start": str(weekly_measurement.week_start) if weekly_measurement else None,
            "end": str(weekly_measurement.week_start + timedelta(days=7)) if weekly_measurement else None
        } if weekly_measurement else {
            "start": None,
            "end": None
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
            "weight_kg": weekly_measurement.weight_kg if weekly_measurement else None,
            "weight_prev_kg": weekly_measurement.weight_prev_kg if weekly_measurement else None,
            "body_fat_pct": weekly_measurement.body_fat_pct if weekly_measurement else None,
            "waist_cm": weekly_measurement.waist_cm if weekly_measurement else None,
            "waist_prev_cm": weekly_measurement.waist_prev_cm if weekly_measurement else None,
            "sleep_avg_hrs": weekly_measurement.sleep_avg_hrs if weekly_measurement else None,
            "rhr_bpm": weekly_measurement.rhr_bpm if weekly_measurement else None,
            "energy_level_avg": weekly_measurement.energy_level_avg if weekly_measurement else None
        } if weekly_measurement else {
            "weight_kg": None,
            "weight_prev_kg": None,
            "body_fat_pct": None,
            "waist_cm": None,
            "waist_prev_cm": None,
            "sleep_avg_hrs": None,
            "rhr_bpm": None,
            "energy_level_avg": None
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
        "strava_aggregates": strava_aggregates
    }
    
    return contract


def hash_contract(contract: dict) -> str:
    """
    SHA-256 of the deterministically serialized contract.
    """
    serialized = json.dumps(contract, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()

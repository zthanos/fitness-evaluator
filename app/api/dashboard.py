"""Dashboard API endpoints for overview statistics and recent data."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date, datetime, timedelta
from typing import Optional
from app.database import get_db
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.models.weekly_eval import WeeklyEval
from app.models.evaluation import Evaluation

router = APIRouter()


@router.get("/stats", summary="Get dashboard statistics")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Get compact statistics for dashboard overview.
    
    **Requirements: 18.1**
    
    **Returns:**
    - `total_activities`: Total count of synced activities
    - `current_weight`: Most recent weight measurement (kg)
    - `weekly_adherence_avg`: Average adherence score for the last 7 days
    - `latest_evaluation_score`: Score from most recent evaluation (0-10)
    - `latest_evaluation_date`: Date of most recent evaluation
    """
    # Total activities count
    total_activities = db.query(func.count(StravaActivity.id)).scalar() or 0
    
    # Current weight (most recent measurement)
    latest_measurement = db.query(WeeklyMeasurement).order_by(
        desc(WeeklyMeasurement.week_start)
    ).first()
    current_weight = latest_measurement.weight_kg if latest_measurement else None
    
    # Weekly adherence average (last 7 days)
    seven_days_ago = date.today() - timedelta(days=7)
    recent_logs = db.query(DailyLog).filter(
        DailyLog.log_date >= seven_days_ago
    ).all()
    
    if recent_logs:
        adherence_scores = [log.adherence_score for log in recent_logs if log.adherence_score is not None]
        weekly_adherence_avg = sum(adherence_scores) / len(adherence_scores) if adherence_scores else None
    else:
        weekly_adherence_avg = None
    
    # Latest evaluation score (from new Evaluation model)
    latest_eval = db.query(Evaluation).order_by(
        desc(Evaluation.created_at)
    ).first()
    
    latest_evaluation_score = None
    latest_evaluation_date = None
    
    if latest_eval:
        # Convert 0-100 score to 0-10 scale for consistency with old dashboard
        latest_evaluation_score = round(latest_eval.overall_score / 10, 1)
        latest_evaluation_date = latest_eval.period_start
    
    return {
        "total_activities": total_activities,
        "current_weight": current_weight,
        "weekly_adherence_avg": round(weekly_adherence_avg, 1) if weekly_adherence_avg else None,
        "latest_evaluation_score": latest_evaluation_score,
        "latest_evaluation_date": latest_evaluation_date
    }


@router.get("/charts/activity-volume", summary="Get activity volume chart data")
async def get_activity_volume_chart(db: Session = Depends(get_db)):
    """
    Get weekly activity volume data for the last 30 days.
    
    **Requirements: 18.2**
    
    **Returns:**
    - `data_points`: Array of {week_start, total_distance_km, total_duration_min}
    """
    thirty_days_ago = date.today() - timedelta(days=30)
    
    # Get activities from last 30 days
    activities = db.query(StravaActivity).filter(
        StravaActivity.start_date >= datetime.combine(thirty_days_ago, datetime.min.time())
    ).order_by(StravaActivity.start_date).all()
    
    # Group by week
    weekly_data = {}
    for activity in activities:
        # Get Monday of the week
        activity_date = activity.start_date.date()
        week_start = activity_date - timedelta(days=activity_date.weekday())
        
        if week_start not in weekly_data:
            weekly_data[week_start] = {
                'total_distance_km': 0,
                'total_duration_min': 0
            }
        
        weekly_data[week_start]['total_distance_km'] += (activity.distance_m or 0) / 1000
        weekly_data[week_start]['total_duration_min'] += (activity.moving_time_s or 0) / 60
    
    # Convert to sorted array
    data_points = [
        {
            'week_start': str(week_start),
            'total_distance_km': round(data['total_distance_km'], 2),
            'total_duration_min': round(data['total_duration_min'], 0)
        }
        for week_start, data in sorted(weekly_data.items())
    ]
    
    return {"data_points": data_points}


@router.get("/charts/weight-trend", summary="Get weight trend chart data")
async def get_weight_trend_chart(db: Session = Depends(get_db)):
    """
    Get weight trend data for the last 30 days.
    
    **Requirements: 18.2**
    
    **Returns:**
    - `data_points`: Array of {measurement_date, weight_kg}
    """
    thirty_days_ago = date.today() - timedelta(days=30)
    
    measurements = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.week_start >= thirty_days_ago
    ).order_by(WeeklyMeasurement.week_start).all()
    
    data_points = [
        {
            'measurement_date': str(m.week_start),
            'weight_kg': m.weight_kg
        }
        for m in measurements if m.weight_kg is not None
    ]
    
    return {"data_points": data_points}


@router.get("/recent/activities", summary="Get recent activities")
async def get_recent_activities(db: Session = Depends(get_db)):
    """
    Get the 5 most recent activities with summary information.
    
    **Requirements: 18.3**
    
    **Returns:**
    - `activities`: Array of recent activity summaries
    """
    activities = db.query(StravaActivity).order_by(
        desc(StravaActivity.start_date)
    ).limit(5).all()
    
    return {
        "activities": [
            {
                "strava_id": a.strava_id,
                "activity_type": a.activity_type,
                "start_date": a.start_date,
                "distance_km": round((a.distance_m or 0) / 1000, 2),
                "duration_min": round((a.moving_time_s or 0) / 60, 0),
                "elevation_m": a.elevation_m
            }
            for a in activities
        ]
    }


@router.get("/recent/logs", summary="Get recent daily logs")
async def get_recent_logs(db: Session = Depends(get_db)):
    """
    Get the 5 most recent daily logs with summary information.
    
    **Requirements: 18.4**
    
    **Returns:**
    - `logs`: Array of recent log summaries
    """
    logs = db.query(DailyLog).order_by(
        desc(DailyLog.log_date)
    ).limit(5).all()
    
    return {
        "logs": [
            {
                "log_date": l.log_date,
                "calories_in": l.calories_in,
                "protein_g": l.protein_g,
                "adherence_score": l.adherence_score,
                "notes": l.notes
            }
            for l in logs
        ]
    }


@router.get("/latest-evaluation", summary="Get latest evaluation summary")
async def get_latest_evaluation(db: Session = Depends(get_db)):
    """
    Get summary of the most recent evaluation from the new Evaluation model.
    
    **Requirements: 18.5**
    
    **Returns:**
    - `score`: Overall evaluation score (0-100)
    - `top_strengths`: Top 3 strengths from the evaluation
    - `top_improvements`: Top 3 areas for improvement
    - `period_start`: Start date of the evaluation period
    - `period_end`: End date of the evaluation period
    - `period_type`: Type of period (weekly, bi-weekly, monthly)
    - `generated_at`: When the evaluation was generated
    - `evaluation_id`: ID of the evaluation for linking to detail page
    """
    latest_eval = db.query(Evaluation).order_by(
        desc(Evaluation.created_at)
    ).first()
    
    if not latest_eval:
        return {
            "score": None,
            "top_strengths": [],
            "top_improvements": [],
            "period_start": None,
            "period_end": None,
            "period_type": None,
            "generated_at": None,
            "evaluation_id": None
        }
    
    # Get top 3 strengths and improvements
    top_strengths = latest_eval.strengths[:3] if latest_eval.strengths else []
    top_improvements = latest_eval.improvements[:3] if latest_eval.improvements else []
    
    return {
        "score": latest_eval.overall_score,
        "top_strengths": top_strengths,
        "top_improvements": top_improvements,
        "period_start": latest_eval.period_start,
        "period_end": latest_eval.period_end,
        "period_type": latest_eval.period_type,
        "generated_at": latest_eval.created_at,
        "evaluation_id": latest_eval.id
    }

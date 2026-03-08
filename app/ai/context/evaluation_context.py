"""
Evaluation Context Builder

This module provides the EvaluationContextBuilder class for assembling
context for weekly evaluation operations with proper week_id filtering.
"""

from datetime import date
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.ai.context.builder import ContextBuilder
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.models.athlete_goal import AthleteGoal


class EvaluationContextBuilder(ContextBuilder):
    """Context builder for weekly evaluations with token_budget=3200"""
    
    def __init__(self, db: Session, token_budget: int = 3200):
        """
        Initialize EvaluationContextBuilder.
        
        Args:
            db: SQLAlchemy Session for database queries
            token_budget: Maximum token count for context (default: 3200)
        """
        super().__init__(token_budget)
        self.db = db
    
    def gather_data(
        self,
        athlete_id: int,
        week_id: str,
        period_start: date,
        period_end: date
    ) -> 'EvaluationContextBuilder':
        """
        Gather all data for weekly evaluation.
        
        This method queries activities using StravaActivity.week_id field
        (NOT computed from start_date) to fix the week_id bug. It also
        queries metrics, logs, and goals for the specified period.
        
        Args:
            athlete_id: ID of the athlete
            week_id: ISO week identifier (format: YYYY-WW)
            period_start: Start date of the evaluation period
            period_end: End date of the evaluation period
            
        Returns:
            self for fluent interface
        """
        # Query activities using week_id field (fixes bug)
        activities = self.db.query(StravaActivity).filter(
            StravaActivity.week_id == week_id
        ).order_by(StravaActivity.start_date).all()
        
        # Query metrics for the period
        metrics = self.db.query(WeeklyMeasurement).filter(
            WeeklyMeasurement.week_start >= period_start,
            WeeklyMeasurement.week_start <= period_end
        ).all()
        
        # Query logs for the period
        logs = self.db.query(DailyLog).filter(
            DailyLog.log_date >= period_start,
            DailyLog.log_date <= period_end
        ).all()
        
        # Query active goals
        goals = self.db.query(AthleteGoal).filter(
            AthleteGoal.athlete_id == str(athlete_id),
            AthleteGoal.status == "active"
        ).all()
        
        # Format as evidence cards
        activity_cards = [self._format_activity_card(a) for a in activities]
        metric_cards = [self._format_metric_card(m) for m in metrics]
        log_cards = [self._format_log_card(l) for l in logs]
        goal_cards = [self._format_goal_card(g) for g in goals]
        
        # Add to retrieved data layer
        self.add_retrieved_data(activity_cards + metric_cards + log_cards + goal_cards)
        
        return self
    
    def _format_activity_card(self, activity: StravaActivity) -> Dict[str, Any]:
        """
        Format activity as evidence card.
        
        Args:
            activity: StravaActivity model instance
            
        Returns:
            Dictionary with activity data formatted as evidence card
        """
        return {
            "type": "activity",
            "id": activity.id,
            "date": activity.start_date.isoformat(),
            "activity_type": activity.activity_type,
            "distance_km": round(activity.distance_m / 1000, 2) if activity.distance_m else None,
            "duration_min": round(activity.moving_time_s / 60, 1) if activity.moving_time_s else None,
            "elevation_m": activity.elevation_m,
            "avg_hr": activity.avg_hr,
            "max_hr": activity.max_hr
        }
    
    def _format_metric_card(self, metric: WeeklyMeasurement) -> Dict[str, Any]:
        """
        Format metric as evidence card.
        
        Args:
            metric: WeeklyMeasurement model instance
            
        Returns:
            Dictionary with metric data formatted as evidence card
        """
        return {
            "type": "metric",
            "id": metric.id,
            "week_start": metric.week_start.isoformat(),
            "weight_kg": metric.weight_kg,
            "body_fat_pct": metric.body_fat_pct,
            "waist_cm": metric.waist_cm,
            "rhr_bpm": metric.rhr_bpm,
            "sleep_avg_hrs": metric.sleep_avg_hrs
        }
    
    def _format_log_card(self, log: DailyLog) -> Dict[str, Any]:
        """
        Format log as evidence card.
        
        Args:
            log: DailyLog model instance
            
        Returns:
            Dictionary with log data formatted as evidence card
        """
        return {
            "type": "log",
            "id": log.id,
            "date": log.log_date.isoformat(),
            "calories_in": log.calories_in,
            "protein_g": log.protein_g,
            "carbs_g": log.carbs_g,
            "fat_g": log.fat_g,
            "adherence_score": log.adherence_score
        }
    
    def _format_goal_card(self, goal: AthleteGoal) -> Dict[str, Any]:
        """
        Format goal as evidence card.
        
        Args:
            goal: AthleteGoal model instance
            
        Returns:
            Dictionary with goal data formatted as evidence card
        """
        return {
            "type": "goal",
            "id": goal.id,
            "title": goal.description,  # Using description as title
            "target_date": goal.target_date.isoformat() if goal.target_date else None,
            "category": goal.goal_type
        }

"""Adherence Calculator Service

Calculates adherence scores at multiple levels (session, week, plan).
Provides time series data for charting progress.

Adherence scoring:
- Session: 100% if completed, 0% otherwise
- Week: Percentage of completed sessions in that week
- Plan: Percentage of completed sessions across all weeks
"""
from typing import List, Dict, Any
from app.models.training_plan import TrainingPlan
from app.models.training_plan_week import TrainingPlanWeek
from app.models.training_plan_session import TrainingPlanSession
import logging

logger = logging.getLogger(__name__)


class AdherenceCalculator:
    """
    Adherence Calculator for training plan progress tracking.
    
    Calculates adherence scores at multiple levels:
    - Per-session: Binary (100% or 0%)
    - Per-week: Percentage of completed sessions
    - Overall plan: Percentage of completed sessions across all weeks
    
    Also provides time series data for adherence charting.
    """
    
    @staticmethod
    def calculate_session_adherence(session: TrainingPlanSession) -> float:
        """
        Calculate per-session adherence.
        
        Per requirement 15.1: 100% when completed is true, 0% otherwise.
        
        Args:
            session: Training plan session
            
        Returns:
            Adherence score: 100.0 if completed, 0.0 otherwise
        """
        return 100.0 if session.completed else 0.0
    
    @staticmethod
    def calculate_week_adherence(week: TrainingPlanWeek) -> float:
        """
        Calculate per-week adherence.
        
        Per requirement 15.2: Percentage of completed sessions in that week.
        
        Args:
            week: Training plan week with sessions
            
        Returns:
            Adherence percentage (0-100)
        """
        if not week.sessions:
            return 0.0
        
        completed_count = sum(1 for session in week.sessions if session.completed)
        total_count = len(week.sessions)
        
        return (completed_count / total_count) * 100.0
    
    @staticmethod
    def calculate_plan_adherence(plan: TrainingPlan) -> float:
        """
        Calculate overall plan adherence.
        
        Per requirement 15.3: Percentage of completed sessions across all weeks.
        
        Args:
            plan: Training plan with weeks and sessions
            
        Returns:
            Adherence percentage (0-100)
        """
        total_sessions = 0
        completed_sessions = 0
        
        for week in plan.weeks:
            for session in week.sessions:
                total_sessions += 1
                if session.completed:
                    completed_sessions += 1
        
        if total_sessions == 0:
            return 0.0
        
        return (completed_sessions / total_sessions) * 100.0
    
    @staticmethod
    def get_adherence_time_series(plan: TrainingPlan) -> List[Dict[str, Any]]:
        """
        Get adherence by week for charting.
        
        Provides time series data showing adherence progression over weeks.
        Useful for visualizing progress trends.
        
        Args:
            plan: Training plan with weeks and sessions
            
        Returns:
            List of dictionaries with 'week' and 'adherence' keys
            Example: [{'week': 1, 'adherence': 100.0}, {'week': 2, 'adherence': 85.7}]
        """
        time_series = []
        
        for week in plan.weeks:
            adherence = AdherenceCalculator.calculate_week_adherence(week)
            time_series.append({
                'week': week.week_number,
                'adherence': adherence
            })
        
        return time_series
    
    @staticmethod
    def get_adherence_summary(plan: TrainingPlan) -> Dict[str, Any]:
        """
        Get comprehensive adherence summary for a plan.
        
        Provides overall adherence, weekly breakdown, and session counts.
        Useful for API responses and UI display.
        
        Args:
            plan: Training plan with weeks and sessions
            
        Returns:
            Dictionary with adherence metrics:
            - overall_adherence: Overall plan adherence percentage
            - adherence_by_week: Time series data
            - total_sessions: Total number of sessions
            - completed_sessions: Number of completed sessions
            - pending_sessions: Number of pending sessions
        """
        total_sessions = 0
        completed_sessions = 0
        
        for week in plan.weeks:
            for session in week.sessions:
                total_sessions += 1
                if session.completed:
                    completed_sessions += 1
        
        pending_sessions = total_sessions - completed_sessions
        overall_adherence = AdherenceCalculator.calculate_plan_adherence(plan)
        adherence_by_week = AdherenceCalculator.get_adherence_time_series(plan)
        
        return {
            'overall_adherence': overall_adherence,
            'adherence_by_week': adherence_by_week,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'pending_sessions': pending_sessions
        }

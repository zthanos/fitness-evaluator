"""
GetWeeklyMetrics LangChain StructuredTool for retrieving weekly body metrics.

This tool allows the LLM to query WeeklyMeasurement records for a specified athlete
and week to access body composition and wellness data.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.models.weekly_measurement import WeeklyMeasurement
from app.database import SessionLocal
from app.ai.telemetry import get_tool_logger
from datetime import datetime, timedelta
import re


class GetWeeklyMetricsInput(BaseModel):
    """Input schema for GetWeeklyMetrics tool."""
    
    athlete_id: int = Field(
        ...,
        description="The ID of the athlete whose metrics to retrieve",
        gt=0
    )
    week_id: str = Field(
        ...,
        description="ISO week identifier in format YYYY-WW with zero-padded week number (e.g., '2024-W15', '2026-W09'). Week must be 2 digits."
    )
    
    @field_validator('week_id')
    @classmethod
    def validate_week_id(cls, v: str) -> str:
        """Ensure week_id matches ISO week format."""
        pattern = r'^\d{4}-W\d{2}$'
        if not re.match(pattern, v):
            raise ValueError(f"week_id must match format YYYY-WW, got: {v}")
        
        # Validate year and week ranges
        parts = v.split('-W')
        year = int(parts[0])
        week = int(parts[1])
        
        if year < 2000 or year > 2100:
            raise ValueError(f"Year must be between 2000 and 2100, got: {year}")
        if week < 1 or week > 53:
            raise ValueError(f"Week must be between 1 and 53, got: {week}")
        
        return v


@tool(args_schema=GetWeeklyMetricsInput)
def get_weekly_metrics(athlete_id: int, week_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve weekly body metrics for an athlete.
    
    This tool queries the database for WeeklyMeasurement records for the specified
    week and returns formatted metrics including weight, body fat percentage, waist
    circumference, resting heart rate, sleep, and energy levels.
    
    Args:
        athlete_id: The ID of the athlete whose metrics to retrieve
        week_id: ISO week identifier in format YYYY-WW with zero-padded week (e.g., '2024-W15', '2026-W09' not '2026-W9')
        
    Returns:
        Dictionary with formatted metrics data, or None if no metrics found for the week
    """
    # Get tool logger
    logger = get_tool_logger()
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Parse week_id to get week_start date
        # ISO week format: YYYY-WW
        year, week = week_id.split('-W')
        year = int(year)
        week = int(week)
        
        # Calculate the Monday of the specified ISO week
        # ISO week 1 is the week containing the first Thursday of the year
        jan_4 = datetime(year, 1, 4)
        week_start = jan_4 - timedelta(days=jan_4.weekday())  # Monday of week containing Jan 4
        week_start = week_start + timedelta(weeks=week - 1)
        week_start_date = week_start.date()
        
        # Query metrics for the specified week
        # Note: WeeklyMeasurement uses week_start (date) not week_id
        metric = db.query(WeeklyMeasurement).filter(
            WeeklyMeasurement.week_start == week_start_date
        ).first()
        
        if not metric:
            # Log successful invocation with no results
            logger.log_invocation(
                tool_name="get_weekly_metrics",
                parameters={"athlete_id": athlete_id, "week_id": week_id},
                result=None
            )
            return None
        
        # Format metrics as evidence card
        formatted_metric = {
            "type": "metric",
            "id": metric.id,
            "week_start": metric.week_start.isoformat(),
            "week_id": week_id,
            "weight_kg": round(metric.weight_kg, 1) if metric.weight_kg else None,
            "weight_prev_kg": round(metric.weight_prev_kg, 1) if metric.weight_prev_kg else None,
            "body_fat_pct": round(metric.body_fat_pct, 1) if metric.body_fat_pct else None,
            "waist_cm": round(metric.waist_cm, 1) if metric.waist_cm else None,
            "waist_prev_cm": round(metric.waist_prev_cm, 1) if metric.waist_prev_cm else None,
            "rhr_bpm": metric.rhr_bpm,
            "sleep_avg_hrs": round(metric.sleep_avg_hrs, 1) if metric.sleep_avg_hrs else None,
            "energy_level_avg": round(metric.energy_level_avg, 1) if metric.energy_level_avg else None
        }
        
        # Log successful invocation
        logger.log_invocation(
            tool_name="get_weekly_metrics",
            parameters={"athlete_id": athlete_id, "week_id": week_id},
            result=formatted_metric
        )
        
        return formatted_metric
        
    except Exception as e:
        # Log failed invocation
        logger.log_invocation(
            tool_name="get_weekly_metrics",
            parameters={"athlete_id": athlete_id, "week_id": week_id},
            result=None,
            error=e
        )
        raise
        
    finally:
        # Always close the database session
        db.close()

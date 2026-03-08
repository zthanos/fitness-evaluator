"""
GetRecentActivities LangChain StructuredTool for retrieving recent athlete activities.

This tool allows the LLM to query StravaActivity records for a specified athlete
within a given time period.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.models.strava_activity import StravaActivity
from app.database import SessionLocal
from app.ai.telemetry import get_tool_logger


class GetRecentActivitiesInput(BaseModel):
    """Input schema for GetRecentActivities tool."""
    
    athlete_id: int = Field(
        ...,
        description="The ID of the athlete whose activities to retrieve",
        gt=0
    )
    days_back: int = Field(
        ...,
        description="Number of days to look back from today",
        gt=0,
        le=365
    )
    
    @field_validator('days_back')
    @classmethod
    def validate_days_back(cls, v: int) -> int:
        """Ensure days_back is reasonable."""
        if v > 365:
            raise ValueError("days_back cannot exceed 365 days")
        return v


@tool(args_schema=GetRecentActivitiesInput)
def get_recent_activities(athlete_id: int, days_back: int) -> List[Dict[str, Any]]:
    """
    Retrieve recent Strava activities for an athlete.
    
    This tool queries the database for activities within the specified time period
    and returns formatted activity data including distance, duration, heart rate,
    and elevation information.
    
    Args:
        athlete_id: The ID of the athlete whose activities to retrieve
        days_back: Number of days to look back from today (max 365)
        
    Returns:
        List of activity dictionaries with formatted data
    """
    # Get tool logger
    logger = get_tool_logger()
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Query activities for the athlete within the date range
        activities = db.query(StravaActivity).filter(
            StravaActivity.athlete_id == athlete_id,
            StravaActivity.start_date >= start_date,
            StravaActivity.start_date <= end_date
        ).order_by(StravaActivity.start_date.desc()).all()
        
        # Format activities as evidence cards
        formatted_activities = []
        for activity in activities:
            formatted_activities.append({
                "type": "activity",
                "id": activity.id,
                "strava_id": activity.strava_id,
                "date": activity.start_date.isoformat(),
                "activity_type": activity.activity_type,
                "distance_km": round(activity.distance_m / 1000, 2) if activity.distance_m else None,
                "duration_min": round(activity.moving_time_s / 60, 1) if activity.moving_time_s else None,
                "elevation_m": round(activity.elevation_m, 0) if activity.elevation_m else None,
                "avg_hr": activity.avg_hr,
                "max_hr": activity.max_hr,
                "calories": activity.calories,
                "week_id": activity.week_id
            })
        
        # Log successful invocation
        logger.log_invocation(
            tool_name="get_recent_activities",
            parameters={"athlete_id": athlete_id, "days_back": days_back},
            result=formatted_activities
        )
        
        return formatted_activities
        
    except Exception as e:
        # Log failed invocation
        logger.log_invocation(
            tool_name="get_recent_activities",
            parameters={"athlete_id": athlete_id, "days_back": days_back},
            result=None,
            error=e
        )
        raise
        
    finally:
        # Always close the database session
        db.close()

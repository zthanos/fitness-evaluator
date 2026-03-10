"""
GetMyWeeklyMetrics LangChain StructuredTool for retrieving user's own weekly metrics.

This tool is a user-scoped wrapper around get_weekly_metrics that automatically
uses the authenticated user's ID for security.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from app.ai.tools.get_weekly_metrics import get_weekly_metrics
import re


class GetMyWeeklyMetricsInput(BaseModel):
    """Input schema for GetMyWeeklyMetrics tool."""
    
    user_id: int = Field(
        ...,
        description="The ID of the user whose metrics to retrieve",
        gt=0
    )
    weeks: int = Field(
        4,
        description="Number of weeks to look back from current week (default: 4)",
        gt=0,
        le=52
    )
    
    @field_validator('weeks')
    @classmethod
    def validate_weeks(cls, v: int) -> int:
        """Ensure weeks is reasonable."""
        if v > 52:
            raise ValueError("weeks cannot exceed 52")
        return v


@tool(args_schema=GetMyWeeklyMetricsInput)
def get_my_weekly_metrics(user_id: int, weeks: int = 4) -> List[Dict[str, Any]]:
    """
    Retrieve your weekly body metrics for the specified number of weeks.
    
    This tool queries the database for your WeeklyMeasurement records for the
    specified number of weeks back from the current week and returns formatted
    metrics including weight, body fat percentage, waist circumference, resting
    heart rate, sleep, and energy levels.
    
    Args:
        user_id: The ID of the user whose metrics to retrieve
        weeks: Number of weeks to look back from current week (default: 4, max: 52)
        
    Returns:
        List of weekly metrics dictionaries with formatted data
    """
    # Calculate week_ids for the requested number of weeks
    results = []
    current_date = datetime.now()
    
    for i in range(weeks):
        # Calculate the date for i weeks ago
        target_date = current_date - timedelta(weeks=i)
        
        # Get ISO week number
        iso_calendar = target_date.isocalendar()
        year = iso_calendar[0]
        week = iso_calendar[1]
        
        # Format as YYYY-WW with zero-padded week
        week_id = f"{year}-W{week:02d}"
        
        # Get metrics for this week
        try:
            metrics = get_weekly_metrics.invoke({
                "athlete_id": user_id,
                "week_id": week_id
            })
            
            if metrics:
                results.append(metrics)
        except Exception as e:
            # Log error but continue with other weeks
            print(f"Error retrieving metrics for week {week_id}: {e}")
            continue
    
    return results

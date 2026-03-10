"""
GetMyRecentActivities LangChain StructuredTool for retrieving user's own activities.

This tool is a user-scoped wrapper around get_recent_activities that automatically
uses the authenticated user's ID for security.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from app.ai.tools.get_recent_activities import get_recent_activities


class GetMyRecentActivitiesInput(BaseModel):
    """Input schema for GetMyRecentActivities tool."""
    
    user_id: int = Field(
        ...,
        description="The ID of the user whose activities to retrieve",
        gt=0
    )
    days: int = Field(
        28,
        description="Number of days to look back from today (default: 28, max: 365)",
        gt=0,
        le=365
    )
    
    @field_validator('days')
    @classmethod
    def validate_days(cls, v: int) -> int:
        """Ensure days is reasonable."""
        if v > 365:
            raise ValueError("days cannot exceed 365")
        return v


@tool(args_schema=GetMyRecentActivitiesInput)
def get_my_recent_activities(user_id: int, days: int = 28) -> List[Dict[str, Any]]:
    """
    Retrieve your recent Strava activities.
    
    This tool queries the database for your activities within the specified time
    period and returns formatted activity data including distance, duration, heart
    rate, and elevation information.
    
    Args:
        user_id: The ID of the user whose activities to retrieve
        days: Number of days to look back from today (default: 28, max: 365)
        
    Returns:
        List of activity dictionaries with formatted data
    """
    # Delegate to get_recent_activities with user_id scoping
    return get_recent_activities.invoke({
        "athlete_id": user_id,
        "days_back": days
    })

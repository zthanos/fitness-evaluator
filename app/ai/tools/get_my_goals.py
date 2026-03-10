"""
GetMyGoals LangChain StructuredTool for retrieving user's own goals.

This tool is a user-scoped wrapper around get_athlete_goals that automatically
uses the authenticated user's ID for security.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from app.ai.tools.get_athlete_goals import get_athlete_goals


class GetMyGoalsInput(BaseModel):
    """Input schema for GetMyGoals tool."""
    
    user_id: int = Field(
        ...,
        description="The ID of the user whose goals to retrieve",
        gt=0
    )


@tool(args_schema=GetMyGoalsInput)
def get_my_goals(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve your active fitness goals.
    
    This tool queries the database for your active AthleteGoal records and returns
    formatted goal data including goal type, target values, target dates, and
    descriptions to help understand your training objectives.
    
    Args:
        user_id: The ID of the user whose goals to retrieve
        
    Returns:
        List of goal dictionaries with formatted data
    """
    # Delegate to get_athlete_goals with user_id scoping
    return get_athlete_goals.invoke({"athlete_id": user_id})

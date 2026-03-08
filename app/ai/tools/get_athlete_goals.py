"""
GetAthleteGoals LangChain StructuredTool for retrieving active athlete goals.

This tool allows the LLM to query AthleteGoal records for a specified athlete
to understand their training objectives.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.models.athlete_goal import AthleteGoal, GoalStatus
from app.database import SessionLocal
from app.ai.telemetry import get_tool_logger


class GetAthleteGoalsInput(BaseModel):
    """Input schema for GetAthleteGoals tool."""
    
    athlete_id: int = Field(
        ...,
        description="The ID of the athlete whose goals to retrieve",
        gt=0
    )


@tool(args_schema=GetAthleteGoalsInput)
def get_athlete_goals(athlete_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve active goals for an athlete.
    
    This tool queries the database for active AthleteGoal records and returns
    formatted goal data including goal type, target values, target dates, and
    descriptions to help understand the athlete's training objectives.
    
    Args:
        athlete_id: The ID of the athlete whose goals to retrieve
        
    Returns:
        List of goal dictionaries with formatted data
    """
    # Get tool logger
    logger = get_tool_logger()
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Query active goals for the athlete
        goals = db.query(AthleteGoal).filter(
            AthleteGoal.athlete_id == str(athlete_id),
            AthleteGoal.status == GoalStatus.ACTIVE.value
        ).order_by(AthleteGoal.created_at.desc()).all()
        
        # Format goals as evidence cards
        formatted_goals = []
        for goal in goals:
            formatted_goals.append({
                "type": "goal",
                "id": goal.id,
                "athlete_id": goal.athlete_id,
                "goal_type": goal.goal_type,
                "target_value": goal.target_value,
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
                "description": goal.description,
                "status": goal.status,
                "created_at": goal.created_at.isoformat() if goal.created_at else None,
                "updated_at": goal.updated_at.isoformat() if goal.updated_at else None
            })
        
        # Log successful invocation
        logger.log_invocation(
            tool_name="get_athlete_goals",
            parameters={"athlete_id": athlete_id},
            result=formatted_goals
        )
        
        return formatted_goals
        
    except Exception as e:
        # Log failed invocation
        logger.log_invocation(
            tool_name="get_athlete_goals",
            parameters={"athlete_id": athlete_id},
            result=None,
            error=e
        )
        raise
        
    finally:
        # Always close the database session
        db.close()

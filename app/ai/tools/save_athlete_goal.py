"""
SaveAthleteGoal LangChain StructuredTool for saving athlete goals.

This tool allows the LLM to save new fitness goals for athletes after gathering
goal type, target values, target dates, and descriptions.
"""

from typing import Dict, Any, Optional
from datetime import date
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.models.athlete_goal import AthleteGoal, GoalType, GoalStatus
from app.database import SessionLocal
from app.ai.telemetry import get_tool_logger


class SaveAthleteGoalInput(BaseModel):
    """Input schema for SaveAthleteGoal tool."""
    
    user_id: int = Field(
        ...,
        description="The ID of the user saving the goal",
        gt=0
    )
    goal_type: str = Field(
        ...,
        description="Type of goal (weight_loss, weight_gain, performance, endurance, strength, custom)"
    )
    description: str = Field(
        ...,
        description="Detailed goal description from conversation (e.g., 'Lose 5kg for Posidonia Tour cycling event on May 30, 2026')"
    )
    target_value: Optional[float] = Field(
        None,
        description=(
            "Numeric target value. For weight goals, this should be the TARGET WEIGHT in kg (not the amount to lose/gain). "
            "For performance goals, this could be distance (km), time (minutes), or other metrics. "
            "Can be None if the goal doesn't have a specific numeric target."
        )
    )
    target_date: Optional[str] = Field(
        None,
        description="Target completion date in ISO format (YYYY-MM-DD)"
    )
    
    @field_validator('goal_type')
    @classmethod
    def validate_goal_type(cls, v: str) -> str:
        """Ensure goal_type is valid."""
        valid_types = [gt.value for gt in GoalType]
        if v not in valid_types:
            raise ValueError(f"goal_type must be one of {valid_types}, got: {v}")
        return v
    
    @field_validator('target_date')
    @classmethod
    def validate_target_date(cls, v: Optional[str]) -> Optional[str]:
        """Ensure target_date is valid ISO format."""
        if v is None:
            return v
        
        try:
            # Parse to validate format
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"target_date must be in ISO format (YYYY-MM-DD), got: {v}")


@tool(args_schema=SaveAthleteGoalInput)
def save_athlete_goal(
    user_id: int,
    goal_type: str,
    description: str,
    target_value: Optional[float] = None,
    target_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Save a new fitness goal for an athlete.
    
    This tool creates a new AthleteGoal record in the database with the provided
    goal information. Use this after gathering goal type, target values, target
    dates, and detailed descriptions from the athlete.
    
    IMPORTANT: For weight goals (weight_loss or weight_gain):
    - target_value should be the TARGET WEIGHT in kg (not the amount to lose/gain)
    - If the athlete says "lose 5kg" and their current weight is 80kg, target_value should be 75
    - If you don't know the current weight, you can omit target_value and include the weight change in the description
    
    Args:
        user_id: The ID of the user saving the goal
        goal_type: Type of goal (weight_loss, weight_gain, performance, endurance, strength, custom)
        description: Detailed goal description including all context (e.g., "Lose 5kg for Posidonia Tour cycling event")
        target_value: Optional numeric target. For weight goals, this is the TARGET WEIGHT in kg. Can be None.
        target_date: Optional target completion date in ISO format (YYYY-MM-DD)
        
    Returns:
        Dictionary with success status, goal_id, and message
    """
    # Get tool logger
    logger = get_tool_logger()
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Parse target_date if provided
        parsed_target_date = None
        if target_date:
            parsed_target_date = date.fromisoformat(target_date)
        
        # Create new goal
        new_goal = AthleteGoal(
            athlete_id=str(user_id),
            goal_type=goal_type,
            description=description,
            target_value=target_value,
            target_date=parsed_target_date,
            status=GoalStatus.ACTIVE.value
        )
        
        # Save to database
        db.add(new_goal)
        db.commit()
        db.refresh(new_goal)
        
        # Format result
        result = {
            "success": True,
            "goal_id": new_goal.id,
            "message": f"Goal saved successfully with ID: {new_goal.id}",
            "goal": {
                "id": new_goal.id,
                "athlete_id": new_goal.athlete_id,
                "goal_type": new_goal.goal_type,
                "description": new_goal.description,
                "target_value": new_goal.target_value,
                "target_date": new_goal.target_date.isoformat() if new_goal.target_date else None,
                "status": new_goal.status,
                "created_at": new_goal.created_at.isoformat() if new_goal.created_at else None
            }
        }
        
        # Log successful invocation
        logger.log_invocation(
            tool_name="save_athlete_goal",
            parameters={
                "user_id": user_id,
                "goal_type": goal_type,
                "description": description,
                "target_value": target_value,
                "target_date": target_date
            },
            result=result
        )
        
        return result
        
    except Exception as e:
        # Log failed invocation
        logger.log_invocation(
            tool_name="save_athlete_goal",
            parameters={
                "user_id": user_id,
                "goal_type": goal_type,
                "description": description,
                "target_value": target_value,
                "target_date": target_date
            },
            result=None,
            error=e
        )
        
        # Return error result
        return {
            "success": False,
            "message": f"Failed to save goal: {str(e)}",
            "error": str(e)
        }
        
    finally:
        # Always close the database session
        db.close()

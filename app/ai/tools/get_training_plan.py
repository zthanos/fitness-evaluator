"""
GetTrainingPlan LangChain StructuredTool for retrieving training plans.

This tool allows the LLM to retrieve existing training plans for review or iteration.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.ai.telemetry import get_tool_logger


class GetTrainingPlanInput(BaseModel):
    """Input schema for GetTrainingPlan tool."""
    
    user_id: int = Field(
        ...,
        description="The ID of the user retrieving the plan",
        gt=0
    )
    plan_id: str = Field(
        ...,
        description="The UUID of the training plan to retrieve"
    )


@tool(args_schema=GetTrainingPlanInput)
def get_training_plan(user_id: int, plan_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve an existing training plan.
    
    This tool retrieves a training plan from the database with all weeks and sessions.
    Use this to review existing plans or before making modifications.
    
    Args:
        user_id: The ID of the user retrieving the plan
        plan_id: The UUID of the training plan to retrieve
        
    Returns:
        Dictionary with plan data including all weeks and sessions, or None if not found
    """
    # Get tool logger
    logger = get_tool_logger()
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Retrieve plan using TrainingPlanEngine
        from app.services.training_plan_engine import TrainingPlanEngine
        engine = TrainingPlanEngine(db)
        plan = engine.get_plan(plan_id, user_id)
        
        if not plan:
            # Log successful invocation with no results
            logger.log_invocation(
                tool_name="get_training_plan",
                parameters={"user_id": user_id, "plan_id": plan_id},
                result=None
            )
            return None
        
        # Convert plan to dictionary
        plan_dict = {
            "id": plan.id,
            "user_id": plan.user_id,
            "title": plan.title,
            "sport": plan.sport,
            "goal_id": plan.goal_id,
            "start_date": plan.start_date.isoformat(),
            "end_date": plan.end_date.isoformat(),
            "status": plan.status,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
            "weeks": []
        }
        
        # Add weeks
        for week in plan.weeks:
            week_dict = {
                "week_number": week.week_number,
                "focus": week.focus,
                "volume_target": week.volume_target,
                "sessions": []
            }
            
            # Add sessions
            for session in week.sessions:
                session_dict = {
                    "day_of_week": session.day_of_week,
                    "session_type": session.session_type,
                    "duration_minutes": session.duration_minutes,
                    "intensity": session.intensity,
                    "description": session.description,
                    "completed": session.completed,
                    "matched_activity_id": session.matched_activity_id
                }
                week_dict["sessions"].append(session_dict)
            
            plan_dict["weeks"].append(week_dict)
        
        # Log successful invocation
        logger.log_invocation(
            tool_name="get_training_plan",
            parameters={"user_id": user_id, "plan_id": plan_id},
            result=plan_dict
        )
        
        return plan_dict
        
    except Exception as e:
        # Log failed invocation
        logger.log_invocation(
            tool_name="get_training_plan",
            parameters={"user_id": user_id, "plan_id": plan_id},
            result=None,
            error=e
        )
        raise
        
    finally:
        # Always close the database session
        db.close()

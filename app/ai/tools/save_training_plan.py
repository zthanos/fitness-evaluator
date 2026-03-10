"""
SaveTrainingPlan LangChain StructuredTool for persisting training plans.

This tool allows the LLM to save generated training plans to the database after
athlete confirmation.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.ai.telemetry import get_tool_logger
from app.schemas.training_plan import TrainingPlan, TrainingWeek, TrainingSession


class TrainingSessionInput(BaseModel):
    """Input schema for training session."""
    day_of_week: int = Field(..., description="Day of week (1-7, Monday-Sunday)", ge=1, le=7)
    session_type: str = Field(..., description="Session type (e.g., easy_run, tempo_run, interval, long_run, rest)")
    duration_minutes: int = Field(..., description="Duration in minutes", gt=0)
    intensity: str = Field(..., description="Intensity level (recovery, easy, moderate, hard, max)")
    description: str = Field(..., description="Session description")


class TrainingWeekInput(BaseModel):
    """Input schema for training week."""
    week_number: int = Field(..., description="Week number (1-based)", gt=0)
    focus: str = Field(..., description="Week focus (e.g., Base building, Intensity, Recovery)")
    volume_target: float = Field(..., description="Volume target in hours", gt=0)
    sessions: List[TrainingSessionInput] = Field(..., description="List of training sessions")


class SaveTrainingPlanInput(BaseModel):
    """Input schema for SaveTrainingPlan tool."""
    
    user_id: int = Field(
        ...,
        description="The ID of the user saving the plan",
        gt=0
    )
    title: str = Field(
        ...,
        description="Plan title (e.g., 'Marathon Training')",
        min_length=1
    )
    sport: str = Field(
        ...,
        description="Primary sport (running, cycling, swimming, triathlon, other)"
    )
    start_date: str = Field(
        ...,
        description="Plan start date in ISO format (YYYY-MM-DD)"
    )
    duration_weeks: int = Field(
        ...,
        description="Plan duration in weeks",
        gt=0
    )
    weeks: List[TrainingWeekInput] = Field(
        ...,
        description="List of training weeks"
    )
    goal_id: Optional[str] = Field(
        None,
        description="Linked goal ID (optional)"
    )
    status: str = Field(
        "active",
        description="Plan status (draft, active, completed, abandoned)"
    )
    
    @field_validator('sport')
    @classmethod
    def validate_sport(cls, v: str) -> str:
        """Ensure sport is valid."""
        valid_sports = ['running', 'cycling', 'swimming', 'triathlon', 'other']
        if v not in valid_sports:
            raise ValueError(f"sport must be one of {valid_sports}, got: {v}")
        return v
    
    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v: str) -> str:
        """Ensure start_date is valid ISO format."""
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"start_date must be in ISO format (YYYY-MM-DD), got: {v}")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Ensure status is valid."""
        valid_statuses = ['draft', 'active', 'completed', 'abandoned']
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}, got: {v}")
        return v


@tool(args_schema=SaveTrainingPlanInput)
def save_training_plan(
    user_id: int,
    title: str,
    sport: str,
    start_date: str,
    duration_weeks: int,
    weeks: List[Dict[str, Any]],
    goal_id: Optional[str] = None,
    status: str = "active"
) -> Dict[str, Any]:
    """
    Save a generated training plan to the database.
    
    This tool persists a training plan with all weeks and sessions to the database.
    Use this after the athlete has reviewed and confirmed the plan.
    
    Args:
        user_id: The ID of the user saving the plan
        title: Plan title (e.g., 'Marathon Training')
        sport: Primary sport (running, cycling, swimming, triathlon, other)
        start_date: Plan start date in ISO format (YYYY-MM-DD)
        duration_weeks: Plan duration in weeks
        weeks: List of training weeks with sessions
        goal_id: Optional linked goal ID
        status: Plan status (draft, active, completed, abandoned)
        
    Returns:
        Dictionary with success status, plan_id, and message
    """
    # Get tool logger
    logger = get_tool_logger()
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Parse start_date
        parsed_start_date = date.fromisoformat(start_date)
        
        # Calculate end_date
        from datetime import timedelta
        end_date = parsed_start_date + timedelta(weeks=duration_weeks)
        
        # Convert weeks to TrainingWeek dataclasses
        training_weeks = []
        for week_data in weeks:
            # Convert sessions to TrainingSession dataclasses
            training_sessions = []
            for session_data in week_data['sessions']:
                session = TrainingSession(
                    day_of_week=session_data['day_of_week'],
                    session_type=session_data['session_type'],
                    duration_minutes=session_data['duration_minutes'],
                    intensity=session_data['intensity'],
                    description=session_data['description'],
                    completed=False,
                    matched_activity_id=None
                )
                training_sessions.append(session)
            
            week = TrainingWeek(
                week_number=week_data['week_number'],
                focus=week_data['focus'],
                volume_target=week_data['volume_target'],
                sessions=training_sessions
            )
            training_weeks.append(week)
        
        # Create TrainingPlan dataclass
        plan = TrainingPlan(
            id=None,
            user_id=user_id,
            title=title,
            sport=sport,
            goal_id=goal_id,
            start_date=parsed_start_date,
            end_date=end_date,
            status=status,
            weeks=training_weeks,
            created_at=None,
            updated_at=None
        )
        
        # Save plan using TrainingPlanEngine
        from app.services.training_plan_engine import TrainingPlanEngine
        engine = TrainingPlanEngine(db)
        plan_id = engine.save_plan(plan)
        
        # Format result
        result = {
            "success": True,
            "plan_id": plan_id,
            "message": f"Training plan saved successfully with ID: {plan_id}",
            "plan": {
                "id": plan_id,
                "user_id": user_id,
                "title": title,
                "sport": sport,
                "goal_id": goal_id,
                "start_date": start_date,
                "end_date": end_date.isoformat(),
                "status": status,
                "weeks_count": len(training_weeks)
            }
        }
        
        # Log successful invocation
        logger.log_invocation(
            tool_name="save_training_plan",
            parameters={
                "user_id": user_id,
                "title": title,
                "sport": sport,
                "start_date": start_date,
                "duration_weeks": duration_weeks,
                "goal_id": goal_id,
                "status": status
            },
            result=result
        )
        
        return result
        
    except Exception as e:
        # Log failed invocation
        logger.log_invocation(
            tool_name="save_training_plan",
            parameters={
                "user_id": user_id,
                "title": title,
                "sport": sport,
                "start_date": start_date,
                "duration_weeks": duration_weeks,
                "goal_id": goal_id,
                "status": status
            },
            result=None,
            error=e
        )
        
        # Return error result
        return {
            "success": False,
            "message": f"Failed to save training plan: {str(e)}",
            "error": str(e)
        }
        
    finally:
        # Always close the database session
        db.close()

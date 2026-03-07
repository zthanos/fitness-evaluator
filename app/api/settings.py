"""Settings API endpoints for profile, Strava, and LLM configuration."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional
import re
from app.database import get_db
from app.models.athlete import Athlete

router = APIRouter()


# Pydantic models for request/response validation
class ProfileUpdate(BaseModel):
    """Profile update request model."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = None
    date_of_birth: Optional[date] = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format."""
        if v is not None and v != '':
            # Simple email validation regex
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError('Invalid email format')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "date_of_birth": "1990-01-15"
            }
        }


class ProfileResponse(BaseModel):
    """Profile response model."""
    id: int
    name: str
    email: Optional[str]
    date_of_birth: Optional[date]
    current_plan: Optional[str]
    goals: Optional[str]
    
    class Config:
        from_attributes = True


class TrainingPlanUpdate(BaseModel):
    """Training plan update request model."""
    plan_name: Optional[str] = None
    start_date: Optional[date] = None
    goal_description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan_name": "Marathon Training",
                "start_date": "2024-01-01",
                "goal_description": "Complete a marathon in under 4 hours"
            }
        }


@router.get("/profile", response_model=ProfileResponse, summary="Get athlete profile")
async def get_profile(db: Session = Depends(get_db)):
    """
    Get athlete profile information.
    
    **Requirements: 19.1, 19.7**
    
    Returns profile data including name, email, date of birth, current plan, and goals.
    For now, returns the first athlete in the database (single-athlete system).
    """
    athlete = db.query(Athlete).first()
    
    if not athlete:
        # Create default athlete if none exists
        athlete = Athlete(
            name="Athlete",
            email=None,
            date_of_birth=None,
            current_plan=None,
            goals=None
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
    
    return athlete


@router.put("/profile", response_model=ProfileResponse, summary="Update athlete profile")
async def update_profile(
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db)
):
    """
    Update athlete profile information.
    
    **Requirements: 19.1, 19.6, 19.7**
    
    Validates:
    - Email format (handled by EmailStr)
    - Date of birth range (must be between 1900-01-01 and today)
    
    Returns updated profile data.
    """
    athlete = db.query(Athlete).first()
    
    if not athlete:
        # Create athlete if none exists
        athlete = Athlete(
            name=profile_data.name or "Athlete",
            email=profile_data.email,
            date_of_birth=profile_data.date_of_birth
        )
        db.add(athlete)
    else:
        # Update existing athlete
        if profile_data.name is not None:
            athlete.name = profile_data.name
        if profile_data.email is not None:
            athlete.email = profile_data.email
        if profile_data.date_of_birth is not None:
            # Validate date of birth range
            today = date.today()
            min_date = date(1900, 1, 1)
            
            if profile_data.date_of_birth < min_date or profile_data.date_of_birth > today:
                raise HTTPException(
                    status_code=400,
                    detail=f"Date of birth must be between {min_date} and {today}"
                )
            
            athlete.date_of_birth = profile_data.date_of_birth
    
    db.commit()
    db.refresh(athlete)
    
    return athlete


@router.put("/training-plan", response_model=ProfileResponse, summary="Update training plan")
async def update_training_plan(
    plan_data: TrainingPlanUpdate,
    db: Session = Depends(get_db)
):
    """
    Update athlete's training plan settings.
    
    **Requirements: 19.3, 19.7**
    
    Updates plan name, start date, and goal description.
    Stores as JSON in the current_plan and goals fields.
    """
    athlete = db.query(Athlete).first()
    
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete profile not found")
    
    # Update training plan fields
    if plan_data.plan_name is not None or plan_data.start_date is not None:
        # Store plan info in current_plan field
        plan_info = f"{plan_data.plan_name or 'Training Plan'}"
        if plan_data.start_date:
            plan_info += f" (started {plan_data.start_date})"
        athlete.current_plan = plan_info
    
    if plan_data.goal_description is not None:
        athlete.goals = plan_data.goal_description
    
    db.commit()
    db.refresh(athlete)
    
    return athlete


@router.get("/strava", summary="Get Strava connection status")
async def get_strava_status(db: Session = Depends(get_db)):
    """
    Get Strava connection status.
    
    **Requirements: 19.2, 19.7**
    
    Returns connection status and athlete name if connected.
    This is a placeholder - full implementation in Task 10.
    """
    # Placeholder for Strava integration
    return {
        "connected": False,
        "athlete_name": None,
        "message": "Strava integration will be available in Task 10"
    }


@router.post("/strava/connect", summary="Initiate Strava OAuth connection")
async def connect_strava(db: Session = Depends(get_db)):
    """
    Initiate Strava OAuth connection flow.
    
    **Requirements: 19.2, 19.7**
    
    Returns OAuth authorization URL.
    This is a placeholder - full implementation in Task 10.
    """
    return {
        "auth_url": None,
        "message": "Strava integration will be available in Task 10"
    }


@router.post("/strava/disconnect", summary="Disconnect Strava account")
async def disconnect_strava(db: Session = Depends(get_db)):
    """
    Disconnect Strava account.
    
    **Requirements: 19.2, 19.7**
    
    Removes Strava tokens and connection.
    This is a placeholder - full implementation in Task 10.
    """
    return {
        "success": False,
        "message": "Strava integration will be available in Task 10"
    }


@router.get("/llm", summary="Get LLM settings")
async def get_llm_settings():
    """
    Get LLM configuration settings.
    
    **Requirements: 19.4, 19.7**
    
    Returns current LLM model, temperature, and endpoint configuration.
    Note: These settings are configured via environment variables and require server restart.
    """
    from app.config import get_settings
    
    settings = get_settings()
    
    return {
        "llm_type": settings.LLM_TYPE,
        "endpoint": settings.OLLAMA_ENDPOINT,
        "model": settings.OLLAMA_MODEL,
        "temperature": 0.7,  # Default for chat, 0.1 for analysis
        "message": "LLM settings are configured via environment variables. Changes require server restart."
    }


@router.put("/llm", summary="Update LLM settings")
async def update_llm_settings():
    """
    Update LLM settings.
    
    **Requirements: 19.4, 19.7**
    
    Note: LLM settings are configured via environment variables.
    This endpoint returns instructions for updating the .env file.
    """
    return {
        "success": False,
        "message": "LLM settings must be updated in the .env file and require server restart. Update LLM_TYPE, OLLAMA_ENDPOINT, and OLLAMA_MODEL variables."
    }

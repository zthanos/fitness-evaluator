"""Settings API endpoints for profile, Strava, and LLM configuration."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional
import re
from app.database import get_db
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete

router = APIRouter()


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = None
    date_of_birth: Optional[date] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v is not None and v != '':
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError('Invalid email format')
        return v

    class Config:
        json_schema_extra = {"example": {"name": "John Doe", "email": "john@example.com", "date_of_birth": "1990-01-15"}}


class ProfileResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    date_of_birth: Optional[date]
    current_plan: Optional[str]
    goals: Optional[str]

    class Config:
        from_attributes = True


class TrainingPlanUpdate(BaseModel):
    plan_name: Optional[str] = None
    start_date: Optional[date] = None
    goal_description: Optional[str] = None


@router.get("/profile", response_model=ProfileResponse, summary="Get athlete profile")
async def get_profile(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    return athlete


@router.put("/profile", response_model=ProfileResponse, summary="Update athlete profile")
async def update_profile(
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    if profile_data.name is not None:
        athlete.name = profile_data.name
    if profile_data.email is not None:
        athlete.email = profile_data.email
    if profile_data.date_of_birth is not None:
        today = date.today()
        if profile_data.date_of_birth < date(1900, 1, 1) or profile_data.date_of_birth > today:
            raise HTTPException(status_code=400, detail=f"Date of birth must be between 1900-01-01 and {today}")
        athlete.date_of_birth = profile_data.date_of_birth

    db.commit()
    db.refresh(athlete)
    return athlete


@router.put("/training-plan", response_model=ProfileResponse, summary="Update training plan")
async def update_training_plan(
    plan_data: TrainingPlanUpdate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    if plan_data.plan_name is not None or plan_data.start_date is not None:
        plan_info = plan_data.plan_name or 'Training Plan'
        if plan_data.start_date:
            plan_info += f" (started {plan_data.start_date})"
        athlete.current_plan = plan_info

    if plan_data.goal_description is not None:
        athlete.goals = plan_data.goal_description

    db.commit()
    db.refresh(athlete)
    return athlete


@router.get("/strava", summary="Get Strava connection status")
async def get_strava_status(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    from app.models.strava_token import StravaToken
    token = db.query(StravaToken).filter(StravaToken.athlete_id == athlete.id).first()
    if token:
        return {"connected": True, "expires_at": token.expires_at.isoformat()}
    return {"connected": False, "expires_at": None}


@router.post("/strava/connect", summary="Initiate Strava OAuth connection")
async def connect_strava(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    from app.services.strava_client import StravaClient
    client = StravaClient(db)
    auth_url = client.get_authorization_url(athlete.id)
    return {"auth_url": auth_url}


@router.post("/strava/disconnect", summary="Disconnect Strava account")
async def disconnect_strava(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    from app.services.strava_client import StravaClient
    client = StravaClient(db)
    success = client.disconnect(athlete.id)
    return {"success": success}


@router.get("/llm", summary="Get LLM settings")
async def get_llm_settings(athlete: Athlete = Depends(get_current_athlete)):
    from app.config import get_settings
    settings = get_settings()

    if settings.LLM_TYPE.lower() == "lm-studio":
        endpoint = settings.LM_STUDIO_ENDPOINT or settings.LM_STUDIO_BASE_URL or "http://localhost:1234"
        model = settings.LM_STUDIO_MODEL
    else:
        endpoint = settings.OLLAMA_ENDPOINT or "http://localhost:11434"
        model = settings.OLLAMA_MODEL

    return {
        "llm_type": settings.LLM_TYPE,
        "endpoint": endpoint,
        "model": model,
        "temperature": 0.7,
        "message": "LLM settings are configured via environment variables. Changes require server restart.",
    }


@router.put("/llm", summary="Update LLM settings")
async def update_llm_settings(athlete: Athlete = Depends(get_current_athlete)):
    return {
        "success": False,
        "message": "LLM settings must be updated in the .env file and require server restart.",
    }


@router.get("/app", summary="Get application-level configuration (read-only)")
async def get_app_settings(athlete: Athlete = Depends(get_current_athlete)):
    from app.config import get_settings
    settings = get_settings()
    return {
        "strava_api_timeout_s": 300,
        "embedding_timeout_s": settings.EMBEDDING_TIMEOUT,
        "keycloak_url": settings.KEYCLOAK_URL,
        "keycloak_realm": settings.KEYCLOAK_REALM,
        "environment": settings.ENVIRONMENT,
        "log_level": settings.LOG_LEVEL,
    }

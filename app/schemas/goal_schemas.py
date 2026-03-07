"""Pydantic schemas for goal API endpoints."""

from datetime import date, datetime
from pydantic import BaseModel, Field, validator
from typing import Optional
from app.models.athlete_goal import GoalType, GoalStatus


class GoalCreate(BaseModel):
    """Schema for creating a goal."""
    goal_type: str = Field(..., description="Type of goal")
    description: str = Field(..., min_length=10, description="Detailed goal description")
    target_value: Optional[float] = Field(None, description="Numeric target value")
    target_date: Optional[date] = Field(None, description="Target completion date")
    athlete_id: Optional[str] = Field(None, description="Athlete identifier")
    
    @validator('goal_type')
    def validate_goal_type(cls, v):
        valid_types = [gt.value for gt in GoalType]
        if v not in valid_types:
            raise ValueError(f"goal_type must be one of: {', '.join(valid_types)}")
        return v
    
    @validator('target_date')
    def validate_target_date(cls, v):
        if v and v <= date.today():
            raise ValueError("target_date must be in the future")
        return v
    
    @validator('target_value')
    def validate_target_value(cls, v, values):
        if 'goal_type' in values:
            goal_type = values['goal_type']
            if goal_type in ['weight_loss', 'weight_gain']:
                if v is None:
                    raise ValueError(f"target_value is required for {goal_type} goals")
                if v < 30 or v > 300:
                    raise ValueError("target_value for weight goals must be between 30kg and 300kg")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "goal_type": "weight_loss",
                "description": "Lose 10kg in 3 months for wedding. Currently 85kg, target 75kg.",
                "target_value": 75.0,
                "target_date": "2024-06-15"
            }
        }


class GoalUpdate(BaseModel):
    """Schema for updating a goal."""
    status: Optional[str] = Field(None, description="Goal status")
    description: Optional[str] = Field(None, min_length=10, description="Updated description")
    target_value: Optional[float] = Field(None, description="Updated target value")
    target_date: Optional[date] = Field(None, description="Updated target date")
    
    @validator('status')
    def validate_status(cls, v):
        if v:
            valid_statuses = [gs.value for gs in GoalStatus]
            if v not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed"
            }
        }


class GoalResponse(BaseModel):
    """Schema for goal response."""
    id: str = Field(..., description="Goal identifier")
    athlete_id: Optional[str] = Field(None, description="Athlete identifier")
    goal_type: str = Field(..., description="Type of goal")
    target_value: Optional[float] = Field(None, description="Numeric target value")
    target_date: Optional[date] = Field(None, description="Target completion date")
    description: str = Field(..., description="Detailed goal description")
    status: str = Field(..., description="Goal status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "athlete_id": None,
                "goal_type": "weight_loss",
                "target_value": 75.0,
                "target_date": "2024-06-15",
                "description": "Lose 10kg in 3 months for wedding",
                "status": "active",
                "created_at": "2024-03-15T10:30:00",
                "updated_at": "2024-03-15T10:30:00"
            }
        }

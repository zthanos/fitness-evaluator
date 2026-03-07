"""Pydantic schemas for log endpoints."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Generic, TypeVar


# Generic type for paginated responses
T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic schema for paginated responses."""
    logs: List[T]
    total: int
    page: int
    page_size: int


class DailyLogCreate(BaseModel):
    """Schema for creating/updating a daily log."""
    log_date: date
    fasting_hours: Optional[float] = None
    calories_in: Optional[int] = Field(None, ge=0, le=10000)
    protein_g: Optional[float] = Field(None, ge=0, le=1000)
    carbs_g: Optional[float] = Field(None, ge=0, le=1000)
    fat_g: Optional[float] = Field(None, ge=0, le=1000)
    adherence_score: Optional[int] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


class DailyLogResponse(BaseModel):
    """Schema for daily log response."""
    id: str
    log_date: date
    fasting_hours: Optional[float]
    calories_in: Optional[int]
    protein_g: Optional[float]
    carbs_g: Optional[float]
    fat_g: Optional[float]
    adherence_score: Optional[int]
    notes: Optional[str]
    week_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WeeklyMeasurementCreate(BaseModel):
    """Schema for creating/updating weekly measurements."""
    week_start: date
    weight_kg: Optional[float] = Field(None, ge=30, le=300, description="Weight in kg (30-300)")
    weight_prev_kg: Optional[float] = None
    body_fat_pct: Optional[float] = Field(None, ge=3, le=60, description="Body fat percentage (3-60)")
    waist_cm: Optional[float] = Field(None, ge=0, description="Waist circumference in cm")
    waist_prev_cm: Optional[float] = None
    sleep_avg_hrs: Optional[float] = None
    rhr_bpm: Optional[int] = None
    energy_level_avg: Optional[float] = None


class WeeklyMeasurementResponse(BaseModel):
    """Schema for weekly measurement response."""
    id: str
    week_start: date
    weight_kg: Optional[float]
    weight_prev_kg: Optional[float]
    body_fat_pct: Optional[float]
    waist_cm: Optional[float]
    waist_prev_cm: Optional[float]
    sleep_avg_hrs: Optional[float]
    rhr_bpm: Optional[int]
    energy_level_avg: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PlanTargetsCreate(BaseModel):
    """Schema for creating/updating plan targets."""
    effective_from: date
    target_calories: Optional[int] = None
    target_protein_g: Optional[float] = None
    target_fasting_hrs: Optional[float] = None
    target_run_km_wk: Optional[float] = None
    target_strength_sessions: Optional[int] = None
    target_weight_kg: Optional[float] = None
    notes: Optional[str] = None


class PlanTargetsResponse(BaseModel):
    """Schema for plan targets response."""
    id: str
    effective_from: date
    target_calories: Optional[int]
    target_protein_g: Optional[float]
    target_fasting_hrs: Optional[float]
    target_run_km_wk: Optional[float]
    target_strength_sessions: Optional[int]
    target_weight_kg: Optional[float]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

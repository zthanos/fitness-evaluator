"""Pydantic schemas for metrics API endpoints."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict


class BodyMetricCreate(BaseModel):
    """
    Schema for creating a body metric record.
    
    Requirements: 5.1, 5.2, 5.3
    """
    measurement_date: date = Field(..., description="Date of measurement")
    weight: float = Field(..., ge=30, le=300, description="Weight in kg (30-300)")
    body_fat_pct: Optional[float] = Field(None, ge=3, le=60, description="Body fat percentage (3-60)")
    measurements: Optional[Dict[str, float]] = Field(None, description="Additional measurements (e.g., waist_cm)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "measurement_date": "2024-01-15",
                "weight": 75.5,
                "body_fat_pct": 18.5,
                "measurements": {
                    "waist_cm": 85.0
                }
            }
        }


class BodyMetricUpdate(BaseModel):
    """
    Schema for updating a body metric record.
    
    Requirements: 5.6
    
    All fields are optional to allow partial updates.
    """
    weight: Optional[float] = Field(None, ge=30, le=300, description="Weight in kg (30-300)")
    body_fat_pct: Optional[float] = Field(None, ge=3, le=60, description="Body fat percentage (3-60)")
    measurements: Optional[Dict[str, float]] = Field(None, description="Additional measurements (e.g., waist_cm)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "weight": 74.8,
                "body_fat_pct": 18.2,
                "measurements": {
                    "waist_cm": 84.5
                }
            }
        }


class BodyMetricResponse(BaseModel):
    """
    Schema for body metric response.
    
    Requirements: 5.4, 5.5
    
    Includes timestamp and athlete identifier as required by 5.4.
    """
    id: str = Field(..., description="Unique identifier for the metric record")
    measurement_date: date = Field(..., description="Date of measurement")
    weight: float = Field(..., description="Weight in kg")
    body_fat_pct: Optional[float] = Field(None, description="Body fat percentage")
    measurements: Optional[Dict[str, float]] = Field(None, description="Additional measurements")
    created_at: datetime = Field(..., description="Timestamp when record was created")
    updated_at: datetime = Field(..., description="Timestamp when record was last updated")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "measurement_date": "2024-01-15",
                "weight": 75.5,
                "body_fat_pct": 18.5,
                "measurements": {
                    "waist_cm": 85.0
                },
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }

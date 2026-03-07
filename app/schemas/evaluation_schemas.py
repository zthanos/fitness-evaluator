"""Evaluation Report Schemas

Pydantic schemas for evaluation report generation and validation.
"""
from pydantic import BaseModel, Field
from typing import List
from datetime import date


class EvaluationReport(BaseModel):
    """
    Structured evaluation report schema for LangChain output.
    
    Validates that evaluation reports contain all required fields
    with proper types and constraints.
    """
    overall_score: int = Field(..., ge=0, le=100, description="Overall performance score (0-100)")
    strengths: List[str] = Field(..., min_length=1, description="List of athlete strengths and achievements")
    improvements: List[str] = Field(..., description="List of areas needing improvement")
    tips: List[str] = Field(..., description="List of actionable coaching tips")
    recommended_exercises: List[str] = Field(..., description="List of recommended exercises or activities")
    goal_alignment: str = Field(..., min_length=10, description="Assessment of progress toward goals")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Data confidence score (0.0-1.0)")


class EvaluationRequest(BaseModel):
    """Request schema for evaluation generation."""
    period_start: date = Field(..., description="Start date of evaluation period")
    period_end: date = Field(..., description="End date of evaluation period")
    period_type: str = Field(..., description="Period type: weekly, bi-weekly, or monthly")


class EvaluationResponse(BaseModel):
    """Response schema for evaluation endpoints."""
    id: str
    athlete_id: int
    period_start: date
    period_end: date
    period_type: str
    overall_score: int
    strengths: List[str]
    improvements: List[str]
    tips: List[str]
    recommended_exercises: List[str]
    goal_alignment: str
    confidence_score: float
    generated_at: str
    
    class Config:
        from_attributes = True

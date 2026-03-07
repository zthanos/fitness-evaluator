"""Pydantic schemas for activity analysis."""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class EffortAnalysisResponse(BaseModel):
    """
    Structured response schema for AI-generated effort analysis.
    
    Used with LangChain's with_structured_output for validated responses.
    """
    
    effort_level: str = Field(
        description="Overall effort level: 'Easy', 'Moderate', 'Hard', or 'Very Hard'"
    )
    
    summary: str = Field(
        description="Brief 2-3 sentence summary of the activity effort and performance"
    )
    
    heart_rate_analysis: Optional[str] = Field(
        None,
        description="Analysis of heart rate data if available, including zones and intensity"
    )
    
    pace_analysis: Optional[str] = Field(
        None,
        description="Analysis of pace variation and consistency throughout the activity"
    )
    
    elevation_analysis: Optional[str] = Field(
        None,
        description="Analysis of elevation profile and its impact on effort"
    )
    
    recommendations: str = Field(
        description="1-2 actionable recommendations based on the effort analysis"
    )


class ActivityAnalysisCreate(BaseModel):
    """Schema for creating an activity analysis."""
    
    activity_id: str
    analysis_text: str


class ActivityAnalysisResponse(BaseModel):
    """Schema for activity analysis response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    activity_id: str
    analysis_text: str
    generated_at: datetime

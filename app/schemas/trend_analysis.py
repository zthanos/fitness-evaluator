"""
Pydantic schemas for weight trend analysis.

Requirements: 7.1, 7.2, 7.3
"""

from pydantic import BaseModel, Field
from typing import Optional


class TrendAnalysisResponse(BaseModel):
    """
    Structured response schema for weight trend analysis.
    
    Used with LangChain's with_structured_output for validated LLM responses.
    
    Requirements: 7.1, 7.2, 7.3
    """
    
    weekly_change_rate: float = Field(
        description="Average weekly weight change rate in kg/week (positive for gain, negative for loss)"
    )
    
    trend_direction: str = Field(
        description="Overall trend direction: 'increasing', 'decreasing', or 'stable'"
    )
    
    summary: str = Field(
        description="Brief summary of the weight trend (2-3 sentences)"
    )
    
    goal_alignment: str = Field(
        description="Assessment of whether the trend aligns with athlete's stated goals"
    )
    
    recommendations: str = Field(
        description="Specific, actionable recommendations for maintaining, increasing, or decreasing rate of change"
    )
    
    confidence_level: str = Field(
        description="Confidence level in the analysis: 'high', 'medium', or 'low' based on data quality and consistency"
    )
    
    data_points_analyzed: int = Field(
        description="Number of weight measurements included in the analysis"
    )

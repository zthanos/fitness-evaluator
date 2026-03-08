"""
Output contracts for weekly evaluation operations.

This module defines Pydantic v2 models for structured LLM responses
in weekly evaluation operations, including field validation for data
integrity and compliance with Context Engineering requirements.
"""

from typing import List
from pydantic import BaseModel, Field, field_validator


class Recommendation(BaseModel):
    """A single actionable recommendation for the athlete."""
    
    text: str = Field(
        ...,
        description="Actionable recommendation text"
    )
    priority: int = Field(
        ...,
        ge=1,
        le=5,
        description="Priority level (1=highest, 5=lowest)"
    )
    category: str = Field(
        ...,
        description="Recommendation category (training, nutrition, recovery, mindset)"
    )
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate category is one of the allowed values."""
        allowed_categories = {'training', 'nutrition', 'recovery', 'mindset'}
        if v not in allowed_categories:
            raise ValueError(
                f"Category must be one of {allowed_categories}, got '{v}'"
            )
        return v


class WeeklyEvalContract(BaseModel):
    """
    Output contract for weekly evaluation responses.
    
    Defines the expected structure for AI-generated weekly evaluations,
    including holistic assessment, strengths, areas for improvement,
    actionable recommendations, and confidence scoring.
    
    Requirements: 3.2.2, 3.2.7
    """
    
    overall_assessment: str = Field(
        ...,
        description="Holistic assessment of the athlete's training week"
    )
    strengths: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of observed strengths (1-5 items)"
    )
    areas_for_improvement: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of areas needing improvement (1-5 items)"
    )
    recommendations: List[Recommendation] = Field(
        ...,
        max_length=5,
        description="List of actionable recommendations (max 5 items)"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the evaluation (0.0-1.0)"
    )
    
    @field_validator('strengths')
    @classmethod
    def validate_strengths_length(cls, v: List[str]) -> List[str]:
        """Validate strengths list has 1-5 items."""
        if not (1 <= len(v) <= 5):
            raise ValueError(
                f"Strengths must contain 1-5 items, got {len(v)}"
            )
        return v
    
    @field_validator('areas_for_improvement')
    @classmethod
    def validate_areas_length(cls, v: List[str]) -> List[str]:
        """Validate areas_for_improvement list has 1-5 items."""
        if not (1 <= len(v) <= 5):
            raise ValueError(
                f"Areas for improvement must contain 1-5 items, got {len(v)}"
            )
        return v
    
    @field_validator('recommendations')
    @classmethod
    def validate_recommendations_length(cls, v: List[Recommendation]) -> List[Recommendation]:
        """Validate recommendations list has 0-5 items."""
        if len(v) > 5:
            raise ValueError(
                f"Recommendations must contain at most 5 items, got {len(v)}"
            )
        return v
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Validate confidence_score is between 0.0 and 1.0."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"Confidence score must be between 0.0 and 1.0, got {v}"
            )
        return v

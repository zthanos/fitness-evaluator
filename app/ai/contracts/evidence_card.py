"""
Evidence card model for linking AI claims to source database records.

This module defines the Pydantic v2 model for evidence cards that provide
traceability between AI-generated claims and the underlying data sources
(activities, goals, metrics, logs) used to support those claims.
"""

from pydantic import BaseModel, Field, field_validator


class EvidenceCard(BaseModel):
    """
    Evidence card linking AI claims to source database records.

    Evidence cards provide traceability by connecting specific claims
    in AI responses to the database records that support those claims.
    This enables verification and debugging of AI assessments.

    Requirements: 4.1.2
    """

    claim_text: str = Field(
        ...,
        description="The specific claim from the AI response"
    )
    source_type: str = Field(
        ...,
        description="Type of data source (activity, goal, metric, log)"
    )
    source_id: int = Field(
        ...,
        description="Database record ID of the source"
    )
    source_date: str = Field(
        ...,
        description="ISO format date of the source record"
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score indicating how strongly this source supports the claim (0.0-1.0)"
    )

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: int) -> int:
        """
        Validate source_id is a positive integer.

        Note: Full database validation (checking if the record exists) should be
        performed at the service layer where database access is available.
        """
        if v <= 0:
            raise ValueError(
                f"Source ID must be a positive integer, got {v}"
            )
        return v

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """Validate source_type is one of the allowed values."""
        allowed_types = {'activity', 'goal', 'metric', 'log'}
        if v not in allowed_types:
            raise ValueError(
                f"Source type must be one of {allowed_types}, got '{v}'"
            )
        return v

    @field_validator('relevance_score')
    @classmethod
    def validate_relevance_range(cls, v: float) -> float:
        """Validate relevance_score is between 0.0 and 1.0."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"Relevance score must be between 0.0 and 1.0, got {v}"
            )
        return v

"""
Chat response contract for coach chat operations.

This module defines the Pydantic v2 model for structured chat responses
from the AI coach, including the response text, supporting evidence cards,
confidence scoring, and optional follow-up suggestions.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.ai.contracts.evidence_card import EvidenceCard


class ChatResponseContract(BaseModel):
    """
    Output contract for coach chat responses.

    This contract defines the expected structure for AI coach responses
    to athlete queries, including the response text, evidence traceability,
    confidence scoring, and optional follow-up suggestions.

    Requirements: 3.2.3, 3.2.7
    """

    response_text: str = Field(
        ...,
        description="The coach's response to the athlete's query"
    )
    evidence_cards: List[EvidenceCard] = Field(
        default_factory=list,
        description="Supporting data references linking claims to source records"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Hybrid confidence score (0.0-1.0) indicating response reliability"
    )
    follow_up_suggestions: Optional[List[str]] = Field(
        default=None,
        description="Optional follow-up questions or topics (max 3 items)"
    )

    @field_validator('confidence_score')
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Validate confidence_score is between 0.0 and 1.0."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"Confidence score must be between 0.0 and 1.0, got {v}"
            )
        return v

    @field_validator('follow_up_suggestions')
    @classmethod
    def validate_follow_up_count(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate follow_up_suggestions has max 3 items if provided."""
        if v is not None and len(v) > 3:
            raise ValueError(
                f"Follow-up suggestions must have max 3 items, got {len(v)}"
            )
        return v

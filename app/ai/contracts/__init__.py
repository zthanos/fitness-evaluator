"""
Output contracts and data schemas for AI operations.

This module defines Pydantic v2 models for structured input/output validation.
"""

from app.ai.contracts.evaluation_contract import (
    WeeklyEvalContract,
    Recommendation,
)
from app.ai.contracts.evidence_card import EvidenceCard

__all__ = [
    "WeeklyEvalContract",
    "Recommendation",
    "EvidenceCard",
]

"""
Test validators for EvidenceCard model.

Tests the validation logic for source_id, source_type, and relevance_score.
"""

import pytest
from pydantic import ValidationError
from app.ai.contracts.evidence_card import EvidenceCard


def test_valid_evidence_card():
    """Test creating a valid evidence card."""
    card = EvidenceCard(
        claim_text="User completed 5 runs this week",
        source_type="activity",
        source_id=123,
        source_date="2024-01-15",
        relevance_score=0.95
    )
    assert card.source_id == 123
    assert card.source_type == "activity"
    assert card.relevance_score == 0.95


def test_source_id_positive_integer():
    """Test source_id must be a positive integer."""
    # Valid positive integer
    card = EvidenceCard(
        claim_text="Test claim",
        source_type="goal",
        source_id=1,
        source_date="2024-01-15",
        relevance_score=0.8
    )
    assert card.source_id == 1
    
    # Invalid: zero
    with pytest.raises(ValidationError) as exc_info:
        EvidenceCard(
            claim_text="Test claim",
            source_type="goal",
            source_id=0,
            source_date="2024-01-15",
            relevance_score=0.8
        )
    assert "Source ID must be a positive integer" in str(exc_info.value)
    
    # Invalid: negative
    with pytest.raises(ValidationError) as exc_info:
        EvidenceCard(
            claim_text="Test claim",
            source_type="goal",
            source_id=-5,
            source_date="2024-01-15",
            relevance_score=0.8
        )
    assert "Source ID must be a positive integer" in str(exc_info.value)


def test_source_type_enum_validation():
    """Test source_type must be one of the allowed values."""
    # Valid types
    for source_type in ["activity", "goal", "metric", "log"]:
        card = EvidenceCard(
            claim_text="Test claim",
            source_type=source_type,
            source_id=1,
            source_date="2024-01-15",
            relevance_score=0.8
        )
        assert card.source_type == source_type
    
    # Invalid type
    with pytest.raises(ValidationError) as exc_info:
        EvidenceCard(
            claim_text="Test claim",
            source_type="invalid_type",
            source_id=1,
            source_date="2024-01-15",
            relevance_score=0.8
        )
    assert "Source type must be one of" in str(exc_info.value)


def test_relevance_score_range_validation():
    """Test relevance_score must be between 0.0 and 1.0."""
    # Valid scores at boundaries
    card_min = EvidenceCard(
        claim_text="Test claim",
        source_type="metric",
        source_id=1,
        source_date="2024-01-15",
        relevance_score=0.0
    )
    assert card_min.relevance_score == 0.0
    
    card_max = EvidenceCard(
        claim_text="Test claim",
        source_type="metric",
        source_id=1,
        source_date="2024-01-15",
        relevance_score=1.0
    )
    assert card_max.relevance_score == 1.0
    
    # Invalid: below range (Pydantic Field constraints validate first)
    with pytest.raises(ValidationError) as exc_info:
        EvidenceCard(
            claim_text="Test claim",
            source_type="metric",
            source_id=1,
            source_date="2024-01-15",
            relevance_score=-0.1
        )
    # Validation error occurs (either from Field constraint or custom validator)
    assert "relevance_score" in str(exc_info.value)
    
    # Invalid: above range
    with pytest.raises(ValidationError) as exc_info:
        EvidenceCard(
            claim_text="Test claim",
            source_type="metric",
            source_id=1,
            source_date="2024-01-15",
            relevance_score=1.5
        )
    # Validation error occurs (either from Field constraint or custom validator)
    assert "relevance_score" in str(exc_info.value)

"""Tests for token budget limiting in RAGRetriever."""

import pytest
from unittest.mock import Mock
from datetime import datetime

from app.ai.retrieval.rag_retriever import RAGRetriever
from app.ai.retrieval.intent_router import Intent


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock()


@pytest.fixture
def rag_retriever(mock_db):
    """Create RAGRetriever with small token budget for testing."""
    return RAGRetriever(db=mock_db, token_budget_for_retrieval=200)


class TestTokenBudgetLimiting:
    """Test token budget limiting for retrieved records."""
    
    def test_limit_by_token_budget_with_small_budget(self, rag_retriever):
        """Test that results are limited when they exceed token budget."""
        # Create many evidence cards (more than would fit in 200 tokens)
        evidence_cards = [
            {
                "claim_text": f"Run on 2024-03-{10+i:02d} - 5.0 km - 30.0 min - This is a longer description to increase token count",
                "source_type": "activity",
                "source_id": i,
                "source_date": f"2024-03-{10+i:02d}T10:00:00",
                "relevance_score": 1.0
            }
            for i in range(20)
        ]
        
        # Apply token budget limiting
        limited_results = rag_retriever._limit_by_token_budget(evidence_cards)
        
        # Verify results were limited
        assert len(limited_results) < len(evidence_cards)
        assert len(limited_results) > 0  # Should keep at least some results
    
    def test_limit_by_token_budget_with_empty_results(self, rag_retriever):
        """Test that empty results are handled correctly."""
        limited_results = rag_retriever._limit_by_token_budget([])
        assert limited_results == []
    
    def test_limit_by_token_budget_keeps_results_within_budget(self, rag_retriever):
        """Test that limited results fit within token budget."""
        # Create evidence cards
        evidence_cards = [
            {
                "claim_text": f"Activity {i}",
                "source_type": "activity",
                "source_id": i,
                "source_date": f"2024-03-{10+i:02d}T10:00:00",
                "relevance_score": 1.0
            }
            for i in range(10)
        ]
        
        # Apply token budget limiting
        limited_results = rag_retriever._limit_by_token_budget(evidence_cards)
        
        # Verify token count is within budget
        import json
        total_tokens = 0
        for result in limited_results:
            result_str = json.dumps(result)
            result_tokens = len(rag_retriever.encoding.encode(result_str))
            total_tokens += result_tokens
        
        assert total_tokens <= rag_retriever.token_budget_for_retrieval
    
    def test_limit_by_token_budget_with_large_budget(self, mock_db):
        """Test that all results are kept when budget is large enough."""
        # Create retriever with large budget
        large_budget_retriever = RAGRetriever(db=mock_db, token_budget_for_retrieval=10000)
        
        # Create small set of evidence cards
        evidence_cards = [
            {
                "claim_text": f"Activity {i}",
                "source_type": "activity",
                "source_id": i,
                "source_date": f"2024-03-{10+i:02d}T10:00:00",
                "relevance_score": 1.0
            }
            for i in range(5)
        ]
        
        # Apply token budget limiting
        limited_results = large_budget_retriever._limit_by_token_budget(evidence_cards)
        
        # Verify all results were kept
        assert len(limited_results) == len(evidence_cards)


class TestIntegrationWithRetrieve:
    """Test token budget limiting integrated with retrieve method."""
    
    def test_retrieve_applies_token_budget_limiting(self, mock_db):
        """Test that retrieve method applies token budget limiting."""
        # Create retriever with small budget
        retriever = RAGRetriever(db=mock_db, token_budget_for_retrieval=200)
        
        # Create many evidence cards (before token limiting)
        from unittest.mock import patch
        large_evidence_cards = [
            {
                "claim_text": f"Run on 2024-03-{10+i:02d} - 5.0 km - 30.0 min - Additional details to increase token count",
                "source_type": "activity",
                "source_id": i,
                "source_date": f"2024-03-{10+i:02d}T10:00:00",
                "relevance_score": 1.0
            }
            for i in range(20)
        ]
        
        # Mock the generate_evidence_cards to return our large set
        with patch.object(retriever, 'generate_evidence_cards', return_value=large_evidence_cards):
            # Mock the query methods to return empty lists (we're testing token limiting, not querying)
            with patch.object(retriever, '_query_activities', return_value=[]):
                with patch.object(retriever, '_query_metrics', return_value=[]):
                    with patch.object(retriever, '_query_logs', return_value=[]):
                        with patch.object(retriever, '_query_goals', return_value=[]):
                            # Execute retrieval
                            results = retriever.retrieve(
                                query="Show me my activities",
                                athlete_id=1,
                                intent=Intent.RECENT_PERFORMANCE,
                                generate_cards=True
                            )
        
        # Verify results were limited by token budget
        # With a 200 token budget, we should get fewer than 20 results
        assert len(results) < 20
        assert len(results) > 0  # Should keep at least some results

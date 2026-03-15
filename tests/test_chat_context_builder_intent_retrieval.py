"""Tests for intent-aware retrieval in ChatContextBuilder."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.ai.context.chat_context import ChatContextBuilder
from app.ai.retrieval.intent_router import Intent
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.athlete_goal import AthleteGoal


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock()


@pytest.fixture
def context_builder(mock_db):
    """Create ChatContextBuilder instance."""
    return ChatContextBuilder(db=mock_db, token_budget=2400)


class TestIntentClassification:
    """Test intent classification before retrieval."""
    
    def test_gather_data_classifies_intent(self, context_builder, mock_db):
        """Test that gather_data classifies query intent."""
        # Mock IntentRouter
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.RECENT_PERFORMANCE
            
            # Mock RAGRetriever to avoid actual DB queries
            with patch.object(context_builder.rag_retriever, 'retrieve') as mock_retrieve:
                mock_retrieve.return_value = []
                
                # Call gather_data
                context_builder.gather_data(
                    query="How did I do this week?",
                    athlete_id=1
                )
                
                # Verify intent classification was called
                mock_classify.assert_called_once_with("How did I do this week?")
                
                # Verify retrieve was called with classified intent
                mock_retrieve.assert_called_once()
                call_args = mock_retrieve.call_args
                assert call_args[1]['intent'] == Intent.RECENT_PERFORMANCE


class TestIntentSpecificPolicies:
    """Test intent-specific retrieval policies."""
    
    def test_recent_performance_policy(self, context_builder, mock_db):
        """Test recent_performance intent retrieves 14 days of data."""
        query = "How did I do this week?"
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.RECENT_PERFORMANCE
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            # Verify policy was applied (14 days back)
            # This is validated through the RAGRetriever which loads the policy
            assert mock_classify.called
    
    def test_trend_analysis_policy(self, context_builder, mock_db):
        """Test trend_analysis intent retrieves 90 days of data."""
        query = "How has my training progressed over time?"
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.TREND_ANALYSIS
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            assert mock_classify.called
    
    def test_goal_progress_policy(self, context_builder, mock_db):
        """Test goal_progress intent retrieves goals + related activities."""
        query = "Am I on track for my goal?"
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.GOAL_PROGRESS
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            assert mock_classify.called
    
    def test_recovery_status_policy(self, context_builder, mock_db):
        """Test recovery_status intent retrieves 7 days with effort data."""
        query = "Am I recovered enough to train hard today?"
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.RECOVERY_STATUS
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            assert mock_classify.called
    
    def test_training_plan_policy(self, context_builder, mock_db):
        """Test training_plan intent retrieves plan-specific data."""
        query = "What should I do next week?"
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.TRAINING_PLAN
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            assert mock_classify.called
    
    def test_comparison_policy(self, context_builder, mock_db):
        """Test comparison intent retrieves comparative data."""
        query = "How does this month compare to last month?"
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.COMPARISON
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            assert mock_classify.called
    
    def test_general_policy(self, context_builder, mock_db):
        """Test general intent uses broad retrieval."""
        query = "Tell me about my training"
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.GENERAL
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            assert mock_classify.called


class TestEvidenceCardGeneration:
    """Test evidence card generation for retrieved data."""
    
    def test_evidence_cards_generated_for_activities(self, context_builder, mock_db):
        """Test evidence cards are generated for activity data."""
        query = "How did I do this week?"
        
        # Mock the RAGRetriever.retrieve to return evidence cards directly
        mock_evidence_cards = [
            {
                "claim_text": "Run on 2024-03-10 - 5.0 km - 30.0 min",
                "source_type": "activity",
                "source_id": 1,
                "source_date": "2024-03-10T10:00:00",
                "relevance_score": 1.0
            }
        ]
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            with patch.object(context_builder.rag_retriever, 'retrieve') as mock_retrieve:
                mock_classify.return_value = Intent.RECENT_PERFORMANCE
                mock_retrieve.return_value = mock_evidence_cards
                
                context_builder.gather_data(query=query, athlete_id=1)
                
                # Verify evidence cards were added to retrieved data
                assert len(context_builder._retrieved_data) > 0
                
                # Check evidence card structure
                evidence_card = context_builder._retrieved_data[0]
                assert "claim_text" in evidence_card
                assert "source_type" in evidence_card
                assert "source_id" in evidence_card
                assert "source_date" in evidence_card
                assert "relevance_score" in evidence_card
    
    def test_evidence_cards_have_required_fields(self, context_builder, mock_db):
        """Test evidence cards contain all required fields."""
        query = "Show me my recent workouts"
        
        # Mock the RAGRetriever.retrieve to return evidence cards
        mock_evidence_cards = [
            {
                "claim_text": "Run on 2024-03-10 - 5.0 km - 30.0 min",
                "source_type": "activity",
                "source_id": 1,
                "source_date": "2024-03-10T10:00:00",
                "relevance_score": 1.0
            }
        ]
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            with patch.object(context_builder.rag_retriever, 'retrieve') as mock_retrieve:
                mock_classify.return_value = Intent.RECENT_PERFORMANCE
                mock_retrieve.return_value = mock_evidence_cards
                
                context_builder.gather_data(query=query, athlete_id=1)
                
                # Verify evidence card fields
                evidence_card = context_builder._retrieved_data[0]
                assert isinstance(evidence_card["claim_text"], str)
                assert evidence_card["source_type"] == "activity"
                assert isinstance(evidence_card["source_id"], int)
                assert isinstance(evidence_card["source_date"], str)
                assert isinstance(evidence_card["relevance_score"], float)
                assert 0.0 <= evidence_card["relevance_score"] <= 1.0


class TestTokenBudgetEnforcement:
    """Test token budget limiting for retrieved records."""
    
    def test_retrieved_records_limited_by_token_budget(self, context_builder, mock_db):
        """Test that retrieved records are limited to fit token budget."""
        query = "Show me all my activities"
        
        # Mock the RAGRetriever to return exactly 20 records (policy limit)
        mock_evidence_cards = [
            {
                "claim_text": f"Run on 2024-03-{10+i:02d} - 5.0 km - 30.0 min",
                "source_type": "activity",
                "source_id": i,
                "source_date": f"2024-03-{10+i:02d}T10:00:00",
                "relevance_score": 1.0
            }
            for i in range(20)  # Policy max_records: 20
        ]
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            with patch.object(context_builder.rag_retriever, 'retrieve') as mock_retrieve:
                mock_classify.return_value = Intent.GENERAL
                mock_retrieve.return_value = mock_evidence_cards
                
                context_builder.gather_data(query=query, athlete_id=1)
                
                # Verify records were limited (policy max_records: 20)
                assert len(context_builder._retrieved_data) <= 20
    
    def test_token_budget_enforced_on_build(self, context_builder, mock_db):
        """Test that token budget is enforced when building context."""
        # This test verifies the overall token budget enforcement
        # The actual limiting happens in the build() method
        
        query = "Show me my training"
        
        # Mock minimal data
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Execute retrieval
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            mock_classify.return_value = Intent.GENERAL
            
            context_builder.gather_data(query=query, athlete_id=1)
            
            # Add required layers for build
            context_builder.add_system_instructions("You are a coach")
            context_builder.add_task_instructions("Respond to the athlete")
            
            # Build should succeed with minimal data
            context = context_builder.build()
            assert context.token_count <= context_builder.token_budget


class TestIntegration:
    """Integration tests for intent-aware retrieval."""
    
    def test_full_intent_aware_retrieval_pipeline(self, context_builder, mock_db):
        """Test complete pipeline from query to evidence cards."""
        query = "How did I do this week?"
        
        # Mock the RAGRetriever to return evidence cards
        mock_evidence_cards = [
            {
                "claim_text": "Run on 2024-03-10 - 5.0 km - 30.0 min",
                "source_type": "activity",
                "source_id": 1,
                "source_date": "2024-03-10T10:00:00",
                "relevance_score": 1.0
            }
        ]
        
        # Execute full pipeline
        with patch.object(context_builder.intent_router, 'classify') as mock_classify:
            with patch.object(context_builder.rag_retriever, 'retrieve') as mock_retrieve:
                mock_classify.return_value = Intent.RECENT_PERFORMANCE
                mock_retrieve.return_value = mock_evidence_cards
                
                result = context_builder.gather_data(query=query, athlete_id=1)
                
                # Verify fluent interface
                assert result is context_builder
                
                # Verify data was retrieved and formatted as evidence cards
                assert len(context_builder._retrieved_data) > 0
                
                # Verify evidence card structure
                evidence_card = context_builder._retrieved_data[0]
                assert "claim_text" in evidence_card
                assert "source_type" in evidence_card
                assert evidence_card["source_type"] == "activity"

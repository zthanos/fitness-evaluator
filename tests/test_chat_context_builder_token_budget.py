"""
Tests for ChatContextBuilder token budget enforcement during history selection.

Tests cover:
- Token budget enforcement with different policies
- Budget exceeded scenarios
- Token counting accuracy
- Integration with context building
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.ai.context.chat_context import ChatContextBuilder
from app.ai.context.builder import ContextBudgetExceeded
from app.ai.retrieval.intent_router import Intent


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def large_conversation():
    """Large conversation that would exceed token budget."""
    conversation = []
    for i in range(30):
        conversation.append({
            "role": "user",
            "content": f"This is a long user message number {i} with lots of content to increase token count. " * 10
        })
        conversation.append({
            "role": "assistant",
            "content": f"This is a long assistant response number {i} with detailed information and explanations. " * 10
        })
    return conversation


class TestTokenBudgetEnforcement:
    """Test token budget enforcement during history selection."""
    
    def test_token_aware_policy_respects_budget(self, mock_db, large_conversation):
        """Test that token_aware policy respects token budget."""
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=2400,
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=large_conversation,
            current_query="Continue"
        )
        
        # Calculate tokens in selected history
        total_tokens = 0
        for message in selected:
            total_tokens += len(builder.encoding.encode(message["content"])) + 4
        
        # Should be within available budget (2400 - 1350 reserved = 1050)
        assert total_tokens <= 1050
    
    def test_last_n_turns_may_exceed_budget(self, mock_db, large_conversation):
        """Test that last_n_turns policy may exceed budget (no enforcement)."""
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=2400,
            history_selection_policy="last_n_turns",
            last_n_turns=10  # Request 10 turns
        )
        
        selected = builder.select_relevant_history(
            conversation_history=large_conversation,
            current_query="Continue"
        )
        
        # Should select 10 turns = 20 messages regardless of budget
        assert len(selected) == 20
    
    def test_small_budget_limits_history(self, mock_db):
        """Test that small token budget limits history selection."""
        # Create conversation with longer messages to exceed small budget
        conversation = []
        for i in range(6):
            conversation.append({
                "role": "user",
                "content": f"This is a longer message number {i} with more content. " * 3
            })
            conversation.append({
                "role": "assistant",
                "content": f"This is a longer reply number {i} with detailed information. " * 3
            })
        
        # Very small budget
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=1400,  # Minimal budget
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Should select fewer messages due to small budget
        # Available: 1400 - 1350 = 50 tokens
        assert len(selected) < len(conversation)  # Should trim some messages
    
    def test_large_budget_allows_more_history(self, mock_db):
        """Test that large token budget allows more history."""
        conversation = []
        for i in range(20):
            conversation.append({"role": "user", "content": f"Message {i}"})
            conversation.append({"role": "assistant", "content": f"Reply {i}"})
        
        # Large budget
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=5000,  # Large budget
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Should select many messages with large budget
        # Available: 5000 - 1350 = 3650 tokens
        assert len(selected) > 10


class TestTokenCountingAccuracy:
    """Test token counting accuracy."""
    
    def test_token_counting_includes_message_overhead(self, mock_db):
        """Test that token counting includes message formatting overhead."""
        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Calculate expected tokens
        expected_tokens = 0
        for message in selected:
            # Content tokens + 4 for formatting
            expected_tokens += len(builder.encoding.encode(message["content"])) + 4
        
        # Verify calculation is consistent
        assert expected_tokens > 0
    
    def test_empty_message_token_count(self, mock_db):
        """Test token counting with empty messages."""
        conversation = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Should handle empty messages
        assert len(selected) == 2


class TestContextBuildingIntegration:
    """Test integration of token budget with context building."""
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_build_enforces_total_budget(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that build() enforces total token budget with automatic trimming."""
        # Mock intent router
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        # Mock RAG retriever to return large data
        mock_retriever = Mock()
        large_data = [{"content": "Large data " * 100} for _ in range(50)]
        mock_retriever.retrieve.return_value = large_data
        mock_retriever_class.return_value = mock_retriever
        
        # Create large conversation
        large_conversation = []
        for i in range(20):
            large_conversation.append({
                "role": "user",
                "content": f"Long message {i} " * 50
            })
            large_conversation.append({
                "role": "assistant",
                "content": f"Long reply {i} " * 50
            })
        
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=2400,
            history_selection_policy="last_n_turns",
            last_n_turns=10
        )
        
        # Gather data with large history
        builder.gather_data(
            query="Test query",
            athlete_id=1,
            conversation_history=large_conversation
        )
        
        # Add required layers
        builder.add_system_instructions("System instructions")
        builder.add_task_instructions("Task instructions")
        
        # Build should automatically trim to fit budget
        context = builder.build()
        
        # Should be within budget after automatic trimming
        assert context.token_count <= 2400
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_token_aware_policy_prevents_budget_exceeded(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that token_aware policy helps prevent budget exceeded."""
        # Mock intent router
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        # Mock RAG retriever with moderate data
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = [
            {"content": "Data item " * 10} for _ in range(10)
        ]
        mock_retriever_class.return_value = mock_retriever
        
        # Create moderate conversation
        conversation = []
        for i in range(10):
            conversation.append({"role": "user", "content": f"Message {i}"})
            conversation.append({"role": "assistant", "content": f"Reply {i}"})
        
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=2400,
            history_selection_policy="token_aware"  # Use token-aware
        )
        
        # Gather data
        builder.gather_data(
            query="Test query",
            athlete_id=1,
            conversation_history=conversation
        )
        
        # Add required layers
        builder.add_system_instructions("System instructions for coaching")
        builder.add_task_instructions("Task instructions for response")
        
        # Build should succeed (token_aware limits history)
        context = builder.build()
        assert context.token_count <= 2400


class TestEdgeCases:
    """Test edge cases for token budget enforcement."""
    
    def test_zero_budget_available(self, mock_db):
        """Test behavior when no budget available for history."""
        conversation = [
            {"role": "user", "content": "Message"},
            {"role": "assistant", "content": "Reply"},
        ]
        
        # Budget exactly matches reserved tokens
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=1350,  # Exactly reserved amount
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Should return empty or minimal history
        assert len(selected) == 0
    
    def test_negative_budget_available(self, mock_db):
        """Test behavior when budget is less than reserved."""
        conversation = [
            {"role": "user", "content": "Message"},
            {"role": "assistant", "content": "Reply"},
        ]
        
        # Budget less than reserved
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=1000,  # Less than reserved 1350
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Should return empty history
        assert len(selected) == 0
    
    def test_single_message_exceeds_budget(self, mock_db):
        """Test when single message exceeds available budget."""
        conversation = [
            {"role": "user", "content": "Short"},
            {"role": "assistant", "content": "Very long message " * 200},  # Very long
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=1400,  # Small budget
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Should handle gracefully, possibly selecting only short message
        assert len(selected) <= 2


class TestPolicyComparison:
    """Compare token usage across different policies."""
    
    def test_token_aware_uses_fewer_tokens_than_last_n(self, mock_db, large_conversation):
        """Test that token_aware uses fewer tokens than last_n_turns."""
        # Token-aware policy
        builder_token_aware = ChatContextBuilder(
            db=mock_db,
            token_budget=2400,
            history_selection_policy="token_aware"
        )
        
        selected_token_aware = builder_token_aware.select_relevant_history(
            conversation_history=large_conversation,
            current_query="Continue"
        )
        
        # Last N turns policy
        builder_last_n = ChatContextBuilder(
            db=mock_db,
            token_budget=2400,
            history_selection_policy="last_n_turns",
            last_n_turns=10
        )
        
        selected_last_n = builder_last_n.select_relevant_history(
            conversation_history=large_conversation,
            current_query="Continue"
        )
        
        # Token-aware should select fewer messages
        assert len(selected_token_aware) < len(selected_last_n)
    
    def test_all_policies_handle_small_conversations(self, mock_db):
        """Test that all policies handle small conversations similarly."""
        small_conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        
        policies = ["last_n_turns", "token_aware"]
        results = []
        
        for policy in policies:
            builder = ChatContextBuilder(
                db=mock_db,
                history_selection_policy=policy
            )
            
            selected = builder.select_relevant_history(
                conversation_history=small_conversation,
                current_query="Continue"
            )
            results.append(len(selected))
        
        # All policies should return similar results for small conversations
        assert all(r <= 4 for r in results)  # At most 2 turns
        
        # For relevance policy, need to patch RAGEngine
        with patch('app.services.rag_engine.RAGEngine'):
            builder_relevance = ChatContextBuilder(
                db=mock_db,
                history_selection_policy="relevance"
            )
            selected_relevance = builder_relevance.select_relevant_history(
                conversation_history=small_conversation,
                current_query="Continue"
            )
            assert len(selected_relevance) <= 4

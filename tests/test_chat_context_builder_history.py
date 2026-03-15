"""
Tests for ChatContextBuilder dynamic history selection.

Tests cover:
- Last N turns policy
- Relevance-based selection using embeddings
- Token-aware trimming
- Configuration options
- Various conversation lengths
- Token budget enforcement
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from sqlalchemy.orm import Session

from app.ai.context.chat_context import ChatContextBuilder
from app.ai.retrieval.intent_router import Intent


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_rag_engine():
    """Mock RAG engine for embedding generation."""
    mock_engine = MagicMock()
    
    def generate_embedding(text: str):
        """Generate deterministic embedding based on text hash."""
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(768).astype('float32')
        embedding = embedding / np.linalg.norm(embedding)
        return embedding
    
    mock_engine.generate_embedding = generate_embedding
    return mock_engine


@pytest.fixture
def sample_conversation():
    """Sample conversation history with 10 turns (20 messages)."""
    return [
        {"role": "user", "content": "What's my recent running performance?"},
        {"role": "assistant", "content": "You've been running consistently. Last week you ran 25km total."},
        {"role": "user", "content": "How should I train for a marathon?"},
        {"role": "assistant", "content": "For marathon training, focus on building base mileage gradually."},
        {"role": "user", "content": "What about nutrition?"},
        {"role": "assistant", "content": "Proper nutrition is crucial. Focus on carbs before long runs."},
        {"role": "user", "content": "Tell me about recovery strategies"},
        {"role": "assistant", "content": "Recovery includes rest days, sleep, and proper hydration."},
        {"role": "user", "content": "What's my current fitness level?"},
        {"role": "assistant", "content": "Based on your recent activities, you're at intermediate level."},
        {"role": "user", "content": "Should I do speed work?"},
        {"role": "assistant", "content": "Yes, incorporate interval training once per week."},
        {"role": "user", "content": "How often should I run?"},
        {"role": "assistant", "content": "Aim for 4-5 runs per week with rest days in between."},
        {"role": "user", "content": "What about cross-training?"},
        {"role": "assistant", "content": "Cross-training like cycling or swimming helps prevent injury."},
        {"role": "user", "content": "Can you review my last run?"},
        {"role": "assistant", "content": "Your last run showed good pace consistency and heart rate control."},
        {"role": "user", "content": "What's my weekly mileage target?"},
        {"role": "assistant", "content": "Aim for 40-50km per week based on your current fitness."},
    ]


class TestLastNTurnsPolicy:
    """Test last_n_turns history selection policy."""
    
    def test_select_last_5_turns_default(self, mock_db, sample_conversation):
        """Test default last_n_turns=5 selects last 10 messages."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=5
        )
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="What should I focus on?"
        )
        
        # Should select last 5 turns = 10 messages
        assert len(selected) == 10
        assert selected[0]["content"] == "Should I do speed work?"
        assert selected[-1]["content"] == "Aim for 40-50km per week based on your current fitness."
    
    def test_select_last_3_turns(self, mock_db, sample_conversation):
        """Test last_n_turns=3 selects last 6 messages."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=3
        )
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="What should I focus on?"
        )
        
        # Should select last 3 turns = 6 messages
        assert len(selected) == 6
        assert selected[0]["content"] == "What about cross-training?"
    
    def test_short_conversation_returns_all(self, mock_db):
        """Test that short conversations return all messages."""
        short_conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=5
        )
        
        selected = builder.select_relevant_history(
            conversation_history=short_conversation,
            current_query="How are you?"
        )
        
        # Should return all messages since conversation is shorter than 5 turns
        assert len(selected) == 2
        assert selected == short_conversation
    
    def test_empty_conversation_returns_empty(self, mock_db):
        """Test that empty conversation returns empty list."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=[],
            current_query="Hello"
        )
        
        assert selected == []


class TestRelevanceBasedSelection:
    """Test relevance-based history selection using embeddings."""
    
    @patch('app.services.rag_engine.RAGEngine')
    def test_relevance_selection_includes_recent_turn(
        self,
        mock_rag_engine_class,
        mock_db,
        sample_conversation,
        mock_rag_engine
    ):
        """Test that relevance selection always includes most recent turn."""
        mock_rag_engine_class.return_value = mock_rag_engine
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="relevance",
            relevance_threshold=0.7
        )
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="What's my weekly mileage?"
        )
        
        # Should always include most recent turn (last 2 messages)
        assert len(selected) >= 2
        assert selected[-2]["content"] == "What's my weekly mileage target?"
        assert selected[-1]["content"] == "Aim for 40-50km per week based on your current fitness."
    
    @patch('app.services.rag_engine.RAGEngine')
    def test_relevance_selection_filters_by_threshold(
        self,
        mock_rag_engine_class,
        mock_db,
        mock_rag_engine
    ):
        """Test that relevance selection filters by similarity threshold."""
        mock_rag_engine_class.return_value = mock_rag_engine
        
        conversation = [
            {"role": "user", "content": "What's my running pace?"},
            {"role": "assistant", "content": "Your average pace is 5:30/km."},
            {"role": "user", "content": "Tell me about nutrition"},
            {"role": "assistant", "content": "Focus on balanced meals with carbs and protein."},
            {"role": "user", "content": "How fast should I run?"},
            {"role": "assistant", "content": "Maintain a comfortable pace for most runs."},
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="relevance",
            relevance_threshold=0.8,  # High threshold
            last_n_turns=5
        )
        
        # Query about running pace should match first turn
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="What pace should I target?"
        )
        
        # Should include recent turn + relevant past turns
        assert len(selected) >= 2
        assert selected[-2]["content"] == "How fast should I run?"
    
    @patch('app.services.rag_engine.RAGEngine')
    def test_relevance_fallback_on_error(
        self,
        mock_rag_engine_class,
        mock_db,
        sample_conversation
    ):
        """Test that relevance selection falls back to last_n_turns on error."""
        # Mock RAG engine to raise exception
        mock_rag_engine_class.side_effect = Exception("Embedding error")
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="relevance",
            last_n_turns=3
        )
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="What should I do?"
        )
        
        # Should fallback to last_n_turns (3 turns = 6 messages)
        assert len(selected) == 6
    
    @patch('app.services.rag_engine.RAGEngine')
    def test_short_conversation_returns_all_relevance(
        self,
        mock_rag_engine_class,
        mock_db,
        mock_rag_engine
    ):
        """Test that short conversations return all messages in relevance mode."""
        mock_rag_engine_class.return_value = mock_rag_engine
        
        short_conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm good!"},
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="relevance"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=short_conversation,
            current_query="What's up?"
        )
        
        # Should return all messages (2 turns or less)
        assert len(selected) == 4


class TestTokenAwareSelection:
    """Test token-aware history selection."""
    
    def test_token_aware_respects_budget(self, mock_db):
        """Test that token-aware selection respects token budget."""
        # Create conversation with longer messages to exceed budget
        conversation = []
        for i in range(10):
            conversation.append({
                "role": "user",
                "content": f"This is a longer user message number {i} with more content to increase token count. " * 5
            })
            conversation.append({
                "role": "assistant",
                "content": f"This is a longer assistant response number {i} with detailed information. " * 5
            })
        
        # Use small token budget to force trimming
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=1500,  # Small budget
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="What's next?"
        )
        
        # Should select fewer messages due to token budget
        assert len(selected) < len(conversation)
        # Should include most recent messages
        assert "number 9" in selected[-1]["content"]
    
    def test_token_aware_starts_from_recent(self, mock_db):
        """Test that token-aware selection prioritizes recent messages."""
        conversation = [
            {"role": "user", "content": "Old message 1"},
            {"role": "assistant", "content": "Old reply 1"},
            {"role": "user", "content": "Old message 2"},
            {"role": "assistant", "content": "Old reply 2"},
            {"role": "user", "content": "Recent message"},
            {"role": "assistant", "content": "Recent reply"},
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            token_budget=1600,
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="Continue"
        )
        
        # Should include most recent messages
        assert "Recent reply" in selected[-1]["content"]
    
    def test_token_aware_empty_conversation(self, mock_db):
        """Test token-aware selection with empty conversation."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="token_aware"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=[],
            current_query="Hello"
        )
        
        assert selected == []


class TestPolicyConfiguration:
    """Test history selection policy configuration."""
    
    def test_default_policy_is_last_n_turns(self, mock_db, sample_conversation):
        """Test that default policy is last_n_turns."""
        builder = ChatContextBuilder(db=mock_db)
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="What next?"
        )
        
        # Default should be last_n_turns with n=5 (10 messages)
        assert len(selected) == 10
    
    def test_invalid_policy_falls_back_to_default(self, mock_db, sample_conversation):
        """Test that invalid policy falls back to last_n_turns."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="invalid_policy"
        )
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="What next?"
        )
        
        # Should fallback to last_n_turns
        assert len(selected) == 10
    
    def test_custom_last_n_turns_value(self, mock_db, sample_conversation):
        """Test custom last_n_turns configuration."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=2
        )
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="What next?"
        )
        
        # Should select 2 turns = 4 messages
        assert len(selected) == 4
    
    def test_custom_relevance_threshold(self, mock_db):
        """Test custom relevance threshold configuration."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="relevance",
            relevance_threshold=0.9  # Very high threshold
        )
        
        # Verify configuration is stored
        assert builder.relevance_threshold == 0.9


class TestGatherDataIntegration:
    """Test integration of history selection with gather_data."""
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_gather_data_applies_history_selection(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db,
        sample_conversation
    ):
        """Test that gather_data applies history selection."""
        # Mock intent router
        mock_router = Mock()
        mock_router.classify.return_value = Intent.RECENT_PERFORMANCE
        mock_router_class.return_value = mock_router
        
        # Mock RAG retriever
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=3
        )
        
        builder.gather_data(
            query="What's my progress?",
            athlete_id=1,
            conversation_history=sample_conversation
        )
        
        # Verify history was selected (3 turns = 6 messages)
        assert len(builder._conversation_history) == 6
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_gather_data_without_history(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test gather_data without conversation history."""
        # Mock intent router
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        # Mock RAG retriever
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        builder = ChatContextBuilder(db=mock_db)
        
        builder.gather_data(
            query="Hello",
            athlete_id=1,
            conversation_history=None
        )
        
        # Should have empty history
        assert builder._conversation_history == []


class TestVariousConversationLengths:
    """Test history selection with various conversation lengths."""
    
    def test_very_short_conversation_1_turn(self, mock_db):
        """Test with 1 turn (2 messages)."""
        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=5
        )
        
        selected = builder.select_relevant_history(
            conversation_history=conversation,
            current_query="How are you?"
        )
        
        assert len(selected) == 2
        assert selected == conversation
    
    def test_medium_conversation_10_turns(self, mock_db, sample_conversation):
        """Test with 10 turns (20 messages)."""
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=5
        )
        
        selected = builder.select_relevant_history(
            conversation_history=sample_conversation,
            current_query="Continue"
        )
        
        # Should select 5 turns = 10 messages
        assert len(selected) == 10
    
    def test_very_long_conversation_50_turns(self, mock_db):
        """Test with 50 turns (100 messages)."""
        # Generate long conversation
        long_conversation = []
        for i in range(50):
            long_conversation.append({"role": "user", "content": f"User message {i}"})
            long_conversation.append({"role": "assistant", "content": f"Assistant reply {i}"})
        
        builder = ChatContextBuilder(
            db=mock_db,
            history_selection_policy="last_n_turns",
            last_n_turns=5
        )
        
        selected = builder.select_relevant_history(
            conversation_history=long_conversation,
            current_query="Continue"
        )
        
        # Should select only last 5 turns = 10 messages
        assert len(selected) == 10
        assert selected[0]["content"] == "User message 45"
        assert selected[-1]["content"] == "Assistant reply 49"

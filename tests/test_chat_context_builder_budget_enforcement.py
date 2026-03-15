"""
Tests for ChatContextBuilder token budget enforcement with automatic trimming.

Tests cover:
- Layer-by-layer token tracking
- Automatic trimming of history when budget exceeded
- Automatic trimming of retrieved data when budget exceeded
- Protection of system/task instructions and athlete summary
- Budget enforcement with various context sizes
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


class TestLayerTokenTracking:
    """Test layer-by-layer token tracking."""
    
    def test_track_system_instructions_tokens(self, mock_db):
        """Test that system instructions tokens are tracked."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        instructions = "You are a fitness coach."
        builder.add_system_instructions(instructions)
        
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["system_instructions"] > 0
        assert layer_tokens["system_instructions"] == builder._count_layer_tokens(instructions)
    
    def test_track_task_instructions_tokens(self, mock_db):
        """Test that task instructions tokens are tracked."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        instructions = "Respond to the athlete's query."
        builder.add_task_instructions(instructions)
        
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["task_instructions"] > 0
        assert layer_tokens["task_instructions"] == builder._count_layer_tokens(instructions)
    
    def test_track_domain_knowledge_tokens(self, mock_db):
        """Test that domain knowledge tokens are tracked."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        knowledge = {"training_zones": ["Z1", "Z2", "Z3"], "effort_levels": ["easy", "moderate", "hard"]}
        builder.add_domain_knowledge(knowledge)
        
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["domain_knowledge"] > 0
    
    def test_track_athlete_summary_tokens(self, mock_db):
        """Test that athlete summary tokens are tracked."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        summary = "Athlete runs 4x per week, prefers morning workouts."
        builder.add_athlete_summary(summary)
        
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["athlete_summary"] > 0
        assert layer_tokens["athlete_summary"] == builder._count_layer_tokens(summary)
    
    def test_track_retrieved_data_tokens(self, mock_db):
        """Test that retrieved data tokens are tracked."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        data = [
            {"activity": "Run", "distance": 5.0},
            {"activity": "Bike", "distance": 20.0}
        ]
        builder.add_retrieved_data(data)
        
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["retrieved_data"] > 0
    
    def test_track_conversation_history_tokens(self, mock_db):
        """Test that conversation history tokens are tracked."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        history = [
            {"role": "user", "content": "How am I doing?"},
            {"role": "assistant", "content": "You're making great progress!"}
        ]
        builder.add_conversation_history(history)
        
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["conversation_history"] > 0
    
    def test_get_total_tokens(self, mock_db):
        """Test that total tokens are calculated correctly."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        builder.add_system_instructions("System")
        builder.add_task_instructions("Task")
        builder.add_domain_knowledge({"key": "value"})
        
        total = builder.get_total_tokens()
        layer_tokens = builder.get_layer_tokens()
        
        assert total == sum(layer_tokens.values())
        assert total > 0
    
    def test_get_available_tokens(self, mock_db):
        """Test that available tokens are calculated correctly."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        builder.add_system_instructions("System instructions")
        
        available = builder.get_available_tokens()
        used = builder.get_total_tokens()
        
        assert available == 2400 - used
        assert available > 0


class TestAutomaticHistoryTrimming:
    """Test automatic trimming of conversation history."""
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_trim_history_when_budget_exceeded(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that history is trimmed when budget is exceeded."""
        # Mock dependencies
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        # Create large conversation
        large_history = []
        for i in range(20):
            large_history.append({"role": "user", "content": f"Message {i} " * 50})
            large_history.append({"role": "assistant", "content": f"Reply {i} " * 50})
        
        original_length = len(large_history)
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        # Add layers
        builder.add_system_instructions("System instructions")
        builder.add_task_instructions("Task instructions")
        builder.add_conversation_history(large_history)
        
        # Build should trim history automatically
        context = builder.build()
        
        # Should have fewer messages than original
        assert len(builder._conversation_history) < original_length
        # Should keep at least most recent turn (2 messages)
        assert len(builder._conversation_history) >= 2
        # Should be within budget
        assert context.token_count <= 2400
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_preserve_recent_turn_when_trimming(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that most recent turn is preserved when trimming."""
        # Mock dependencies
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        # Create conversation with identifiable messages
        history = []
        for i in range(15):
            history.append({"role": "user", "content": f"User message {i} " * 40})
            history.append({"role": "assistant", "content": f"Assistant reply {i} " * 40})
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        builder.add_system_instructions("System")
        builder.add_task_instructions("Task")
        builder.add_conversation_history(history)
        
        context = builder.build()
        
        # Most recent messages should be preserved
        assert "User message 14" in builder._conversation_history[-2]["content"]
        assert "Assistant reply 14" in builder._conversation_history[-1]["content"]
    
    def test_no_trimming_when_within_budget(self, mock_db):
        """Test that history is not trimmed when within budget."""
        small_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_conversation_history(small_history)
        
        original_length = len(builder._conversation_history)
        builder._trim_history_to_budget()
        
        # Should not trim when within budget
        assert len(builder._conversation_history) == original_length


class TestAutomaticDataTrimming:
    """Test automatic trimming of retrieved data."""
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_trim_retrieved_data_when_budget_exceeded(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that retrieved data is trimmed when budget is exceeded."""
        # Mock dependencies
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        # Create large retrieved data
        large_data = []
        for i in range(50):
            large_data.append({
                "activity": f"Activity {i}",
                "details": "Long details " * 30
            })
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = large_data
        mock_retriever_class.return_value = mock_retriever
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        # Add layers
        builder.add_system_instructions("System instructions")
        builder.add_task_instructions("Task instructions")
        builder.add_retrieved_data(large_data)
        
        # Build should trim data automatically
        context = builder.build()
        
        # Should have fewer items than original
        assert len(builder._retrieved_data) < len(large_data)
        # Should keep at least 1 item
        assert len(builder._retrieved_data) >= 1
        # Should be within budget
        assert context.token_count <= 2400
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_trim_lowest_relevance_first(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that lowest relevance items are trimmed first."""
        # Mock dependencies
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        # Create data with identifiable items (highest relevance first)
        data = []
        for i in range(30):
            data.append({
                "id": i,
                "relevance": 30 - i,  # Decreasing relevance
                "content": "Content " * 100  # Larger content to trigger trimming
            })
        
        original_data_length = len(data)
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = data
        mock_retriever_class.return_value = mock_retriever
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        builder.add_system_instructions("System")
        builder.add_task_instructions("Task")
        builder.add_retrieved_data(data)
        
        context = builder.build()
        
        # First items (highest relevance) should be preserved
        assert builder._retrieved_data[0]["id"] == 0
        # Should have trimmed some items
        assert len(builder._retrieved_data) < original_data_length


class TestProtectedLayers:
    """Test that certain layers are never trimmed."""
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_never_trim_system_instructions(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that system instructions are never trimmed."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        system_instructions = "You are a fitness coach with expertise."
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_system_instructions(system_instructions)
        builder.add_task_instructions("Task")
        
        # Add large history to trigger trimming
        large_history = [{"role": "user", "content": "Message " * 100}] * 20
        builder.add_conversation_history(large_history)
        
        context = builder.build()
        
        # System instructions should be unchanged
        assert builder._system_instructions == system_instructions
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_never_trim_task_instructions(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that task instructions are never trimmed."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        task_instructions = "Respond to the athlete's query with evidence."
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_system_instructions("System")
        builder.add_task_instructions(task_instructions)
        
        # Add large history
        large_history = [{"role": "user", "content": "Message " * 100}] * 20
        builder.add_conversation_history(large_history)
        
        context = builder.build()
        
        # Task instructions should be unchanged
        assert builder._task_instructions == task_instructions
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_never_trim_athlete_summary(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that athlete summary is never trimmed."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        athlete_summary = "Athlete runs 4x per week, prefers morning workouts."
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_system_instructions("System")
        builder.add_task_instructions("Task")
        builder.add_athlete_summary(athlete_summary)
        
        # Add large history
        large_history = [{"role": "user", "content": "Message " * 100}] * 20
        builder.add_conversation_history(large_history)
        
        context = builder.build()
        
        # Athlete summary should be in domain knowledge
        assert "athlete_summary" in builder._domain_knowledge
        assert builder._domain_knowledge["athlete_summary"] == athlete_summary


class TestBudgetEnforcementEdgeCases:
    """Test edge cases for budget enforcement."""
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_raise_exception_when_protected_layers_exceed_budget(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that exception is raised when protected layers alone exceed budget."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        # Create very large protected content
        large_system = "System instructions " * 500
        large_task = "Task instructions " * 500
        
        builder = ChatContextBuilder(db=mock_db, token_budget=500)  # Small budget
        builder.add_system_instructions(large_system)
        builder.add_task_instructions(large_task)
        
        # Should raise exception because protected layers exceed budget
        with pytest.raises(ContextBudgetExceeded) as exc_info:
            builder.build()
        
        assert exc_info.value.actual > exc_info.value.budget
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_successful_build_after_trimming(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test that build succeeds after automatic trimming."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = []
        mock_retriever_class.return_value = mock_retriever
        
        # Create moderate content
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"Message {i} " * 30})
            history.append({"role": "assistant", "content": f"Reply {i} " * 30})
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_system_instructions("System instructions")
        builder.add_task_instructions("Task instructions")
        builder.add_conversation_history(history)
        
        # Should succeed after trimming
        context = builder.build()
        assert context.token_count <= 2400
    
    def test_empty_layers_handled_correctly(self, mock_db):
        """Test that empty layers are handled correctly."""
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        
        # Add empty layers
        builder.add_conversation_history([])
        builder.add_retrieved_data([])
        
        layer_tokens = builder.get_layer_tokens()
        assert layer_tokens["conversation_history"] == 0
        assert layer_tokens["retrieved_data"] == 0


class TestVariousContextSizes:
    """Test budget enforcement with various context sizes."""
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_small_context_within_budget(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test small context that fits within budget."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = [{"activity": "Run"}]
        mock_retriever_class.return_value = mock_retriever
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_system_instructions("System")
        builder.add_task_instructions("Task")
        builder.add_conversation_history([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ])
        
        context = builder.build()
        assert context.token_count <= 2400
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_medium_context_with_trimming(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test medium context that requires some trimming."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        data = [{"activity": f"Activity {i}", "details": "Details " * 20} for i in range(20)]
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = data
        mock_retriever_class.return_value = mock_retriever
        
        history = []
        for i in range(8):
            history.append({"role": "user", "content": f"Message {i} " * 15})
            history.append({"role": "assistant", "content": f"Reply {i} " * 15})
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_system_instructions("System instructions")
        builder.add_task_instructions("Task instructions")
        builder.add_conversation_history(history)
        builder.add_retrieved_data(data)
        
        context = builder.build()
        assert context.token_count <= 2400
    
    @patch('app.ai.context.chat_context.IntentRouter')
    @patch('app.ai.context.chat_context.RAGRetriever')
    def test_large_context_with_aggressive_trimming(
        self,
        mock_retriever_class,
        mock_router_class,
        mock_db
    ):
        """Test large context that requires aggressive trimming."""
        mock_router = Mock()
        mock_router.classify.return_value = Intent.GENERAL
        mock_router_class.return_value = mock_router
        
        # Large data
        data = [{"content": "Large content " * 50} for _ in range(40)]
        mock_retriever = Mock()
        mock_retriever.retrieve.return_value = data
        mock_retriever_class.return_value = mock_retriever
        
        # Large history
        history = []
        for i in range(25):
            history.append({"role": "user", "content": f"Long message {i} " * 40})
            history.append({"role": "assistant", "content": f"Long reply {i} " * 40})
        
        original_history_length = len(history)
        original_data_length = len(data)
        
        builder = ChatContextBuilder(db=mock_db, token_budget=2400)
        builder.add_system_instructions("System instructions")
        builder.add_task_instructions("Task instructions")
        builder.add_conversation_history(history)
        builder.add_retrieved_data(data)
        
        context = builder.build()
        
        # Should trim aggressively but stay within budget
        assert context.token_count <= 2400
        # Should have trimmed both history and data
        assert len(builder._conversation_history) < original_history_length
        assert len(builder._retrieved_data) < original_data_length

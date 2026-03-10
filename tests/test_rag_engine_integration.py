"""Integration tests for RAG Engine with two-layer context retrieval

Tests the complete flow of:
1. Active session buffer management
2. Vector store persistence
3. Context retrieval combining both layers
4. Session deletion

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 17.2, 20.1
"""
import pytest
import os
import tempfile
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.models.base import Base
from app.models.chat_message import ChatMessage
from app.services.rag_engine import RAGEngine
from app.services.session_buffer import SessionBuffer


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def temp_index_path():
    """Create a temporary path for FAISS index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test_index.bin")


@pytest.fixture
def mock_embedding():
    """Mock embedding generation."""
    import numpy as np
    def _generate_embedding(text: str):
        # Generate a deterministic embedding based on text hash
        import numpy as np
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(768).astype('float32')
        # L2-normalize
        embedding = embedding / np.linalg.norm(embedding)
        return embedding
    return _generate_embedding


class TestTwoLayerContextRetrieval:
    """Test complete two-layer context retrieval flow."""
    
    def test_complete_chat_flow(self, db_session, temp_index_path, mock_embedding):
        """Test complete chat flow with both layers."""
        with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
            # Initialize components
            rag_engine = RAGEngine(db_session, temp_index_path)
            session_buffer = SessionBuffer()
            
            # Simulate first chat session (session 100)
            session_100_messages = [
                ChatMessage(id=1, session_id=100, role='user', content='I want to train for a marathon', created_at=datetime.now()),
                ChatMessage(id=2, session_id=100, role='assistant', content='Great! Let me help you create a training plan', created_at=datetime.now()),
                ChatMessage(id=3, session_id=100, role='user', content='I can run 3 times per week', created_at=datetime.now()),
            ]
            
            # Add to active buffer
            for msg in session_100_messages:
                session_buffer.add_message(100, msg)
            
            # Retrieve context (should only have active buffer)
            context = rag_engine.retrieve_context(
                query="What should my training plan look like?",
                user_id=1,
                active_session_messages=session_buffer.get_messages(100),
                top_k=5
            )
            
            assert "=== Current Session ===" in context
            assert "marathon" in context.lower()
            
            # End session - persist to vector store
            rag_engine.persist_session(
                user_id=1,
                session_id=100,
                messages=session_100_messages,
                eval_score=8.5
            )
            
            # Clear active buffer
            session_buffer.clear_session(100)
            
            # Simulate second chat session (session 200)
            session_200_messages = [
                ChatMessage(id=4, session_id=200, role='user', content='How is my training going?', created_at=datetime.now()),
            ]
            
            for msg in session_200_messages:
                session_buffer.add_message(200, msg)
            
            # Retrieve context (should have both layers now)
            context = rag_engine.retrieve_context(
                query="Tell me about my marathon training",
                user_id=1,
                active_session_messages=session_buffer.get_messages(200),
                top_k=5
            )
            
            # Should have current session
            assert "=== Current Session ===" in context
            assert "How is my training going?" in context
            
            # Should have historical context from session 100
            assert "=== Relevant Past Conversations ===" in context
            # At least one message from session 100 should be retrieved
            assert any(phrase in context for phrase in ["marathon", "training plan", "3 times per week"])
    
    def test_user_isolation(self, db_session, temp_index_path, mock_embedding):
        """Test that users cannot access each other's context."""
        with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
            rag_engine = RAGEngine(db_session, temp_index_path)
            
            # User 1 session
            user1_messages = [
                ChatMessage(id=1, session_id=100, role='user', content='User 1 secret training plan', created_at=datetime.now()),
            ]
            rag_engine.persist_session(user_id=1, session_id=100, messages=user1_messages, eval_score=8.0)
            
            # User 2 session
            user2_messages = [
                ChatMessage(id=2, session_id=200, role='user', content='User 2 different training plan', created_at=datetime.now()),
            ]
            rag_engine.persist_session(user_id=2, session_id=200, messages=user2_messages, eval_score=7.0)
            
            # User 1 retrieves context
            context_user1 = rag_engine.retrieve_context(
                query="training plan",
                user_id=1,
                active_session_messages=[],
                top_k=5
            )
            
            # Should only see user 1's content
            assert "User 1 secret" in context_user1
            assert "User 2 different" not in context_user1
            
            # User 2 retrieves context
            context_user2 = rag_engine.retrieve_context(
                query="training plan",
                user_id=2,
                active_session_messages=[],
                top_k=5
            )
            
            # Should only see user 2's content
            assert "User 2 different" in context_user2
            assert "User 1 secret" not in context_user2
    
    def test_session_deletion_flow(self, db_session, temp_index_path, mock_embedding):
        """Test complete session deletion flow."""
        with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
            rag_engine = RAGEngine(db_session, temp_index_path)
            session_buffer = SessionBuffer()
            
            # Create and persist session
            messages = [
                ChatMessage(id=1, session_id=100, role='user', content='Sensitive information', created_at=datetime.now()),
                ChatMessage(id=2, session_id=100, role='assistant', content='Response to sensitive info', created_at=datetime.now()),
            ]
            
            # Add to buffer
            for msg in messages:
                session_buffer.add_message(100, msg)
            
            # Persist to vector store
            rag_engine.persist_session(user_id=1, session_id=100, messages=messages, eval_score=8.0)
            
            # Verify it's retrievable
            context_before = rag_engine.retrieve_context(
                query="sensitive",
                user_id=1,
                active_session_messages=[],
                top_k=5
            )
            assert "Sensitive information" in context_before
            
            # Delete session
            start_time = time.time()
            rag_engine.delete_session(user_id=1, session_id=100)
            deletion_time = time.time() - start_time
            
            # Should complete within 2 seconds (Requirement 2.3)
            assert deletion_time < 2.0
            
            # Clear buffer
            session_buffer.clear_session(100)
            
            # Verify it's no longer retrievable
            context_after = rag_engine.retrieve_context(
                query="sensitive",
                user_id=1,
                active_session_messages=[],
                top_k=5
            )
            assert "Sensitive information" not in context_after
    
    def test_performance_with_large_history(self, db_session, temp_index_path, mock_embedding):
        """Test performance with large chat history."""
        with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
            rag_engine = RAGEngine(db_session, temp_index_path)
            
            # Create 50 historical sessions with 10 messages each
            for session_id in range(1, 51):
                messages = [
                    ChatMessage(
                        id=session_id * 10 + i,
                        session_id=session_id,
                        role='user' if i % 2 == 0 else 'assistant',
                        content=f'Session {session_id} message {i}',
                        created_at=datetime.now()
                    )
                    for i in range(10)
                ]
                rag_engine.persist_session(user_id=1, session_id=session_id, messages=messages, eval_score=8.0)
            
            # Test retrieval performance
            start_time = time.time()
            context = rag_engine.retrieve_context(
                query="training plan",
                user_id=1,
                active_session_messages=[],
                top_k=5
            )
            retrieval_time = time.time() - start_time
            
            # Should complete within 500ms (Requirement 17.2)
            assert retrieval_time < 0.5
            
            # Should return results
            assert "=== Relevant Past Conversations ===" in context
    
    def test_active_buffer_priority(self, db_session, temp_index_path, mock_embedding):
        """Test that active buffer messages take priority over historical."""
        with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
            rag_engine = RAGEngine(db_session, temp_index_path)
            
            # Add historical messages
            historical = [
                ChatMessage(id=1, session_id=100, role='user', content='Old training plan discussion', created_at=datetime.now()),
            ]
            rag_engine.persist_session(user_id=1, session_id=100, messages=historical, eval_score=7.0)
            
            # Create active session with recent messages
            active = [
                ChatMessage(id=2, session_id=200, role='user', content='Current training plan discussion', created_at=datetime.now()),
                ChatMessage(id=3, session_id=200, role='assistant', content='Let me help with your current plan', created_at=datetime.now()),
            ]
            
            # Retrieve context
            context = rag_engine.retrieve_context(
                query="training plan",
                user_id=1,
                active_session_messages=active,
                top_k=5
            )
            
            # Current session should appear first
            current_pos = context.find("=== Current Session ===")
            past_pos = context.find("=== Relevant Past Conversations ===")
            
            assert current_pos < past_pos
            assert "Current training plan" in context
    
    def test_eval_score_in_key(self, db_session, temp_index_path, mock_embedding):
        """Test that evaluation score is included in key format."""
        with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
            rag_engine = RAGEngine(db_session, temp_index_path)
            
            messages = [
                ChatMessage(id=1, session_id=100, role='user', content='Test message', created_at=datetime.now()),
            ]
            
            # Persist with specific eval score
            rag_engine.persist_session(user_id=1, session_id=100, messages=messages, eval_score=9.2)
            
            # Retrieve and check key format
            from app.models.faiss_metadata import FaissMetadata
            metadata = db_session.query(FaissMetadata).filter(
                FaissMetadata.record_type == 'chat_message',
                FaissMetadata.user_id == 1
            ).first()
            
            # Key should contain eval score
            assert 'eval_9.2' in metadata.record_id
            assert metadata.record_id.startswith('chat:1:100:')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

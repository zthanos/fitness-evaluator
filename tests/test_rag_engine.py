"""Unit tests for RAG Engine with two-layer context retrieval

Tests the RAGEngine class implementation including:
- FAISS integration with nomic-embed-text embeddings
- User-scoped vector search
- Active session buffer integration
- Session persistence and deletion

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 20.1
"""
import pytest
import os
import tempfile
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import Mock, patch, MagicMock

from app.models.base import Base
from app.models.chat_message import ChatMessage
from app.models.faiss_metadata import FaissMetadata
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
    def _generate_embedding(text: str):
        # Generate a deterministic embedding based on text hash
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(768).astype('float32')
        # L2-normalize
        embedding = embedding / np.linalg.norm(embedding)
        return embedding
    return _generate_embedding


@pytest.fixture
def rag_engine(db_session, temp_index_path, mock_embedding):
    """Create a RAGEngine instance with mocked embedding."""
    with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
        engine = RAGEngine(db_session, temp_index_path)
        yield engine


class TestRAGEngineInitialization:
    """Test RAGEngine initialization and index management."""
    
    def test_initialize_new_index(self, db_session, temp_index_path):
        """Test creating a new FAISS index."""
        with patch.object(RAGEngine, 'generate_embedding'):
            engine = RAGEngine(db_session, temp_index_path)
            
            assert engine.index is not None
            assert engine.index.ntotal == 0
            assert engine.EMBEDDING_DIM == 768
    
    def test_load_existing_index(self, db_session, temp_index_path, mock_embedding):
        """Test loading an existing FAISS index."""
        # Create and save an index
        with patch.object(RAGEngine, 'generate_embedding', side_effect=mock_embedding):
            engine1 = RAGEngine(db_session, temp_index_path)
            
            # Add some test data
            test_embedding = mock_embedding("test message")
            engine1.index.add(np.array([test_embedding]))
            engine1.save_index()
            
            # Create new engine instance (should load existing index)
            engine2 = RAGEngine(db_session, temp_index_path)
            
            assert engine2.index.ntotal == 1


class TestUserScopedVectorSearch:
    """Test user-scoped vector search (Requirement 20.1)."""
    
    def test_search_similar_with_user_filter(self, rag_engine, db_session, mock_embedding):
        """Test that search_similar filters by user_id."""
        # Add messages for user 1
        for i in range(3):
            embedding = mock_embedding(f"user1 message {i}")
            vector_id = rag_engine.index.ntotal
            rag_engine.index.add(np.array([embedding]))
            
            metadata = FaissMetadata(
                vector_id=vector_id,
                record_type='chat_message',
                record_id=f"chat:1:100:2024-01-15:eval_8.0",
                embedding_text=f"user1 message {i}",
                user_id=1
            )
            db_session.add(metadata)
        
        # Add messages for user 2
        for i in range(2):
            embedding = mock_embedding(f"user2 message {i}")
            vector_id = rag_engine.index.ntotal
            rag_engine.index.add(np.array([embedding]))
            
            metadata = FaissMetadata(
                vector_id=vector_id,
                record_type='chat_message',
                record_id=f"chat:2:200:2024-01-15:eval_7.0",
                embedding_text=f"user2 message {i}",
                user_id=2
            )
            db_session.add(metadata)
        
        db_session.commit()
        
        # Search for user 1
        query_embedding = mock_embedding("user1 message 0")
        results_user1 = rag_engine.search_similar(query_embedding, user_id=1, top_k=5)
        
        # Should only return user 1's messages
        assert len(results_user1) == 3
        for result in results_user1:
            assert 'user1' in result['text']
        
        # Search for user 2
        query_embedding = mock_embedding("user2 message 0")
        results_user2 = rag_engine.search_similar(query_embedding, user_id=2, top_k=5)
        
        # Should only return user 2's messages
        assert len(results_user2) == 2
        for result in results_user2:
            assert 'user2' in result['text']
    
    def test_search_similar_empty_index(self, rag_engine):
        """Test search on empty index returns empty list."""
        query_embedding = np.random.randn(768).astype('float32')
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        results = rag_engine.search_similar(query_embedding, user_id=1, top_k=5)
        
        assert results == []


class TestContextRetrieval:
    """Test two-layer context retrieval (Requirements 1.1, 1.2, 1.3)."""
    
    def test_retrieve_context_with_active_buffer(self, rag_engine, db_session):
        """Test context retrieval includes active session messages."""
        # Create active session messages
        messages = [
            ChatMessage(id=1, session_id=100, role='user', content='Hello', created_at=datetime.now()),
            ChatMessage(id=2, session_id=100, role='assistant', content='Hi there!', created_at=datetime.now()),
            ChatMessage(id=3, session_id=100, role='user', content='How are you?', created_at=datetime.now()),
        ]
        
        context = rag_engine.retrieve_context(
            query="What's the weather?",
            user_id=1,
            active_session_messages=messages,
            top_k=5
        )
        
        # Should include active session header
        assert "=== Current Session ===" in context
        
        # Should include all messages
        assert "user: Hello" in context
        assert "assistant: Hi there!" in context
        assert "user: How are you?" in context
    
    def test_retrieve_context_with_vector_store(self, rag_engine, db_session, mock_embedding):
        """Test context retrieval includes vector store results."""
        # Add historical messages to vector store
        historical_messages = [
            "I went for a run yesterday",
            "My training is going well",
            "I need help with my nutrition plan"
        ]
        
        for i, text in enumerate(historical_messages):
            embedding = mock_embedding(text)
            vector_id = rag_engine.index.ntotal
            rag_engine.index.add(np.array([embedding]))
            
            metadata = FaissMetadata(
                vector_id=vector_id,
                record_type='chat_message',
                record_id=f"chat:1:50:2024-01-10:eval_8.5",
                embedding_text=text,
                user_id=1
            )
            db_session.add(metadata)
        
        db_session.commit()
        
        # Retrieve context
        context = rag_engine.retrieve_context(
            query="Tell me about my training",
            user_id=1,
            active_session_messages=[],
            top_k=3
        )
        
        # Should include vector store header
        assert "=== Relevant Past Conversations ===" in context
        
        # Should include at least one historical message
        assert any(msg in context for msg in historical_messages)
    
    def test_retrieve_context_limits_active_messages(self, rag_engine):
        """Test that only last 10 active messages are included."""
        # Create 15 messages
        messages = [
            ChatMessage(id=i, session_id=100, role='user', content=f'Message {i}', created_at=datetime.now())
            for i in range(15)
        ]
        
        context = rag_engine.retrieve_context(
            query="test",
            user_id=1,
            active_session_messages=messages,
            top_k=5
        )
        
        # Should only include last 10 messages
        assert "Message 5" in context  # 6th message (index 5) should be included
        assert "Message 4" not in context  # 5th message should not be included


class TestSessionPersistence:
    """Test session persistence to vector store (Requirements 1.4, 1.5, 1.6)."""
    
    def test_persist_session_creates_vectors(self, rag_engine, db_session):
        """Test that persist_session adds vectors to FAISS index."""
        messages = [
            ChatMessage(id=1, session_id=100, role='user', content='Hello', created_at=datetime.now()),
            ChatMessage(id=2, session_id=100, role='assistant', content='Hi!', created_at=datetime.now()),
        ]
        
        initial_count = rag_engine.index.ntotal
        
        rag_engine.persist_session(
            user_id=1,
            session_id=100,
            messages=messages,
            eval_score=8.5
        )
        
        # Should add 2 vectors
        assert rag_engine.index.ntotal == initial_count + 2
    
    def test_persist_session_creates_metadata(self, rag_engine, db_session):
        """Test that persist_session creates metadata records."""
        messages = [
            ChatMessage(id=1, session_id=100, role='user', content='Hello', created_at=datetime.now()),
        ]
        
        rag_engine.persist_session(
            user_id=1,
            session_id=100,
            messages=messages,
            eval_score=9.0
        )
        
        # Check metadata was created
        metadata = db_session.query(FaissMetadata).filter(
            FaissMetadata.record_type == 'chat_message',
            FaissMetadata.user_id == 1
        ).all()
        
        assert len(metadata) == 1
        assert metadata[0].user_id == 1
        assert metadata[0].embedding_text == 'Hello'
    
    def test_persist_session_key_format(self, rag_engine, db_session):
        """Test that persist_session uses correct key format (Requirement 1.5)."""
        messages = [
            ChatMessage(id=1, session_id=100, role='user', content='Test', created_at=datetime.now()),
        ]
        
        rag_engine.persist_session(
            user_id=1,
            session_id=100,
            messages=messages,
            eval_score=7.5
        )
        
        metadata = db_session.query(FaissMetadata).filter(
            FaissMetadata.record_type == 'chat_message'
        ).first()
        
        # Key format: chat:{user_id}:{session_id}:{date}:eval_{score}
        assert metadata.record_id.startswith('chat:1:100:')
        assert 'eval_7.5' in metadata.record_id
    
    def test_persist_session_empty_messages(self, rag_engine, db_session):
        """Test that persist_session handles empty message list."""
        initial_count = rag_engine.index.ntotal
        
        rag_engine.persist_session(
            user_id=1,
            session_id=100,
            messages=[],
            eval_score=8.0
        )
        
        # Should not add any vectors
        assert rag_engine.index.ntotal == initial_count


class TestSessionDeletion:
    """Test session deletion (Requirements 2.1, 2.2, 2.3, 2.4)."""
    
    def test_delete_session_removes_metadata(self, rag_engine, db_session):
        """Test that delete_session removes metadata records."""
        # Add session messages
        messages = [
            ChatMessage(id=1, session_id=100, role='user', content='Message 1', created_at=datetime.now()),
            ChatMessage(id=2, session_id=100, role='user', content='Message 2', created_at=datetime.now()),
        ]
        
        rag_engine.persist_session(
            user_id=1,
            session_id=100,
            messages=messages,
            eval_score=8.0
        )
        
        # Verify metadata exists
        metadata_before = db_session.query(FaissMetadata).filter(
            FaissMetadata.record_type == 'chat_message',
            FaissMetadata.user_id == 1
        ).count()
        assert metadata_before == 2
        
        # Delete session
        rag_engine.delete_session(user_id=1, session_id=100)
        
        # Verify metadata removed
        metadata_after = db_session.query(FaissMetadata).filter(
            FaissMetadata.record_type == 'chat_message',
            FaissMetadata.user_id == 1
        ).count()
        assert metadata_after == 0
    
    def test_delete_session_prefix_match(self, rag_engine, db_session):
        """Test that delete_session uses prefix match (Requirement 2.2)."""
        # Add messages for session 100
        messages_100 = [
            ChatMessage(id=1, session_id=100, role='user', content='Session 100', created_at=datetime.now()),
        ]
        rag_engine.persist_session(user_id=1, session_id=100, messages=messages_100, eval_score=8.0)
        
        # Add messages for session 101
        messages_101 = [
            ChatMessage(id=2, session_id=101, role='user', content='Session 101', created_at=datetime.now()),
        ]
        rag_engine.persist_session(user_id=1, session_id=101, messages=messages_101, eval_score=7.0)
        
        # Delete session 100
        rag_engine.delete_session(user_id=1, session_id=100)
        
        # Session 100 should be deleted
        metadata_100 = db_session.query(FaissMetadata).filter(
            FaissMetadata.record_id.like('chat:1:100:%')
        ).count()
        assert metadata_100 == 0
        
        # Session 101 should still exist
        metadata_101 = db_session.query(FaissMetadata).filter(
            FaissMetadata.record_id.like('chat:1:101:%')
        ).count()
        assert metadata_101 == 1
    
    def test_delete_session_nonexistent(self, rag_engine, db_session):
        """Test deleting a non-existent session doesn't raise error."""
        # Should not raise an exception
        rag_engine.delete_session(user_id=1, session_id=999)
    
    def test_delete_session_error_handling(self, rag_engine, db_session):
        """Test that delete_session handles errors gracefully (Requirement 2.4)."""
        # Add a session
        messages = [
            ChatMessage(id=1, session_id=100, role='user', content='Test', created_at=datetime.now()),
        ]
        rag_engine.persist_session(user_id=1, session_id=100, messages=messages)
        
        # Mock database error
        with patch.object(db_session, 'commit', side_effect=Exception("Database error")):
            with pytest.raises(Exception):
                rag_engine.delete_session(user_id=1, session_id=100)


class TestPerformance:
    """Test performance requirements (Requirement 17.2)."""
    
    def test_vector_retrieval_performance(self, rag_engine, db_session, mock_embedding):
        """Test that vector retrieval completes within 500ms."""
        import time
        
        # Add 100 messages to index
        for i in range(100):
            embedding = mock_embedding(f"message {i}")
            vector_id = rag_engine.index.ntotal
            rag_engine.index.add(np.array([embedding]))
            
            metadata = FaissMetadata(
                vector_id=vector_id,
                record_type='chat_message',
                record_id=f"chat:1:100:2024-01-15:eval_8.0",
                embedding_text=f"message {i}",
                user_id=1
            )
            db_session.add(metadata)
        
        db_session.commit()
        
        # Measure retrieval time
        query_embedding = mock_embedding("test query")
        start_time = time.time()
        results = rag_engine.search_similar(query_embedding, user_id=1, top_k=5)
        elapsed_time = time.time() - start_time
        
        # Should complete within 500ms (0.5 seconds)
        assert elapsed_time < 0.5
        assert len(results) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

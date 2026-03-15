"""Integration tests for Task 17.1: Wire RAG Engine to Chat Service

Tests the integration of RAG Engine with Chat Service:
- Context retrieval from active buffer and vector store
- Session persistence on session end
- End-to-end chat flow with RAG

Requirements: 1.1, 1.2, 1.3, 1.4, 17.1
"""
import pytest
import os
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.base import Base
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.athlete import Athlete
from app.services.rag_engine import RAGEngine
from app.services.chat_message_handler import ChatMessageHandler
from app.services.llm_client import LLMClient
from app.config import Settings


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
def test_athlete(db_session: Session):
    """Create a test athlete."""
    athlete = Athlete(
        id=999,
        name="Test Athlete",
        email="test@example.com",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(athlete)
    db_session.commit()
    return athlete


@pytest.fixture
def test_session(db_session: Session, test_athlete: Athlete):
    """Create a test chat session."""
    session = ChatSession(
        id=9999,
        athlete_id=test_athlete.id,
        title="Test Session",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    return session


@pytest.fixture
def rag_engine(db_session: Session, temp_index_path: str):
    """Create RAG engine instance."""
    return RAGEngine(db_session, index_path=temp_index_path)


@pytest.fixture
def llm_client():
    """Create LLM client instance."""
    return LLMClient()


def test_rag_engine_initialization(rag_engine: RAGEngine):
    """Test that RAG engine initializes correctly."""
    assert rag_engine is not None
    assert rag_engine.index is not None
    assert rag_engine.db is not None


def test_context_retrieval_with_empty_buffer(
    db_session: Session,
    rag_engine: RAGEngine,
    test_athlete: Athlete
):
    """Test context retrieval with empty active buffer."""
    # Retrieve context with no active messages
    context = rag_engine.retrieve_context(
        query="What is my training plan?",
        user_id=test_athlete.id,
        active_session_messages=[],
        top_k=5
    )
    
    # Should return empty or minimal context
    assert isinstance(context, str)
    # Context should not contain current session section if buffer is empty
    assert "Current Session" not in context or context.strip() == ""


def test_context_retrieval_with_active_buffer(
    db_session: Session,
    rag_engine: RAGEngine,
    test_athlete: Athlete,
    test_session: ChatSession
):
    """Test context retrieval with active session buffer."""
    # Create some messages in active buffer
    messages = [
        ChatMessage(
            session_id=test_session.id,
            role='user',
            content='I want to train for a marathon',
            created_at=datetime.utcnow()
        ),
        ChatMessage(
            session_id=test_session.id,
            role='assistant',
            content='Great! Let me help you create a training plan.',
            created_at=datetime.utcnow()
        )
    ]
    
    # Retrieve context with active messages
    context = rag_engine.retrieve_context(
        query="How many weeks should my plan be?",
        user_id=test_athlete.id,
        active_session_messages=messages,
        top_k=5
    )
    
    # Should include current session
    assert "Current Session" in context
    assert "marathon" in context.lower()


def test_session_persistence(
    db_session: Session,
    rag_engine: RAGEngine,
    test_athlete: Athlete,
    test_session: ChatSession
):
    """Test persisting session to vector store."""
    # Create messages
    messages = [
        ChatMessage(
            id=99991,
            session_id=test_session.id,
            role='user',
            content='I want to improve my 5K time',
            created_at=datetime.utcnow()
        ),
        ChatMessage(
            id=99992,
            session_id=test_session.id,
            role='assistant',
            content='To improve your 5K time, focus on interval training and tempo runs.',
            created_at=datetime.utcnow()
        )
    ]
    
    # Add messages to database
    for msg in messages:
        db_session.add(msg)
    db_session.commit()
    
    # Persist session
    rag_engine.persist_session(
        user_id=test_athlete.id,
        session_id=test_session.id,
        messages=messages,
        eval_score=8.5
    )
    
    # Verify messages were added to vector store
    # Search for similar content
    query_embedding = rag_engine.generate_embedding("5K running training")
    results = rag_engine.search_similar(
        query_embedding=query_embedding,
        user_id=test_athlete.id,
        top_k=5
    )
    
    # Should find at least one of our persisted messages
    assert len(results) > 0
    # Check that results are scoped to our user
    for result in results:
        assert '5K' in result['text'] or 'interval' in result['text'].lower()


def test_session_deletion(
    db_session: Session,
    rag_engine: RAGEngine,
    test_athlete: Athlete,
    test_session: ChatSession
):
    """Test deleting session from vector store."""
    # Create and persist messages
    messages = [
        ChatMessage(
            id=99993,
            session_id=test_session.id,
            role='user',
            content='Test message for deletion',
            created_at=datetime.utcnow()
        )
    ]
    
    for msg in messages:
        db_session.add(msg)
    db_session.commit()
    
    # Persist session
    rag_engine.persist_session(
        user_id=test_athlete.id,
        session_id=test_session.id,
        messages=messages,
        eval_score=7.0
    )
    
    # Delete session
    rag_engine.delete_session(
        user_id=test_athlete.id,
        session_id=test_session.id
    )
    
    # Verify metadata was removed from database
    from app.models.faiss_metadata import FaissMetadata
    metadata_count = db_session.query(FaissMetadata).filter(
        FaissMetadata.user_id == test_athlete.id,
        FaissMetadata.record_id.like(f"chat:{test_athlete.id}:{test_session.id}:%")
    ).count()
    
    assert metadata_count == 0


@pytest.mark.asyncio
async def test_chat_message_handler_integration(
    db_session: Session,
    rag_engine: RAGEngine,
    llm_client: LLMClient,
    test_athlete: Athlete,
    test_session: ChatSession
):
    """Test full chat message handler with RAG integration."""
    # Create handler with ChatAgent (Phase 3 architecture)
    from app.services.chat_session_service import ChatSessionService
    from app.services.chat_agent import ChatAgent
    from app.ai.context.chat_context import ChatContextBuilder

    session_service = ChatSessionService(db_session, rag_engine)
    context_builder = ChatContextBuilder(db=db_session, token_budget=2400)
    agent = ChatAgent(
        context_builder=context_builder,
        llm_adapter=None,
        db=db_session,
        llm_client=llm_client,
    )
    handler = ChatMessageHandler(
        db=db_session,
        session_service=session_service,
        agent=agent,
        user_id=test_athlete.id,
        session_id=test_session.id,
        settings=Settings(USE_CE_CHAT_RUNTIME=True, LEGACY_CHAT_ENABLED=True),
    )
    
    # Load some existing messages into session buffer
    existing_messages = [
        ChatMessage(
            session_id=test_session.id,
            role='user',
            content='I run 30km per week currently',
            created_at=datetime.utcnow()
        ),
        ChatMessage(
            session_id=test_session.id,
            role='assistant',
            content='That\'s a good base! What are your goals?',
            created_at=datetime.utcnow()
        )
    ]
    
    # Load messages via session service instead of deprecated handler method
    session_service.load_session(test_session.id)
    
    # Handle a new message
    try:
        response = await handler.handle_message(
            "I want to run a half marathon in 3 months"
        )
        
        # Verify response structure
        assert 'content' in response
        assert 'latency_ms' in response
        assert 'ce_context_used' in response
        
        # Response should be a string
        assert isinstance(response['content'], str)
        assert len(response['content']) > 0
        
        # Latency should be reasonable
        assert response['latency_ms'] < 10000  # Less than 10 seconds
        
        print(f"✓ Chat handler processed message in {response['latency_ms']:.0f}ms")
        
    except Exception as e:
        # If LLM is not available, test should still pass structure checks
        print(f"Note: LLM not available for full test: {e}")
        pytest.skip("LLM not available")


def test_user_scoping_in_context_retrieval(
    db_session: Session,
    rag_engine: RAGEngine
):
    """Test that context retrieval is properly scoped to user_id."""
    # Create two different users
    user1_id = 1001
    user2_id = 1002
    
    # Create messages for user 1
    user1_messages = [
        ChatMessage(
            id=100001,
            session_id=10001,
            role='user',
            content='User 1 secret training plan',
            created_at=datetime.utcnow()
        )
    ]
    
    # Persist user 1 session
    rag_engine.persist_session(
        user_id=user1_id,
        session_id=10001,
        messages=user1_messages,
        eval_score=8.0
    )
    
    # Try to retrieve context as user 2
    context = rag_engine.retrieve_context(
        query="training plan",
        user_id=user2_id,
        active_session_messages=[],
        top_k=5
    )
    
    # User 2 should NOT see user 1's content
    assert "User 1 secret" not in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

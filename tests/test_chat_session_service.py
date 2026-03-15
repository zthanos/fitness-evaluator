"""Tests for ChatSessionService

Tests session lifecycle and persistence management:
- Session creation, loading, deletion
- Active buffer management
- Message appending and persistence
- Session isolation

Requirements: Phase 1 - Extract ChatSessionService
Design: ChatSessionService Interface (design.md)
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.base import Base
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.athlete import Athlete
from app.services.chat_session_service import ChatSessionService


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
def mock_rag_engine():
    """Create a mock RAG engine."""
    engine = Mock()
    engine.persist_session = Mock()
    engine.delete_session = Mock()
    return engine


@pytest.fixture
def test_athlete(db_session: Session):
    """Create a test athlete."""
    athlete = Athlete(
        id=1,
        name="Test Athlete",
        email="test@example.com",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(athlete)
    db_session.commit()
    return athlete


@pytest.fixture
def session_service(db_session: Session, mock_rag_engine):
    """Create ChatSessionService instance."""
    return ChatSessionService(db=db_session, rag_engine=mock_rag_engine)


# Test 1.4.1: test_create_session_success
def test_create_session_success(
    session_service: ChatSessionService,
    test_athlete: Athlete,
    db_session: Session
):
    """Test successful session creation.
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Test Chat Session"
    )
    
    # Verify session was created
    assert session_id is not None
    assert isinstance(session_id, int)
    
    # Verify session exists in database
    session = db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    assert session is not None
    assert session.athlete_id == test_athlete.id
    assert session.title == "Test Chat Session"
    assert session.created_at is not None
    assert session.updated_at is not None
    
    # Verify empty buffer was initialized
    assert session_id in session_service.active_buffers
    assert len(session_service.active_buffers[session_id]) == 0



# Test 1.4.2: test_load_session_with_messages
def test_load_session_with_messages(
    session_service: ChatSessionService,
    test_athlete: Athlete,
    db_session: Session
):
    """Test loading session with existing messages.
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session
    session = ChatSession(
        athlete_id=test_athlete.id,
        title="Test Session",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Add messages to database
    msg1 = ChatMessage(
        session_id=session.id,
        role='user',
        content='Hello',
        created_at=datetime.utcnow()
    )
    msg2 = ChatMessage(
        session_id=session.id,
        role='assistant',
        content='Hi there!',
        created_at=datetime.utcnow()
    )
    db_session.add(msg1)
    db_session.add(msg2)
    db_session.commit()
    
    # Load session
    messages = session_service.load_session(session.id)
    
    # Verify messages loaded
    assert len(messages) == 2
    assert messages[0].role == 'user'
    assert messages[0].content == 'Hello'
    assert messages[1].role == 'assistant'
    assert messages[1].content == 'Hi there!'
    
    # Verify active buffer populated
    assert session.id in session_service.active_buffers
    assert len(session_service.active_buffers[session.id]) == 2


# Test 1.4.3: test_load_session_not_found
def test_load_session_not_found(
    session_service: ChatSessionService
):
    """Test loading non-existent session returns empty list.
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Load non-existent session
    messages = session_service.load_session(session_id=99999)
    
    # Verify empty list returned
    assert messages == []
    
    # Verify buffer initialized
    assert 99999 in session_service.active_buffers
    assert len(session_service.active_buffers[99999]) == 0


# Test 1.4.4: test_append_messages_to_buffer
def test_append_messages_to_buffer(
    session_service: ChatSessionService,
    test_athlete: Athlete
):
    """Test appending messages to active buffer.
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Test Session"
    )
    
    # Append messages
    session_service.append_messages(
        session_id=session_id,
        user_message="What's my training plan?",
        assistant_message="Here's your training plan..."
    )
    
    # Verify messages in buffer
    buffer = session_service.active_buffers[session_id]
    assert len(buffer) == 2
    assert buffer[0].role == 'user'
    assert buffer[0].content == "What's my training plan?"
    assert buffer[1].role == 'assistant'
    assert buffer[1].content == "Here's your training plan..."
    
    # Append more messages
    session_service.append_messages(
        session_id=session_id,
        user_message="Thanks!",
        assistant_message="You're welcome!"
    )
    
    # Verify buffer updated
    buffer = session_service.active_buffers[session_id]
    assert len(buffer) == 4
    assert buffer[2].content == "Thanks!"
    assert buffer[3].content == "You're welcome!"


# Test 1.4.5: test_get_active_buffer_empty
def test_get_active_buffer_empty(
    session_service: ChatSessionService
):
    """Test getting active buffer for non-existent session.
    
    Requirements: 1.2 Session State Isolation
    """
    # Get buffer for non-existent session
    buffer = session_service.get_active_buffer(session_id=99999)
    
    # Verify empty list returned
    assert buffer == []
    assert isinstance(buffer, list)


# Test 1.4.6: test_get_active_buffer_with_messages
def test_get_active_buffer_with_messages(
    session_service: ChatSessionService,
    test_athlete: Athlete
):
    """Test getting active buffer with messages.
    
    Requirements: 1.2 Session State Isolation
    """
    # Create session and add messages
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Test Session"
    )
    
    session_service.append_messages(
        session_id=session_id,
        user_message="Hello",
        assistant_message="Hi!"
    )
    
    # Get buffer
    buffer = session_service.get_active_buffer(session_id)
    
    # Verify buffer contents
    assert len(buffer) == 2
    assert buffer[0].content == "Hello"
    assert buffer[1].content == "Hi!"
    
    # Verify it's a copy (modifying returned buffer doesn't affect internal state)
    buffer.append(ChatMessage(
        session_id=session_id,
        role='user',
        content='Modified',
        created_at=datetime.utcnow()
    ))
    
    # Get buffer again
    buffer2 = session_service.get_active_buffer(session_id)
    assert len(buffer2) == 2  # Original buffer unchanged


# Test 1.4.7: test_persist_session_to_db_and_vector_store
def test_persist_session_to_db_and_vector_store(
    session_service: ChatSessionService,
    test_athlete: Athlete,
    db_session: Session,
    mock_rag_engine
):
    """Test persisting session to database and vector store.
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session and add messages
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Test Session"
    )
    
    session_service.append_messages(
        session_id=session_id,
        user_message="Hello",
        assistant_message="Hi there!"
    )
    
    # Persist session
    session_service.persist_session(
        session_id=session_id,
        eval_score=8.5
    )
    
    # Verify messages persisted to database
    messages = db_session.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).all()
    
    assert len(messages) == 2
    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi there!"
    
    # Verify session updated_at timestamp updated
    session = db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    assert session.updated_at is not None
    
    # Verify RAG engine persist_session called
    mock_rag_engine.persist_session.assert_called_once()
    call_kwargs = mock_rag_engine.persist_session.call_args[1]
    assert call_kwargs['user_id'] == test_athlete.id
    assert call_kwargs['session_id'] == session_id
    assert call_kwargs['eval_score'] == 8.5
    assert len(call_kwargs['messages']) == 2


# Test 1.4.8: test_clear_buffer
def test_clear_buffer(
    session_service: ChatSessionService,
    test_athlete: Athlete
):
    """Test clearing active buffer.
    
    Requirements: 1.2 Session State Isolation
    """
    # Create session and add messages
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Test Session"
    )
    
    session_service.append_messages(
        session_id=session_id,
        user_message="Hello",
        assistant_message="Hi!"
    )
    
    # Verify buffer has messages
    assert len(session_service.active_buffers[session_id]) == 2
    
    # Clear buffer
    session_service.clear_buffer(session_id)
    
    # Verify buffer cleared
    assert len(session_service.active_buffers[session_id]) == 0
    
    # Clear non-existent buffer (should not raise error)
    session_service.clear_buffer(session_id=99999)


# Test 1.4.9: test_delete_session_removes_all_data
def test_delete_session_removes_all_data(
    session_service: ChatSessionService,
    test_athlete: Athlete,
    db_session: Session,
    mock_rag_engine
):
    """Test deleting session removes all data.
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session and add messages
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Test Session"
    )
    
    session_service.append_messages(
        session_id=session_id,
        user_message="Hello",
        assistant_message="Hi!"
    )
    
    # Persist session
    session_service.persist_session(session_id)
    
    # Verify session exists
    session = db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    assert session is not None
    
    # Delete session
    session_service.delete_session(session_id)
    
    # Verify session deleted from database
    session = db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    assert session is None
    
    # Verify messages deleted (cascade)
    messages = db_session.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).all()
    assert len(messages) == 0
    
    # Verify active buffer removed
    assert session_id not in session_service.active_buffers
    
    # Verify RAG engine delete_session called
    mock_rag_engine.delete_session.assert_called_once_with(
        user_id=test_athlete.id,
        session_id=session_id
    )


# Test 1.4.10: test_multiple_sessions_isolated_buffers
def test_multiple_sessions_isolated_buffers(
    session_service: ChatSessionService,
    test_athlete: Athlete
):
    """Test multiple sessions have isolated buffers.
    
    Requirements: 1.2 Session State Isolation
    """
    # Create two sessions
    session_id_1 = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Session 1"
    )
    
    session_id_2 = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Session 2"
    )
    
    # Add messages to session 1
    session_service.append_messages(
        session_id=session_id_1,
        user_message="Session 1 message",
        assistant_message="Session 1 response"
    )
    
    # Add messages to session 2
    session_service.append_messages(
        session_id=session_id_2,
        user_message="Session 2 message",
        assistant_message="Session 2 response"
    )
    
    # Verify buffers are isolated
    buffer_1 = session_service.get_active_buffer(session_id_1)
    buffer_2 = session_service.get_active_buffer(session_id_2)
    
    assert len(buffer_1) == 2
    assert len(buffer_2) == 2
    assert buffer_1[0].content == "Session 1 message"
    assert buffer_2[0].content == "Session 2 message"
    
    # Clear session 1 buffer
    session_service.clear_buffer(session_id_1)
    
    # Verify only session 1 buffer cleared
    buffer_1 = session_service.get_active_buffer(session_id_1)
    buffer_2 = session_service.get_active_buffer(session_id_2)
    
    assert len(buffer_1) == 0
    assert len(buffer_2) == 2


# Additional edge case tests
def test_persist_session_empty_buffer(
    session_service: ChatSessionService,
    test_athlete: Athlete,
    mock_rag_engine
):
    """Test persisting session with empty buffer does nothing."""
    # Create session without messages
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Empty Session"
    )
    
    # Persist empty session
    session_service.persist_session(session_id)
    
    # Verify RAG engine not called
    mock_rag_engine.persist_session.assert_not_called()


def test_append_messages_to_nonexistent_buffer(
    session_service: ChatSessionService
):
    """Test appending messages to non-existent buffer creates it."""
    # Append to non-existent session
    session_service.append_messages(
        session_id=99999,
        user_message="Hello",
        assistant_message="Hi!"
    )
    
    # Verify buffer created
    assert 99999 in session_service.active_buffers
    assert len(session_service.active_buffers[99999]) == 2


def test_delete_nonexistent_session(
    session_service: ChatSessionService,
    mock_rag_engine
):
    """Test deleting non-existent session doesn't raise error."""
    # Delete non-existent session (should not raise)
    session_service.delete_session(session_id=99999)
    
    # Verify RAG engine not called
    mock_rag_engine.delete_session.assert_not_called()


def test_session_timestamps(
    session_service: ChatSessionService,
    test_athlete: Athlete,
    db_session: Session
):
    """Test session timestamps are set correctly."""
    # Create session
    session_id = session_service.create_session(
        athlete_id=test_athlete.id,
        title="Test Session"
    )
    
    # Get session
    session = db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    # Verify timestamps
    assert session.created_at is not None
    assert session.updated_at is not None
    assert isinstance(session.created_at, datetime)
    assert isinstance(session.updated_at, datetime)


def test_message_ordering(
    session_service: ChatSessionService,
    test_athlete: Athlete,
    db_session: Session
):
    """Test messages are ordered chronologically."""
    # Create session
    session = ChatSession(
        athlete_id=test_athlete.id,
        title="Test Session",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    
    # Add messages with different timestamps
    import time
    msg1 = ChatMessage(
        session_id=session.id,
        role='user',
        content='First',
        created_at=datetime.utcnow()
    )
    db_session.add(msg1)
    db_session.commit()
    
    time.sleep(0.01)  # Small delay
    
    msg2 = ChatMessage(
        session_id=session.id,
        role='assistant',
        content='Second',
        created_at=datetime.utcnow()
    )
    db_session.add(msg2)
    db_session.commit()
    
    # Load session
    messages = session_service.load_session(session.id)
    
    # Verify ordering
    assert len(messages) == 2
    assert messages[0].content == 'First'
    assert messages[1].content == 'Second'
    assert messages[0].created_at <= messages[1].created_at

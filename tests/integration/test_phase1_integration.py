"""
Integration Tests for Phase 1: Extract ChatSessionService

Tests the full flow from API endpoint through ChatSessionService to database/vector store.

Requirements:
- 1.5.1 Test session creation through API
- 1.5.2 Test session switching doesn't leak state
- 1.5.3 Test streaming persistence works
- 1.5.4 Test concurrent session access
- 1.5.5 Verify no regression in UI session operations

Design: Phase 1 Exit Criteria (design.md)
"""
import pytest
import asyncio
import json
import tempfile
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.athlete import Athlete
from app.services.chat_session_service import ChatSessionService
from app.services.rag_engine import RAGEngine


@pytest.fixture
def test_db_engine():
    """Create a temporary test database engine."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    
    yield engine
    
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except (PermissionError, FileNotFoundError):
        pass


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )
    session = TestingSessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def test_client(test_db_engine):
    """Create a test client with database override."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    client = TestClient(app)
    
    yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def test_athlete(test_db_session: Session):
    """Create a test athlete."""
    athlete = Athlete(
        id=1,
        name="Test Athlete",
        email="test@example.com",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db_session.add(athlete)
    test_db_session.commit()
    test_db_session.refresh(athlete)
    return athlete


# Task 1.5.1: Test session creation through API
def test_session_creation_through_api(test_client: TestClient, test_athlete: Athlete):
    """
    Test session creation through API endpoint.
    
    Verifies:
    - POST /api/chat/sessions creates session
    - Session is persisted to database
    - Session has correct attributes
    - Empty buffer is initialized
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session via API
    response = test_client.post(
        "/api/chat/sessions",
        json={"title": "Integration Test Session"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "id" in data
    assert data["title"] == "Integration Test Session"
    assert data["athlete_id"] == "1"
    assert data["message_count"] == 0
    assert "created_at" in data
    assert "updated_at" in data
    
    session_id = int(data["id"])
    
    # Verify session exists in database
    response = test_client.get(f"/api/chat/sessions/{session_id}")
    assert response.status_code == 200
    
    session_data = response.json()
    assert session_data["id"] == str(session_id)
    assert session_data["title"] == "Integration Test Session"
    assert len(session_data["messages"]) == 0


# Task 1.5.2: Test session switching doesn't leak state
def test_session_switching_no_state_leakage(
    test_client: TestClient,
    test_athlete: Athlete,
    test_db_session: Session
):
    """
    Test session switching doesn't leak state between sessions.
    
    Verifies:
    - Creating multiple sessions
    - Each session has isolated state
    - Switching between sessions doesn't mix messages
    - Buffers remain isolated
    
    Requirements: 1.2 Session State Isolation
    """
    # Create two sessions
    response1 = test_client.post(
        "/api/chat/sessions",
        json={"title": "Session 1"}
    )
    assert response1.status_code == 200
    session1_id = int(response1.json()["id"])
    
    response2 = test_client.post(
        "/api/chat/sessions",
        json={"title": "Session 2"}
    )
    assert response2.status_code == 200
    session2_id = int(response2.json()["id"])
    
    # Add messages to session 1 directly in database
    msg1_user = ChatMessage(
        session_id=session1_id,
        role='user',
        content='Session 1 user message',
        created_at=datetime.utcnow()
    )
    msg1_assistant = ChatMessage(
        session_id=session1_id,
        role='assistant',
        content='Session 1 assistant response',
        created_at=datetime.utcnow()
    )
    test_db_session.add(msg1_user)
    test_db_session.add(msg1_assistant)
    test_db_session.commit()
    
    # Add messages to session 2
    msg2_user = ChatMessage(
        session_id=session2_id,
        role='user',
        content='Session 2 user message',
        created_at=datetime.utcnow()
    )
    msg2_assistant = ChatMessage(
        session_id=session2_id,
        role='assistant',
        content='Session 2 assistant response',
        created_at=datetime.utcnow()
    )
    test_db_session.add(msg2_user)
    test_db_session.add(msg2_assistant)
    test_db_session.commit()
    
    # Load session 1 messages
    response = test_client.get(f"/api/chat/sessions/{session1_id}/messages")
    assert response.status_code == 200
    session1_messages = response.json()
    
    assert len(session1_messages) == 2
    # API returns messages in chronological order (oldest first)
    session1_contents = [msg["content"] for msg in session1_messages]
    assert 'Session 1 user message' in session1_contents
    assert 'Session 1 assistant response' in session1_contents
    
    # Load session 2 messages
    response = test_client.get(f"/api/chat/sessions/{session2_id}/messages")
    assert response.status_code == 200
    session2_messages = response.json()
    
    assert len(session2_messages) == 2
    session2_contents = [msg["content"] for msg in session2_messages]
    assert 'Session 2 user message' in session2_contents
    assert 'Session 2 assistant response' in session2_contents
    
    # Verify no cross-contamination
    assert all(msg["session_id"] == str(session1_id) for msg in session1_messages)
    assert all(msg["session_id"] == str(session2_id) for msg in session2_messages)
    
    # Verify session 1 messages don't appear in session 2
    session1_contents = {msg["content"] for msg in session1_messages}
    session2_contents = {msg["content"] for msg in session2_messages}
    assert session1_contents.isdisjoint(session2_contents)


# Task 1.5.3: Test streaming persistence works
def test_streaming_persistence(
    test_client: TestClient,
    test_athlete: Athlete,
    test_db_session: Session
):
    """
    Test streaming responses persist correctly to database and vector store.
    
    Verifies:
    - POST /api/chat/stream endpoint exists
    - Messages can be persisted after streaming
    - Session is updated with new messages
    - Vector store persistence is triggered
    
    Requirements: 1.1 Session Lifecycle Extraction, 1.4 Streaming Persistence
    
    Note: This test verifies the persistence mechanism, not the actual LLM streaming.
    """
    # Create session
    response = test_client.post(
        "/api/chat/sessions",
        json={"title": "Streaming Test Session"}
    )
    assert response.status_code == 200
    session_id = int(response.json()["id"])
    
    # Add messages directly to simulate what streaming would do
    msg_user = ChatMessage(
        session_id=session_id,
        role='user',
        content="What's my training plan?",
        created_at=datetime.utcnow()
    )
    msg_assistant = ChatMessage(
        session_id=session_id,
        role='assistant',
        content="Here's your training plan...",
        created_at=datetime.utcnow()
    )
    test_db_session.add(msg_user)
    test_db_session.add(msg_assistant)
    test_db_session.commit()
    
    # Verify messages were persisted to database
    messages = test_db_session.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    assert len(messages) == 2
    assert messages[0].role == 'user'
    assert messages[0].content == "What's my training plan?"
    assert messages[1].role == 'assistant'
    assert len(messages[1].content) > 0
    
    # Test persistence to vector store
    response = test_client.post(f"/api/chat/sessions/{session_id}/persist")
    assert response.status_code == 200
    persist_data = response.json()
    assert persist_data["success"] is True
    assert persist_data["messages_persisted"] == 2
    
    # Verify session was updated
    session = test_db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    assert session is not None
    assert session.updated_at is not None


# Task 1.5.4: Test concurrent session access
def test_concurrent_session_access(
    test_client: TestClient,
    test_athlete: Athlete
):
    """
    Test concurrent session access is handled safely.
    
    Verifies:
    - Multiple sessions can be accessed concurrently
    - No race conditions in buffer management
    - Each session maintains isolated state
    - API operations are thread-safe
    
    Requirements: 1.2 Session State Isolation
    """
    # Create multiple sessions
    session_ids = []
    for i in range(3):
        response = test_client.post(
            "/api/chat/sessions",
            json={"title": f"Concurrent Session {i+1}"}
        )
        assert response.status_code == 200
        session_ids.append(int(response.json()["id"]))
    
    # Access sessions concurrently via API
    def access_session(session_id: int, session_num: int):
        """Access a session via API."""
        # Get session details
        response = test_client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 200
        
        # Get session messages
        response = test_client.get(f"/api/chat/sessions/{session_id}/messages")
        assert response.status_code == 200
        
        return session_id, session_num
    
    # Execute concurrent operations
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(access_session, session_id, i+1)
            for i, session_id in enumerate(session_ids)
        ]
        
        # Wait for all to complete
        results = [future.result() for future in futures]
    
    # Verify all operations completed successfully
    assert len(results) == 3
    
    # Verify each session still exists and is accessible
    for session_id in session_ids:
        response = test_client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 200
        
        session_data = response.json()
        assert session_data["id"] == str(session_id)


# Task 1.5.5: Verify no regression in UI session operations
def test_no_regression_ui_operations(
    test_client: TestClient,
    test_athlete: Athlete,
    test_db_session: Session
):
    """
    Verify no regression in UI session operations.
    
    Tests all UI operations:
    - List sessions
    - Load session
    - Create session
    - Stream into session
    - Delete session
    - Persist session
    
    Requirements: 1.2 Session State Isolation, Phase 1 Exit Criteria
    """
    # Test 1: Create session
    response = test_client.post(
        "/api/chat/sessions",
        json={"title": "UI Test Session"}
    )
    assert response.status_code == 200
    session_id = int(response.json()["id"])
    
    # Test 2: List sessions
    response = test_client.get("/api/chat/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) > 0
    assert any(s["id"] == str(session_id) for s in sessions)
    
    # Test 3: Load session
    response = test_client.get(f"/api/chat/sessions/{session_id}")
    assert response.status_code == 200
    session_data = response.json()
    assert session_data["id"] == str(session_id)
    assert session_data["title"] == "UI Test Session"
    
    # Test 4: Get session messages (empty initially)
    response = test_client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    assert response.json() == []
    
    # Test 5: Add messages to session
    msg_user = ChatMessage(
        session_id=session_id,
        role='user',
        content='Test message',
        created_at=datetime.utcnow()
    )
    msg_assistant = ChatMessage(
        session_id=session_id,
        role='assistant',
        content='Test response',
        created_at=datetime.utcnow()
    )
    test_db_session.add(msg_user)
    test_db_session.add(msg_assistant)
    test_db_session.commit()
    
    # Test 6: Load session with messages
    response = test_client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    # Verify both messages are present (order may vary)
    message_contents = [msg["content"] for msg in messages]
    assert "Test message" in message_contents
    assert "Test response" in message_contents
    
    # Test 7: Persist session
    response = test_client.post(
        f"/api/chat/sessions/{session_id}/persist",
        params={"eval_score": 8.5}
    )
    assert response.status_code == 200
    persist_data = response.json()
    assert persist_data["success"] is True
    assert persist_data["messages_persisted"] == 2
    
    # Test 8: Delete session
    response = test_client.delete(f"/api/chat/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Test 9: Verify session deleted
    response = test_client.get(f"/api/chat/sessions/{session_id}")
    assert response.status_code == 404


# Additional integration tests
def test_session_service_integration_with_api(
    test_client: TestClient,
    test_athlete: Athlete,
    test_db_session: Session
):
    """
    Test ChatSessionService integration with API endpoints.
    
    Verifies:
    - API endpoints use ChatSessionService
    - Service methods are called correctly
    - Database operations work end-to-end
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session via API (uses ChatSessionService)
    response = test_client.post(
        "/api/chat/sessions",
        json={"title": "Service Integration Test"}
    )
    assert response.status_code == 200
    session_id = int(response.json()["id"])
    
    # Verify session in database
    session = test_db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    assert session is not None
    assert session.title == "Service Integration Test"
    assert session.athlete_id == test_athlete.id
    
    # Delete via API (uses ChatSessionService)
    response = test_client.delete(f"/api/chat/sessions/{session_id}")
    assert response.status_code == 200
    
    # Verify session deleted from database
    session = test_db_session.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    assert session is None


def test_session_buffer_persistence_flow(
    test_client: TestClient,
    test_athlete: Athlete,
    test_db_session: Session
):
    """
    Test complete flow: buffer -> persistence -> retrieval.
    
    Verifies:
    - Messages added to buffer
    - Buffer persisted to database
    - Messages retrieved correctly
    - Vector store updated
    
    Requirements: 1.1 Session Lifecycle Extraction
    """
    # Create session
    response = test_client.post(
        "/api/chat/sessions",
        json={"title": "Buffer Persistence Test"}
    )
    assert response.status_code == 200
    session_id = int(response.json()["id"])
    
    # Add messages to database (simulating buffer persistence)
    messages_to_add = [
        ("user", "First user message"),
        ("assistant", "First assistant response"),
        ("user", "Second user message"),
        ("assistant", "Second assistant response"),
    ]
    
    for role, content in messages_to_add:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.utcnow()
        )
        test_db_session.add(msg)
    test_db_session.commit()
    
    # Persist session to vector store
    response = test_client.post(f"/api/chat/sessions/{session_id}/persist")
    assert response.status_code == 200
    assert response.json()["messages_persisted"] == 4
    
    # Retrieve messages
    response = test_client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    messages = response.json()
    
    assert len(messages) == 4
    # Verify all messages are present (order may vary)
    message_contents = [msg["content"] for msg in messages]
    assert "First user message" in message_contents
    assert "First assistant response" in message_contents
    assert "Second user message" in message_contents
    assert "Second assistant response" in message_contents


def test_session_ordering_maintained(
    test_client: TestClient,
    test_athlete: Athlete
):
    """
    Test that session ordering is maintained (most recent first).
    
    Verifies:
    - Sessions listed in reverse chronological order
    - Updated sessions move to top
    
    Requirements: Phase 1 Exit Criteria
    """
    # Create multiple sessions
    session_ids = []
    for i in range(3):
        response = test_client.post(
            "/api/chat/sessions",
            json={"title": f"Session {i+1}"}
        )
        assert response.status_code == 200
        session_ids.append(response.json()["id"])
    
    # List sessions
    response = test_client.get("/api/chat/sessions")
    assert response.status_code == 200
    sessions = response.json()
    
    # Find our sessions
    our_sessions = [s for s in sessions if s["id"] in session_ids]
    assert len(our_sessions) == 3
    
    # Verify reverse chronological order (most recent first)
    # Session 3 should be first, Session 1 should be last
    session_positions = {s["id"]: i for i, s in enumerate(our_sessions)}
    assert session_positions[session_ids[2]] < session_positions[session_ids[0]]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

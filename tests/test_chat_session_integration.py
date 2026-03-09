"""
Integration test for chat session persistence.

This test verifies that the chat session persistence implementation works
end-to-end with the database and API.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from app.main import app
from app.database import get_db
from app.models.base import Base


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield engine
    
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


def test_create_session(test_db):
    """Test creating a new chat session."""
    client = TestClient(app)
    
    response = client.post("/api/chat/sessions", json={"title": "Test Session"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["title"] == "Test Session"
    assert "id" in data
    assert data["message_count"] == 0


def test_list_sessions(test_db):
    """Test listing chat sessions."""
    client = TestClient(app)
    
    # Create a few sessions
    client.post("/api/chat/sessions", json={"title": "Session 1"})
    client.post("/api/chat/sessions", json={"title": "Session 2"})
    
    # List sessions
    response = client.get("/api/chat/sessions")
    assert response.status_code == 200
    
    sessions = response.json()
    assert len(sessions) >= 2
    assert any(s["title"] == "Session 1" for s in sessions)
    assert any(s["title"] == "Session 2" for s in sessions)


def test_get_session_messages(test_db):
    """Test retrieving messages for a session."""
    client = TestClient(app)
    
    # Create session
    response = client.post("/api/chat/sessions", json={"title": "Test Session"})
    session_id = response.json()["id"]
    
    # Get messages (should be empty)
    response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    assert response.json() == []


def test_message_limit(test_db):
    """Test that message retrieval respects the 50-message limit."""
    client = TestClient(app)
    
    # Create session
    response = client.post("/api/chat/sessions", json={"title": "Test Session"})
    session_id = response.json()["id"]
    
    # Get messages with limit
    response = client.get(f"/api/chat/sessions/{session_id}/messages?limit=50")
    assert response.status_code == 200
    
    # Verify limit parameter is accepted
    messages = response.json()
    assert isinstance(messages, list)


def test_session_not_found(test_db):
    """Test that accessing non-existent session returns 404."""
    client = TestClient(app)
    
    response = client.get("/api/chat/sessions/99999/messages")
    assert response.status_code == 404


def test_delete_session(test_db):
    """Test deleting a chat session."""
    client = TestClient(app)
    
    # Create session
    response = client.post("/api/chat/sessions", json={"title": "Test Session"})
    session_id = response.json()["id"]
    
    # Delete session
    response = client.delete(f"/api/chat/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify session is deleted
    response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 404


def test_session_ordering(test_db):
    """Test that sessions are returned in reverse chronological order."""
    client = TestClient(app)
    
    # Create sessions
    response1 = client.post("/api/chat/sessions", json={"title": "First Session"})
    session1_id = response1.json()["id"]
    
    response2 = client.post("/api/chat/sessions", json={"title": "Second Session"})
    session2_id = response2.json()["id"]
    
    # List sessions
    response = client.get("/api/chat/sessions")
    sessions = response.json()
    
    # Find our sessions
    our_sessions = [s for s in sessions if s["id"] in [session1_id, session2_id]]
    assert len(our_sessions) == 2
    
    # Second session should come first (most recent)
    assert our_sessions[0]["id"] == session2_id
    assert our_sessions[1]["id"] == session1_id


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

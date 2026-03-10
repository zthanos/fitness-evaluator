"""Unit tests for Active Session Buffer

Tests the SessionBuffer class implementation for in-memory message storage.

Requirements: 1.1, 1.3
"""
import pytest
from datetime import datetime

from app.models.chat_message import ChatMessage
from app.services.session_buffer import SessionBuffer, get_session_buffer


class TestSessionBuffer:
    """Test SessionBuffer functionality."""
    
    def test_initialize_empty_buffer(self):
        """Test creating a new empty buffer."""
        buffer = SessionBuffer()
        
        assert buffer.get_session_count() == 0
        assert buffer.get_messages(100) == []
    
    def test_add_message(self):
        """Test adding messages to buffer."""
        buffer = SessionBuffer()
        
        message1 = ChatMessage(
            id=1,
            session_id=100,
            role='user',
            content='Hello',
            created_at=datetime.now()
        )
        
        buffer.add_message(100, message1)
        
        messages = buffer.get_messages(100)
        assert len(messages) == 1
        assert messages[0].content == 'Hello'
    
    def test_add_multiple_messages(self):
        """Test adding multiple messages to same session."""
        buffer = SessionBuffer()
        
        messages_to_add = [
            ChatMessage(id=1, session_id=100, role='user', content='Message 1', created_at=datetime.now()),
            ChatMessage(id=2, session_id=100, role='assistant', content='Message 2', created_at=datetime.now()),
            ChatMessage(id=3, session_id=100, role='user', content='Message 3', created_at=datetime.now()),
        ]
        
        for msg in messages_to_add:
            buffer.add_message(100, msg)
        
        retrieved = buffer.get_messages(100)
        assert len(retrieved) == 3
        assert retrieved[0].content == 'Message 1'
        assert retrieved[1].content == 'Message 2'
        assert retrieved[2].content == 'Message 3'
    
    def test_multiple_sessions(self):
        """Test managing multiple sessions simultaneously."""
        buffer = SessionBuffer()
        
        # Add messages to session 100
        buffer.add_message(100, ChatMessage(id=1, session_id=100, role='user', content='Session 100', created_at=datetime.now()))
        
        # Add messages to session 200
        buffer.add_message(200, ChatMessage(id=2, session_id=200, role='user', content='Session 200', created_at=datetime.now()))
        
        # Verify both sessions exist
        assert len(buffer.get_messages(100)) == 1
        assert len(buffer.get_messages(200)) == 1
        assert buffer.get_session_count() == 2
        
        # Verify content is correct
        assert buffer.get_messages(100)[0].content == 'Session 100'
        assert buffer.get_messages(200)[0].content == 'Session 200'
    
    def test_get_messages_nonexistent_session(self):
        """Test getting messages from non-existent session returns empty list."""
        buffer = SessionBuffer()
        
        messages = buffer.get_messages(999)
        
        assert messages == []
    
    def test_clear_session(self):
        """Test clearing a specific session."""
        buffer = SessionBuffer()
        
        # Add messages to two sessions
        buffer.add_message(100, ChatMessage(id=1, session_id=100, role='user', content='Session 100', created_at=datetime.now()))
        buffer.add_message(200, ChatMessage(id=2, session_id=200, role='user', content='Session 200', created_at=datetime.now()))
        
        # Clear session 100
        buffer.clear_session(100)
        
        # Session 100 should be empty
        assert buffer.get_messages(100) == []
        assert not buffer.has_session(100)
        
        # Session 200 should still exist
        assert len(buffer.get_messages(200)) == 1
        assert buffer.has_session(200)
    
    def test_clear_nonexistent_session(self):
        """Test clearing a non-existent session doesn't raise error."""
        buffer = SessionBuffer()
        
        # Should not raise an exception
        buffer.clear_session(999)
    
    def test_clear_all(self):
        """Test clearing all sessions."""
        buffer = SessionBuffer()
        
        # Add messages to multiple sessions
        buffer.add_message(100, ChatMessage(id=1, session_id=100, role='user', content='Session 100', created_at=datetime.now()))
        buffer.add_message(200, ChatMessage(id=2, session_id=200, role='user', content='Session 200', created_at=datetime.now()))
        buffer.add_message(300, ChatMessage(id=3, session_id=300, role='user', content='Session 300', created_at=datetime.now()))
        
        assert buffer.get_session_count() == 3
        
        # Clear all
        buffer.clear_all()
        
        assert buffer.get_session_count() == 0
        assert buffer.get_messages(100) == []
        assert buffer.get_messages(200) == []
        assert buffer.get_messages(300) == []
    
    def test_has_session(self):
        """Test checking if session exists."""
        buffer = SessionBuffer()
        
        assert not buffer.has_session(100)
        
        buffer.add_message(100, ChatMessage(id=1, session_id=100, role='user', content='Test', created_at=datetime.now()))
        
        assert buffer.has_session(100)
        assert not buffer.has_session(200)
    
    def test_message_ordering(self):
        """Test that messages maintain insertion order."""
        buffer = SessionBuffer()
        
        # Add messages in specific order
        for i in range(5):
            buffer.add_message(100, ChatMessage(
                id=i,
                session_id=100,
                role='user',
                content=f'Message {i}',
                created_at=datetime.now()
            ))
        
        messages = buffer.get_messages(100)
        
        # Verify order is maintained
        for i, msg in enumerate(messages):
            assert msg.content == f'Message {i}'


class TestGetSessionBuffer:
    """Test global session buffer singleton."""
    
    def test_get_session_buffer_singleton(self):
        """Test that get_session_buffer returns same instance."""
        buffer1 = get_session_buffer()
        buffer2 = get_session_buffer()
        
        assert buffer1 is buffer2
    
    def test_get_session_buffer_state_persists(self):
        """Test that buffer state persists across get_session_buffer calls."""
        buffer1 = get_session_buffer()
        buffer1.add_message(100, ChatMessage(id=1, session_id=100, role='user', content='Test', created_at=datetime.now()))
        
        buffer2 = get_session_buffer()
        messages = buffer2.get_messages(100)
        
        assert len(messages) == 1
        assert messages[0].content == 'Test'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

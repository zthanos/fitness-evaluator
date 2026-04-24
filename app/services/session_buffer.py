"""Active Session Buffer Management

In-memory storage for current chat session messages.
Provides fast access to recent conversation context.

Requirements: 1.1, 1.3
"""
import logging
from typing import Dict, List
from app.models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


class SessionBuffer:
    """
    Active Session Buffer for in-memory message storage.
    
    Stores messages from the current chat session for immediate access.
    Buffer is cleared when session ends or user navigates away.
    
    Requirements: 1.1, 1.3
    """
    
    def __init__(self):
        """Initialize empty session buffer."""
        # Dictionary mapping session_id to list of messages
        self._buffers: Dict[int, List[ChatMessage]] = {}
        logger.debug("Initialized")
    
    def add_message(self, session_id: int, message: ChatMessage) -> None:
        """
        Add a message to the active session buffer.
        
        Args:
            session_id: Session ID
            message: ChatMessage instance
            
        Requirements: 1.1
        """
        if session_id not in self._buffers:
            self._buffers[session_id] = []
        
        self._buffers[session_id].append(message)
        logger.debug("Added message to session %d (total: %d)", session_id, len(self._buffers[session_id]))
    
    def get_messages(self, session_id: int) -> List[ChatMessage]:
        """
        Retrieve all messages from the active session buffer.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of ChatMessage instances (ordered by creation time)
            
        Requirements: 1.1, 1.3
        """
        messages = self._buffers.get(session_id, [])
        logger.debug("Retrieved %d messages for session %d", len(messages), session_id)
        return messages
    
    def clear_session(self, session_id: int) -> None:
        """
        Clear the buffer for a specific session.
        
        Args:
            session_id: Session ID
            
        Requirements: 1.3
        """
        if session_id in self._buffers:
            message_count = len(self._buffers[session_id])
            del self._buffers[session_id]
            logger.debug("Cleared %d messages for session %d", message_count, session_id)
        else:
            logger.debug("No buffer found for session %d", session_id)
    
    def clear_all(self) -> None:
        """
        Clear all session buffers.
        
        Useful for cleanup or testing.
        """
        session_count = len(self._buffers)
        self._buffers.clear()
        logger.debug("Cleared all buffers (%d sessions)", session_count)
    
    def get_session_count(self) -> int:
        """
        Get the number of active sessions in the buffer.
        
        Returns:
            Number of active sessions
        """
        return len(self._buffers)
    
    def has_session(self, session_id: int) -> bool:
        """
        Check if a session exists in the buffer.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session exists, False otherwise
        """
        return session_id in self._buffers


# Global session buffer instance
_session_buffer = None


def get_session_buffer() -> SessionBuffer:
    """
    Get the global session buffer instance.
    
    Returns:
        SessionBuffer instance
    """
    global _session_buffer
    if _session_buffer is None:
        _session_buffer = SessionBuffer()
    return _session_buffer

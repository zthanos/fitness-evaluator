"""ChatMessage model for storing individual messages within chat sessions."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class ChatMessage(Base):
    """
    Represents a single message within a chat session.
    
    Messages are ordered by created_at timestamp in ascending order.
    
    Requirements: 17.2, Property 6 (Chat Message Ordering)
    """
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    session = relationship('ChatSession', back_populates='messages')
    
    # Constraints
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name='check_message_role'),
    )
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, role='{self.role}')>"

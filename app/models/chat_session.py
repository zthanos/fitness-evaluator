"""ChatSession model for storing conversation threads."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class ChatSession(Base):
    """
    Represents a chat conversation thread between an athlete and the AI coach.
    
    Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
    """
    __tablename__ = 'chat_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    athlete_id = Column(Integer, ForeignKey('athletes.id', ondelete='CASCADE'), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship('ChatMessage', back_populates='session', cascade='all, delete-orphan', lazy='dynamic')
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, athlete_id={self.athlete_id}, title='{self.title}')>"

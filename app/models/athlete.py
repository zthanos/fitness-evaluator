"""Athlete model for storing athlete profile information."""

from sqlalchemy import Column, Integer, String, Date, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class Athlete(Base):
    """
    Represents an athlete profile with personal information and goals.

    Requirements: 19.1, 19.3, 22
    """
    __tablename__ = 'athletes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Keycloak subject claim — unique per user, set on first login.
    # NULL for legacy single-user records created before auth was introduced.
    keycloak_sub = Column(String(255), nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    date_of_birth = Column(Date, nullable=True)
    current_plan = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chat_sessions = relationship('ChatSession', backref='athlete', cascade='all, delete-orphan', lazy='dynamic')
    strava_token = relationship('StravaToken', back_populates='athlete', uselist=False, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Athlete(id={self.id}, name='{self.name}', email='{self.email}')>"

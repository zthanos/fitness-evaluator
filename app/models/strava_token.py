# app/models/strava_token.py
from sqlalchemy import Column, Integer, LargeBinary, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base, TimestampMixin


class StravaToken(Base, TimestampMixin):
    """
    Stores encrypted Strava OAuth tokens for athletes.
    Tokens are encrypted using Fernet symmetric encryption.
    """
    __tablename__ = "strava_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    access_token_encrypted = Column(LargeBinary, nullable=False)
    refresh_token_encrypted = Column(LargeBinary, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Relationship
    athlete = relationship("Athlete", back_populates="strava_token")

    # Unique constraint - one token per athlete
    __table_args__ = (
        UniqueConstraint('athlete_id', name='uq_strava_tokens_athlete_id'),
    )

    def __repr__(self):
        return f"<StravaToken(athlete_id={self.athlete_id}, expires_at={self.expires_at})>"

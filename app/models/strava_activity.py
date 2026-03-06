from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from app.models.base import Base, TimestampMixin
import uuid

class StravaActivity(Base, TimestampMixin):
    __tablename__ = 'strava_activities'
    
    # Use String(36) for SQLite compatibility instead of UUID
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    strava_id: int = Column(Integer, unique=True, nullable=False)
    activity_type: str = Column(String(50), nullable=False)
    start_date: datetime = Column(DateTime, nullable=False)
    moving_time_s: int = Column(Integer, nullable=True)
    distance_m: float = Column(Float, nullable=True)
    elevation_m: float = Column(Float, nullable=True)
    avg_hr: int = Column(Integer, nullable=True)
    max_hr: int = Column(Integer, nullable=True)
    calories: float = Column(Float, nullable=True)
    raw_json: dict = Column(Text, nullable=False)
    week_id: str = Column(String(36), nullable=True)
    
    # Add unique constraint for strava_id
    __table_args__ = (
        UniqueConstraint('strava_id'),
    )

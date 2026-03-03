from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import Base, TimestampMixin
import uuid

class StravaActivity(Base, TimestampMixin):
    __tablename__ = 'strava_activities'
    
    id: uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strava_id: int = Column(Integer, unique=True, nullable=False)
    activity_type: str = Column(String(50), nullable=False)
    start_date: datetime = Column(DateTime, nullable=False)
    moving_time_s: int = Column(Integer, nullable=True)
    distance_m: float = Column(Float, nullable=True)
    elevation_m: float = Column(Float, nullable=True)
    avg_hr: int = Column(Integer, nullable=True)
    max_hr: int = Column(Integer, nullable=True)
    raw_json: dict = Column(Text, nullable=False)
    week_id: uuid.UUID = Column(PG_UUID(as_uuid=True), nullable=True)
    
    # Add unique constraint for strava_id
    __table_args__ = (
        UniqueConstraint('strava_id'),
    )

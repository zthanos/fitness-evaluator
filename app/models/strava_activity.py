from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, ForeignKey, event
from sqlalchemy.orm import relationship, validates
from app.models.base import Base, TimestampMixin
import uuid
import re

class StravaActivity(Base, TimestampMixin):
    __tablename__ = 'strava_activities'
    
    # Use String(36) for SQLite compatibility instead of UUID
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: int = Column(Integer, ForeignKey("athletes.id"), nullable=True)  # Added for v2 platform
    strava_id: int = Column(BigInteger, unique=True, nullable=False)
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
    # v1 enrichment fields (extracted from raw_json on sync)
    avg_cadence: float = Column(Float, nullable=True)
    max_cadence: float = Column(Float, nullable=True)
    avg_watts: float = Column(Float, nullable=True)
    max_watts: float = Column(Float, nullable=True)
    weighted_avg_watts: float = Column(Float, nullable=True)
    kilojoules: float = Column(Float, nullable=True)
    suffer_score: int = Column(Integer, nullable=True)
    trainer: bool = Column(Integer, nullable=True)   # stored as 0/1 for SQLite compat
    sport_type: str = Column(String(50), nullable=True)
    
    # Relationship to analysis
    analysis = relationship("ActivityAnalysis", back_populates="activity", uselist=False, cascade="all, delete-orphan")
    
    # Add unique constraint for strava_id
    __table_args__ = (
        UniqueConstraint('strava_id'),
    )
    
    @validates('week_id')
    def validate_week_id(self, key, value):
        """Validate week_id format matches ISO week format: YYYY-WW"""
        if value is not None:
            pattern = r'^\d{4}-W\d{2}$'
            if not re.match(pattern, value):
                raise ValueError(f"week_id must match format YYYY-WW (e.g., '2024-W15'), got: {value}")
        return value
    
    @staticmethod
    def compute_week_id(start_date: datetime) -> str:
        """Compute ISO week_id from start_date.
        
        Args:
            start_date: The activity start date
            
        Returns:
            ISO week identifier in format YYYY-WW (e.g., "2024-W15")
        """
        iso_calendar = start_date.isocalendar()
        year = iso_calendar[0]
        week = iso_calendar[1]
        return f"{year}-W{week:02d}"
    
    def populate_week_id(self):
        """Automatically populate week_id from start_date if not already set."""
        if self.start_date and not self.week_id:
            self.week_id = self.compute_week_id(self.start_date)


# SQLAlchemy event listener to automatically populate week_id before insert/update
@event.listens_for(StravaActivity, 'before_insert')
@event.listens_for(StravaActivity, 'before_update')
def populate_week_id_on_save(mapper, connection, target):
    """Automatically populate week_id from start_date when saving."""
    if target.start_date and not target.week_id:
        target.week_id = StravaActivity.compute_week_id(target.start_date)

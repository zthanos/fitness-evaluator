from datetime import date
from sqlalchemy import Column, Date, Float, Integer, Text, UUID, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import Base, TimestampMixin
import uuid

class DailyLog(Base, TimestampMixin):
    __tablename__ = 'daily_logs'
    
    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    log_date: date = Column(Date, unique=True, nullable=False)
    fasting_hours: float = Column(Float, nullable=True)
    calories_in: int = Column(Integer, nullable=True)
    protein_g: float = Column(Float, nullable=True)
    carbs_g: float = Column(Float, nullable=True)
    fat_g: float = Column(Float, nullable=True)
    adherence_score: int = Column(Integer, nullable=True)
    notes: str = Column(Text, nullable=True)
    week_id: uuid.UUID = Column(UUID(as_uuid=True), nullable=True)
    
    # Add check constraint for adherence_score (1-10 range)
    __table_args__ = (
        CheckConstraint('adherence_score >= 1 AND adherence_score <= 10', name='check_adherence_score_range'),
    )

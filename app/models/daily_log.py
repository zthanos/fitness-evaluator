from datetime import date
from sqlalchemy import Column, Date, Float, Integer, Text, String, CheckConstraint
from app.models.base import Base, TimestampMixin
import uuid

class DailyLog(Base, TimestampMixin):
    __tablename__ = 'daily_logs'
    
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    log_date: date = Column(Date, unique=True, nullable=False)
    fasting_hours: float = Column(Float, nullable=True)
    calories_in: int = Column(Integer, nullable=True)
    protein_g: float = Column(Float, nullable=True)
    carbs_g: float = Column(Float, nullable=True)
    fat_g: float = Column(Float, nullable=True)
    adherence_score: int = Column(Integer, nullable=True)
    notes: str = Column(Text, nullable=True)
    week_id: str = Column(String(36), nullable=True)
    
    # Add check constraints per Requirements 8.2
    __table_args__ = (
        CheckConstraint('adherence_score >= 0 AND adherence_score <= 100', name='check_adherence_score_range'),
        CheckConstraint('calories_in >= 0 AND calories_in <= 10000', name='check_calories_range'),
        CheckConstraint('protein_g >= 0 AND protein_g <= 1000', name='check_protein_range'),
        CheckConstraint('carbs_g >= 0 AND carbs_g <= 1000', name='check_carbs_range'),
        CheckConstraint('fat_g >= 0 AND fat_g <= 1000', name='check_fat_range'),
    )

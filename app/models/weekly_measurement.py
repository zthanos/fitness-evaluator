from datetime import date
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from app.models.base import Base, TimestampMixin
import uuid

class WeeklyMeasurement(Base, TimestampMixin):
    __tablename__ = 'weekly_measurements'

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: int = Column(Integer, ForeignKey('athletes.id', ondelete='CASCADE'), nullable=True, index=True)
    week_start: date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint('athlete_id', 'week_start', name='uq_weekly_measurements_athlete_week'),
    )
    weight_kg: float = Column(Float, nullable=True)
    weight_prev_kg: float = Column(Float, nullable=True)
    body_fat_pct: float = Column(Float, nullable=True)
    waist_cm: float = Column(Float, nullable=True)
    waist_prev_cm: float = Column(Float, nullable=True)
    sleep_avg_hrs: float = Column(Float, nullable=True)
    rhr_bpm: int = Column(Integer, nullable=True)
    energy_level_avg: float = Column(Float, nullable=True)

from datetime import date
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, Text, String
from app.models.base import Base, TimestampMixin
import uuid

class PlanTargets(Base, TimestampMixin):
    __tablename__ = 'plan_targets'

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: int = Column(Integer, ForeignKey('athletes.id', ondelete='CASCADE'), nullable=True, index=True)
    effective_from: date = Column(Date, nullable=False)
    target_calories: int = Column(Integer, nullable=True)
    target_protein_g: float = Column(Float, nullable=True)
    target_fasting_hrs: float = Column(Float, nullable=True)
    target_run_km_wk: float = Column(Float, nullable=True)
    target_strength_sessions: int = Column(Integer, nullable=True)
    target_weight_kg: float = Column(Float, nullable=True)
    notes: str = Column(Text, nullable=True)

from datetime import date
from sqlalchemy import Column, Date, Float, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import Base, TimestampMixin
import uuid

class PlanTargets(Base, TimestampMixin):
    __tablename__ = 'plan_targets'
    
    id: uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effective_from: date = Column(Date, nullable=False)
    target_calories: int = Column(Integer, nullable=True)
    target_protein_g: float = Column(Float, nullable=True)
    target_fasting_hrs: float = Column(Float, nullable=True)
    target_run_km_wk: float = Column(Float, nullable=True)
    target_strength_sessions: int = Column(Integer, nullable=True)
    target_weight_kg: float = Column(Float, nullable=True)
    notes: str = Column(Text, nullable=True)

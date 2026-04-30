"""Persisted structured fitness state — one row per athlete, upserted by FitnessStateBuilder."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.models.base import Base, TimestampMixin


class AthleteFitnessState(Base, TimestampMixin):
    __tablename__ = "athlete_fitness_states"

    athlete_id: int = Column(Integer, ForeignKey("athletes.id", ondelete="CASCADE"),
                             primary_key=True)

    # Cadence profile (rpm)
    comfort_cadence_indoor: float  = Column(Float, nullable=True)
    comfort_cadence_outdoor: float = Column(Float, nullable=True)
    climbing_cadence: float        = Column(Float, nullable=True)

    # Current limiter — free-text token, e.g. "outdoor_transfer", "aerobic_base"
    current_limiter: str           = Column(String(100), nullable=True)
    limiter_confidence: float      = Column(Float, nullable=True, default=0.0)

    # Load & fatigue
    fatigue_level: str             = Column(String(20), nullable=True)   # low/moderate/high/overreaching
    weekly_consistency: float      = Column(Float, nullable=True)        # 0-1
    acwr_ratio: float              = Column(Float, nullable=True)

    # HR trends
    hr_response_trend: str         = Column(String(20), nullable=True)   # improving/stable/degrading
    rhr_trend: str                 = Column(String(20), nullable=True)

    # Meta
    state_confidence: float        = Column(Float, nullable=True, default=0.0)
    last_updated_at: datetime      = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Generated view (not primary truth — derived from the structured fields above)
    summary_text: str              = Column(Text, nullable=True)

    # Composite score (0-100) and activity-based classification
    fitness_score: float           = Column(Float, nullable=True)
    athlete_classification: str    = Column(String(100), nullable=True)

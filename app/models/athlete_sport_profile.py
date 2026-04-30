"""Per-sport performance profile — one row per (athlete, sport_group), upserted by SportProfileBuilder."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from app.models.base import Base


class AthleteSportProfile(Base):
    __tablename__ = "athlete_sport_profiles"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    athlete_id: int = Column(Integer, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True)
    sport_group: str = Column(String(20), nullable=False)  # ride | run | swim | strength

    # Distance & speed
    longest_distance_km: float        = Column(Float, nullable=True)
    best_60min_distance_km: float     = Column(Float, nullable=True)
    best_120min_distance_km: float    = Column(Float, nullable=True)
    typical_endurance_speed_kmh: float = Column(Float, nullable=True)
    best_long_speed_kmh: float        = Column(Float, nullable=True)

    # Volume (4-week rolling average)
    weekly_volume_km: float           = Column(Float, nullable=True)
    weekly_training_time_min: float   = Column(Float, nullable=True)

    # Cadence (rpm)
    typical_cadence_rpm: float        = Column(Float, nullable=True)
    indoor_cadence_rpm: float         = Column(Float, nullable=True)
    outdoor_cadence_rpm: float        = Column(Float, nullable=True)
    climbing_cadence_rpm: float       = Column(Float, nullable=True)

    # Power — cycling only
    ftp_estimate_w: float             = Column(Float, nullable=True)
    ftp_confidence: str               = Column(String(10), nullable=True)  # high | medium | low
    avg_power_baseline_w: float       = Column(Float, nullable=True)
    best_weighted_power_w: float      = Column(Float, nullable=True)

    # Heart rate
    max_hr_estimate: int              = Column(Integer, nullable=True)
    hr_zone_model: dict               = Column(JSON, nullable=True)

    # Pace zones — running only
    pace_zone_model: dict             = Column(JSON, nullable=True)

    # Coaching insights
    current_strengths: list           = Column(JSON, nullable=True)
    current_limiters: list            = Column(JSON, nullable=True)
    profile_confidence: float         = Column(Float, nullable=True)
    last_updated_at: datetime         = Column(DateTime, nullable=False, default=datetime.utcnow)
    summary_text: str                 = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("athlete_id", "sport_group", name="uq_athlete_sport_group"),
    )

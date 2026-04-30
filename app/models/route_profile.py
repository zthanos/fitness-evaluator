"""Route profile — one row per uploaded GPX, persisted after RouteAnalyzer runs."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from app.models.base import Base


class RouteProfile(Base):
    __tablename__ = "route_profiles"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    athlete_id: int = Column(Integer, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source
    filename: str         = Column(String(255), nullable=True)
    sport: str            = Column(String(20),  nullable=False)  # ride | run
    gpx_hash: str         = Column(String(64),  nullable=True, index=True)  # SHA-256 for dedup

    # Core metrics
    distance_km: float            = Column(Float, nullable=True)
    total_elevation_gain_m: float = Column(Float, nullable=True)
    total_elevation_loss_m: float = Column(Float, nullable=True)
    max_elevation_m: float        = Column(Float, nullable=True)
    min_elevation_m: float        = Column(Float, nullable=True)
    max_gradient_pct: float       = Column(Float, nullable=True)
    avg_climb_gradient_pct: float = Column(Float, nullable=True)

    # Difficulty
    difficulty_score: float = Column(Float, nullable=True)   # 0–100
    route_difficulty: str   = Column(String(20), nullable=True)  # easy | moderate | hard | extreme

    # Segment detail (JSON arrays)
    climb_segments:    list = Column(JSON, nullable=True)
    descent_segments:  list = Column(JSON, nullable=True)
    flat_segments:     list = Column(JSON, nullable=True)
    critical_sections: list = Column(JSON, nullable=True)
    elevation_profile: list = Column(JSON, nullable=True)  # [{dist_km, elev_m}, …]

    # Human-readable summary for LLM context
    analysis_summary: str = Column(Text, nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

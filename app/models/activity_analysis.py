"""Activity Analysis model for AI-generated effort analysis."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class ActivityAnalysis(Base):
    """
    Activity Analysis model.
    
    Stores AI-generated effort analysis for activities.
    Each activity can have one analysis (unique constraint on activity_id).
    """
    
    __tablename__ = "activity_analyses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String(36), ForeignKey("strava_activities.id", ondelete="CASCADE"), nullable=False, unique=True)
    analysis_text = Column(Text, nullable=False)
    generated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    
    # Relationship to activity
    activity = relationship("StravaActivity", back_populates="analysis")
    
    def __repr__(self):
        return f"<ActivityAnalysis(id={self.id}, activity_id={self.activity_id})>"

"""Evaluation Model

Represents performance evaluation reports for athletes.
Stores evaluation data with scores, strengths, improvements, tips, and recommendations.
"""
from datetime import date, datetime
from sqlalchemy import Column, String, Integer, Date, Text, Float, JSON
from app.models.base import Base, TimestampMixin
import uuid


class Evaluation(Base, TimestampMixin):
    """
    Evaluation Model
    
    Stores performance evaluation reports generated for athletes over specific time periods.
    Includes scores, strengths, areas for improvement, tips, and exercise recommendations.
    
    Attributes:
        id: Unique identifier (UUID)
        athlete_id: Reference to athlete
        period_start: Start date of evaluation period
        period_end: End date of evaluation period
        period_type: Type of period ('weekly', 'bi-weekly', 'monthly')
        overall_score: Overall performance score (0-100)
        strengths: JSON array of identified strengths
        improvements: JSON array of areas for improvement
        tips: JSON array of actionable tips
        recommended_exercises: JSON array of recommended exercises
        goal_alignment: Text assessment of goal progress
        confidence_score: Confidence in evaluation (0.0-1.0)
        created_at: Timestamp when evaluation was created
        updated_at: Timestamp when evaluation was last updated
    """
    
    __tablename__ = 'evaluations'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id = Column(Integer, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    period_type = Column(String(20), nullable=False)
    overall_score = Column(Integer, nullable=False)
    strengths = Column(JSON, nullable=False)
    improvements = Column(JSON, nullable=False)
    tips = Column(JSON, nullable=False)
    recommended_exercises = Column(JSON, nullable=False)
    goal_alignment = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    
    def __repr__(self):
        return f"<Evaluation(id={self.id}, athlete_id={self.athlete_id}, score={self.overall_score})>"
    
    def to_dict(self):
        """Convert evaluation to dictionary for API responses."""
        return {
            'id': self.id,
            'athlete_id': self.athlete_id,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'period_type': self.period_type,
            'overall_score': self.overall_score,
            'strengths': self.strengths,
            'improvements': self.improvements,
            'tips': self.tips,
            'recommended_exercises': self.recommended_exercises,
            'goal_alignment': self.goal_alignment,
            'confidence_score': self.confidence_score,
            'generated_at': self.created_at.isoformat() if self.created_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

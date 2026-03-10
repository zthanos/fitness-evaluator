"""Training Plan Session Model

Represents an individual workout within a training plan week.
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class TrainingPlanSession(Base):
    """
    Training Plan Session Model
    
    Stores individual workout sessions within a training plan week.
    Sessions can be automatically matched to Strava activities.
    
    Attributes:
        id: Unique identifier (UUID)
        week_id: Reference to parent training plan week
        day_of_week: Day of week (1=Monday, 7=Sunday)
        session_type: Type of session (e.g., "easy_run", "interval", "rest")
        duration_minutes: Planned duration in minutes
        intensity: Intensity level (easy, moderate, hard, recovery)
        description: Detailed session description
        completed: Whether session has been completed
        matched_activity_id: Reference to matched Strava activity
    """
    
    __tablename__ = 'training_plan_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    week_id = Column(String(36), ForeignKey('training_plan_weeks.id', ondelete='CASCADE'), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    session_type = Column(String(50), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    intensity = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, nullable=False, default=False)
    matched_activity_id = Column(String(36), ForeignKey('strava_activities.id', ondelete='SET NULL'), nullable=True)
    
    # Relationships
    week = relationship('TrainingPlanWeek', back_populates='sessions')
    matched_activity = relationship('StravaActivity', backref='matched_sessions')
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('day_of_week >= 1 AND day_of_week <= 7', name='check_day_of_week'),
        Index('idx_training_plan_sessions_week_id', 'week_id'),
        Index('idx_training_plan_sessions_completed', 'completed'),
        Index('idx_training_plan_sessions_matched_activity', 'matched_activity_id'),
    )
    
    def __repr__(self):
        return f"<TrainingPlanSession(id={self.id}, week_id={self.week_id}, day_of_week={self.day_of_week}, session_type={self.session_type}, completed={self.completed})>"
    
    def validate(self):
        """Validate training plan session data integrity."""
        errors = []
        
        # Validate day_of_week (constraint also enforced at DB level)
        if not (1 <= self.day_of_week <= 7):
            errors.append("day_of_week must be between 1 and 7")
        
        # Validate session_type
        valid_session_types = [
            'easy_run', 'tempo_run', 'interval', 'long_run', 'recovery_run',
            'easy_ride', 'tempo_ride', 'interval_ride', 'long_ride',
            'swim_technique', 'swim_endurance', 'swim_interval',
            'rest', 'cross_training', 'strength'
        ]
        if self.session_type not in valid_session_types:
            errors.append(f"Invalid session_type: {self.session_type}. Must be one of {valid_session_types}")
        
        # Validate duration_minutes
        if self.duration_minutes < 0:
            errors.append("duration_minutes must be >= 0")
        
        # Validate intensity
        valid_intensities = ['recovery', 'easy', 'moderate', 'hard', 'max']
        if self.intensity not in valid_intensities:
            errors.append(f"Invalid intensity: {self.intensity}. Must be one of {valid_intensities}")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        return True
    
    def to_dict(self):
        """Convert session to dictionary for API responses."""
        return {
            'id': self.id,
            'week_id': self.week_id,
            'day_of_week': self.day_of_week,
            'session_type': self.session_type,
            'duration_minutes': self.duration_minutes,
            'intensity': self.intensity,
            'description': self.description,
            'completed': self.completed,
            'matched_activity_id': self.matched_activity_id,
        }

"""Training Plan Week Model

Represents a single week within a training plan with focus and volume targets.
"""
from sqlalchemy import Column, String, Integer, Float, ForeignKey, UniqueConstraint, Index, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class TrainingPlanWeek(Base):
    """
    Training Plan Week Model
    
    Stores weekly structure within a training plan.
    Each week has a focus area and volume target.
    
    Attributes:
        id: Unique identifier (UUID)
        plan_id: Reference to parent training plan
        week_number: Week number within the plan (1-indexed)
        focus: Weekly focus description (e.g., "Base building", "Intensity")
        volume_target: Target training volume in hours
    """
    
    __tablename__ = 'training_plan_weeks'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(36), ForeignKey('training_plans.id', ondelete='CASCADE'), nullable=False, index=True)
    week_number = Column(Integer, nullable=False)
    phase = Column(String(20), nullable=True)           # base | specific | taper
    focus = Column(String(500), nullable=True)
    volume_target = Column(Float, nullable=True)
    distance_target_km = Column(Float, nullable=True)  # target long-session km this week
    
    # Relationships
    plan = relationship('TrainingPlan', back_populates='weeks')
    sessions = relationship('TrainingPlanSession', back_populates='week', cascade='all, delete-orphan', order_by='TrainingPlanSession.day_of_week')
    
    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('plan_id', 'week_number', name='uq_plan_week'),
        Index('idx_training_plan_weeks_plan_id', 'plan_id'),
    )
    
    def __repr__(self):
        return f"<TrainingPlanWeek(id={self.id}, plan_id={self.plan_id}, week_number={self.week_number}, focus={self.focus})>"
    
    def validate(self):
        """Validate training plan week data integrity."""
        errors = []
        
        # Validate week_number
        if self.week_number < 1:
            errors.append("week_number must be >= 1")
        
        # Validate volume_target
        if self.volume_target is not None and self.volume_target < 0:
            errors.append("volume_target must be >= 0")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        return True
    
    def to_dict(self):
        """Convert week to dictionary for API responses."""
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'week_number': self.week_number,
            'focus': self.focus,
            'volume_target': self.volume_target,
        }

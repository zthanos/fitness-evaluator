"""Athlete Goal Model

Represents fitness goals set by athletes with LLM assistance.
Supports various goal types and tracks progress status.
"""
from datetime import date, datetime
from sqlalchemy import Column, String, Float, Date, Text, Enum as SQLEnum
from app.models.base import Base, TimestampMixin
import uuid
import enum


class GoalType(str, enum.Enum):
    """Goal type enumeration."""
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_GAIN = "weight_gain"
    PERFORMANCE = "performance"
    ENDURANCE = "endurance"
    STRENGTH = "strength"
    CUSTOM = "custom"


class GoalStatus(str, enum.Enum):
    """Goal status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class AthleteGoal(Base, TimestampMixin):
    """
    Athlete Goal Model
    
    Stores fitness goals set by athletes through LLM-assisted conversation.
    The LLM asks clarifying questions and uses tool calling to save structured goals.
    
    Attributes:
        id: Unique identifier (UUID)
        athlete_id: Reference to athlete (for future multi-athlete support)
        goal_type: Type of goal (weight_loss, weight_gain, performance, etc.)
        target_value: Numeric target (e.g., target weight, distance, time)
        target_date: Target completion date
        description: Detailed goal description from conversation
        status: Current status (active, completed, abandoned)
        created_at: Timestamp when goal was created
        updated_at: Timestamp when goal was last updated
    """
    
    __tablename__ = 'athlete_goals'
    
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: str = Column(String(36), nullable=True)  # For future multi-athlete support
    goal_type: str = Column(String(50), nullable=False)
    target_value: float = Column(Float, nullable=True)
    target_date: date = Column(Date, nullable=True)
    description: str = Column(Text, nullable=False)
    status: str = Column(String(20), nullable=False, default=GoalStatus.ACTIVE.value)
    
    def __repr__(self):
        return f"<AthleteGoal(id={self.id}, type={self.goal_type}, status={self.status})>"
    
    def to_dict(self):
        """Convert goal to dictionary for API responses."""
        return {
            'id': self.id,
            'athlete_id': self.athlete_id,
            'goal_type': self.goal_type,
            'target_value': self.target_value,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

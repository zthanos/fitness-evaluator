from sqlalchemy import Column, ForeignKey, Integer, String, Text, CheckConstraint
from app.models.base import Base, TimestampMixin
import uuid


class MealTemplate(Base, TimestampMixin):
    __tablename__ = 'meal_templates'

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: int = Column(Integer, ForeignKey('athletes.id', ondelete='CASCADE'), nullable=False, index=True)
    name: str = Column(String(200), nullable=False)
    meal_type: str = Column(String(20), nullable=True)  # default meal type suggestion
    items_json: str = Column(Text, nullable=False)  # JSON array of item snapshots

    __table_args__ = (
        CheckConstraint(
            "meal_type IS NULL OR meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name='check_template_meal_type'
        ),
    )

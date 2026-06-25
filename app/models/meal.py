from datetime import date
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, Boolean, Text, CheckConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Meal(Base, TimestampMixin):
    __tablename__ = 'meals'

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: int = Column(Integer, ForeignKey('athletes.id', ondelete='CASCADE'), nullable=False, index=True)
    log_date: date = Column(Date, nullable=False, index=True)
    meal_type: str = Column(String(20), nullable=False)  # breakfast, lunch, dinner, snack
    name: str = Column(String(200), nullable=True)

    items = relationship('MealItem', back_populates='meal', cascade='all, delete-orphan', lazy='joined')

    __table_args__ = (
        CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name='check_meal_type'
        ),
    )


class MealItem(Base, TimestampMixin):
    __tablename__ = 'meal_items'

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meal_id: str = Column(String(36), ForeignKey('meals.id', ondelete='CASCADE'), nullable=False, index=True)
    name: str = Column(String(200), nullable=False)
    quantity: float = Column(Float, nullable=True)
    unit: str = Column(String(50), nullable=True)
    calories: float = Column(Float, nullable=True)
    protein_g: float = Column(Float, nullable=True)
    carbs_g: float = Column(Float, nullable=True)
    fat_g: float = Column(Float, nullable=True)
    source: str = Column(String(20), nullable=False, default='manual')  # manual | ai | product_search | template
    confidence: float = Column(Float, nullable=False, default=1.0)
    needs_confirmation: bool = Column(Boolean, nullable=False, default=False)
    source_ref: str = Column(String(500), nullable=True)  # URL or product ID for product_search

    meal = relationship('Meal', back_populates='items')

    __table_args__ = (
        CheckConstraint(
            "source IN ('manual', 'ai', 'product_search', 'template')",
            name='check_meal_item_source'
        ),
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='check_meal_item_confidence'),
    )

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


MealType = Literal['breakfast', 'lunch', 'dinner', 'snack']
ItemSource = Literal['manual', 'ai', 'product_search', 'template']


# --- MealItem ---

class MealItemCreate(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    source: ItemSource = 'manual'
    confidence: float = Field(default=1.0, ge=0, le=1)
    needs_confirmation: bool = False
    source_ref: Optional[str] = None


class MealItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    needs_confirmation: Optional[bool] = None


class MealItemResponse(BaseModel):
    id: str
    meal_id: str
    name: str
    quantity: Optional[float]
    unit: Optional[str]
    calories: Optional[float]
    protein_g: Optional[float]
    carbs_g: Optional[float]
    fat_g: Optional[float]
    source: str
    confidence: float
    needs_confirmation: bool
    source_ref: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Meal ---

class MealCreate(BaseModel):
    log_date: date
    meal_type: MealType
    name: Optional[str] = None
    items: list[MealItemCreate] = []


class MealUpdate(BaseModel):
    meal_type: Optional[MealType] = None
    name: Optional[str] = None


class MealTotals(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    item_count: int
    confirmed_count: int
    estimated_count: int


class MealResponse(BaseModel):
    id: str
    log_date: date
    meal_type: str
    name: Optional[str]
    items: list[MealItemResponse]
    totals: MealTotals
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- DayLog aggregate ---

class DayTotals(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_count: int
    item_count: int
    confidence_score: float  # ratio confirmed / total items


class DayLogResponse(BaseModel):
    log_date: date
    meals: list[MealResponse]
    totals: DayTotals


# --- MealTemplate ---

class MealTemplateCreate(BaseModel):
    name: str
    meal_type: Optional[MealType] = None
    items: list[MealItemCreate]


class MealTemplateResponse(BaseModel):
    id: str
    name: str
    meal_type: Optional[str]
    items: list[MealItemCreate]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

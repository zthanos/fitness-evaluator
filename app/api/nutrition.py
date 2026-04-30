"""Nutrition tracking endpoints — meals, items, day aggregates, templates."""

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete
from app.models.meal import Meal, MealItem
from app.models.meal_template import MealTemplate
from app.models.daily_log import DailyLog
from app.schemas.nutrition_schemas import (
    MealCreate,
    MealUpdate,
    MealItemCreate,
    MealItemUpdate,
    MealItemResponse,
    MealResponse,
    MealTotals,
    DayLogResponse,
    DayTotals,
    MealTemplateCreate,
    MealTemplateResponse,
)
from app.ai.skills.meal_analyzer import MealAnalyzerSkill, MealAnalysisResult
from app.services.food_search import FoodSearchService, FoodProduct

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _meal_totals(items: list[MealItem]) -> MealTotals:
    confirmed = [i for i in items if not i.needs_confirmation]
    estimated = [i for i in items if i.needs_confirmation]
    return MealTotals(
        calories=sum(i.calories or 0 for i in items),
        protein_g=sum(i.protein_g or 0 for i in items),
        carbs_g=sum(i.carbs_g or 0 for i in items),
        fat_g=sum(i.fat_g or 0 for i in items),
        item_count=len(items),
        confirmed_count=len(confirmed),
        estimated_count=len(estimated),
    )


def _meal_to_response(meal: Meal) -> MealResponse:
    return MealResponse(
        id=meal.id,
        log_date=meal.log_date,
        meal_type=meal.meal_type,
        name=meal.name,
        items=[MealItemResponse.model_validate(i) for i in meal.items],
        totals=_meal_totals(meal.items),
        created_at=meal.created_at,
        updated_at=meal.updated_at,
    )


def _day_totals(meals: list[Meal]) -> DayTotals:
    all_items = [item for m in meals for item in m.items]
    confirmed_items = [i for i in all_items if not i.needs_confirmation]
    confidence = len(confirmed_items) / len(all_items) if all_items else 1.0
    return DayTotals(
        calories=sum(i.calories or 0 for i in all_items),
        protein_g=sum(i.protein_g or 0 for i in all_items),
        carbs_g=sum(i.carbs_g or 0 for i in all_items),
        fat_g=sum(i.fat_g or 0 for i in all_items),
        meal_count=len(meals),
        item_count=len(all_items),
        confidence_score=round(confidence, 3),
    )


def _get_meal_or_404(meal_id: str, athlete_id: int, db: Session) -> Meal:
    meal = db.query(Meal).filter(
        Meal.id == meal_id,
        Meal.athlete_id == athlete_id,
    ).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    return meal


def _get_item_or_404(item_id: str, meal: Meal, db: Session) -> MealItem:
    item = db.query(MealItem).filter(
        MealItem.id == item_id,
        MealItem.meal_id == meal.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Meal item not found")
    return item


def _sync_daily_log(athlete_id: int, log_date: date, db: Session) -> None:
    """Recalculate macro totals from all meal items and upsert into DailyLog."""
    meals = db.query(Meal).filter(
        Meal.athlete_id == athlete_id,
        Meal.log_date == log_date,
    ).all()
    all_items = [item for m in meals for item in m.items]

    total_calories = round(sum(i.calories or 0 for i in all_items))
    total_protein  = round(sum(i.protein_g or 0 for i in all_items), 1)
    total_carbs    = round(sum(i.carbs_g or 0 for i in all_items), 1)
    total_fat      = round(sum(i.fat_g or 0 for i in all_items), 1)

    existing = db.query(DailyLog).filter(
        DailyLog.athlete_id == athlete_id,
        DailyLog.log_date == log_date,
    ).first()

    if existing:
        existing.calories_in = total_calories
        existing.protein_g   = total_protein
        existing.carbs_g     = total_carbs
        existing.fat_g       = total_fat
    else:
        db.add(DailyLog(
            athlete_id=athlete_id,
            log_date=log_date,
            calories_in=total_calories,
            protein_g=total_protein,
            carbs_g=total_carbs,
            fat_g=total_fat,
        ))
    db.commit()


# ---------------------------------------------------------------------------
# Day log (aggregate, computed on the fly)
# ---------------------------------------------------------------------------

@router.get("/day/{log_date}", response_model=DayLogResponse, summary="Get full day log with meals and totals")
async def get_day_log(
    log_date: date,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meals = (
        db.query(Meal)
        .filter(Meal.athlete_id == athlete.id, Meal.log_date == log_date)
        .order_by(Meal.created_at)
        .all()
    )
    return DayLogResponse(
        log_date=log_date,
        meals=[_meal_to_response(m) for m in meals],
        totals=_day_totals(meals),
    )


# ---------------------------------------------------------------------------
# Meals
# ---------------------------------------------------------------------------

@router.post("/meals", response_model=MealResponse, status_code=201, summary="Create meal with optional items")
async def create_meal(
    payload: MealCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meal = Meal(
        athlete_id=athlete.id,
        log_date=payload.log_date,
        meal_type=payload.meal_type,
        name=payload.name,
    )
    db.add(meal)
    db.flush()

    for item_data in payload.items:
        item = MealItem(meal_id=meal.id, **item_data.model_dump())
        db.add(item)

    db.commit()
    db.refresh(meal)
    _sync_daily_log(athlete.id, meal.log_date, db)
    return _meal_to_response(meal)


@router.get("/meals/{meal_id}", response_model=MealResponse, summary="Get meal by ID")
async def get_meal(
    meal_id: str,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meal = _get_meal_or_404(meal_id, athlete.id, db)
    return _meal_to_response(meal)


@router.put("/meals/{meal_id}", response_model=MealResponse, summary="Update meal type or name")
async def update_meal(
    meal_id: str,
    payload: MealUpdate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meal = _get_meal_or_404(meal_id, athlete.id, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(meal, field, value)
    db.commit()
    db.refresh(meal)
    return _meal_to_response(meal)


@router.delete("/meals/{meal_id}", status_code=204, summary="Delete meal and all its items")
async def delete_meal(
    meal_id: str,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meal = _get_meal_or_404(meal_id, athlete.id, db)
    log_date = meal.log_date
    db.delete(meal)
    db.commit()
    _sync_daily_log(athlete.id, log_date, db)


# ---------------------------------------------------------------------------
# Meal items
# ---------------------------------------------------------------------------

@router.post("/meals/{meal_id}/items", response_model=MealItemResponse, status_code=201, summary="Add item to meal")
async def add_meal_item(
    meal_id: str,
    payload: MealItemCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meal = _get_meal_or_404(meal_id, athlete.id, db)
    item = MealItem(meal_id=meal_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    _sync_daily_log(athlete.id, meal.log_date, db)
    return MealItemResponse.model_validate(item)


@router.put("/meals/{meal_id}/items/{item_id}", response_model=MealItemResponse, summary="Update meal item")
async def update_meal_item(
    meal_id: str,
    item_id: str,
    payload: MealItemUpdate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meal = _get_meal_or_404(meal_id, athlete.id, db)
    item = _get_item_or_404(item_id, meal, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    _sync_daily_log(athlete.id, meal.log_date, db)
    return MealItemResponse.model_validate(item)


@router.delete("/meals/{meal_id}/items/{item_id}", status_code=204, summary="Delete meal item")
async def delete_meal_item(
    meal_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    meal = _get_meal_or_404(meal_id, athlete.id, db)
    item = _get_item_or_404(item_id, meal, db)
    db.delete(item)
    db.commit()
    _sync_daily_log(athlete.id, meal.log_date, db)


# ---------------------------------------------------------------------------
# Confirm AI items (bulk)
# ---------------------------------------------------------------------------

class _ConfirmBody(BaseModel):
    item_ids: Optional[list[str]] = None


@router.post("/meals/{meal_id}/confirm", response_model=MealResponse, summary="Confirm all pending AI items in a meal")
async def confirm_meal_items(
    meal_id: str,
    body: _ConfirmBody = _ConfirmBody(),
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """Mark needs_confirmation=False for specified items (or all if item_ids is omitted)."""
    meal = _get_meal_or_404(meal_id, athlete.id, db)
    for item in meal.items:
        if body.item_ids is None or item.id in body.item_ids:
            item.needs_confirmation = False
    db.commit()
    db.refresh(meal)
    return _meal_to_response(meal)


# ---------------------------------------------------------------------------
# Product search (Open Food Facts — no API key required)
# ---------------------------------------------------------------------------

@router.get("/search", response_model=list[FoodProduct], summary="Search food products via Open Food Facts")
async def search_food(
    q: str,
    athlete: Athlete = Depends(get_current_athlete),
):
    if len(q.strip()) < 2:
        raise HTTPException(status_code=422, detail="Query must be at least 2 characters")
    service = FoodSearchService()
    return service.search(q.strip())


# ---------------------------------------------------------------------------
# AI photo analysis
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/analyze-photo", response_model=MealAnalysisResult, summary="Analyze meal photo with AI vision")
async def analyze_meal_photo(
    file: UploadFile = File(...),
    meal_type: str = Form(default="lunch"),
    context: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Upload a meal image and receive AI-estimated nutritional breakdown.
    Items with confidence < 0.7 are flagged needs_confirmation=true.
    Call POST /meals to persist after user review.
    """
    content_type = file.content_type or "image/jpeg"
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {content_type}")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB)")

    skill = MealAnalyzerSkill()
    result = skill.analyze(image_bytes, content_type, user_context=context)

    if result.error:
        raise HTTPException(status_code=502, detail=result.error)

    return result


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@router.post("/templates", response_model=MealTemplateResponse, status_code=201, summary="Save meal as template")
async def create_template(
    payload: MealTemplateCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    items_json = json.dumps([i.model_dump() for i in payload.items])
    template = MealTemplate(
        athlete_id=athlete.id,
        name=payload.name,
        meal_type=payload.meal_type,
        items_json=items_json,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_to_response(template)


@router.get("/templates", response_model=list[MealTemplateResponse], summary="List meal templates")
async def list_templates(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    templates = (
        db.query(MealTemplate)
        .filter(MealTemplate.athlete_id == athlete.id)
        .order_by(MealTemplate.name)
        .all()
    )
    return [_template_to_response(t) for t in templates]


@router.delete("/templates/{template_id}", status_code=204, summary="Delete meal template")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    template = db.query(MealTemplate).filter(
        MealTemplate.id == template_id,
        MealTemplate.athlete_id == athlete.id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()


def _template_to_response(template: MealTemplate) -> MealTemplateResponse:
    from app.schemas.nutrition_schemas import MealItemCreate
    items = [MealItemCreate(**i) for i in json.loads(template.items_json)]
    return MealTemplateResponse(
        id=template.id,
        name=template.name,
        meal_type=template.meal_type,
        items=items,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )

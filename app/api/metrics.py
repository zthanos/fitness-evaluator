"""Metrics API endpoints for body measurements tracking."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models.weekly_measurement import WeeklyMeasurement
from app.schemas.metrics_schemas import (
    BodyMetricCreate,
    BodyMetricUpdate,
    BodyMetricResponse,
)

router = APIRouter()


@router.post("", response_model=BodyMetricResponse, summary="Create body metric record")
async def create_metric(metric: BodyMetricCreate, db: Session = Depends(get_db)):
    """
    Create a new body metric record.
    
    **Requirements: 5.4, 5.5**
    
    **Fields:**
    - `measurement_date`: Date of measurement (YYYY-MM-DD)
    - `weight`: Body weight in kilograms (30-300)
    - `body_fat_pct`: Body fat percentage (3-60) - optional
    - `measurements`: Additional circumference measurements (JSON) - optional
    
    **Validation:**
    - Weight must be between 30kg and 300kg (Requirement 5.2)
    - Body fat percentage must be between 3% and 60% (Requirement 5.3)
    - Specific validation error messages displayed (Requirement 5.7)
    """
    # Check for existing record on the same date
    existing = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.week_start == metric.measurement_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A metric record already exists for {metric.measurement_date}"
        )
    
    # Create new metric record
    db_metric = WeeklyMeasurement(
        week_start=metric.measurement_date,
        weight_kg=metric.weight,
        body_fat_pct=metric.body_fat_pct,
        waist_cm=metric.measurements.get('waist_cm') if metric.measurements else None,
        sleep_avg_hrs=metric.measurements.get('sleep_avg_hrs') if metric.measurements else None,
        rhr_bpm=metric.measurements.get('rhr_bpm') if metric.measurements else None,
        energy_level_avg=metric.measurements.get('energy_level_avg') if metric.measurements else None,
    )
    
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    
    return _format_response(db_metric)


@router.put("/{metric_id}", response_model=BodyMetricResponse, summary="Update body metric record")
async def update_metric(
    metric_id: str,
    metric: BodyMetricUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing body metric record.
    
    **Requirements: 5.6**
    
    **Restrictions:**
    - Metrics can only be edited within 24 hours of creation (Requirement 5.6)
    
    **Parameters:**
    - `metric_id`: String UUID of the metric record
    
    **Fields:**
    - `weight`: Body weight in kilograms (30-300) - optional
    - `body_fat_pct`: Body fat percentage (3-60) - optional
    - `measurements`: Additional circumference measurements (JSON) - optional
    """
    # Find existing record
    existing = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == metric_id
    ).first()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Metric record not found")
    
    # Check 24-hour edit window (Requirement 5.6)
    time_since_creation = datetime.utcnow() - existing.created_at
    if time_since_creation > timedelta(hours=24):
        raise HTTPException(
            status_code=403,
            detail="Metrics can only be edited within 24 hours of creation"
        )
    
    # Update fields
    if metric.weight is not None:
        existing.weight_kg = metric.weight
    
    if metric.body_fat_pct is not None:
        existing.body_fat_pct = metric.body_fat_pct
    
    if metric.measurements is not None:
        if 'waist_cm' in metric.measurements:
            existing.waist_cm = metric.measurements['waist_cm']
        if 'sleep_avg_hrs' in metric.measurements:
            existing.sleep_avg_hrs = metric.measurements['sleep_avg_hrs']
        if 'rhr_bpm' in metric.measurements:
            existing.rhr_bpm = metric.measurements['rhr_bpm']
        if 'energy_level_avg' in metric.measurements:
            existing.energy_level_avg = metric.measurements['energy_level_avg']
    
    db.commit()
    db.refresh(existing)
    
    return _format_response(existing)


@router.get("", response_model=list[BodyMetricResponse], summary="Get metrics history")
async def get_metrics(
    date_from: str = None,
    date_to: str = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve body metrics history with optional date filtering.
    
    **Requirements: 5.4, 5.5**
    
    **Query Parameters:**
    - `date_from`: Start date (YYYY-MM-DD) - optional
    - `date_to`: End date (YYYY-MM-DD) - optional
    
    **Returns:**
    - List of body metric records ordered by date (most recent first)
    - Each record includes timestamp and athlete identifier (Requirement 5.4)
    """
    query = db.query(WeeklyMeasurement).order_by(WeeklyMeasurement.week_start.desc())
    
    if date_from:
        query = query.filter(WeeklyMeasurement.week_start >= date_from)
    
    if date_to:
        query = query.filter(WeeklyMeasurement.week_start <= date_to)
    
    metrics = query.all()
    return [_format_response(m) for m in metrics]


@router.get("/{metric_id}", response_model=BodyMetricResponse, summary="Get specific metric record")
async def get_metric(metric_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific body metric record by ID.
    
    **Parameters:**
    - `metric_id`: String UUID of the metric record
    """
    metric = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == metric_id
    ).first()
    
    if not metric:
        raise HTTPException(status_code=404, detail="Metric record not found")
    
    return _format_response(metric)


def _format_response(metric: WeeklyMeasurement) -> dict:
    """
    Format a WeeklyMeasurement model as a BodyMetricResponse.
    
    This helper function maps the database model to the API response format,
    consolidating circumference measurements into a measurements object.
    """
    measurements = {}
    if metric.waist_cm is not None:
        measurements['waist_cm'] = metric.waist_cm
    if metric.sleep_avg_hrs is not None:
        measurements['sleep_avg_hrs'] = metric.sleep_avg_hrs
    if metric.rhr_bpm is not None:
        measurements['rhr_bpm'] = metric.rhr_bpm
    if metric.energy_level_avg is not None:
        measurements['energy_level_avg'] = metric.energy_level_avg
    
    return {
        'id': metric.id,
        'measurement_date': metric.week_start,
        'weight': metric.weight_kg,
        'body_fat_pct': metric.body_fat_pct,
        'measurements': measurements if measurements else None,
        'created_at': metric.created_at,
        'updated_at': metric.updated_at,
    }

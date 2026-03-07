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
from app.services.llm_client import LLMClient
from typing import Optional

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


@router.get("/trends/analysis", summary="Get AI-powered weight trend analysis")
async def get_trend_analysis(
    athlete_goals: Optional[str] = None,
    current_plan: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered weight trend analysis using LangChain structured output.
    
    **Requirements: 7.1, 7.2, 7.3, 7.4, 7.5**
    
    **Query Parameters:**
    - `athlete_goals`: Athlete's stated goals (optional)
    - `current_plan`: Current training/nutrition plan (optional)
    
    **Returns:**
    - Structured trend analysis with:
        - `weekly_change_rate`: Average kg/week change
        - `trend_direction`: 'increasing', 'decreasing', or 'stable'
        - `summary`: Brief trend summary
        - `goal_alignment`: Assessment vs goals
        - `recommendations`: Actionable suggestions
        - `confidence_level`: 'high', 'medium', or 'low'
        - `data_points_analyzed`: Number of measurements
    
    **Requirements:**
    - At least 4 weeks of weight data (Requirement 7.1)
    - Calculates weekly average weight change rate (Requirement 7.2)
    - Includes athlete goals and plan in context (Requirement 7.2)
    - Uses temperature=0.1 for consistent outputs (Requirement 7.3)
    
    **Error Handling:**
    - Returns 400 if insufficient data (< 4 weeks)
    - Returns basic analysis if LLM fails (Requirement 7.6)
    """
    # Fetch all metrics ordered by date
    metrics = db.query(WeeklyMeasurement).order_by(
        WeeklyMeasurement.week_start.asc()
    ).all()
    
    # Check minimum data requirement (Requirement 7.1)
    if len(metrics) < 4:
        raise HTTPException(
            status_code=400,
            detail=f"At least 4 weeks of weight data required for trend analysis. Currently have {len(metrics)} measurements."
        )
    
    # Check time span requirement
    first_date = metrics[0].week_start
    last_date = metrics[-1].week_start
    days_elapsed = (last_date - first_date).days
    
    if days_elapsed < 28:  # 4 weeks
        raise HTTPException(
            status_code=400,
            detail=f"Data must span at least 4 weeks. Current span: {days_elapsed} days."
        )
    
    # Format metrics for LLM client
    metrics_data = []
    for metric in metrics:
        metrics_data.append({
            'measurement_date': metric.week_start,
            'weight': metric.weight_kg,
            'body_fat_pct': metric.body_fat_pct
        })
    
    # Generate trend analysis using LLM client
    try:
        llm_client = LLMClient()
        analysis = await llm_client.generate_trend_analysis(
            metrics=metrics_data,
            athlete_goals=athlete_goals,
            current_plan=current_plan
        )
        
        return analysis
        
    except ValueError as e:
        # Re-raise validation errors
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        # Handle generation failures gracefully (Requirement 7.6)
        # Return a basic analysis based on calculated metrics
        first_weight = metrics[0].weight_kg
        last_weight = metrics[-1].weight_kg
        total_change = last_weight - first_weight
        weeks_elapsed = days_elapsed / 7.0
        weekly_change_rate = total_change / weeks_elapsed if weeks_elapsed > 0 else 0
        
        trend_direction = 'stable'
        if abs(weekly_change_rate) < 0.2:
            trend_direction = 'stable'
        elif weekly_change_rate > 0:
            trend_direction = 'increasing'
        else:
            trend_direction = 'decreasing'
        
        return {
            'weekly_change_rate': round(weekly_change_rate, 3),
            'trend_direction': trend_direction,
            'summary': f"Weight has changed by {total_change:+.2f} kg over {weeks_elapsed:.1f} weeks, averaging {weekly_change_rate:+.3f} kg/week.",
            'goal_alignment': "Unable to assess goal alignment - LLM analysis unavailable.",
            'recommendations': "Continue monitoring your weight weekly. Consult with a coach for personalized recommendations.",
            'confidence_level': 'low',
            'data_points_analyzed': len(metrics),
            'error': f"LLM analysis failed: {str(e)}"
        }

"""Log management endpoints for daily logs, weekly measurements, and plan targets."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.models.daily_log import DailyLog
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.plan_targets import PlanTargets
from app.schemas.log_schemas import (
    DailyLogCreate,
    DailyLogResponse,
    WeeklyMeasurementCreate,
    WeeklyMeasurementResponse,
    PlanTargetsCreate,
    PlanTargetsResponse,
    PaginatedResponse,
)

router = APIRouter()


# Daily Log Endpoints
@router.post("/daily", response_model=DailyLogResponse, summary="Create or update daily log")
async def create_daily_log(log: DailyLogCreate, db: Session = Depends(get_db)):
    """
    Create or update a daily nutrition and adherence log.
    
    **Fields:**
    - `log_date`: Date of the log (YYYY-MM-DD)
    - `fasting_hours`: Hours of intermittent fasting completed
    - `calories_in`: Total caloric intake in kcal
    - `protein_g`: Protein intake in grams
    - `carbs_g`: Carbohydrate intake in grams
    - `fat_g`: Fat intake in grams
    - `adherence_score`: Self-rated plan adherence (1-10)
    - `notes`: Optional free-text observations
    """
    existing = db.query(DailyLog).filter(DailyLog.log_date == log.log_date).first()
    
    if existing:
        # Update existing entry
        for field, value in log.dict().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new entry
    db_log = DailyLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


@router.get("/daily/{log_date}", response_model=DailyLogResponse, summary="Get daily log by date")
async def get_daily_log(log_date: date, db: Session = Depends(get_db)):
    """
    Retrieve a specific daily log by date.
    
    **Parameters:**
    - `log_date`: Date in YYYY-MM-DD format
    """
    log = db.query(DailyLog).filter(DailyLog.log_date == log_date).first()
    if not log:
        raise HTTPException(status_code=404, detail="Daily log not found")
    return log


@router.get("/daily", response_model=PaginatedResponse[DailyLogResponse], summary="List daily logs")
async def list_daily_logs(
    start_date: date = None,
    end_date: date = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db)
):
    """
    List daily logs within an optional date range with pagination.
    
    **Query Parameters:**
    - `start_date`: Start date (YYYY-MM-DD) - optional
    - `end_date`: End date (YYYY-MM-DD) - optional
    - `page`: Page number (default: 1)
    - `page_size`: Number of records per page (default: 25)
    
    **Returns:**
    - `logs`: List of daily log records
    - `total`: Total number of records matching filters
    - `page`: Current page number
    - `page_size`: Records per page
    """
    query = db.query(DailyLog).order_by(DailyLog.log_date.desc())
    
    if start_date:
        query = query.filter(DailyLog.log_date >= start_date)
    if end_date:
        query = query.filter(DailyLog.log_date <= end_date)
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.put("/daily/{log_id}", response_model=DailyLogResponse, summary="Update daily log")
async def update_daily_log(log_id: str, log: DailyLogCreate, db: Session = Depends(get_db)):
    """
    Update an existing daily log by ID.
    
    **Parameters:**
    - `log_id`: String UUID of the daily log record
    
    **Fields:**
    - `log_date`: Date of the log (YYYY-MM-DD)
    - `calories_in`: Total caloric intake (0-10000)
    - `protein_g`: Protein intake in grams (0-1000)
    - `carbs_g`: Carbohydrate intake in grams (0-1000)
    - `fat_g`: Fat intake in grams (0-1000)
    - `adherence_score`: Self-rated plan adherence (0-100)
    - `notes`: Optional free-text observations
    """
    existing = db.query(DailyLog).filter(DailyLog.id == log_id).first()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Daily log not found")
    
    # Update fields
    for field, value in log.dict().items():
        setattr(existing, field, value)
    
    db.commit()
    db.refresh(existing)
    return existing


# Weekly Measurement Endpoints
@router.post("/weekly", response_model=WeeklyMeasurementResponse, summary="Create or update weekly measurements")
async def create_weekly_measurement(
    measurement: WeeklyMeasurementCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update weekly body measurements and health metrics.
    
    **Fields:**
    - `week_start`: Monday of the week (YYYY-MM-DD)
    - `weight_kg`: Body weight in kilograms
    - `weight_prev_kg`: Previous week weight for trend analysis
    - `body_fat_pct`: Body fat percentage
    - `waist_cm`: Waist circumference in centimeters
    - `waist_prev_cm`: Previous week waist measurement
    - `sleep_avg_hrs`: Average nightly sleep hours
    - `rhr_bpm`: Resting heart rate in beats per minute
    - `energy_level_avg`: Average daily energy level (1-10)
    """
    existing = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.week_start == measurement.week_start
    ).first()
    
    if existing:
        # Update existing entry
        for field, value in measurement.dict().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new entry
    db_measurement = WeeklyMeasurement(**measurement.dict())
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)
    return db_measurement


@router.get("/weekly/{week_start}", response_model=WeeklyMeasurementResponse, summary="Get weekly measurements")
async def get_weekly_measurement(week_start: date, db: Session = Depends(get_db)):
    """
    Retrieve weekly measurements for a specific week.
    
    **Parameters:**
    - `week_start`: Monday of the week (YYYY-MM-DD)
    """
    measurement = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.week_start == week_start
    ).first()
    if not measurement:
        raise HTTPException(status_code=404, detail="Weekly measurement not found")
    return measurement


@router.put("/weekly/{measurement_id}", response_model=WeeklyMeasurementResponse, summary="Update weekly measurements")
async def update_weekly_measurement(
    measurement_id: str,
    measurement: WeeklyMeasurementCreate,
    db: Session = Depends(get_db)
):
    """
    Update an existing weekly measurement by ID.
    
    **Parameters:**
    - `measurement_id`: String UUID of the measurement record
    
    **Fields:**
    - `week_start`: Monday of the week (YYYY-MM-DD)
    - `weight_kg`: Body weight in kilograms (30-300)
    - `body_fat_pct`: Body fat percentage (3-60)
    - `waist_cm`: Waist circumference in centimeters
    - Other optional health metrics
    """
    existing = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == measurement_id
    ).first()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Weekly measurement not found")
    
    # Check if measurement is within 24 hours (Requirement 5.6)
    from datetime import datetime, timedelta
    time_since_creation = datetime.utcnow() - existing.created_at
    if time_since_creation > timedelta(hours=24):
        raise HTTPException(
            status_code=403, 
            detail="Measurements can only be edited within 24 hours of creation"
        )
    
    # Update fields
    for field, value in measurement.dict().items():
        setattr(existing, field, value)
    
    db.commit()
    db.refresh(existing)
    return existing


@router.get("/weekly", response_model=list[WeeklyMeasurementResponse], summary="List all weekly measurements")
async def list_weekly_measurements(db: Session = Depends(get_db)):
    """
    List all weekly measurements ordered by most recent first.
    """
    return db.query(WeeklyMeasurement).order_by(WeeklyMeasurement.week_start.desc()).all()


# Plan Targets Endpoints
@router.post("/targets", response_model=PlanTargetsResponse, summary="Create plan targets")
async def create_plan_targets(targets: PlanTargetsCreate, db: Session = Depends(get_db)):
    """
    Create a new version of plan targets for goal tracking.
    
    **Fields:**
    - `effective_from`: Date targets become active (YYYY-MM-DD)
    - `target_calories`: Daily caloric target (kcal)
    - `target_protein_g`: Daily protein target (g)
    - `target_fasting_hrs`: Minimum fasting window (hours)
    - `target_run_km_wk`: Weekly running distance target (km)
    - `target_strength_sessions`: Weekly strength training sessions
    - `target_weight_kg`: Goal body weight (kg)
    - `notes`: Plan rationale and notes
    """
    db_targets = PlanTargets(**targets.dict())
    db.add(db_targets)
    db.commit()
    db.refresh(db_targets)
    return db_targets


@router.get("/targets/by-id/{target_id}", response_model=PlanTargetsResponse, summary="Get plan targets by ID")
async def get_plan_targets(target_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific plan targets entry by UUID.
    
    **Parameters:**
    - `target_id`: String UUID of the plan targets record
    """
    targets = db.query(PlanTargets).filter(PlanTargets.id == target_id).first()
    if not targets:
        raise HTTPException(status_code=404, detail="Plan targets not found")
    return targets


@router.get("/targets", response_model=list[PlanTargetsResponse], summary="List all plan targets")
async def list_plan_targets(db: Session = Depends(get_db)):
    """
    List all plan targets ordered by most recent effective date first.
    """
    return db.query(PlanTargets).order_by(PlanTargets.effective_from.desc()).all()


@router.get("/targets/current", response_model=PlanTargetsResponse, summary="Get current active plan targets")
async def get_current_plan_targets(db: Session = Depends(get_db)):
    """
    Get the most recent active plan targets (highest effective_from date).
    """
    targets = db.query(PlanTargets).order_by(PlanTargets.effective_from.desc()).first()
    if not targets:
        raise HTTPException(status_code=404, detail="No plan targets found")
    return targets


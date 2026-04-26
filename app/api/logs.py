"""Log management endpoints for daily logs, weekly measurements, and plan targets."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete
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
async def create_daily_log(
    log: DailyLogCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    existing = db.query(DailyLog).filter(
        DailyLog.athlete_id == athlete.id,
        DailyLog.log_date == log.log_date,
    ).first()

    if existing:
        for field, value in log.model_dump().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing

    db_log = DailyLog(athlete_id=athlete.id, **log.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


@router.get("/daily/{log_date}", response_model=DailyLogResponse, summary="Get daily log by date")
async def get_daily_log(
    log_date: date,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    log = db.query(DailyLog).filter(
        DailyLog.athlete_id == athlete.id,
        DailyLog.log_date == log_date,
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="Daily log not found")
    return log


@router.get("/daily", response_model=PaginatedResponse[DailyLogResponse], summary="List daily logs")
async def list_daily_logs(
    start_date: date = None,
    end_date: date = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    query = db.query(DailyLog).filter(
        DailyLog.athlete_id == athlete.id
    ).order_by(DailyLog.log_date.desc())

    if start_date:
        query = query.filter(DailyLog.log_date >= start_date)
    if end_date:
        query = query.filter(DailyLog.log_date <= end_date)

    total = query.count()
    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()

    return {"logs": logs, "total": total, "page": page, "page_size": page_size}


@router.put("/daily/{log_id}", response_model=DailyLogResponse, summary="Update daily log")
async def update_daily_log(
    log_id: str,
    log: DailyLogCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    existing = db.query(DailyLog).filter(
        DailyLog.id == log_id,
        DailyLog.athlete_id == athlete.id,
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Daily log not found")

    for field, value in log.model_dump().items():
        setattr(existing, field, value)

    db.commit()
    db.refresh(existing)
    return existing


# Weekly Measurement Endpoints
@router.post("/weekly", response_model=WeeklyMeasurementResponse, summary="Create or update weekly measurements")
async def create_weekly_measurement(
    measurement: WeeklyMeasurementCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    existing = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.athlete_id == athlete.id,
        WeeklyMeasurement.week_start == measurement.week_start,
    ).first()

    if existing:
        for field, value in measurement.model_dump().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing

    db_measurement = WeeklyMeasurement(athlete_id=athlete.id, **measurement.model_dump())
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)
    return db_measurement


@router.get("/weekly/{week_start}", response_model=WeeklyMeasurementResponse, summary="Get weekly measurements")
async def get_weekly_measurement(
    week_start: date,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    measurement = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.athlete_id == athlete.id,
        WeeklyMeasurement.week_start == week_start,
    ).first()
    if not measurement:
        raise HTTPException(status_code=404, detail="Weekly measurement not found")
    return measurement


@router.put("/weekly/{measurement_id}", response_model=WeeklyMeasurementResponse, summary="Update weekly measurements")
async def update_weekly_measurement(
    measurement_id: str,
    measurement: WeeklyMeasurementCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    existing = db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.id == measurement_id,
        WeeklyMeasurement.athlete_id == athlete.id,
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Weekly measurement not found")

    from datetime import datetime, timedelta, timezone
    if datetime.now(timezone.utc).replace(tzinfo=None) - existing.created_at > timedelta(hours=24):
        raise HTTPException(status_code=403, detail="Measurements can only be edited within 24 hours of creation")

    for field, value in measurement.model_dump().items():
        setattr(existing, field, value)

    db.commit()
    db.refresh(existing)
    return existing


@router.get("/weekly", response_model=list[WeeklyMeasurementResponse], summary="List all weekly measurements")
async def list_weekly_measurements(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    return db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.athlete_id == athlete.id
    ).order_by(WeeklyMeasurement.week_start.desc()).all()


# Plan Targets Endpoints
@router.post("/targets", response_model=PlanTargetsResponse, summary="Create plan targets")
async def create_plan_targets(
    targets: PlanTargetsCreate,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    db_targets = PlanTargets(athlete_id=athlete.id, **targets.model_dump())
    db.add(db_targets)
    db.commit()
    db.refresh(db_targets)
    return db_targets


@router.get("/targets/by-id/{target_id}", response_model=PlanTargetsResponse, summary="Get plan targets by ID")
async def get_plan_targets(
    target_id: str,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    targets = db.query(PlanTargets).filter(
        PlanTargets.id == target_id,
        PlanTargets.athlete_id == athlete.id,
    ).first()
    if not targets:
        raise HTTPException(status_code=404, detail="Plan targets not found")
    return targets


@router.get("/targets", response_model=list[PlanTargetsResponse], summary="List all plan targets")
async def list_plan_targets(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    return db.query(PlanTargets).filter(
        PlanTargets.athlete_id == athlete.id
    ).order_by(PlanTargets.effective_from.desc()).all()


@router.get("/targets/current", response_model=PlanTargetsResponse, summary="Get current active plan targets")
async def get_current_plan_targets(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    targets = db.query(PlanTargets).filter(
        PlanTargets.athlete_id == athlete.id
    ).order_by(PlanTargets.effective_from.desc()).first()
    if not targets:
        raise HTTPException(status_code=404, detail="No plan targets found")
    return targets

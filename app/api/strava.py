"""Strava synchronization and activity management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date
from uuid import UUID
from app.database import get_db
from app.models.strava_activity import StravaActivity
from app.services.strava_service import (
    sync_week_activities,
    compute_weekly_aggregates,
)

router = APIRouter()


@router.post("/sync/{week_start}", summary="Sync Strava activities for a week")
async def sync_strava_activities(week_start: date, db: Session = Depends(get_db)):
    """
    Trigger Strava synchronization for the given week.
    
    Fetches activities from Strava API and upserts them into the database.
    Uses the week_start date to determine the sync window (week_start to week_start+7).
    
    **Parameters:**
    - `week_start`: Monday of the week to sync (YYYY-MM-DD)
    
    **Returns:**
    - `week_start`: The start date of the synced week
    - `activities_synced`: Count of activities fetched and stored
    - `message`: Status message
    """
    try:
        # Create a week_id UUID from the week_start date
        from uuid import uuid5, NAMESPACE_DNS
        week_id = uuid5(NAMESPACE_DNS, str(week_start))
        
        count = await sync_week_activities(week_id, db)
        return {
            "week_start": week_start,
            "activities_synced": count,
            "message": f"Successfully synced {count} activities"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/activities/{week_start}", summary="List Strava activities for a week")
async def get_week_activities(week_start: date, db: Session = Depends(get_db)):
    """
    List all Strava activities for a specific week.
    
    Returns activity details including type, distance, duration, and metrics.
    
    **Parameters:**
    - `week_start`: Monday of the week (YYYY-MM-DD)
    
    **Returns:**
    - `week_start`: The start date of the queried week
    - `activities`: Array of activity objects with:
      - `strava_id`: Unique Strava activity identifier
      - `activity_type`: Run, Ride, WeightTraining, etc.
      - `start_date`: Activity start time (ISO 8601)
      - `distance_m`: Distance in meters
      - `moving_time_s`: Active movement time in seconds
      - `elevation_m`: Total elevation gain in meters
      - `avg_hr`: Average heart rate (bpm)
      - `max_hr`: Maximum heart rate (bpm)
    """
    from datetime import timedelta
    week_end = week_start + timedelta(days=7)
    
    activities = db.query(StravaActivity).filter(
        StravaActivity.start_date >= week_start,
        StravaActivity.start_date < week_end
    ).order_by(StravaActivity.start_date).all()
    
    if not activities:
        return {"week_start": week_start, "activities": []}
    
    return {
        "week_start": week_start,
        "activities": [
            {
                "strava_id": a.strava_id,
                "activity_type": a.activity_type,
                "start_date": a.start_date,
                "distance_m": a.distance_m,
                "moving_time_s": a.moving_time_s,
                "elevation_m": a.elevation_m,
                "avg_hr": a.avg_hr,
                "max_hr": a.max_hr,
            }
            for a in activities
        ]
    }


@router.get("/aggregates/{week_start}", summary="Get weekly activity aggregates")
async def get_weekly_aggregates(week_start: date, db: Session = Depends(get_db)):
    """
    Get aggregated statistics for Strava activities in a week.
    
    Computes totals and counts for all activities in the week window.
    Useful for weekly analysis and evaluation.
    
    **Parameters:**
    - `week_start`: Monday of the week (YYYY-MM-DD)
    
    **Returns:**
    - `week_start`: The start date
    - `aggregates`: Dictionary containing:
      - `run_km`: Total running distance (km)
      - `ride_km`: Total cycling distance (km)
      - `strength_sessions`: Count of strength training activities
      - `total_moving_time_min`: Total active time (minutes)
      - `session_counts`: Activity counts by type
    """
    from uuid import uuid5, NAMESPACE_DNS
    week_id = uuid5(NAMESPACE_DNS, str(week_start))
    
    aggregates = compute_weekly_aggregates(week_id, db)
    return {
        "week_start": week_start,
        "aggregates": aggregates
    }

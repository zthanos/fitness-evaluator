"""Strava synchronization and activity management endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
from typing import Optional
from app.database import get_db
from app.models.strava_activity import StravaActivity
from app.models.activity_analysis import ActivityAnalysis
from app.services.strava_service import (
    sync_week_activities,
    compute_weekly_aggregates,
)
from app.services.llm_client import LLMClient

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
        # Start one week before the requested week_start
        start_week = week_start - timedelta(days=7)
        today = date.today()

        total_count = 0
        current_week = start_week

        # Sync in weekly windows from (week_start - 7) up to today
        while current_week <= today:
            total_count += await sync_week_activities(current_week, db)
            current_week = current_week + timedelta(days=7)

        return {
            "week_start": week_start,
            "activities_synced": total_count,
            "message": f"Successfully synced {total_count} activities from {start_week} through {current_week - timedelta(days=1)}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/activities/all", summary="List all Strava activities with pagination")
async def get_all_activities(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Number of activities per page"),
    type: Optional[str] = Query(None, description="Filter by activity type"),
    date_from: Optional[date] = Query(None, description="Filter activities from this date"),
    date_to: Optional[date] = Query(None, description="Filter activities until this date"),
    distance_min: Optional[float] = Query(None, ge=0, description="Filter activities with minimum distance (km)"),
    distance_max: Optional[float] = Query(None, ge=0, description="Filter activities with maximum distance (km)"),
    sort_by: str = Query("start_date", description="Sort by field (start_date, distance_m, moving_time_s, elevation_m)"),
    sort_dir: str = Query("desc", description="Sort direction (asc or desc)"),
    db: Session = Depends(get_db)
):
    """
    List all Strava activities with pagination, filtering, and sorting.
    
    **Parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Number of activities per page (default: 25, max: 100)
    - `type`: Filter by activity type (e.g., Run, Ride, WeightTraining)
    - `date_from`: Filter activities from this date (YYYY-MM-DD)
    - `date_to`: Filter activities until this date (YYYY-MM-DD)
    - `distance_min`: Filter activities with minimum distance in kilometers
    - `distance_max`: Filter activities with maximum distance in kilometers
    - `sort_by`: Sort by field (start_date, distance_m, moving_time_s, elevation_m)
    - `sort_dir`: Sort direction (asc or desc)
    
    **Returns:**
    - `activities`: Array of activity objects
    - `total`: Total number of activities matching filters
    - `page`: Current page number
    - `page_size`: Number of activities per page
    - `total_pages`: Total number of pages
    """
    # Build query
    query = db.query(StravaActivity)
    
    # Apply filters
    if type:
        query = query.filter(StravaActivity.activity_type == type)
    if date_from:
        query = query.filter(StravaActivity.start_date >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(StravaActivity.start_date <= datetime.combine(date_to, datetime.max.time()))
    if distance_min is not None:
        # Convert km to meters for database comparison
        query = query.filter(StravaActivity.distance_m >= distance_min * 1000)
    if distance_max is not None:
        # Convert km to meters for database comparison
        query = query.filter(StravaActivity.distance_m <= distance_max * 1000)
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(StravaActivity, sort_by, StravaActivity.start_date)
    if sort_dir.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    offset = (page - 1) * page_size
    activities = query.offset(offset).limit(page_size).all()
    
    return {
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
                "calories": a.calories,
            }
            for a in activities
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/activities/detail/{activity_id}", summary="Get activity details")
async def get_activity_detail(activity_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information for a specific activity.
    
    **Parameters:**
    - `activity_id`: Strava activity ID
    
    **Returns:**
    - Activity object with all details
    """
    activity = db.query(StravaActivity).filter(StravaActivity.strava_id == activity_id).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    return {
        "strava_id": activity.strava_id,
        "activity_type": activity.activity_type,
        "start_date": activity.start_date,
        "distance_m": activity.distance_m,
        "moving_time_s": activity.moving_time_s,
        "elevation_m": activity.elevation_m,
        "avg_hr": activity.avg_hr,
        "max_hr": activity.max_hr,
        "calories": activity.calories,
        "raw_json": activity.raw_json
    }


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
                "calories": a.calories,
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
    week_id = str(uuid5(NAMESPACE_DNS, str(week_start)))
    
    aggregates = compute_weekly_aggregates(week_id, db)
    return {
        "week_start": week_start,
        "aggregates": aggregates
    }



@router.get("/activities/detail/{activity_id}/analysis", summary="Get or generate activity effort analysis")
async def get_activity_analysis(activity_id: int, db: Session = Depends(get_db)):
    """
    Get AI-generated effort analysis for an activity.
    
    Returns cached analysis if available, otherwise generates new analysis.
    Analysis includes effort level, heart rate zones, pace variation, and recommendations.
    
    **Parameters:**
    - `activity_id`: Strava activity ID
    
    **Returns:**
    - `analysis_text`: Formatted effort analysis
    - `generated_at`: Timestamp when analysis was generated
    - `cached`: Boolean indicating if analysis was cached
    """
    # Find the activity
    activity = db.query(StravaActivity).filter(StravaActivity.strava_id == activity_id).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Check for existing analysis
    existing_analysis = db.query(ActivityAnalysis).filter(
        ActivityAnalysis.activity_id == activity.id
    ).first()
    
    if existing_analysis:
        return {
            "analysis_text": existing_analysis.analysis_text,
            "generated_at": existing_analysis.generated_at,
            "cached": True
        }
    
    # Generate new analysis
    try:
        llm_client = LLMClient()
        
        # Prepare activity data for analysis
        activity_data = {
            "activity_type": activity.activity_type,
            "distance_m": activity.distance_m,
            "moving_time_s": activity.moving_time_s,
            "elevation_m": activity.elevation_m,
            "avg_hr": activity.avg_hr,
            "max_hr": activity.max_hr,
            "raw_json": activity.raw_json
        }
        
        # Generate analysis using LLM
        analysis_text = await llm_client.generate_effort_analysis(activity_data)
        
        # Store analysis in database
        new_analysis = ActivityAnalysis(
            activity_id=activity.id,
            analysis_text=analysis_text
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)
        
        return {
            "analysis_text": new_analysis.analysis_text,
            "generated_at": new_analysis.generated_at,
            "cached": False
        }
        
    except Exception as e:
        # If analysis generation fails, return error but don't break the API
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate effort analysis: {str(e)}"
        )

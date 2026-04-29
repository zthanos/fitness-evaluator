"""Strava synchronization and activity management endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any
import json
from app.database import get_db, SessionLocal
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete
from app.models.strava_activity import StravaActivity
from app.models.activity_analysis import ActivityAnalysis
from app.services.strava_service import compute_weekly_aggregates
from app.services.session_matcher import SessionMatcher
from app.services.strava_client import StravaClient
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _rebuild_sport_profiles(db: Session, athlete_id: int) -> None:
    """Rebuild all AthleteSportProfile rows for athlete_id (best-effort)."""
    try:
        from app.ai.skills.sport_profile_builder import SportProfileBuilder
        SportProfileBuilder(db, athlete_id).build_all()
        logger.info("SportProfileBuilder: rebuilt profiles for athlete %d", athlete_id)
    except Exception as exc:
        logger.warning("SportProfileBuilder failed for athlete %d: %s", athlete_id, exc)


async def _do_sync(athlete_id: int):
    """Background worker: creates its own DB session so it outlives the request."""
    db = SessionLocal()
    try:
        client = StravaClient(db)
        count = await client.sync_activities(athlete_id)
        logger.info("Background Strava sync complete for athlete %d: %d activities", athlete_id, count)
        _rebuild_sport_profiles(db, athlete_id)
    except Exception as e:
        logger.error("Background Strava sync failed for athlete %d: %s", athlete_id, e)
    finally:
        db.close()


async def _do_enrich(athlete_id: int, days: int, force: bool):
    """Background worker: enriches activities with full Strava detail API data."""
    import asyncio
    from datetime import timedelta
    db = SessionLocal()
    try:
        client = StravaClient(db)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = db.query(StravaActivity).filter(
            StravaActivity.athlete_id == athlete_id,
            StravaActivity.start_date >= cutoff,
        )
        if not force:
            # Skip only activities with properly stored JSON that already has splits.
            # '"splits_metric"' (double-quoted key) only exists in valid JSON from the
            # detail endpoint. Legacy Python str(dict) rows have 'splits_metric'
            # (single-quoted) and must be re-fetched to get parseable JSON.
            query = query.filter(
                ~StravaActivity.raw_json.contains('"splits_metric"')
            )
        activities = query.order_by(StravaActivity.start_date.desc()).all()

        logger.info("Enriching %d activities for athlete %d", len(activities), athlete_id)
        enriched_count = 0
        for activity in activities:
            try:
                data = await client.get_activity(athlete_id, activity.strava_id)
                fields = StravaClient._map_activity_fields(athlete_id, data)
                for k, v in fields.items():
                    if k not in ("athlete_id", "strava_id"):
                        setattr(activity, k, v)
                db.commit()
                enriched_count += 1
                # Strava rate limit: 100 req/15 min → 1 req every ~9s; use 6s for headroom
                await asyncio.sleep(6)
            except Exception as e:
                logger.error("Failed to enrich activity %d: %s", activity.strava_id, e)
                continue

        logger.info(
            "Enrichment complete for athlete %d: %d/%d activities enriched",
            athlete_id, enriched_count, len(activities),
        )
        _rebuild_sport_profiles(db, athlete_id)
    except Exception as e:
        logger.error("Bulk enrichment failed for athlete %d: %s", athlete_id, e)
    finally:
        db.close()


@router.post("/enrich", summary="Enrich activities with Strava detail data")
async def enrich_activities(
    background_tasks: BackgroundTasks,
    days: int = Query(60, ge=1, le=365, description="Lookback period in days"),
    force: bool = Query(False, description="Re-enrich already-enriched activities"),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Kick off background enrichment of activities with full Strava detail API data.

    Enrichment adds splits, laps, cadence, power, and suffer score to activities
    that were synced from the list endpoint (which only returns summary fields).
    Rate-limited to ~6 s per activity to stay within Strava's 100 req/15 min limit.
    """
    background_tasks.add_task(_do_enrich, athlete.id, days, force)
    return {
        "message": "Enrichment started — activity details will be updated shortly",
        "days": days,
        "force": force,
    }


@router.post("/sync/{week_start}", summary="Sync Strava activities")
async def sync_strava_activities(
    week_start: date,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(get_current_athlete),
):
    """Kick off a background sync of this athlete's Strava activities."""
    background_tasks.add_task(_do_sync, athlete.id)
    return {
        "week_start": str(week_start),
        "activities_synced": 0,
        "message": "Sync started — activities will appear shortly",
    }


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
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    query = db.query(StravaActivity).filter(StravaActivity.athlete_id == athlete.id)
    
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
                "sport_type": a.sport_type,
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
async def get_activity_detail(
    activity_id: int,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Get detailed information for a specific activity.
    Auto-enriches from Strava on first view if splits data is missing.

    **Parameters:**
    - `activity_id`: Strava activity ID

    **Returns:**
    - Activity object with all details including performance metrics
    """
    activity = db.query(StravaActivity).filter(
        StravaActivity.strava_id == activity_id,
        StravaActivity.athlete_id == athlete.id,
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Auto-enrich when splits data is absent OR raw_json is legacy Python-dict format.
    # '"splits_metric"' (double-quoted) only appears in properly stored JSON.
    # Legacy str(dict) data has 'splits_metric' (single-quoted) and can't be parsed
    # by the frontend, so it must also be re-fetched.
    enriched = False
    if '"splits_metric"' not in (activity.raw_json or ""):
        try:
            client = StravaClient(db)
            data = await client.get_activity(athlete.id, activity_id)
            fields = StravaClient._map_activity_fields(athlete.id, data)
            for k, v in fields.items():
                if k not in ("athlete_id", "strava_id"):
                    setattr(activity, k, v)
            # Clear stale AI analysis so it regenerates with the enriched data
            db.query(ActivityAnalysis).filter(
                ActivityAnalysis.activity_id == activity.id
            ).delete()
            db.commit()
            enriched = True
            logger.info("Auto-enriched activity %d for athlete %d", activity_id, athlete.id)
        except Exception as e:
            logger.warning("Could not auto-enrich activity %d: %s", activity_id, e)

    return {
        "strava_id": activity.strava_id,
        "activity_type": activity.activity_type,
        "sport_type": activity.sport_type,
        "start_date": activity.start_date,
        "distance_m": activity.distance_m,
        "moving_time_s": activity.moving_time_s,
        "elevation_m": activity.elevation_m,
        "avg_hr": activity.avg_hr,
        "max_hr": activity.max_hr,
        "calories": activity.calories,
        "avg_cadence": activity.avg_cadence,
        "max_cadence": activity.max_cadence,
        "avg_watts": activity.avg_watts,
        "max_watts": activity.max_watts,
        "weighted_avg_watts": activity.weighted_avg_watts,
        "kilojoules": activity.kilojoules,
        "suffer_score": activity.suffer_score,
        "trainer": bool(activity.trainer) if activity.trainer is not None else None,
        "raw_json": activity.raw_json,
        "enriched": enriched,
    }


@router.get("/activities/{week_start}", summary="List Strava activities for a week")
async def get_week_activities(
    week_start: date,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
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
        StravaActivity.athlete_id == athlete.id,
        StravaActivity.start_date >= week_start,
        StravaActivity.start_date < week_end,
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
async def get_weekly_aggregates(
    week_start: date,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
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
    iso = week_start.isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"
    aggregates = compute_weekly_aggregates(week_id, db, athlete_id=athlete.id)
    return {"week_start": week_start, "aggregates": aggregates}



_STALE_ANALYSIS_PREFIXES = (
    "Unable to generate",
    "Analysis complete.",  # empty-result sentinel from early version
)


@router.get("/activities/detail/{activity_id}/analysis", summary="Get or generate activity effort analysis")
async def get_activity_analysis(
    activity_id: int,
    force: bool = Query(False, description="Delete cached analysis and regenerate"),
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
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
    activity = db.query(StravaActivity).filter(
        StravaActivity.strava_id == activity_id,
        StravaActivity.athlete_id == athlete.id,
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Check for existing analysis; discard if forced or if it holds a stale fallback
    existing_analysis = db.query(ActivityAnalysis).filter(
        ActivityAnalysis.activity_id == activity.id
    ).first()

    if existing_analysis:
        is_stale = any(
            existing_analysis.analysis_text.startswith(p)
            for p in _STALE_ANALYSIS_PREFIXES
        )
        if force or is_stale:
            db.delete(existing_analysis)
            db.commit()
            existing_analysis = None

    if existing_analysis:
        return {
            "analysis_text": existing_analysis.analysis_text,
            "generated_at": existing_analysis.generated_at,
            "cached": True,
        }
    
    # Generate new analysis via WorkoutAnalyzer skill (uses reliable chat_completion)
    try:
        from app.ai.skills.workout_analyzer import WorkoutAnalyzer
        from app.ai.skills.schemas import WorkoutAnalyzerInput

        analyzer = WorkoutAnalyzer(db, athlete.id)
        analyses = await analyzer.run(WorkoutAnalyzerInput(strava_id=activity_id))
        if not analyses:
            raise ValueError("WorkoutAnalyzer returned no results")

        wa = analyses[0]

        # Build analysis as sequential paragraphs — one per coaching question:
        # 1. What kind of session?  2. What does it show?  3. Limiter?
        # 4. Why it matters?  5. What to do next?
        paragraphs: list[str] = []
        if wa.session_type:
            paragraphs.append(wa.session_type)
        elif wa.effort_level:
            # Fallback when new LLM fields are missing (old cache or LLM parse failure)
            paragraphs.append(f"{wa.effort_level.capitalize()} session.")
        if wa.main_insight:
            paragraphs.append(wa.main_insight)
        if wa.key_limiter:
            paragraphs.append(wa.key_limiter)
        elif wa.limiter_hypothesis:
            paragraphs.append(wa.limiter_hypothesis.replace("_", " ").capitalize() + ".")
        if wa.why_it_matters:
            paragraphs.append(wa.why_it_matters)
        if wa.next_action:
            paragraphs.append(wa.next_action)

        analysis_text = "\n\n".join(paragraphs).strip() or "Analysis complete."

        new_analysis = ActivityAnalysis(
            activity_id=activity.id,
            analysis_text=analysis_text,
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)

        return {
            "analysis_text": new_analysis.analysis_text,
            "generated_at": new_analysis.generated_at,
            "cached": False,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate effort analysis: {str(e)}",
        )


@router.get("/webhook", summary="Strava webhook verification")
async def verify_webhook(request: Request):
    """
    Handle Strava webhook subscription verification.
    
    Strava sends a GET request with a challenge parameter during subscription setup.
    We must echo back the challenge to verify the webhook endpoint.
    
    **Query Parameters:**
    - `hub.mode`: Should be "subscribe"
    - `hub.challenge`: Random string to echo back
    - `hub.verify_token`: Token for verification (optional)
    
    **Returns:**
    - `hub.challenge`: Echo of the challenge parameter
    
    **Reference:**
    - https://developers.strava.com/docs/webhooks/
    """
    try:
        # Get query parameters
        params = dict(request.query_params)
        
        mode = params.get('hub.mode')
        challenge = params.get('hub.challenge')
        verify_token = params.get('hub.verify_token')
        
        logger.info(f"Webhook verification request: mode={mode}, verify_token={verify_token}")
        
        # Validate subscription request
        if mode != 'subscribe':
            raise HTTPException(status_code=400, detail="Invalid hub.mode")
        
        if not challenge:
            raise HTTPException(status_code=400, detail="Missing hub.challenge")
        
        # Optional: Verify token if configured
        # if verify_token != os.getenv('STRAVA_WEBHOOK_VERIFY_TOKEN'):
        #     raise HTTPException(status_code=403, detail="Invalid verify_token")
        
        # Echo back the challenge
        return {"hub.challenge": challenge}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in webhook verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook", summary="Strava webhook event handler")
async def handle_webhook_event(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Strava webhook events for new activities.
    
    Receives notifications when athletes create, update, or delete activities.
    For new activities, stores them in the database and triggers session matching.
    
    **Event Types:**
    - `create`: New activity created
    - `update`: Activity updated
    - `delete`: Activity deleted
    
    **Object Types:**
    - `activity`: Activity event
    - `athlete`: Athlete authorization/deauthorization
    
    **Request Body Example:**
    ```json
    {
        "object_type": "activity",
        "object_id": 12345678,
        "aspect_type": "create",
        "owner_id": 123456,
        "subscription_id": 123,
        "event_time": 1516126040
    }
    ```
    
    **Returns:**
    - Success message with processing details
    
    **Reference:**
    - https://developers.strava.com/docs/webhooks/
    """
    try:
        # Parse webhook event
        event = await request.json()
        
        object_type = event.get('object_type')
        object_id = event.get('object_id')
        aspect_type = event.get('aspect_type')
        owner_id = event.get('owner_id')
        event_time = event.get('event_time')
        
        logger.info(
            f"Webhook event received: type={object_type}, "
            f"aspect={aspect_type}, id={object_id}, owner={owner_id}"
        )
        
        # Only process activity creation events
        if object_type != 'activity':
            logger.info(f"Ignoring non-activity event: {object_type}")
            return {"status": "ignored", "reason": "not an activity event"}
        
        if aspect_type == 'create':
            # Handle new activity creation
            result = await _handle_activity_create(
                activity_id=object_id,
                athlete_id=owner_id,
                event_time=event_time,
                db=db
            )
            return result
        
        elif aspect_type == 'update':
            # Handle activity update (optional: could re-match)
            logger.info(f"Activity {object_id} updated - no action taken")
            return {"status": "ignored", "reason": "update events not processed"}
        
        elif aspect_type == 'delete':
            # Handle activity deletion (optional: could unmatch session)
            logger.info(f"Activity {object_id} deleted - no action taken")
            return {"status": "ignored", "reason": "delete events not processed"}
        
        else:
            logger.warning(f"Unknown aspect_type: {aspect_type}")
            return {"status": "ignored", "reason": f"unknown aspect_type: {aspect_type}"}
        
    except Exception as e:
        logger.error(f"Error handling webhook event: {e}")
        # Return 200 to prevent Strava from retrying
        return {"status": "error", "message": str(e)}


async def _handle_activity_create(
    activity_id: int,
    athlete_id: int,
    event_time: int,
    db: Session
) -> Dict[str, Any]:
    """
    Handle new activity creation from webhook.
    
    Steps:
    1. Fetch activity details from Strava API
    2. Store activity in database
    3. Trigger SessionMatcher for automatic matching
    
    Args:
        activity_id: Strava activity ID
        athlete_id: Strava athlete ID
        event_time: Unix timestamp of event
        db: Database session
        
    Returns:
        Dictionary with processing status and results
    """
    try:
        # Check if activity already exists
        existing = db.query(StravaActivity).filter(
            StravaActivity.strava_id == activity_id
        ).first()
        
        if existing:
            logger.info(f"Activity {activity_id} already exists in database")
            return {
                "status": "skipped",
                "reason": "activity already exists",
                "activity_id": activity_id
            }
        
        # Fetch real activity details from Strava API.
        # The app is single-user; token is stored under athlete_id=1.
        try:
            client = StravaClient(db)
            data = await client.get_activity(1, activity_id)
        except Exception as e:
            logger.warning("Could not fetch activity %d from Strava (%s); storing minimal record", activity_id, e)
            data = {}

        activity = StravaActivity(
            strava_id=activity_id,
            athlete_id=athlete_id,
            activity_type=data.get("type", "Unknown"),
            start_date=datetime.fromisoformat(data["start_date"].replace("Z", "+00:00")) if data.get("start_date") else datetime.fromtimestamp(event_time),
            moving_time_s=data.get("moving_time", 0),
            distance_m=data.get("distance", 0.0),
            elevation_m=data.get("total_elevation_gain"),
            avg_hr=data.get("average_heartrate"),
            max_hr=data.get("max_heartrate"),
            calories=data.get("calories"),
            raw_json=json.dumps(data, default=str) if data else "{}",
        )
        
        db.add(activity)
        db.commit()
        db.refresh(activity)

        logger.info(f"Stored activity {activity_id} in database")

        _rebuild_sport_profiles(db, athlete_id)

        # Trigger session matching (Requirement 14.1)
        matcher = SessionMatcher(db)
        matched_session_id = matcher.match_activity(activity, athlete_id)
        
        if matched_session_id:
            logger.info(
                f"Activity {activity_id} matched to session {matched_session_id}"
            )
            return {
                "status": "success",
                "activity_id": activity_id,
                "matched": True,
                "session_id": matched_session_id
            }
        else:
            logger.info(f"Activity {activity_id} could not be matched to any session")
            return {
                "status": "success",
                "activity_id": activity_id,
                "matched": False
            }
        
    except Exception as e:
        logger.error(f"Error processing activity {activity_id}: {e}")
        db.rollback()
        raise

# app/services/strava_service.py
import time
import httpx
from datetime import datetime, timezone, timedelta, date
from uuid import uuid5, NAMESPACE_DNS
from sqlalchemy.orm import Session
from app.config import get_settings

# In-memory storage for tokens (in production, this would be a database)
_strava_tokens = {}

def build_authorization_url() -> str:
    """
    Returns the Strava OAuth2 consent URL with scopes read,activity:read_all.
    """
    settings = get_settings()
    return (
        "https://www.strava.com/oauth/authorize?" +
        f"client_id={settings.STRAVA_CLIENT_ID}&" +
        "response_type=code&" +
        f"redirect_uri={settings.STRAVA_REDIRECT_URI}&" +
        "scope=read,activity:read_all&" +
        "state=fitness_eval"
    )

async def exchange_code(code: str) -> dict:
    """
    POSTs to https://www.strava.com/oauth/token with grant_type=authorization_code.
    Returns and caches the token dict.
    """
    settings = get_settings()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": settings.STRAVA_CLIENT_ID,
                "client_secret": settings.STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.STRAVA_REDIRECT_URI
            }
        )
        response.raise_for_status()
        token_data = response.json()
        
        # Cache the tokens
        _strava_tokens["access_token"] = token_data["access_token"]
        _strava_tokens["refresh_token"] = token_data["refresh_token"]
        _strava_tokens["expires_at"] = token_data["expires_at"]
        
        return token_data

async def refresh_access_token() -> str:
    """
    Checks if expires_at < time.time() + 60. If so, POSTs with grant_type=refresh_token.
    Returns the current access token.
    """
    if "expires_at" not in _strava_tokens:
        raise ValueError("No access token available")
    
    # Check if token expires within 60 seconds
    if _strava_tokens["expires_at"] < time.time() + 60:
        settings = get_settings()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": settings.STRAVA_CLIENT_ID,
                    "client_secret": settings.STRAVA_CLIENT_SECRET,
                    "refresh_token": _strava_tokens["refresh_token"],
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            # Update cached tokens
            _strava_tokens["access_token"] = token_data["access_token"]
            _strava_tokens["refresh_token"] = token_data["refresh_token"]
            _strava_tokens["expires_at"] = token_data["expires_at"]
    
    return _strava_tokens["access_token"]

async def sync_week_activities(week_start: date, db: Session) -> int:
    """
    Calls /v3/athlete/activities?after={unix_start}&before={unix_end} with a valid access token.
    For each activity: upsert into strava_activities using strava_id as the conflict key.
    Returns the number of activities upserted.
    """
    from app.models.strava_activity import StravaActivity

    # Derive a stable week_id from the week_start date for grouping activities
    week_id = str(uuid5(NAMESPACE_DNS, str(week_start)))

    # Calculate start and end times for the week
    week_end = week_start + timedelta(days=7)
    
    # Convert to Unix timestamps
    unix_start = int(datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp())
    unix_end = int(datetime.combine(week_end, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp())
    
    # Get access token
    access_token = await refresh_access_token()
    
    # Fetch activities from Strava API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.strava.com/api/v3/athlete/activities?after={unix_start}&before={unix_end}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        activities_data = response.json()
        
        # Upsert each activity into the database
        upserted_count = 0
        for activity_data in activities_data:
            strava_id = activity_data["id"]

            existing_activity = db.query(StravaActivity).filter(
                StravaActivity.strava_id == strava_id
            ).first()

            if existing_activity:
                # Update only mapped fields; never touch primary key id
                existing_activity.activity_type = activity_data.get("type", existing_activity.activity_type)
                existing_activity.start_date = datetime.fromisoformat(activity_data["start_date"]).replace(tzinfo=timezone.utc)
                existing_activity.moving_time_s = activity_data.get("moving_time")
                existing_activity.distance_m = activity_data.get("distance")
                existing_activity.elevation_m = activity_data.get("total_elevation_gain")
                existing_activity.avg_hr = activity_data.get("average_heartrate")
                existing_activity.max_hr = activity_data.get("max_heartrate")
                existing_activity.calories = activity_data.get("calories")
                existing_activity.raw_json = str(activity_data)
                existing_activity.week_id = week_id
            else:
                # Create new activity
                activity = StravaActivity(
                    strava_id=strava_id,
                    activity_type=activity_data.get("type", "Unknown"),
                    start_date=datetime.fromisoformat(activity_data["start_date"]).replace(tzinfo=timezone.utc),
                    moving_time_s=activity_data.get("moving_time"),
                    distance_m=activity_data.get("distance"),
                    elevation_m=activity_data.get("total_elevation_gain"),
                    avg_hr=activity_data.get("average_heartrate"),
                    max_hr=activity_data.get("max_heartrate"),
                    calories=activity_data.get("calories"),
                    raw_json=str(activity_data),
                    week_id=week_id
                )
                db.add(activity)

            upserted_count += 1
        
        db.commit()
        return upserted_count

def compute_weekly_aggregates(week_id: str, db: Session) -> dict:
    """
    Queries StravaActivity rows for the week and returns aggregated statistics.
    """
    from app.models.strava_activity import StravaActivity
    
    activities = db.query(StravaActivity).filter(
        StravaActivity.week_id == week_id
    ).all()
    
    # Initialize aggregates
    run_km = 0.0
    ride_km = 0.0
    strength_sessions = 0
    total_moving_time_min = 0.0
    total_calories = 0.0
    total_elevation_m = 0.0
    session_counts = {}
    
    # Heart rate tracking
    hr_activities = []  # Activities with HR data
    avg_hr_sum = 0.0
    avg_hr_count = 0
    max_hr_overall = 0
    
    for activity in activities:
        activity_type = activity.activity_type
        distance = activity.distance_m or 0
        moving_time = activity.moving_time_s or 0
        calories = activity.calories or 0
        elevation = activity.elevation_m or 0
        avg_hr = activity.avg_hr
        max_hr = activity.max_hr
        
        if activity_type == "Run":
            run_km += distance / 1000  # Convert meters to kilometers
        elif activity_type == "Ride":
            ride_km += distance / 1000  # Convert meters to kilometers
        elif activity_type == "WeightTraining" or activity_type == "StrengthTraining":
            strength_sessions += 1
        
        # Track session counts
        if activity_type in session_counts:
            session_counts[activity_type] += 1
        else:
            session_counts[activity_type] = 1
        
        # Add moving time (convert seconds to minutes)
        total_moving_time_min += moving_time / 60
        
        # Add calories
        total_calories += calories
        
        # Add elevation
        total_elevation_m += elevation
        
        # Track heart rate data
        if avg_hr and avg_hr > 0:
            avg_hr_sum += avg_hr
            avg_hr_count += 1
            hr_activities.append({
                "type": activity_type,
                "avg_hr": avg_hr,
                "max_hr": max_hr,
                "duration_min": round(moving_time / 60, 1)
            })
        
        if max_hr and max_hr > max_hr_overall:
            max_hr_overall = max_hr
    
    # Calculate average heart rate across all activities with HR data
    avg_hr_weekly = round(avg_hr_sum / avg_hr_count, 1) if avg_hr_count > 0 else None
    
    return {
        "run_km": round(run_km, 2),
        "ride_km": round(ride_km, 2),
        "strength_sessions": strength_sessions,
        "total_moving_time_min": round(total_moving_time_min, 2),
        "total_calories": round(total_calories, 0),
        "total_elevation_m": round(total_elevation_m, 1),
        "session_counts": session_counts,
        "heart_rate_data": {
            "avg_hr_weekly": avg_hr_weekly,
            "max_hr_overall": max_hr_overall if max_hr_overall > 0 else None,
            "activities_with_hr": len(hr_activities),
            "hr_by_activity": hr_activities
        }
    }

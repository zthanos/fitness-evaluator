"""Strava OAuth authentication routes."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete
from app.services.strava_client import StravaClient

router = APIRouter()


@router.get("/config")
async def auth_config():
    """Return Keycloak configuration for the frontend JS adapter."""
    from app.config import get_settings
    settings = get_settings()
    return {
        "url": settings.KEYCLOAK_URL,
        "realm": settings.KEYCLOAK_REALM,
        "clientId": settings.KEYCLOAK_CLIENT_ID,
    }


@router.get("/strava")
async def strava_auth(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Initiate Strava OAuth flow for the authenticated athlete.

    Returns the authorization URL that the user should visit in their browser.
    The athlete ID is embedded in the OAuth state parameter so the callback
    can associate the Strava token with the correct athlete.

    Requirements: 19.2, 20.1
    """
    client = StravaClient(db)
    auth_url = client.get_authorization_url(athlete.id)
    return {"authorization_url": auth_url}


@router.get("/strava/callback")
async def strava_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """
    Handle Strava OAuth callback.

    Called by Strava after the user grants consent. The state parameter
    carries the athlete ID that was set when the OAuth flow was initiated
    (via GET /auth/strava) by the authenticated user.

    Requirements: 20.1, 20.2
    """
    try:
        athlete_id = int(state)
        client = StravaClient(db)
        await client.exchange_code(code, athlete_id)
        return RedirectResponse(url="/settings.html?strava_connected=true", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/settings.html?strava_error={str(e)}", status_code=303)


@router.get("/strava/status")
async def strava_status(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Check if Strava is connected for the authenticated athlete.

    Requirements: 19.2
    """
    from app.models.strava_token import StravaToken

    token = db.query(StravaToken).filter(StravaToken.athlete_id == athlete.id).first()
    if token:
        return {"connected": True, "expires_at": token.expires_at.isoformat()}
    return {"connected": False, "expires_at": None}


@router.post("/strava/disconnect")
async def strava_disconnect(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Disconnect Strava account for the authenticated athlete.

    Requirements: 19.2, 20.7
    """
    client = StravaClient(db)
    success = client.disconnect(athlete.id)
    if success:
        return {"message": "Strava account disconnected successfully"}
    raise HTTPException(status_code=404, detail="No Strava connection found")


@router.post("/strava/sync")
async def sync_strava_activities(
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Manually trigger Strava activity sync for the authenticated athlete.

    Requirements: 20.6, 20.7
    """
    import traceback
    try:
        client = StravaClient(db)
        synced_count = await client.sync_activities(athlete.id)
        return {
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} new activities",
        }
    except ValueError as e:
        traceback.print_exc()
        raise HTTPException(status_code=401, detail=str(e) or "Authorization error")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e) or 'Unknown error'}")

"""Strava OAuth authentication routes."""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.strava_client import StravaClient

router = APIRouter()


@router.get("/strava")
async def strava_auth(athlete_id: int = Query(default=1), db: Session = Depends(get_db)):
    """
    Initiate Strava OAuth flow.
    
    Returns the authorization URL that users should visit in their browser
    to grant access to their Strava activity data.
    
    Requirements: 19.2, 20.1
    """
    client = StravaClient(db)
    auth_url = client.get_authorization_url(athlete_id)
    return {"authorization_url": auth_url}


@router.get("/strava/callback")
async def strava_callback(
    code: str,
    state: str = Query(default="1"),
    db: Session = Depends(get_db)
):
    """
    Handle Strava OAuth callback.
    
    Exchanges the authorization code for access and refresh tokens,
    then redirects to settings page with success message.
    Called automatically after user grants consent on Strava.
    
    Requirements: 20.1, 20.2
    
    **Parameters:**
    - `code`: Authorization code from Strava OAuth flow
    - `state`: Athlete ID passed through OAuth flow
    """
    try:
        athlete_id = int(state)
        client = StravaClient(db)
        result = await client.exchange_code(code, athlete_id)
        
        # Redirect to settings page with success
        redirect_url = "/settings.html?strava_connected=true"
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        # On error, redirect to settings with error parameter
        redirect_url = f"/settings.html?strava_error={str(e)}"
        return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/strava/status")
async def strava_status(athlete_id: int = Query(default=1), db: Session = Depends(get_db)):
    """
    Check if Strava is connected for the athlete.
    
    Returns the connection status and token expiration.
    
    Requirements: 19.2
    """
    from app.models.strava_token import StravaToken
    
    token = db.query(StravaToken).filter(
        StravaToken.athlete_id == athlete_id
    ).first()
    
    if token:
        return {
            "connected": True,
            "expires_at": token.expires_at.isoformat()
        }
    else:
        return {
            "connected": False,
            "expires_at": None
        }


@router.post("/strava/disconnect")
async def strava_disconnect(athlete_id: int = Query(default=1), db: Session = Depends(get_db)):
    """
    Disconnect Strava account by deleting stored tokens.
    
    Requirements: 19.2, 20.7
    """
    client = StravaClient(db)
    success = client.disconnect(athlete_id)
    
    if success:
        return {"message": "Strava account disconnected successfully"}
    else:
        raise HTTPException(status_code=404, detail="No Strava connection found")


@router.post("/strava/sync")
async def sync_strava_activities(athlete_id: int = Query(default=1), db: Session = Depends(get_db)):
    """
    Manually trigger Strava activity sync.
    
    Syncs new activities from Strava to the database.
    If activities exist, syncs from the latest activity date.
    If no activities exist, syncs all activities from Strava account.
    
    Requirements: 20.6, 20.7
    
    **Returns:**
    - `synced_count`: Number of new activities synced
    - `message`: Status message
    """
    import traceback
    try:
        client = StravaClient(db)
        synced_count = await client.sync_activities(athlete_id)
        
        return {
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} new activities"
        }
    except ValueError as e:
        # Handle authorization revocation
        error_msg = str(e) or "Authorization error"
        print(f"ValueError during sync: {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=401, detail=error_msg)
    except Exception as e:
        # Log the full error for debugging
        error_msg = str(e) or "Unknown error occurred"
        print(f"Exception during sync: {error_msg}")
        print(f"Exception type: {type(e).__name__}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Sync failed: {error_msg}")




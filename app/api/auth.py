"""Strava OAuth authentication routes."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.strava_service import (
    build_authorization_url,
    exchange_code,
)

router = APIRouter()


@router.get("/strava")
async def strava_auth():
    """
    Initiate Strava OAuth flow.
    
    Returns the authorization URL that users should visit in their browser
    to grant access to their Strava activity data.
    """
    auth_url = build_authorization_url()
    return {"authorization_url": auth_url}


@router.get("/strava/callback")
async def strava_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle Strava OAuth callback.
    
    Exchanges the authorization code for access and refresh tokens,
    then redirects to index.html with success message and athlete information.
    Called automatically after user grants consent on Strava.
    
    **Parameters:**
    - `code`: Authorization code from Strava OAuth flow
    """
    try:
        tokens = await exchange_code(code)
        
        # Extract athlete information from the token response
        athlete = tokens.get("athlete", {})
        athlete_name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
        athlete_id = athlete.get("id", "")
        
        # If no athlete name, use a default
        if not athlete_name:
            athlete_name = "Strava User"
        
        # Redirect to index.html with success parameters
        redirect_url = f"/index.html?success=true&athlete_name={athlete_name}&athlete_id={athlete_id}"
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        # On error, redirect to index.html with error parameter
        redirect_url = f"/index.html?success=false&error={str(e)}"
        return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/strava/status")
async def strava_status():
    """
    Check if Strava tokens are available.
    
    Returns the connection status and whether tokens are present.
    """
    from app.services.strava_service import _strava_tokens
    
    has_tokens = "access_token" in _strava_tokens and "refresh_token" in _strava_tokens
    
    return {
        "connected": has_tokens,
        "has_access_token": "access_token" in _strava_tokens,
        "has_refresh_token": "refresh_token" in _strava_tokens,
        "token_expires_at": _strava_tokens.get("expires_at") if has_tokens else None
    }
@router.get("/strava/status")
async def strava_status():
    """
    Check if Strava tokens are available.

    Returns the connection status and whether tokens are present.
    """
    from app.services.strava_service import _strava_tokens

    has_tokens = "access_token" in _strava_tokens and "refresh_token" in _strava_tokens

    return {
        "connected": has_tokens,
        "has_access_token": "access_token" in _strava_tokens,
        "has_refresh_token": "refresh_token" in _strava_tokens,
        "token_expires_at": _strava_tokens.get("expires_at") if has_tokens else None
    }



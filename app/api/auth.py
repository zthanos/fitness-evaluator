"""Strava OAuth authentication routes."""

from fastapi import APIRouter, HTTPException, Depends
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
    
    Exchanges the authorization code for access and refresh tokens.
    Called automatically after user grants consent on Strava.
    
    **Parameters:**
    - `code`: Authorization code from Strava OAuth flow
    """
    try:
        tokens = await exchange_code(code)
        return {
            "message": "Successfully authenticated with Strava",
            "access_token": tokens.get("access_token"),
            "expires_at": tokens.get("expires_at"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


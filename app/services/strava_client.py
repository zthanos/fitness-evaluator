# app/services/strava_client.py
"""
StravaClient service for OAuth integration and activity syncing.
Implements Requirements 20 (Strava OAuth Integration) and 30 (Security).
"""
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from app.config import get_settings
from app.models.strava_token import StravaToken
from app.models.strava_activity import StravaActivity


class StravaClient:
    """
    Manages Strava API integration with OAuth authentication and token encryption.
    
    Requirements:
    - 20.1: OAuth flow with authorization URL redirect
    - 20.2: Token exchange and refresh token handling
    - 20.3: Fernet encryption for tokens stored in database
    - 20.4: Encryption key in environment variable
    - 20.5: Automatic token refresh when expired
    - 20.6: Configurable scheduled sync
    - 20.7: Handle authorization revocation
    - 30.1: Encrypt tokens using Fernet symmetric encryption
    - 30.2: Store encryption keys in environment variables
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize StravaClient with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.settings = get_settings()
        
        # Initialize Fernet cipher for token encryption
        if not self.settings.STRAVA_ENCRYPTION_KEY:
            raise ValueError("STRAVA_ENCRYPTION_KEY must be set in environment variables")
        
        self.cipher = Fernet(self.settings.STRAVA_ENCRYPTION_KEY.encode())
    
    def get_authorization_url(self, athlete_id: int) -> str:
        """
        Generate Strava OAuth authorization URL.
        
        Requirements: 20.1
        
        Args:
            athlete_id: ID of the athlete connecting their Strava account
            
        Returns:
            Authorization URL to redirect user to Strava
        """
        return (
            "https://www.strava.com/oauth/authorize?"
            f"client_id={self.settings.STRAVA_CLIENT_ID}&"
            "response_type=code&"
            f"redirect_uri={self.settings.STRAVA_REDIRECT_URI}&"
            "scope=read,activity:read_all&"
            f"state={athlete_id}"
        )
    
    async def exchange_code(self, code: str, athlete_id: int) -> dict:
        """
        Exchange authorization code for access and refresh tokens.
        
        Requirements: 20.2, 20.3, 20.4, 30.1, 30.2
        
        Args:
            code: Authorization code from Strava OAuth callback
            athlete_id: ID of the athlete
            
        Returns:
            Dictionary with token information
            
        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.settings.STRAVA_CLIENT_ID,
                    "client_secret": self.settings.STRAVA_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                }
            )
            response.raise_for_status()
            token_data = response.json()
        
        # Encrypt tokens before storing
        access_token_encrypted = self._encrypt_token(token_data["access_token"])
        refresh_token_encrypted = self._encrypt_token(token_data["refresh_token"])
        expires_at = datetime.fromtimestamp(token_data["expires_at"], tz=timezone.utc)
        
        # Store or update tokens in database
        strava_token = self.db.query(StravaToken).filter(
            StravaToken.athlete_id == athlete_id
        ).first()
        
        if strava_token:
            # Update existing token
            strava_token.access_token_encrypted = access_token_encrypted
            strava_token.refresh_token_encrypted = refresh_token_encrypted
            strava_token.expires_at = expires_at
            strava_token.updated_at = datetime.now(timezone.utc)
        else:
            # Create new token record
            strava_token = StravaToken(
                athlete_id=athlete_id,
                access_token_encrypted=access_token_encrypted,
                refresh_token_encrypted=refresh_token_encrypted,
                expires_at=expires_at
            )
            self.db.add(strava_token)
        
        self.db.commit()
        
        return {
            "athlete_id": athlete_id,
            "expires_at": expires_at.isoformat(),
            "strava_athlete_id": token_data.get("athlete", {}).get("id")
        }
    
    async def refresh_token(self, athlete_id: int) -> str:
        """
        Refresh access token if expired or expiring soon.
        
        Requirements: 20.5
        
        Args:
            athlete_id: ID of the athlete
            
        Returns:
            Current valid access token (decrypted)
            
        Raises:
            ValueError: If no token found for athlete
            httpx.HTTPStatusError: If token refresh fails
        """
        strava_token = self.db.query(StravaToken).filter(
            StravaToken.athlete_id == athlete_id
        ).first()
        
        if not strava_token:
            raise ValueError(f"No Strava token found for athlete {athlete_id}")
        
        # Check if token expires within 5 minutes
        now = datetime.now(timezone.utc)
        
        # Ensure expires_at is timezone-aware for comparison
        expires_at = strava_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at > now + timedelta(minutes=5):
            # Token is still valid, return it
            return self._decrypt_token(strava_token.access_token_encrypted)
        
        # Token expired or expiring soon, refresh it
        refresh_token = self._decrypt_token(strava_token.refresh_token_encrypted)
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.settings.STRAVA_CLIENT_ID,
                    "client_secret": self.settings.STRAVA_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            token_data = response.json()
        
        # Update tokens in database
        strava_token.access_token_encrypted = self._encrypt_token(token_data["access_token"])
        strava_token.refresh_token_encrypted = self._encrypt_token(token_data["refresh_token"])
        strava_token.expires_at = datetime.fromtimestamp(token_data["expires_at"], tz=timezone.utc)
        strava_token.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        return token_data["access_token"]
    
    async def get_activities(self, athlete_id: int, after: Optional[datetime] = None, per_page: int = 200) -> List[dict]:
        """
        Fetch activities from Strava API with pagination support.
        
        Requirements: 20.6
        
        Args:
            athlete_id: ID of the athlete
            after: Only fetch activities after this datetime (optional)
            per_page: Number of activities per page (max 200, default 200)
            
        Returns:
            List of activity dictionaries from Strava API
            
        Raises:
            ValueError: If no token found for athlete
            httpx.HTTPStatusError: If API request fails
        """
        # Get valid access token (will refresh if needed)
        access_token = await self.refresh_token(athlete_id)
        
        all_activities = []
        page = 1
        
        while True:
            # Build query parameters
            params = {
                "per_page": min(per_page, 200),  # Strava max is 200
                "page": page
            }
            if after:
                params["after"] = int(after.timestamp())
            
            # Fetch activities from Strava
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.get(
                    "https://www.strava.com/api/v3/athlete/activities",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params
                )
                response.raise_for_status()
                activities = response.json()
            
            # If no activities returned, we've reached the end
            if not activities:
                break
            
            all_activities.extend(activities)
            
            # If we got fewer activities than requested, we've reached the end
            if len(activities) < params["per_page"]:
                break
            
            page += 1
        
        return all_activities
    
    async def sync_activities(self, athlete_id: int) -> int:
        """
        Sync activities from Strava to database.
        
        Requirements: 20.6, 20.7
        
        Args:
            athlete_id: ID of the athlete
            
        Returns:
            Number of new activities synced
            
        Raises:
            ValueError: If no token found for athlete
            httpx.HTTPStatusError: If API request fails (including revoked authorization)
        """
        # Get the most recent activity to determine sync starting point
        latest_activity = self.db.query(StravaActivity).filter(
            StravaActivity.athlete_id == athlete_id
        ).order_by(StravaActivity.start_date.desc()).first()
        
        # Ensure after datetime is timezone-aware
        after = None
        if latest_activity:
            after = latest_activity.start_date
            # If the datetime is naive, make it UTC-aware
            if after and after.tzinfo is None:
                after = after.replace(tzinfo=timezone.utc)
        
        try:
            # Fetch activities from Strava
            activities_data = await self.get_activities(athlete_id, after)
        except httpx.HTTPStatusError as e:
            # Handle authorization revocation (401 Unauthorized)
            if e.response.status_code == 401:
                # Delete the token from database
                self.db.query(StravaToken).filter(
                    StravaToken.athlete_id == athlete_id
                ).delete()
                self.db.commit()
                raise ValueError("Strava authorization has been revoked")
            raise
        
        # Sync activities to database
        synced_count = 0
        for activity_data in activities_data:
            strava_id = activity_data["id"]
            
            # Check if activity already exists
            existing = self.db.query(StravaActivity).filter(
                StravaActivity.strava_id == strava_id
            ).first()
            
            if not existing:
                # Create new activity (simplified - would need proper mapping)
                activity = StravaActivity(
                    athlete_id=athlete_id,
                    strava_id=strava_id,
                    activity_type=activity_data.get("type", "Unknown"),
                    start_date=datetime.fromisoformat(
                        activity_data["start_date"].replace("Z", "+00:00")
                    ),
                    moving_time_s=activity_data.get("moving_time"),
                    distance_m=activity_data.get("distance"),
                    elevation_m=activity_data.get("total_elevation_gain"),
                    avg_hr=activity_data.get("average_heartrate"),
                    max_hr=activity_data.get("max_heartrate"),
                    calories=activity_data.get("calories"),
                    raw_json=str(activity_data)
                )
                self.db.add(activity)
                synced_count += 1
        
        self.db.commit()
        return synced_count
    
    def disconnect(self, athlete_id: int) -> bool:
        """
        Disconnect Strava account by deleting stored tokens.
        
        Requirements: 20.7
        
        Args:
            athlete_id: ID of the athlete
            
        Returns:
            True if tokens were deleted, False if no tokens found
        """
        deleted = self.db.query(StravaToken).filter(
            StravaToken.athlete_id == athlete_id
        ).delete()
        
        self.db.commit()
        return deleted > 0
    
    def _encrypt_token(self, token: str) -> bytes:
        """
        Encrypt a token using Fernet symmetric encryption.
        
        Requirements: 20.3, 30.1
        
        Args:
            token: Plain text token
            
        Returns:
            Encrypted token as bytes
        """
        return self.cipher.encrypt(token.encode())
    
    def _decrypt_token(self, encrypted: bytes) -> str:
        """
        Decrypt a token using Fernet symmetric encryption.
        
        Requirements: 20.3, 30.1
        
        Args:
            encrypted: Encrypted token as bytes
            
        Returns:
            Decrypted plain text token
        """
        return self.cipher.decrypt(encrypted).decode()

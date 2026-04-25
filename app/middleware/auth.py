"""Keycloak JWT authentication dependency.

Usage in any endpoint:
    from app.middleware.auth import get_current_athlete
    ...
    async def my_endpoint(athlete: Athlete = Depends(get_current_athlete)):
        ...
"""
import logging
from functools import lru_cache
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.athlete import Athlete

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


# ── JWKS cache ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch and cache Keycloak's public signing keys."""
    settings = get_settings()
    try:
        response = httpx.get(settings.keycloak_jwks_uri, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to fetch JWKS from %s: %s", settings.keycloak_jwks_uri, e)
        raise


def _invalidate_jwks_cache() -> None:
    """Call this if token validation fails with a key error — forces a JWKS refresh."""
    _get_jwks.cache_clear()


# ── Token validation ──────────────────────────────────────────────────────────

def _validate_token(token: str) -> dict:
    """Validate a Bearer token against Keycloak's JWKS. Returns the decoded payload."""
    settings = get_settings()
    try:
        jwks = _get_jwks()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )

    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            issuer=settings.keycloak_issuer,
            options={"verify_at_hash": False},
        )
        return payload
    except JWTError as e:
        # If the error looks like an unknown key, refresh the cache and retry once
        _invalidate_jwks_cache()
        try:
            jwks = _get_jwks()
            return jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=settings.KEYCLOAK_CLIENT_ID,
                issuer=settings.keycloak_issuer,
                options={"verify_at_hash": False},
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )


# ── Athlete auto-provisioning ─────────────────────────────────────────────────

def _get_or_create_athlete(sub: str, payload: dict, db: Session) -> Athlete:
    """Return the Athlete for this Keycloak user, creating one on first login."""
    athlete = db.query(Athlete).filter(Athlete.keycloak_sub == sub).first()
    if athlete:
        return athlete

    athlete = Athlete(
        keycloak_sub=sub,
        name=payload.get("name") or payload.get("preferred_username", "Unknown"),
        email=payload.get("email"),
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    logger.info("Auto-provisioned athlete id=%d for keycloak_sub=%s", athlete.id, sub)
    return athlete


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_current_athlete(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Athlete:
    """Validate Bearer JWT and return (or auto-provision) the Athlete."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _validate_token(credentials.credentials)
    sub: str = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )

    return _get_or_create_athlete(sub, payload, db)

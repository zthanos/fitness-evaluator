"""Routes API — GPX upload, analysis, and route profile retrieval.

Endpoints
---------
POST /api/routes/analyze  — upload GPX → analyze → persist RouteProfile → return
GET  /api/routes/{id}     — fetch previously saved RouteProfile
GET  /api/routes          — list athlete's saved route profiles
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete
from app.models.route_profile import RouteProfile
from app.ai.skills.route_analyzer import analyze, RouteAnalysis

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_GPX_BYTES = 10 * 1024 * 1024  # 10 MB
_VALID_SPORTS  = {"ride", "run"}


# ── POST /analyze ─────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_route(
    file:   UploadFile  = File(..., description="GPX file"),
    sport:  str         = Form(..., description="ride | run"),
    athlete: Athlete    = Depends(get_current_athlete),
    db:      Session    = Depends(get_db),
):
    """
    Upload a GPX file, run RouteAnalyzer, persist the RouteProfile, and return
    the full analysis.  If the same file (matched by SHA-256 hash) was already
    analysed for this athlete, returns the cached profile instead.
    """
    if sport not in _VALID_SPORTS:
        raise HTTPException(400, f"sport must be one of {sorted(_VALID_SPORTS)}")

    if not file.filename or not file.filename.lower().endswith(".gpx"):
        raise HTTPException(400, "Only .gpx files are accepted")

    content = await file.read()
    if len(content) > _MAX_GPX_BYTES:
        raise HTTPException(413, f"GPX file exceeds {_MAX_GPX_BYTES // 1024 // 1024} MB limit")
    if not content:
        raise HTTPException(400, "Empty file")

    # ── Run analyzer ─────────────────────────────────────────────────────────
    try:
        analysis: RouteAnalysis = analyze(content, sport, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))

    # ── Dedup by hash ─────────────────────────────────────────────────────────
    existing = (
        db.query(RouteProfile)
        .filter_by(athlete_id=athlete.id, gpx_hash=analysis.gpx_hash, sport=sport)
        .first()
    )
    if existing:
        logger.info("Route %s already analysed (id=%d)", analysis.gpx_hash[:8], existing.id)
        return {"route_profile": _to_dict(existing), "cached": True}

    # ── Persist ───────────────────────────────────────────────────────────────
    profile = RouteProfile(
        athlete_id             = athlete.id,
        filename               = file.filename,
        sport                  = sport,
        gpx_hash               = analysis.gpx_hash,
        distance_km            = analysis.distance_km,
        total_elevation_gain_m = analysis.total_elevation_gain_m,
        total_elevation_loss_m = analysis.total_elevation_loss_m,
        max_elevation_m        = analysis.max_elevation_m,
        min_elevation_m        = analysis.min_elevation_m,
        max_gradient_pct       = analysis.max_gradient_pct,
        avg_climb_gradient_pct = analysis.avg_climb_gradient_pct,
        difficulty_score       = analysis.difficulty_score,
        route_difficulty       = analysis.route_difficulty,
        climb_segments         = analysis.climb_segments,
        descent_segments       = analysis.descent_segments,
        flat_segments          = analysis.flat_segments,
        critical_sections      = analysis.critical_sections,
        elevation_profile      = analysis.elevation_profile,
        analysis_summary       = analysis.analysis_summary,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    logger.info(
        "RouteProfile id=%d: %s, %.1f km, %.0f m gain, %s",
        profile.id, sport, analysis.distance_km,
        analysis.total_elevation_gain_m, analysis.route_difficulty,
    )
    return {"route_profile": _to_dict(profile), "cached": False}


# ── GET /  (list) ─────────────────────────────────────────────────────────────

@router.get("")
async def list_routes(
    sport:   Optional[str] = None,
    athlete: Athlete        = Depends(get_current_athlete),
    db:      Session        = Depends(get_db),
):
    """List all saved route profiles for the athlete, newest first."""
    q = db.query(RouteProfile).filter_by(athlete_id=athlete.id)
    if sport:
        q = q.filter_by(sport=sport)
    profiles = q.order_by(RouteProfile.created_at.desc()).all()
    return {"route_profiles": [_to_dict(p, include_segments=False) for p in profiles]}


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@router.get("/{route_id}")
async def get_route(
    route_id: int,
    athlete:  Athlete  = Depends(get_current_athlete),
    db:       Session  = Depends(get_db),
):
    """Get a single RouteProfile by id (must belong to the authenticated athlete)."""
    profile = db.query(RouteProfile).filter_by(id=route_id, athlete_id=athlete.id).first()
    if not profile:
        raise HTTPException(404, "Route profile not found")
    return {"route_profile": _to_dict(profile)}


# ── GET /{route_id}/readiness ─────────────────────────────────────────────────

@router.get("/{route_id}/readiness")
async def get_route_readiness(
    route_id: int,
    athlete:  Athlete  = Depends(get_current_athlete),
    db:       Session  = Depends(get_db),
):
    """Compute deterministic athlete-vs-route readiness (no LLM)."""
    from app.models.athlete_sport_profile import AthleteSportProfile
    from app.ai.skills.sport_profile_builder import profile_to_dict
    from app.services.route_readiness import compute_readiness

    route = db.query(RouteProfile).filter_by(id=route_id, athlete_id=athlete.id).first()
    if not route:
        raise HTTPException(404, "Route profile not found")

    sp_model = (
        db.query(AthleteSportProfile)
        .filter_by(athlete_id=athlete.id, sport_group=route.sport)
        .first()
    )
    sport_profile = profile_to_dict(sp_model) if sp_model else {}

    try:
        return compute_readiness(route, sport_profile)
    except Exception as exc:
        logger.error("Readiness computation failed route=%d: %s", route_id, exc, exc_info=True)
        raise HTTPException(500, str(exc))


# ── POST /{route_id}/plan ─────────────────────────────────────────────────────

class CreateRoutePlanRequest(BaseModel):
    event_date:      date
    goal_type:       str   # finish | target_time | improve_climbing | improve_pace
    duration_weeks:  int   = 8
    target_time_min: Optional[int] = None  # only for goal_type == target_time
    goal_id:         Optional[str] = None


_VALID_GOAL_TYPES = {"finish", "target_time", "improve_climbing", "improve_pace"}


@router.post("/{route_id}/plan")
async def create_route_plan(
    route_id: int,
    body:     CreateRoutePlanRequest,
    athlete:  Athlete  = Depends(get_current_athlete),
    db:       Session  = Depends(get_db),
):
    """
    Generate a training plan calibrated to a specific route.

    The plan prepares the athlete FOR the route — sessions are general
    (local roads, gym, track) but their demands mirror the route's
    critical sections, elevation, and target distance.

    Returns the created TrainingPlan id plus a performance estimate at
    current fitness.
    """
    if body.goal_type not in _VALID_GOAL_TYPES:
        raise HTTPException(400, f"goal_type must be one of {sorted(_VALID_GOAL_TYPES)}")
    if body.event_date <= date.today():
        raise HTTPException(400, "event_date must be in the future")
    if body.duration_weeks < 1 or body.duration_weeks > 24:
        raise HTTPException(400, "duration_weeks must be between 1 and 24")

    # Confirm the route belongs to this athlete
    route = db.query(RouteProfile).filter_by(id=route_id, athlete_id=athlete.id).first()
    if not route:
        raise HTTPException(404, "Route profile not found")

    from app.ai.skills.route_specific_training_planner import (
        RouteSpecificTrainingPlanner, RouteSpecificPlannerInput,
    )
    planner = RouteSpecificTrainingPlanner(db=db, athlete_id=athlete.id)
    plan_input = RouteSpecificPlannerInput(
        route_id=route_id,
        event_date=body.event_date,
        goal_type=body.goal_type,
        duration_weeks=body.duration_weeks,
        target_time_min=body.target_time_min,
        goal_id=body.goal_id,
    )

    try:
        result = await planner.run(plan_input)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("RouteSpecificTrainingPlanner failed: %s", exc, exc_info=True)
        raise HTTPException(500, "Plan generation failed — please try again")

    logger.info(
        "Created route plan id=%s for athlete=%d route=%d goal=%s",
        result.plan_id, athlete.id, route_id, body.goal_type,
    )
    return {
        "plan_id":    result.plan_id,
        "title":      result.title,
        "sport":      result.sport,
        "weeks":      result.weeks,
        "summary":    result.summary,
        "route_name": route.filename,
    }


# ── Serialiser ────────────────────────────────────────────────────────────────

def _to_dict(p: RouteProfile, include_segments: bool = True) -> dict:
    d = {
        "id":                    p.id,
        "filename":              p.filename,
        "sport":                 p.sport,
        "distance_km":           p.distance_km,
        "total_elevation_gain_m": p.total_elevation_gain_m,
        "total_elevation_loss_m": p.total_elevation_loss_m,
        "max_elevation_m":       p.max_elevation_m,
        "min_elevation_m":       p.min_elevation_m,
        "max_gradient_pct":      p.max_gradient_pct,
        "avg_climb_gradient_pct": p.avg_climb_gradient_pct,
        "difficulty_score":      p.difficulty_score,
        "route_difficulty":      p.route_difficulty,
        "critical_sections":     p.critical_sections or [],
        "analysis_summary":      p.analysis_summary,
        "created_at":            p.created_at.isoformat() if p.created_at else None,
    }
    if include_segments:
        d["climb_segments"]    = p.climb_segments    or []
        d["descent_segments"]  = p.descent_segments  or []
        d["flat_segments"]     = p.flat_segments     or []
        d["elevation_profile"] = p.elevation_profile or []
    return d

"""Training Plan API endpoints for Plan Progress Screen

Provides endpoints for:
- Listing all training plans for a user
- Getting detailed plan information
- Getting adherence time series data

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 18.1, 18.2, 20.2
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Any, Optional
import time
import logging

from app.database import get_db
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlan as TrainingPlanModel
from app.models.training_plan_week import TrainingPlanWeek as TrainingPlanWeekModel
from app.models.training_plan_session import TrainingPlanSession as TrainingPlanSessionModel
from app.services.adherence_calculator import AdherenceCalculator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", summary="List all training plans")
async def list_training_plans(
    status: Optional[str] = Query(None, description="Filter by status (draft, active, completed, abandoned)"),
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db)
):
    """
    List all training plans for the authenticated user.
    
    Returns plan summaries with adherence metrics for display in the Plans List View.
    
    **Query Parameters:**
    - `user_id`: User ID to filter plans (required)
    
    **Returns:**
    - `plans`: Array of plan summaries with:
      - `id`: Plan UUID
      - `title`: Plan title
      - `sport`: Primary sport
      - `goal`: Goal description (if linked)
      - `start_date`: Plan start date (ISO format)
      - `end_date`: Plan end date (ISO format)
      - `status`: Plan status (draft, active, completed, abandoned)
      - `adherence_percentage`: Overall adherence score
      - `total_sessions`: Total number of sessions
      - `completed_sessions`: Number of completed sessions
    
    **Performance Target:** < 2 seconds at p95 (Requirement 18.1)
    
    Requirements: 12.1, 12.2, 12.3, 12.5, 18.1, 20.2
    """
    start_time = time.time()

    valid_statuses = ['draft', 'active', 'completed', 'abandoned']
    if status and status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")

    try:
        query = db.query(TrainingPlanModel).filter(TrainingPlanModel.user_id == athlete.id)
        if status:
            query = query.filter(TrainingPlanModel.status == status)

        plans = query.options(
            joinedload(TrainingPlanModel.weeks).joinedload(TrainingPlanWeekModel.sessions)
        ).order_by(TrainingPlanModel.created_at.desc()).all()

        plan_summaries = []
        for plan in plans:
            adherence = AdherenceCalculator.calculate_plan_adherence(plan)
            total_sessions = sum(len(week.sessions) for week in plan.weeks)
            completed_sessions = sum(
                sum(1 for s in week.sessions if s.completed) for week in plan.weeks
            )
            plan_summaries.append({
                "id": plan.id,
                "title": plan.title,
                "sport": plan.sport,
                "goal": plan.goal.description if plan.goal else None,
                "start_date": plan.start_date.isoformat(),
                "end_date": plan.end_date.isoformat(),
                "status": plan.status,
                "adherence_percentage": round(adherence, 1),
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
            })

        latency_ms = (time.time() - start_time) * 1000
        logger.info("Listed %d plans for athlete=%d in %.0fms", len(plan_summaries), athlete.id, latency_ms)
        return {"plans": plan_summaries}

    except Exception as e:
        logger.error("Error listing training plans for athlete=%d: %s", athlete.id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plan_id}", summary="Get plan details")
async def get_training_plan(
    plan_id: str,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db)
):
    """
    Get detailed training plan with all weeks and sessions.

    Requirements: 13.1, 13.2, 13.3, 13.4, 13.6, 18.2, 20.2
    """
    start_time = time.time()

    try:
        plan = db.query(TrainingPlanModel).filter(
            TrainingPlanModel.id == plan_id,
            TrainingPlanModel.user_id == athlete.id
        ).options(
            joinedload(TrainingPlanModel.weeks)
            .joinedload(TrainingPlanWeekModel.sessions)
        ).first()
        
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found or access denied")

        overall_adherence = AdherenceCalculator.calculate_plan_adherence(plan)

        # Fetch route context when this is a route-specific plan
        route_context = None
        if plan.route_profile_id:
            try:
                from app.models.route_profile import RouteProfile
                route = db.query(RouteProfile).filter_by(id=plan.route_profile_id).first()
                if route:
                    route_context = {
                        "id":                    route.id,
                        "name":                  (route.filename or "Route").replace(".gpx", "").replace("_", " ").replace("-", " "),
                        "distance_km":           route.distance_km,
                        "total_elevation_gain_m": route.total_elevation_gain_m,
                        "max_gradient_pct":      route.max_gradient_pct,
                        "route_difficulty":      route.route_difficulty,
                        "critical_sections":     route.critical_sections or [],
                        "analysis_summary":      route.analysis_summary,
                    }
            except Exception:
                pass

        # Format weeks
        weeks_data = []
        for week in plan.weeks:
            week_adherence = AdherenceCalculator.calculate_week_adherence(week)
            sessions_data = []
            for session in week.sessions:
                session_data = {
                    "id": session.id,
                    "day_of_week": session.day_of_week,
                    "session_type": session.session_type,
                    "duration_minutes": session.duration_minutes,
                    "intensity": session.intensity,
                    "description": session.description,
                    "completed": session.completed,
                    "matched_activity_id": session.matched_activity_id
                }
                if session.matched_activity and session.matched_activity_id:
                    session_data["matched_activity"] = {
                        "id": session.matched_activity.id,
                        "strava_id": session.matched_activity.strava_id,
                        "distance_m": session.matched_activity.distance_m,
                        "moving_time_s": session.matched_activity.moving_time_s
                    }
                sessions_data.append(session_data)

            weeks_data.append({
                "id": week.id,
                "week_number": week.week_number,
                "phase": week.phase,
                "focus": week.focus,
                "volume_target": week.volume_target,
                "distance_target_km": week.distance_target_km,
                "adherence": round(week_adherence, 1),
                "sessions": sessions_data
            })

        plan_data = {
            "id": plan.id,
            "user_id": plan.user_id,
            "title": plan.title,
            "sport": plan.sport,
            "goal_id": plan.goal_id,
            "goal": {
                "id": plan.goal.id,
                "description": plan.goal.description,
                "goal_type": plan.goal.goal_type,
                "target_date": plan.goal.target_date.isoformat() if plan.goal.target_date else None,
                "target_value": plan.goal.target_value
            } if plan.goal else None,
            "route_profile_id": plan.route_profile_id,
            "route_context": route_context,
            "plan_metadata": plan.plan_metadata,
            "start_date": plan.start_date.isoformat(),
            "end_date": plan.end_date.isoformat(),
            "status": plan.status,
            "overall_adherence": round(overall_adherence, 1),
            "weeks": weeks_data
        }
        
        latency_ms = (time.time() - start_time) * 1000
        logger.info("Retrieved plan %s for athlete=%d in %.0fms", plan_id, athlete.id, latency_ms)
        if latency_ms > 2000:
            logger.warning("PERFORMANCE WARNING: get_training_plan exceeded 2s target: %.0fms", latency_ms)

        return {"plan": plan_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving plan %s for athlete=%d: %s", plan_id, athlete.id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{plan_id}", summary="Delete a training plan")
async def delete_training_plan(
    plan_id: str,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db)
):
    """Delete a training plan and all its weeks/sessions."""
    try:
        plan = db.query(TrainingPlanModel).filter(
            TrainingPlanModel.id == plan_id,
            TrainingPlanModel.user_id == athlete.id
        ).first()

        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found or access denied")

        db.delete(plan)
        db.commit()
        logger.info("Deleted plan %s for athlete=%d", plan_id, athlete.id)
        return {"ok": True}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error deleting plan %s for athlete=%d: %s", plan_id, athlete.id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plan_id}/adherence", summary="Get adherence time series")
async def get_plan_adherence(
    plan_id: str,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db)
):
    """
    Get adherence time series for charting.

    Requirement: 13.5, 20.2
    """
    try:
        plan = db.query(TrainingPlanModel).filter(
            TrainingPlanModel.id == plan_id,
            TrainingPlanModel.user_id == athlete.id
        ).options(
            joinedload(TrainingPlanModel.weeks)
            .joinedload(TrainingPlanWeekModel.sessions)
        ).first()

        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found or access denied")

        adherence_by_week = []
        for week in plan.weeks:
            week_adherence = AdherenceCalculator.calculate_week_adherence(week)
            adherence_by_week.append({
                "week": week.week_number,
                "adherence": round(week_adherence, 1)
            })

        overall_adherence = AdherenceCalculator.calculate_plan_adherence(plan)

        return {
            "adherence_by_week": adherence_by_week,
            "overall_adherence": round(overall_adherence, 1)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving adherence for plan %s for athlete=%d: %s", plan_id, athlete.id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

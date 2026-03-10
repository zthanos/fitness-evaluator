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
from app.models.training_plan import TrainingPlan as TrainingPlanModel
from app.models.training_plan_week import TrainingPlanWeek as TrainingPlanWeekModel
from app.models.training_plan_session import TrainingPlanSession as TrainingPlanSessionModel
from app.services.adherence_calculator import AdherenceCalculator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", summary="List all training plans")
async def list_training_plans(
    user_id: int = Query(1, description="User ID for filtering plans"),
    status: Optional[str] = Query(None, description="Filter by status (draft, active, completed, abandoned)"),
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
    
    # Validate user_id is present (Requirement 20.2)
    if user_id is None:
        logger.error("SECURITY VIOLATION: user_id is None in list_training_plans")
        raise HTTPException(status_code=400, detail="user_id is required")
    
    # Validate status if provided
    valid_statuses = ['draft', 'active', 'completed', 'abandoned']
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
        )
    
    try:
        # Query plans with user_id scoping (Requirement 20.2)
        query = db.query(TrainingPlanModel).filter(
            TrainingPlanModel.user_id == user_id
        )
        
        # Apply status filter if provided
        if status:
            query = query.filter(TrainingPlanModel.status == status)
        
        plans = query.options(
            joinedload(TrainingPlanModel.weeks)
            .joinedload(TrainingPlanWeekModel.sessions)
        ).order_by(TrainingPlanModel.created_at.desc()).all()
        
        # Format response
        plan_summaries = []
        for plan in plans:
            # Calculate adherence (Requirement 12.3)
            adherence = AdherenceCalculator.calculate_plan_adherence(plan)
            
            # Count sessions
            total_sessions = sum(len(week.sessions) for week in plan.weeks)
            completed_sessions = sum(
                sum(1 for session in week.sessions if session.completed)
                for week in plan.weeks
            )
            
            plan_summaries.append({
                "id": plan.id,
                "title": plan.title,
                "sport": plan.sport,
                "goal": None,  # TODO: Load goal description if goal_id is set
                "start_date": plan.start_date.isoformat(),
                "end_date": plan.end_date.isoformat(),
                "status": plan.status,
                "adherence_percentage": round(adherence, 1),
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions
            })
        
        # Log performance (Requirement 18.1)
        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Listed {len(plan_summaries)} plans for user_id={user_id} in {latency_ms:.0f}ms"
        )
        
        # Warn if latency exceeds target (Requirement 18.3)
        if latency_ms > 2000:
            logger.warning(
                f"PERFORMANCE WARNING: list_training_plans exceeded 2s target: {latency_ms:.0f}ms",
                extra={"user_id": user_id, "latency_ms": latency_ms}
            )
        
        return {"plans": plan_summaries}
        
    except Exception as e:
        logger.error(f"Error listing training plans for user_id={user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plan_id}", summary="Get plan details")
async def get_training_plan(
    plan_id: str,
    user_id: int = Query(1, description="User ID for security scoping"),
    db: Session = Depends(get_db)
):
    """
    Get detailed training plan with all weeks and sessions.
    
    Returns complete plan data for display in the Plan Detail View.
    
    **Path Parameters:**
    - `plan_id`: Plan UUID
    
    **Query Parameters:**
    - `user_id`: User ID for security scoping (required)
    
    **Returns:**
    - `plan`: Complete plan object with:
      - `id`: Plan UUID
      - `user_id`: Owner user ID
      - `title`: Plan title
      - `sport`: Primary sport
      - `goal_id`: Linked goal ID (if any)
      - `start_date`: Plan start date (ISO format)
      - `end_date`: Plan end date (ISO format)
      - `status`: Plan status
      - `overall_adherence`: Overall adherence percentage
      - `weeks`: Array of week objects with sessions
    
    **Performance Target:** < 2 seconds at p95 (Requirement 18.2)
    
    Requirements: 13.1, 13.2, 13.3, 13.4, 13.6, 18.2, 20.2
    """
    start_time = time.time()
    
    # Validate user_id is present (Requirement 20.2)
    if user_id is None:
        logger.error(f"SECURITY VIOLATION: user_id is None in get_training_plan for plan_id={plan_id}")
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        # Query plan with user_id scoping (Requirement 20.2)
        plan = db.query(TrainingPlanModel).filter(
            TrainingPlanModel.id == plan_id,
            TrainingPlanModel.user_id == user_id
        ).options(
            joinedload(TrainingPlanModel.weeks)
            .joinedload(TrainingPlanWeekModel.sessions)
        ).first()
        
        if not plan:
            raise HTTPException(
                status_code=404, 
                detail=f"Plan {plan_id} not found or access denied"
            )
        
        # Calculate overall adherence
        overall_adherence = AdherenceCalculator.calculate_plan_adherence(plan)
        
        # Format weeks
        weeks_data = []
        for week in plan.weeks:
            # Calculate week adherence
            week_adherence = AdherenceCalculator.calculate_week_adherence(week)
            
            # Format sessions
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
                
                # Include matched activity details if available
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
                "focus": week.focus,
                "volume_target": week.volume_target,
                "adherence": round(week_adherence, 1),
                "sessions": sessions_data
            })
        
        # Format response
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
            } if plan.goal else None,  # Include full goal object
            "start_date": plan.start_date.isoformat(),
            "end_date": plan.end_date.isoformat(),
            "status": plan.status,
            "overall_adherence": round(overall_adherence, 1),
            "weeks": weeks_data
        }
        
        # Log performance (Requirement 18.2)
        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Retrieved plan {plan_id} for user_id={user_id} in {latency_ms:.0f}ms"
        )
        
        # Warn if latency exceeds target (Requirement 18.3)
        if latency_ms > 2000:
            logger.warning(
                f"PERFORMANCE WARNING: get_training_plan exceeded 2s target: {latency_ms:.0f}ms",
                extra={"user_id": user_id, "plan_id": plan_id, "latency_ms": latency_ms}
            )
        
        return {"plan": plan_data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving plan {plan_id} for user_id={user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plan_id}/adherence", summary="Get adherence time series")
async def get_plan_adherence(
    plan_id: str,
    user_id: int = Query(1, description="User ID for security scoping"),
    db: Session = Depends(get_db)
):
    """
    Get adherence time series for charting.
    
    Returns weekly adherence percentages for display in the adherence chart.
    
    **Path Parameters:**
    - `plan_id`: Plan UUID
    
    **Query Parameters:**
    - `user_id`: User ID for security scoping (required)
    
    **Returns:**
    - `adherence_by_week`: Array of objects with:
      - `week`: Week number
      - `adherence`: Adherence percentage for that week
    - `overall_adherence`: Overall plan adherence percentage
    
    Requirement: 13.5, 20.2
    """
    # Validate user_id is present (Requirement 20.2)
    if user_id is None:
        logger.error(f"SECURITY VIOLATION: user_id is None in get_plan_adherence for plan_id={plan_id}")
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        # Query plan with user_id scoping (Requirement 20.2)
        plan = db.query(TrainingPlanModel).filter(
            TrainingPlanModel.id == plan_id,
            TrainingPlanModel.user_id == user_id
        ).options(
            joinedload(TrainingPlanModel.weeks)
            .joinedload(TrainingPlanWeekModel.sessions)
        ).first()
        
        if not plan:
            raise HTTPException(
                status_code=404, 
                detail=f"Plan {plan_id} not found or access denied"
            )
        
        # Calculate adherence by week
        adherence_by_week = []
        for week in plan.weeks:
            week_adherence = AdherenceCalculator.calculate_week_adherence(week)
            adherence_by_week.append({
                "week": week.week_number,
                "adherence": round(week_adherence, 1)
            })
        
        # Calculate overall adherence
        overall_adherence = AdherenceCalculator.calculate_plan_adherence(plan)
        
        return {
            "adherence_by_week": adherence_by_week,
            "overall_adherence": round(overall_adherence, 1)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving adherence for plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

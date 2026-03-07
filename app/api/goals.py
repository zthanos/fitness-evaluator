"""Goals API endpoints for athlete goal management."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.athlete_goal import AthleteGoal, GoalStatus
from app.schemas.goal_schemas import GoalCreate, GoalUpdate, GoalResponse
from app.services.goal_service import GoalService

router = APIRouter()


@router.post("", response_model=GoalResponse, summary="Create a new goal")
async def create_goal(goal: GoalCreate, db: Session = Depends(get_db)):
    """
    Create a new athlete goal.
    
    This endpoint is typically called by the LLM through tool calling,
    but can also be used directly by the frontend.
    
    **Fields:**
    - `goal_type`: Type of goal (weight_loss, weight_gain, performance, endurance, strength, custom)
    - `description`: Detailed goal description (min 10 characters)
    - `target_value`: Optional numeric target (required for weight goals)
    - `target_date`: Optional target completion date (must be in future)
    - `athlete_id`: Optional athlete identifier
    
    **Validation:**
    - goal_type must be valid enum value
    - target_date must be in the future
    - target_value required and validated for weight goals (30-300kg)
    """
    goal_service = GoalService(db)
    
    try:
        result = goal_service.save_goal(
            goal_type=goal.goal_type,
            description=goal.description,
            target_value=goal.target_value,
            target_date=goal.target_date.isoformat() if goal.target_date else None,
            athlete_id=goal.athlete_id
        )
        
        return result['goal']
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[GoalResponse], summary="List all goals")
async def list_goals(
    status: Optional[str] = None,
    athlete_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve all goals with optional filtering.
    
    **Query Parameters:**
    - `status`: Filter by status (active, completed, abandoned)
    - `athlete_id`: Filter by athlete identifier
    
    **Returns:**
    - List of goals ordered by creation date (most recent first)
    """
    query = db.query(AthleteGoal)
    
    if status:
        # Validate status
        valid_statuses = [gs.value for gs in GoalStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        query = query.filter(AthleteGoal.status == status)
    
    if athlete_id:
        query = query.filter(AthleteGoal.athlete_id == athlete_id)
    
    goals = query.order_by(AthleteGoal.created_at.desc()).all()
    return goals


@router.get("/{goal_id}", response_model=GoalResponse, summary="Get goal by ID")
async def get_goal(goal_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific goal by ID.
    
    **Parameters:**
    - `goal_id`: Goal identifier (UUID)
    """
    goal_service = GoalService(db)
    goal = goal_service.get_goal_by_id(goal_id)
    
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with ID {goal_id} not found")
    
    return goal


@router.put("/{goal_id}", response_model=GoalResponse, summary="Update goal")
async def update_goal(
    goal_id: str,
    goal_update: GoalUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing goal.
    
    **Parameters:**
    - `goal_id`: Goal identifier (UUID)
    
    **Fields (all optional):**
    - `status`: Update goal status (active, completed, abandoned)
    - `description`: Update description
    - `target_value`: Update target value
    - `target_date`: Update target date
    """
    goal_service = GoalService(db)
    goal = goal_service.get_goal_by_id(goal_id)
    
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with ID {goal_id} not found")
    
    try:
        # Update status if provided
        if goal_update.status:
            result = goal_service.update_goal_status(goal_id, goal_update.status)
            goal = result['goal']
        
        # Update other fields if provided
        if goal_update.description:
            goal['description'] = goal_update.description
        if goal_update.target_value is not None:
            goal['target_value'] = goal_update.target_value
        if goal_update.target_date:
            goal['target_date'] = goal_update.target_date
        
        # Refresh from database
        db.commit()
        updated_goal = goal_service.get_goal_by_id(goal_id)
        return updated_goal
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{goal_id}", summary="Delete goal")
async def delete_goal(goal_id: str, db: Session = Depends(get_db)):
    """
    Delete a goal.
    
    **Parameters:**
    - `goal_id`: Goal identifier (UUID)
    
    **Returns:**
    - Success message
    """
    goal_service = GoalService(db)
    
    try:
        result = goal_service.delete_goal(goal_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/active/summary", summary="Get active goals summary")
async def get_active_goals_summary(
    athlete_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get a summary of active goals for display in dashboard/settings.
    
    **Query Parameters:**
    - `athlete_id`: Optional athlete identifier
    
    **Returns:**
    - Count of active goals by type
    - List of active goals with progress indicators
    """
    goal_service = GoalService(db)
    active_goals = goal_service.get_active_goals(athlete_id)
    
    # Group by type
    goals_by_type = {}
    for goal in active_goals:
        goal_type = goal.goal_type
        if goal_type not in goals_by_type:
            goals_by_type[goal_type] = []
        goals_by_type[goal_type].append(goal.to_dict())
    
    return {
        'total_active': len(active_goals),
        'by_type': goals_by_type,
        'goals': [goal.to_dict() for goal in active_goals]
    }

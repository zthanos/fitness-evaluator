# app/api/v1/evaluations.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.eval_service import EvaluationService
from app.models.weekly_eval import WeeklyEval
from app.database import get_db

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def get_evaluation_service(db: Session = Depends(get_db)) -> EvaluationService:
    """Dependency provider for EvaluationService."""
    return EvaluationService(db)


@router.get("/{week_id}", response_model=WeeklyEval)
async def get_evaluation(
    week_id: UUID,
    eval_service: EvaluationService = Depends(get_evaluation_service)
) -> WeeklyEval:
    """
    Retrieve a fitness evaluation for a specific week.
    
    Args:
        week_id: UUID of the week to retrieve
        
    Returns:
        WeeklyEval model instance with the evaluation results
        
    Raises:
        HTTPException: 404 if evaluation not found
    """
    evaluation = eval_service.get_evaluation(week_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluation


@router.post("/{week_id}/evaluate", response_model=WeeklyEval)
async def evaluate_week(
    week_id: UUID,
    eval_service: EvaluationService = Depends(get_evaluation_service)
) -> WeeklyEval:
    """
    Generate a fitness evaluation for a specific week.
    
    Args:
        week_id: UUID of the week to evaluate
        
    Returns:
        WeeklyEval model instance with the generated evaluation results
        
    Raises:
        HTTPException: 400 if evaluation fails (e.g., week not found)
    """
    try:
        evaluation = eval_service.evaluate_week(week_id)
        return evaluation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/latest", response_model=list[WeeklyEval])
async def get_latest_evaluations(
    limit: int = 10,
    eval_service: EvaluationService = Depends(get_evaluation_service)
) -> list[WeeklyEval]:
    """
    Retrieve the latest fitness evaluations.
    
    Args:
        limit: Maximum number of evaluations to return (default: 10)
        
    Returns:
        List of WeeklyEval model instances
    """
    return eval_service.get_latest_evaluations(limit)
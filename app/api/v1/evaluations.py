# app/api/v1/evaluations.py
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.eval_service import EvaluationService
from app.models.weekly_eval import WeeklyEval
from app.models.weekly_measurement import WeeklyMeasurement
from app.database import get_db

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def get_evaluation_service(db: Session = Depends(get_db)) -> EvaluationService:
    """Dependency provider for EvaluationService."""
    return EvaluationService(db)


@router.get("/{week_id}", response_model=WeeklyEval)
async def get_evaluation(
    week_id: str,
    eval_service: EvaluationService = Depends(get_evaluation_service)
) -> WeeklyEval:
    """
    Retrieve a fitness evaluation for a specific week.
    
    Args:
        week_id: String UUID of the week to retrieve
        
    Returns:
        WeeklyEval model instance with the evaluation results
        
    Raises:
        HTTPException: 404 if evaluation not found
    """
    evaluation = eval_service.get_evaluation(week_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluation


@router.post("/{week_start}", response_model=dict)
async def evaluate_week(
    week_start: date,
    eval_service: EvaluationService = Depends(get_evaluation_service)
) -> dict:
    """
    Generate a fitness evaluation for a specific week.
    
    Args:
        week_start: Date of the week start (Monday) to evaluate
        
    Returns:
        Dictionary with week_start, week_id, evaluation, generated_at, input_hash
        
    Raises:
        HTTPException: 404 if WeeklyMeasurement not found for week_start
        HTTPException: 400 if evaluation fails
    """
    # Look up WeeklyMeasurement by week_start to get week_id
    weekly_measurement = eval_service.db.query(WeeklyMeasurement).filter(
        WeeklyMeasurement.week_start == week_start
    ).first()
    
    if not weekly_measurement:
        raise HTTPException(
            status_code=404,
            detail=f"No WeeklyMeasurement found for week starting {week_start}"
        )
    
    week_id = weekly_measurement.id
    
    # Call EvaluationService.evaluate_week with week_id
    try:
        weekly_eval = await eval_service.evaluate_week(week_id)
        
        # Return response with backward compatible structure
        return {
            "week_start": week_start,
            "week_id": str(week_id),
            "evaluation": weekly_eval.parsed_output_json,
            "generated_at": weekly_eval.generated_at,
            "input_hash": weekly_eval.input_hash
        }
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
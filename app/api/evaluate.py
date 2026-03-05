"""Fitness evaluation endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from uuid import UUID, uuid5, NAMESPACE_DNS
from datetime import date
from app.database import get_db
from app.models.weekly_eval import WeeklyEval
from app.schemas.eval_output import EvalOutput
from app.services.eval_service import EvaluationService

router = APIRouter()


@router.post("/{week_start}", summary="Generate or retrieve cached evaluation")
async def evaluate_week(week_start: date, db: Session = Depends(get_db)):
    """
    Perform a complete fitness evaluation for the given week.
    
    Uses contract-first evaluation with input hashing for idempotency.
    If the underlying data hasn't changed, returns the cached result.
    
    **Process:**
    1. Collects all week data (logs, measurements, Strava activities, targets)
    2. Hashes the data contract for idempotency
    3. Checks for existing evaluation with same hash
    4. If cached: returns immediately
    5. If fresh: calls LLM for evaluation
    6. Validates and stores response
    
    **Parameters:**
    - `week_start`: Monday of the week to evaluate (YYYY-MM-DD)
    
    **Returns:**
    - `week_start`: The evaluated week start date
    - `week_id`: UUID identifier for the week
    - `evaluation`: EvalOutput object containing:
      - `overall_score`: Weekly performance score (1-10)
      - `summary`: 2-3 sentence narrative assessment
      - `wins`: Array of achievement highlights
      - `misses`: Array of gaps vs targets
      - `nutrition_analysis`: Macro/calorie analysis
      - `training_analysis`: Activity breakdown
      - `recommendations`: Actionable next steps (max 5)
      - `data_confidence`: Data completeness score (0.0-1.0)
    - `generated_at`: Timestamp of generation
    - `input_hash`: SHA-256 hash of data contract
    - `is_cached`: Boolean indicating if result was cached
    """
    try:
        # Generate week_id from week_start date
        week_id = uuid5(NAMESPACE_DNS, str(week_start))
        
        # Create evaluation service
        eval_service = EvaluationService(db)

        # Perform evaluation (with idempotency check)
        weekly_eval = await eval_service.evaluate_week(week_id)
        
        if not weekly_eval.parsed_output_json:
            raise HTTPException(
                status_code=500,
                detail="Evaluation completed but output is missing"
            )
        
        return {
            "week_start": week_start,
            "week_id": str(week_id),
            "evaluation": weekly_eval.parsed_output_json,
            "generated_at": weekly_eval.generated_at,
            "input_hash": weekly_eval.input_hash,
            "is_cached": weekly_eval.raw_llm_response is not None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/{week_start}", summary="Retrieve existing evaluation")
async def get_evaluation(week_start: date, db: Session = Depends(get_db)):
    """
    Retrieve the most recent evaluation for a week without re-running.
    
    Does NOT trigger a new evaluation. Use POST endpoint to generate/update.
    
    **Parameters:**
    - `week_start`: Monday of the week (YYYY-MM-DD)
    
    **Returns:**
    - `week_start`: The evaluated week start date
    - `week_id`: UUID identifier for the week
    - `evaluation`: Complete EvalOutput object
    - `generated_at`: Timestamp of generation
    - `input_hash`: SHA-256 hash of input data
    - `evidence_map`: Mapping of claims to supporting DB records
    """
    try:
        week_id = uuid5(NAMESPACE_DNS, str(week_start))
        
        weekly_eval = db.query(WeeklyEval).filter(
            WeeklyEval.week_id == str(week_id)
        ).first()
        
        if not weekly_eval:
            raise HTTPException(
                status_code=404,
                detail=f"No evaluation found for week starting {week_start}"
            )
        
        return {
            "week_start": week_start,
            "week_id": str(week_id),
            "evaluation": weekly_eval.parsed_output_json,
            "generated_at": weekly_eval.generated_at,
            "input_hash": weekly_eval.input_hash,
            "evidence_map": weekly_eval.evidence_map_json,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{week_start}/refresh", summary="Force re-evaluation (bypass cache)")
async def refresh_evaluation(week_start: date, db: Session = Depends(get_db)):
    """
    Force re-evaluation of a week, bypassing idempotency cache.
    
    Useful when:
    - LLM model is updated
    - System prompt changes
    - Evaluation logic is improved
    - Previous evaluation quality is questionable
    
    **Parameters:**
    - `week_start`: Monday of the week to re-evaluate (YYYY-MM-DD)
    
    **Returns:**
    - Full evaluation result (same as POST endpoint)
    - `message`: Confirmation that evaluation was refreshed
    """
    try:
        week_id = uuid5(NAMESPACE_DNS, str(week_start))
        
        # Delete existing evaluation to force re-run
        existing = db.query(WeeklyEval).filter(
            WeeklyEval.week_id == str(week_id)
        ).first()
        
        if existing:
            db.delete(existing)
            db.commit()
        
        # Perform fresh evaluation
        eval_service = EvaluationService(db)
        weekly_eval = await eval_service.evaluate_week(week_id)
        
        return {
            "week_start": week_start,
            "week_id": str(week_id),
            "evaluation": weekly_eval.parsed_output_json,
            "generated_at": weekly_eval.generated_at,
            "input_hash": weekly_eval.input_hash,
            "message": "Evaluation refreshed",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")

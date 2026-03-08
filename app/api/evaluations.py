"""Evaluation Report API Endpoints

Provides endpoints for generating and retrieving evaluation reports.
Supports configurable time periods (weekly, bi-weekly, monthly).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
import uuid

from app.database import get_db
from app.services.evaluation_engine import EvaluationEngine
from app.schemas.evaluation_schemas import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationReport
)
from app.models.evaluation import Evaluation

router = APIRouter()


@router.post("/generate", response_model=EvaluationResponse, summary="Generate evaluation report")
async def generate_evaluation(
    request: EvaluationRequest,
    athlete_id: int = Query(1, description="Athlete ID"),
    db: Session = Depends(get_db)
):
    """
    Generate a new evaluation report for the specified period.
    
    **Process:**
    1. Gathers all activities, metrics, and logs for the period
    2. Uses LangChain LLM to analyze data and generate structured report
    3. Validates output against EvaluationReport schema
    4. Stores report with metadata in database
    
    **Parameters:**
    - `period_start`: Start date of evaluation period (YYYY-MM-DD)
    - `period_end`: End date of evaluation period (YYYY-MM-DD)
    - `period_type`: Type of period (weekly, bi-weekly, monthly)
    - `athlete_id`: Athlete identifier (query parameter)
    
    **Returns:**
    - Complete evaluation report with:
      - `overall_score`: Performance score (0-100)
      - `strengths`: List of achievements
      - `improvements`: List of areas needing work
      - `tips`: Actionable coaching advice
      - `recommended_exercises`: Suggested activities
      - `goal_alignment`: Progress assessment
      - `confidence_score`: Data completeness (0.0-1.0)
    
    **Requirements:** 11.1, 11.3, 11.4, 11.5
    """
    try:
        # Validate period type
        if request.period_type not in ['weekly', 'bi-weekly', 'monthly']:
            raise HTTPException(
                status_code=400,
                detail="period_type must be 'weekly', 'bi-weekly', or 'monthly'"
            )
        
        # Validate date range
        if request.period_end < request.period_start:
            raise HTTPException(
                status_code=400,
                detail="period_end must be after period_start"
            )
        
        # Create evaluation engine
        engine = EvaluationEngine(db)
        
        # Generate evaluation
        evaluation = await engine.generate_evaluation(
            athlete_id=athlete_id,
            period_start=request.period_start,
            period_end=request.period_end,
            period_type=request.period_type
        )
        
        # Create database model
        eval_id = str(uuid.uuid4())
        db_evaluation = Evaluation(
            id=eval_id,
            athlete_id=athlete_id,
            period_start=request.period_start,
            period_end=request.period_end,
            period_type=request.period_type,
            overall_score=evaluation.overall_score,
            strengths=evaluation.strengths,
            improvements=evaluation.improvements,
            tips=evaluation.tips,
            recommended_exercises=evaluation.recommended_exercises,
            goal_alignment=evaluation.goal_alignment,
            confidence_score=evaluation.confidence_score
        )
        
        # Save to database
        try:
            db.add(db_evaluation)
            db.commit()
            db.refresh(db_evaluation)
        except Exception as db_error:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save evaluation: {str(db_error)}"
            )
        
        # Convert to response
        return EvaluationResponse(**db_evaluation.to_dict())
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation generation failed: {str(e)}"
        )


@router.get("", response_model=List[EvaluationResponse], summary="Get evaluation history")
async def get_evaluations(
    athlete_id: int = Query(1, description="Athlete ID"),
    date_from: Optional[date] = Query(None, description="Filter by start date"),
    date_to: Optional[date] = Query(None, description="Filter by end date"),
    score_min: Optional[int] = Query(None, ge=0, le=100, description="Minimum score filter"),
    score_max: Optional[int] = Query(None, ge=0, le=100, description="Maximum score filter"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    Retrieve evaluation history for an athlete.
    
    Returns evaluations in reverse chronological order (newest first).
    Supports filtering by date range and score range.
    
    **Parameters:**
    - `athlete_id`: Athlete identifier (query parameter)
    - `date_from`: Optional start date filter
    - `date_to`: Optional end date filter
    - `score_min`: Optional minimum score filter (0-100)
    - `score_max`: Optional maximum score filter (0-100)
    - `limit`: Maximum number of results (default 50, max 100)
    
    **Returns:**
    - List of evaluation reports sorted by generation date (newest first)
    
    **Requirements:** 12.1, 12.5
    """
    try:
        # Build query
        query = db.query(Evaluation).filter(Evaluation.athlete_id == athlete_id)
        
        # Apply filters
        if date_from:
            query = query.filter(Evaluation.period_start >= date_from)
        if date_to:
            query = query.filter(Evaluation.period_end <= date_to)
        if score_min is not None:
            query = query.filter(Evaluation.overall_score >= score_min)
        if score_max is not None:
            query = query.filter(Evaluation.overall_score <= score_max)
        
        # Sort by created_at descending (newest first)
        query = query.order_by(Evaluation.created_at.desc())
        
        # Apply limit
        query = query.limit(limit)
        
        # Execute query
        evaluations = query.all()
        
        # Convert to response models
        return [EvaluationResponse(**eval.to_dict()) for eval in evaluations]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve evaluations: {str(e)}"
        )


@router.get("/{evaluation_id}", response_model=EvaluationResponse, summary="Get evaluation detail")
async def get_evaluation(evaluation_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific evaluation report by ID.
    
    **Parameters:**
    - `evaluation_id`: UUID of the evaluation report
    
    **Returns:**
    - Complete evaluation report with all fields
    
    **Requirements:** 12.2
    """
    try:
        evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        
        if not evaluation:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation {evaluation_id} not found"
            )
        
        return EvaluationResponse(**evaluation.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve evaluation: {str(e)}"
        )


@router.post("/{evaluation_id}/re-evaluate", response_model=EvaluationResponse, summary="Re-evaluate with same parameters")
async def re_evaluate(evaluation_id: str, db: Session = Depends(get_db)):
    """
    Generate a new evaluation using the same parameters as an existing evaluation.

    This endpoint retrieves an existing evaluation and generates a new one with
    the same period_start, period_end, period_type, and athlete_id. The new
    evaluation gets a new UUID and is saved as a separate record.

    **Parameters:**
    - `evaluation_id`: UUID of the original evaluation to re-evaluate

    **Returns:**
    - New evaluation report with a new ID but same parameters as the original

    **Requirements:** 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    try:
        # Retrieve original evaluation by ID
        original = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()

        # Return 404 if not found
        if not original:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation {evaluation_id} not found"
            )

        # Extract parameters from original evaluation
        athlete_id = original.athlete_id
        period_start = original.period_start
        period_end = original.period_end
        period_type = original.period_type

        # Create evaluation engine
        engine = EvaluationEngine(db)

        # Generate new evaluation with same parameters
        evaluation = await engine.generate_evaluation(
            athlete_id=athlete_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type
        )

        # Generate new UUID for new evaluation
        new_eval_id = str(uuid.uuid4())

        # Create database model for new evaluation
        db_evaluation = Evaluation(
            id=new_eval_id,
            athlete_id=athlete_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            overall_score=evaluation.overall_score,
            strengths=evaluation.strengths,
            improvements=evaluation.improvements,
            tips=evaluation.tips,
            recommended_exercises=evaluation.recommended_exercises,
            goal_alignment=evaluation.goal_alignment,
            confidence_score=evaluation.confidence_score
        )

        # Save new evaluation to database
        try:
            db.add(db_evaluation)
            db.commit()
            db.refresh(db_evaluation)
        except Exception as db_error:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save evaluation: {str(db_error)}"
            )

        # Return new evaluation in response
        return EvaluationResponse(**db_evaluation.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Re-evaluation failed: {str(e)}"
        )




@router.post("/{evaluation_id}/re-evaluate", response_model=EvaluationResponse, summary="Re-evaluate with same parameters")
async def re_evaluate(evaluation_id: str, db: Session = Depends(get_db)):
    """
    Generate a new evaluation using the same parameters as an existing evaluation.
    
    This endpoint retrieves an existing evaluation and generates a new one with
    the same period_start, period_end, period_type, and athlete_id. The new
    evaluation gets a new UUID and is saved as a separate record.
    
    **Parameters:**
    - `evaluation_id`: UUID of the original evaluation to re-evaluate
    
    **Returns:**
    - New evaluation report with a new ID but same parameters as the original
    
    **Requirements:** 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    try:
        # Retrieve original evaluation by ID
        original = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        
        # Return 404 if not found
        if not original:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation {evaluation_id} not found"
            )
        
        # Extract parameters from original evaluation
        athlete_id = original.athlete_id
        period_start = original.period_start
        period_end = original.period_end
        period_type = original.period_type
        
        # Create evaluation engine
        engine = EvaluationEngine(db)
        
        # Generate new evaluation with same parameters
        evaluation = await engine.generate_evaluation(
            athlete_id=athlete_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type
        )
        
        # Generate new UUID for new evaluation
        new_eval_id = str(uuid.uuid4())
        
        # Create database model for new evaluation
        db_evaluation = Evaluation(
            id=new_eval_id,
            athlete_id=athlete_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            overall_score=evaluation.overall_score,
            strengths=evaluation.strengths,
            improvements=evaluation.improvements,
            tips=evaluation.tips,
            recommended_exercises=evaluation.recommended_exercises,
            goal_alignment=evaluation.goal_alignment,
            confidence_score=evaluation.confidence_score
        )
        
        # Save new evaluation to database
        try:
            db.add(db_evaluation)
            db.commit()
            db.refresh(db_evaluation)
        except Exception as db_error:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save evaluation: {str(db_error)}"
            )
        
        # Return new evaluation in response
        return EvaluationResponse(**db_evaluation.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Re-evaluation failed: {str(e)}"
        )

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

router = APIRouter()


# In-memory storage for evaluations (replace with database model in production)
# This is a temporary solution until the database schema is updated
evaluations_store = {}


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
    4. Stores report with metadata
    
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
        
        # Store evaluation
        eval_id = str(uuid.uuid4())
        evaluation_data = {
            'id': eval_id,
            'athlete_id': athlete_id,
            'period_start': request.period_start,
            'period_end': request.period_end,
            'period_type': request.period_type,
            'overall_score': evaluation.overall_score,
            'strengths': evaluation.strengths,
            'improvements': evaluation.improvements,
            'tips': evaluation.tips,
            'recommended_exercises': evaluation.recommended_exercises,
            'goal_alignment': evaluation.goal_alignment,
            'confidence_score': evaluation.confidence_score,
            'generated_at': datetime.now().isoformat()
        }
        
        evaluations_store[eval_id] = evaluation_data
        
        return EvaluationResponse(**evaluation_data)
        
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
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results")
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
        # Filter evaluations
        filtered = []
        for eval_data in evaluations_store.values():
            # Filter by athlete
            if eval_data['athlete_id'] != athlete_id:
                continue
            
            # Filter by date range
            if date_from and eval_data['period_start'] < date_from:
                continue
            if date_to and eval_data['period_end'] > date_to:
                continue
            
            # Filter by score range
            if score_min is not None and eval_data['overall_score'] < score_min:
                continue
            if score_max is not None and eval_data['overall_score'] > score_max:
                continue
            
            filtered.append(eval_data)
        
        # Sort by generated_at (newest first)
        filtered.sort(key=lambda x: x['generated_at'], reverse=True)
        
        # Apply limit
        filtered = filtered[:limit]
        
        return [EvaluationResponse(**eval_data) for eval_data in filtered]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve evaluations: {str(e)}"
        )


@router.get("/{evaluation_id}", response_model=EvaluationResponse, summary="Get evaluation detail")
async def get_evaluation(evaluation_id: str):
    """
    Retrieve a specific evaluation report by ID.
    
    **Parameters:**
    - `evaluation_id`: UUID of the evaluation report
    
    **Returns:**
    - Complete evaluation report with all fields
    
    **Requirements:** 12.2
    """
    try:
        if evaluation_id not in evaluations_store:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation {evaluation_id} not found"
            )
        
        eval_data = evaluations_store[evaluation_id]
        return EvaluationResponse(**eval_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve evaluation: {str(e)}"
        )

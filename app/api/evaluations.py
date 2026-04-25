"""Evaluation Report API Endpoints

Provides endpoints for generating and retrieving evaluation reports.
Supports configurable time periods (weekly, bi-weekly, monthly).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional
import uuid

from app.database import get_db
from app.middleware.auth import get_current_athlete
from app.models.athlete import Athlete
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
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Generate a new evaluation report for the specified period.

    **Requirements:** 11.1, 11.3, 11.4, 11.5
    """
    if request.period_type not in ['weekly', 'bi-weekly', 'monthly']:
        raise HTTPException(
            status_code=400,
            detail="period_type must be 'weekly', 'bi-weekly', or 'monthly'"
        )

    if request.period_end < request.period_start:
        raise HTTPException(
            status_code=400,
            detail="period_end must be after period_start"
        )

    try:
        engine = EvaluationEngine(db)
        evaluation = await engine.generate_evaluation(
            athlete_id=athlete.id,
            period_start=request.period_start,
            period_end=request.period_end,
            period_type=request.period_type
        )

        eval_id = str(uuid.uuid4())
        db_evaluation = Evaluation(
            id=eval_id,
            athlete_id=athlete.id,
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
    date_from: Optional[date] = Query(None, description="Filter by start date"),
    date_to: Optional[date] = Query(None, description="Filter by end date"),
    score_min: Optional[int] = Query(None, ge=0, le=100, description="Minimum score filter"),
    score_max: Optional[int] = Query(None, ge=0, le=100, description="Maximum score filter"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Retrieve evaluation history for the authenticated athlete.

    Returns evaluations in reverse chronological order (newest first).

    **Requirements:** 12.1, 12.5
    """
    try:
        query = db.query(Evaluation).filter(Evaluation.athlete_id == athlete.id)

        if date_from:
            query = query.filter(Evaluation.period_start >= date_from)
        if date_to:
            query = query.filter(Evaluation.period_end <= date_to)
        if score_min is not None:
            query = query.filter(Evaluation.overall_score >= score_min)
        if score_max is not None:
            query = query.filter(Evaluation.overall_score <= score_max)

        query = query.order_by(Evaluation.created_at.desc()).limit(limit)
        evaluations = query.all()

        return [EvaluationResponse(**eval.to_dict()) for eval in evaluations]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve evaluations: {str(e)}"
        )


@router.get("/{evaluation_id}", response_model=EvaluationResponse, summary="Get evaluation detail")
async def get_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Retrieve a specific evaluation report by ID.

    **Requirements:** 12.2
    """
    try:
        evaluation = db.query(Evaluation).filter(
            Evaluation.id == evaluation_id,
            Evaluation.athlete_id == athlete.id,
        ).first()

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
async def re_evaluate(
    evaluation_id: str,
    db: Session = Depends(get_db),
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Generate a new evaluation using the same parameters as an existing evaluation.

    **Requirements:** 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    try:
        original = db.query(Evaluation).filter(
            Evaluation.id == evaluation_id,
            Evaluation.athlete_id == athlete.id,
        ).first()

        if not original:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation {evaluation_id} not found"
            )

        engine = EvaluationEngine(db)
        evaluation = await engine.generate_evaluation(
            athlete_id=athlete.id,
            period_start=original.period_start,
            period_end=original.period_end,
            period_type=original.period_type
        )

        new_eval_id = str(uuid.uuid4())
        db_evaluation = Evaluation(
            id=new_eval_id,
            athlete_id=athlete.id,
            period_start=original.period_start,
            period_end=original.period_end,
            period_type=original.period_type,
            overall_score=evaluation.overall_score,
            strengths=evaluation.strengths,
            improvements=evaluation.improvements,
            tips=evaluation.tips,
            recommended_exercises=evaluation.recommended_exercises,
            goal_alignment=evaluation.goal_alignment,
            confidence_score=evaluation.confidence_score
        )

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

        return EvaluationResponse(**db_evaluation.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Re-evaluation failed: {str(e)}"
        )

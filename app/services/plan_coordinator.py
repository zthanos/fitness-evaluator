"""PlanCoordinator — enforces training plan compatibility and feasibility rules.

Rules:
- Only one *primary* plan per sport may be active at a time.
- *Complementary* plans (nutrition, strength, recovery) may coexist freely.
- When a new primary plan is requested, any active primary plan for the same
  sport is a conflict and must be deactivated before the new plan is created.

Sport classification:
- Primary sports: running, cycling, swimming, triathlon → plan_type = 'primary'
- Complementary: nutrition, strength, cross_training → plan_type = 'complementary'
"""
from __future__ import annotations
from typing import List, Dict, Any
from sqlalchemy.orm import Session

_PRIMARY_SPORTS = {"running", "cycling", "swimming", "triathlon"}
_COMPLEMENTARY_SPORTS = {"nutrition", "strength", "cross_training", "recovery"}


def sport_plan_type(sport: str) -> str:
    """Infer plan_type from sport name."""
    return "complementary" if sport.lower() in _COMPLEMENTARY_SPORTS else "primary"


def check_compatibility(
    athlete_id: int,
    sport: str,
    plan_type: str,
    db: Session,
) -> Dict[str, Any]:
    """Return compatibility status and any conflicting active plans.

    Returns:
        {
            "compatible": bool,
            "conflicts": [
                {
                    "id": str,
                    "title": str,
                    "sport": str,
                    "start_date": str,
                    "end_date": str,
                    "reason": str,
                }
            ]
        }
    """
    from app.models.training_plan import TrainingPlan

    # Complementary plans never conflict.
    if plan_type == "complementary":
        return {"compatible": True, "conflicts": []}

    # For primary plans: find any active primary plan for the same sport.
    conflicts_raw = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.user_id == athlete_id,
            TrainingPlan.status == "active",
            TrainingPlan.plan_type == "primary",
            TrainingPlan.sport == sport,
        )
        .all()
    )

    if not conflicts_raw:
        return {"compatible": True, "conflicts": []}

    conflicts = [
        {
            "id":         p.id,
            "title":      p.title,
            "sport":      p.sport,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "end_date":   p.end_date.isoformat()   if p.end_date   else None,
            "reason":     f"Active {p.sport} primary plan already exists — only one primary plan per sport allowed",
        }
        for p in conflicts_raw
    ]
    return {"compatible": False, "conflicts": conflicts}


def deactivate_plan(plan_id: str, athlete_id: int, db: Session) -> bool:
    """Set a plan's status to 'abandoned'. Returns True if found and updated."""
    from app.models.training_plan import TrainingPlan

    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.user_id == athlete_id,
    ).first()

    if not plan:
        return False

    plan.status = "abandoned"
    db.commit()
    return True

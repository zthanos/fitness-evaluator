"""TrainingPlanner — generates a structured multi-week training plan and persists it."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.ai.skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)

# Valid enums mirrored from TrainingPlanSession model
_VALID_SESSION_TYPES = {
    "easy_run", "tempo_run", "interval", "long_run", "recovery_run",
    "easy_ride", "tempo_ride", "interval_ride", "long_ride",
    "swim_technique", "swim_endurance", "swim_interval",
    "rest", "cross_training", "strength",
}
_VALID_INTENSITIES = {"recovery", "easy", "moderate", "hard", "max"}

_SESSION_TYPE_ALIASES = {
    "z2_ride": "easy_ride", "base_ride": "easy_ride", "endurance_ride": "easy_ride",
    "threshold_ride": "tempo_ride", "vo2_ride": "interval_ride",
    "z2_run": "easy_run", "base_run": "easy_run", "endurance_run": "easy_run",
    "threshold_run": "tempo_run", "vo2_run": "interval",
    "rest_day": "rest", "off": "rest", "active_recovery": "recovery_run",
}

_SYSTEM_PROMPT = """You are an elite endurance coach generating a structured training plan.

Given an athlete's fitness state, goals, fatigue level, and nutrition context, produce a
JSON training plan with this EXACT schema:
{
  "title": "short plan name (≤50 chars)",
  "sport": "cycling" | "running" | "swimming" | "triathlon" | "other",
  "duration_weeks": <integer 1-12>,
  "weeks": [
    {
      "week_number": <int>,
      "focus": "one-sentence focus description",
      "volume_target_hours": <float>,
      "sessions": [
        {
          "day_of_week": <1-7, 1=Monday>,
          "session_type": <one of: easy_run tempo_run interval long_run recovery_run easy_ride tempo_ride interval_ride long_ride swim_technique swim_endurance swim_interval rest cross_training strength>,
          "duration_minutes": <int>,
          "intensity": <one of: recovery easy moderate hard max>,
          "description": "specific instruction with target numbers (HR zone, cadence, pace, etc.)"
        }
      ]
    }
  ]
}

Rules:
- All sessions must have valid session_type and intensity from the allowed lists.
- Sessions should be specific and reference the athlete's actual limiters and metrics.
- Rest days should use session_type "rest", duration_minutes 0, intensity "recovery".
- Respond with ONLY the JSON — no markdown, no explanation."""


class TrainingPlannerInput:
    def __init__(
        self,
        duration_weeks: int = 4,
        goal_id: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        self.duration_weeks = duration_weeks
        self.goal_id = goal_id
        self.context = context or {}


class TrainingPlannerOutput:
    def __init__(self, plan_id: str, title: str, sport: str, weeks: int, summary: str):
        self.plan_id = plan_id
        self.title = title
        self.sport = sport
        self.weeks = weeks
        self.summary = summary


class TrainingPlanner(BaseSkill[TrainingPlannerInput, TrainingPlannerOutput]):

    async def run(self, input: TrainingPlannerInput) -> TrainingPlannerOutput:
        context_str = json.dumps(input.context, default=str)
        raw = await self._llm_reason(_SYSTEM_PROMPT, context_str, max_tokens=6000)

        plan_data = self._parse_plan(raw, input.duration_weeks)
        plan_id = self._save_plan(plan_data, input.goal_id)

        return TrainingPlannerOutput(
            plan_id=plan_id,
            title=plan_data.get("title", "Training Plan"),
            sport=plan_data.get("sport", "other"),
            weeks=len(plan_data.get("weeks", [])),
            summary=self._summarise(plan_data),
        )

    # ── Plan parsing ──────────────────────────────────────────────────────────

    def _parse_plan(self, raw: str, fallback_weeks: int) -> dict:
        try:
            cleaned = (
                raw.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            data = json.loads(cleaned)
            # Normalise session types and intensities
            for week in data.get("weeks", []):
                for session in week.get("sessions", []):
                    session["session_type"] = self._normalise_type(session.get("session_type", "rest"))
                    session["intensity"]     = self._normalise_intensity(session.get("intensity", "easy"))
                    session["duration_minutes"] = max(0, int(session.get("duration_minutes", 0)))
                    dow = int(session.get("day_of_week", 1))
                    session["day_of_week"] = max(1, min(7, dow))
            return data
        except Exception as exc:
            logger.warning("TrainingPlanner: could not parse LLM JSON (%s), using skeleton", exc)
            return self._skeleton_plan(fallback_weeks)

    @staticmethod
    def _normalise_type(raw: str) -> str:
        raw = raw.lower().replace(" ", "_").replace("-", "_")
        if raw in _VALID_SESSION_TYPES:
            return raw
        if raw in _SESSION_TYPE_ALIASES:
            return _SESSION_TYPE_ALIASES[raw]
        # Best-effort keyword match
        for keyword in ("run", "ride", "swim", "strength", "rest", "cross"):
            if keyword in raw:
                return {"run": "easy_run", "ride": "easy_ride", "swim": "swim_endurance",
                        "strength": "strength", "rest": "rest", "cross": "cross_training"}[keyword]
        return "rest"

    @staticmethod
    def _normalise_intensity(raw: str) -> str:
        raw = raw.lower()
        if raw in _VALID_INTENSITIES:
            return raw
        mapping = {"z1": "recovery", "z2": "easy", "z3": "moderate", "z4": "hard",
                   "z5": "max", "threshold": "hard", "vo2": "max", "tempo": "moderate"}
        return mapping.get(raw, "easy")

    # ── Plan persistence ──────────────────────────────────────────────────────

    def _save_plan(self, data: dict, goal_id: Optional[str], plan_type: str = "primary") -> str:
        from app.models.training_plan import TrainingPlan
        from app.models.training_plan_week import TrainingPlanWeek
        from app.models.training_plan_session import TrainingPlanSession
        from app.services.plan_coordinator import sport_plan_type

        today = date.today()
        duration = len(data.get("weeks", []))
        end_date = today + timedelta(weeks=max(duration, 1))
        resolved_type = plan_type or sport_plan_type(data.get("sport", "other"))

        plan = TrainingPlan(
            id=str(uuid.uuid4()),
            user_id=self.athlete_id,
            title=data.get("title", "Training Plan")[:255],
            sport=data.get("sport", "other"),
            plan_type=resolved_type,
            goal_id=goal_id,
            start_date=today,
            end_date=end_date,
            status="active",
        )
        self.db.add(plan)
        self.db.flush()  # get plan.id before adding children

        for week_data in data.get("weeks", []):
            week = TrainingPlanWeek(
                id=str(uuid.uuid4()),
                plan_id=plan.id,
                week_number=int(week_data.get("week_number", 1)),
                focus=str(week_data.get("focus", ""))[:255],
                volume_target=float(week_data.get("volume_target_hours", 0)),
            )
            self.db.add(week)
            self.db.flush()

            for s in week_data.get("sessions", []):
                session = TrainingPlanSession(
                    id=str(uuid.uuid4()),
                    week_id=week.id,
                    day_of_week=s["day_of_week"],
                    session_type=s["session_type"],
                    duration_minutes=s["duration_minutes"],
                    intensity=s["intensity"],
                    description=str(s.get("description", ""))[:1000] if s.get("description") else None,
                    completed=False,
                )
                self.db.add(session)

        self.db.commit()
        return plan.id

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _summarise(data: dict) -> str:
        weeks = data.get("weeks", [])
        total_sessions = sum(
            len([s for s in w.get("sessions", []) if s["session_type"] != "rest"])
            for w in weeks
        )
        total_hours = sum(w.get("volume_target_hours", 0) for w in weeks)
        return (
            f"{data.get('title', 'Plan')} — {len(weeks)} weeks, "
            f"{total_sessions} sessions, {total_hours:.1f}h total volume."
        )

    @staticmethod
    def _skeleton_plan(duration_weeks: int) -> dict:
        weeks = []
        for w in range(1, duration_weeks + 1):
            weeks.append({
                "week_number": w,
                "focus": "Base endurance",
                "volume_target_hours": 4.0,
                "sessions": [
                    {"day_of_week": 2, "session_type": "easy_ride", "duration_minutes": 60, "intensity": "easy",
                     "description": "Z2 aerobic ride, steady effort"},
                    {"day_of_week": 4, "session_type": "easy_ride", "duration_minutes": 45, "intensity": "easy",
                     "description": "Recovery spin, keep HR in Z1"},
                    {"day_of_week": 6, "session_type": "easy_ride", "duration_minutes": 90, "intensity": "easy",
                     "description": "Long Z2 ride, aerobic base development"},
                ],
            })
        return {
            "title": f"{duration_weeks}-Week Base Build",
            "sport": "cycling",
            "duration_weeks": duration_weeks,
            "weeks": weeks,
        }

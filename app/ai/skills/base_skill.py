"""Base class for all fitness coach skills."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

InputT  = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseSkill(ABC, Generic[InputT, OutputT]):
    """
    Abstract base for all coach skills.

    Each skill owns its own system prompt and Pydantic I/O schemas.
    Skills are internal — the LLM ReAct loop never calls them directly;
    they are invoked by the four exposed tools.
    """

    def __init__(self, db: Session, athlete_id: int):
        self.db = db
        self.athlete_id = athlete_id
        self._llm: object | None = None   # lazy, set by _get_llm()

    @abstractmethod
    async def run(self, input: InputT) -> OutputT:
        """Execute the skill and return a structured output."""

    # ── Shared LLM helper ────────────────────────────────────────────────────

    async def _llm_reason(self, system: str, user_content: str, max_tokens: int = 1024) -> str:
        """
        Single-turn LLM call with a focused system prompt.
        Returns the raw text response.
        """
        from app.services.llm_client import LLMClient
        client = LLMClient()
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ]
        try:
            result = await client.chat_completion(
                messages, max_tokens=max_tokens, temperature=0.3,
                source=self.__class__.__name__,
            )
            return result.get("content") or ""
        except Exception as exc:
            logger.warning("%s LLM call failed: %s", self.__class__.__name__, exc)
            return ""

    # ── Shared data helpers ──────────────────────────────────────────────────

    def _get_athlete_demographics(self) -> dict:
        """Return age, weight, body fat, resting HR and stated goals from DB (best-effort)."""
        out: dict = {}
        try:
            from datetime import date
            from app.models.athlete import Athlete
            athlete = self.db.query(Athlete).filter_by(id=self.athlete_id).first()
            if athlete:
                if athlete.date_of_birth:
                    today = date.today()
                    dob = athlete.date_of_birth
                    age = today.year - dob.year - (
                        (today.month, today.day) < (dob.month, dob.day)
                    )
                    out["age_years"] = age
                if athlete.height_cm:
                    out["height_cm"] = athlete.height_cm
                if athlete.goals:
                    out["stated_goals"] = athlete.goals
        except Exception:
            pass
        try:
            from app.models.weekly_measurement import WeeklyMeasurement
            latest = (
                self.db.query(WeeklyMeasurement)
                .filter_by(athlete_id=self.athlete_id)
                .order_by(WeeklyMeasurement.week_start.desc())
                .first()
            )
            if latest:
                if latest.weight_kg:
                    out["weight_kg"] = latest.weight_kg
                if latest.body_fat_pct:
                    out["body_fat_pct"] = latest.body_fat_pct
                if latest.rhr_bpm:
                    out["resting_hr_bpm"] = latest.rhr_bpm
        except Exception:
            pass
        return out

    def _recent_activities(self, days: int = 28, limit: int = 20):
        from datetime import datetime, timezone, timedelta
        from app.models.strava_activity import StravaActivity
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            self.db.query(StravaActivity)
            .filter(
                StravaActivity.athlete_id == self.athlete_id,
                StravaActivity.start_date >= cutoff,
            )
            .order_by(StravaActivity.start_date.desc())
            .limit(limit)
            .all()
        )

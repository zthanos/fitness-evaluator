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

    async def _llm_reason(self, system: str, user_content: str) -> str:
        """
        Single-turn LLM call with a focused system prompt.
        Returns the raw text response.
        """
        from app.services.llm_client import LLMClient
        client = LLMClient()
        messages = [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user_content},
        ]
        try:
            return await client.generate_response(messages)
        except Exception as exc:
            logger.warning("%s LLM call failed: %s", self.__class__.__name__, exc)
            return ""

    # ── Shared data helpers ──────────────────────────────────────────────────

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

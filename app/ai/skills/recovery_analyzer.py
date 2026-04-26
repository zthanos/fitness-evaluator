"""RecoveryAnalyzer — evaluates athlete fatigue and recovery readiness."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Optional

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import RecoveryInput, RecoveryStatus

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a precision endurance coach assessing athlete recovery.
Given structured load and recovery metrics, write ONE sentence (≤25 words) recommending
the athlete's next training action. Be specific: mention actual load numbers or RHR values.
No generic advice. No bullet points. No pleasantries."""


class RecoveryAnalyzer(BaseSkill[RecoveryInput, RecoveryStatus]):

    async def run(self, input: RecoveryInput) -> RecoveryStatus:
        acute, chronic, acwr = self._load_metrics(input.lookback_days)
        rhr_bpm = self._latest_rhr()
        rhr_trend = self._rhr_trend()
        fatigue_level = self._fatigue_from_acwr(acwr)
        rest_recommended = self._should_rest(acwr, rhr_trend)

        confidence = self._compute_confidence(acute, acwr, rhr_bpm)

        user_content = (
            f"acute_load_min={round(acute, 1)}, "
            f"chronic_load_min={round(chronic, 1)}, "
            f"acwr={acwr}, "
            f"fatigue_level={fatigue_level}, "
            f"rhr_bpm={rhr_bpm}, "
            f"rhr_trend={rhr_trend}, "
            f"rest_recommended={rest_recommended}"
        )
        recommendation = await self._llm_reason(_SYSTEM_PROMPT, user_content)
        if not recommendation:
            recommendation = self._fallback_recommendation(fatigue_level, rest_recommended)

        return RecoveryStatus(
            acwr_ratio=acwr,
            acute_load_min=round(acute, 1),
            chronic_load_min=round(chronic, 1),
            rhr_bpm=rhr_bpm,
            rhr_trend=rhr_trend,
            fatigue_level=fatigue_level,
            rest_recommended=rest_recommended,
            recommendation=recommendation,
            confidence=confidence,
        )

    # ── Load metrics ─────────────────────────────────────────────────────────

    def _load_metrics(self, lookback_days: int) -> tuple[float, float, Optional[float]]:
        from app.models.strava_activity import StravaActivity
        now = datetime.now(timezone.utc)

        def moving_time_minutes(days_back: int, window: int) -> float:
            cutoff = now - timedelta(days=days_back + window)
            end    = now - timedelta(days=days_back)
            rows = (
                self.db.query(StravaActivity.moving_time_s)
                .filter(
                    StravaActivity.athlete_id == self.athlete_id,
                    StravaActivity.start_date >= cutoff,
                    StravaActivity.start_date < end,
                )
                .all()
            )
            return sum(r[0] or 0 for r in rows) / 60

        acute   = moving_time_minutes(0, 7)
        chronic_total = moving_time_minutes(0, 28)
        chronic = chronic_total / 4  # 7-day average

        acwr: Optional[float] = None
        if chronic > 0:
            acwr = round(acute / chronic, 2)

        return acute, chronic, acwr

    # ── RHR helpers ──────────────────────────────────────────────────────────

    def _latest_rhr(self) -> Optional[float]:
        from app.models.weekly_measurement import WeeklyMeasurement
        row = (
            self.db.query(WeeklyMeasurement.rhr_bpm)
            .filter(
                WeeklyMeasurement.athlete_id == self.athlete_id,
                WeeklyMeasurement.rhr_bpm.isnot(None),
            )
            .order_by(WeeklyMeasurement.week_start.desc())
            .first()
        )
        return float(row[0]) if row else None

    def _rhr_trend(self) -> Optional[str]:
        from app.models.weekly_measurement import WeeklyMeasurement
        rows = (
            self.db.query(WeeklyMeasurement.rhr_bpm)
            .filter(
                WeeklyMeasurement.athlete_id == self.athlete_id,
                WeeklyMeasurement.rhr_bpm.isnot(None),
            )
            .order_by(WeeklyMeasurement.week_start.desc())
            .limit(6)
            .all()
        )
        values = [r[0] for r in rows if r[0]]
        if len(values) < 3:
            return None
        # recent (first two) vs older (last two); lower RHR is better
        diff = mean(values[:2]) - mean(values[-2:])
        if diff < -1:  return "degrading"   # RHR rose recently
        if diff > 1:   return "improving"
        return "stable"

    # ── Decision helpers ─────────────────────────────────────────────────────

    def _fatigue_from_acwr(self, acwr: Optional[float]) -> str:
        if acwr is None:  return "low"
        if acwr > 1.5:    return "overreaching"
        if acwr > 1.3:    return "high"
        if acwr > 0.8:    return "moderate"
        return "low"

    def _should_rest(self, acwr: Optional[float], rhr_trend: Optional[str]) -> bool:
        if acwr is not None and acwr > 1.3:
            return True
        if rhr_trend == "degrading":
            return True
        return False

    def _compute_confidence(
        self, acute: float, acwr: Optional[float], rhr_bpm: Optional[float]
    ) -> float:
        score = 0.0
        if acute > 0:         score += 0.4
        if acwr is not None:  score += 0.4
        if rhr_bpm is not None: score += 0.2
        return round(score, 2)

    def _fallback_recommendation(self, fatigue_level: str, rest_recommended: bool) -> str:
        if rest_recommended:
            return "Your load is high — take an easy day or full rest before resuming hard training."
        if fatigue_level == "moderate":
            return "Load is moderate; keep intensity controlled and prioritise sleep tonight."
        return "Recovery looks good; you can handle a quality session in the next 24 hours."

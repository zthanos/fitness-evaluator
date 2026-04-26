"""FitnessStateBuilder — aggregates recent WorkoutAnalysis outputs into a persisted athlete state."""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import FitnessState, FitnessStateInput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a precision endurance coach.
Given an athlete's structured fitness state, write a 2-3 sentence summary that:
1. Names their current limiter and confidence level.
2. States their fatigue situation.
3. Gives the single most important focus for the next 7 days.
Be specific. No generic advice. No bullet points."""


class FitnessStateBuilder(BaseSkill[FitnessStateInput, FitnessState]):

    async def run(self, input: FitnessStateInput) -> FitnessState:
        from app.ai.skills.workout_analyzer import WorkoutAnalyzer
        from app.ai.skills.schemas import WorkoutAnalyzerInput, WorkoutAnalysis

        # Pull recent workout analyses
        analyzer = WorkoutAnalyzer(self.db, self.athlete_id)
        analyses: list[WorkoutAnalysis] = await analyzer.run(
            WorkoutAnalyzerInput(n_recent=min(20, input.lookback_days // 2))
        )

        state = self._aggregate(analyses, input.lookback_days)

        # Generate summary text
        state_dict = state.model_dump(mode="json", exclude={"summary_text"})
        state.summary_text = await self._llm_reason(_SYSTEM_PROMPT, json.dumps(state_dict, default=str))

        # Persist
        self._upsert(state)
        return state

    # ── Aggregation ──────────────────────────────────────────────────────────

    def _aggregate(self, analyses: list, lookback_days: int) -> FitnessState:
        now = datetime.now(timezone.utc)

        if not analyses:
            return FitnessState(
                athlete_id=self.athlete_id,
                comfort_cadence_indoor=None,
                comfort_cadence_outdoor=None,
                climbing_cadence=None,
                current_limiter=None,
                limiter_confidence=0.0,
                fatigue_level="low",
                weekly_consistency=0.0,
                acwr_ratio=None,
                hr_response_trend=None,
                rhr_trend=None,
                state_confidence=0.0,
                last_updated_at=now,
                summary_text=None,
            )

        # Cadence by context
        indoor_cadences  = [a.avg_cadence for a in analyses if a.is_indoor and a.avg_cadence]
        outdoor_cadences = [a.avg_cadence for a in analyses if not a.is_indoor and a.avg_cadence]
        climbing_cadences = [
            a.avg_cadence for a in analyses
            if not a.is_indoor and a.avg_cadence
            and self._is_climb(a)
        ]

        # Limiter — most common hypothesis with confidence
        limiters = [a.limiter_hypothesis for a in analyses if a.limiter_hypothesis]
        current_limiter: Optional[str] = None
        limiter_confidence = 0.0
        if limiters:
            most_common, count = Counter(limiters).most_common(1)[0]
            current_limiter  = most_common
            limiter_confidence = round(count / len(limiters), 2)

        # ACWR — acute (7d) vs chronic (28d) moving time
        acwr = self._compute_acwr(lookback_days)

        # Fatigue from ACWR
        fatigue_level = self._fatigue_from_acwr(acwr)

        # Weekly consistency
        consistency = self._compute_consistency(lookback_days)

        # HR trend — compare first half vs second half avg_hr of similar activities
        hr_trend = self._compute_hr_trend(analyses)

        # RHR trend from WeeklyMeasurement
        rhr_trend = self._compute_rhr_trend()

        # Confidence based on data richness
        confidence = min(1.0, round(
            (len(analyses) / 10) * 0.5 +
            (1.0 if current_limiter else 0.0) * 0.3 +
            (1.0 if acwr is not None else 0.0) * 0.2,
            2
        ))

        return FitnessState(
            athlete_id=self.athlete_id,
            comfort_cadence_indoor= round(mean(indoor_cadences), 1)  if indoor_cadences  else None,
            comfort_cadence_outdoor=round(mean(outdoor_cadences), 1) if outdoor_cadences else None,
            climbing_cadence=       round(mean(climbing_cadences), 1) if climbing_cadences else None,
            current_limiter=current_limiter,
            limiter_confidence=limiter_confidence,
            fatigue_level=fatigue_level,
            weekly_consistency=consistency,
            acwr_ratio=acwr,
            hr_response_trend=hr_trend,
            rhr_trend=rhr_trend,
            state_confidence=confidence,
            last_updated_at=now,
            summary_text=None,  # filled after LLM call
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _is_climb(self, a) -> bool:
        """Heuristic: elevation_m / distance_km > 20 m/km."""
        if not hasattr(a, "elevation_m") or not a.elevation_m:
            return False
        # We don't have distance on WorkoutAnalysis directly — skip for now
        return False

    def _compute_acwr(self, lookback_days: int) -> Optional[float]:
        from app.models.strava_activity import StravaActivity
        now = datetime.now(timezone.utc)

        def load(days_back: int, window: int) -> float:
            cutoff = now - timedelta(days=days_back)
            end    = now - timedelta(days=days_back - window)
            rows = (
                self.db.query(StravaActivity.moving_time_s)
                .filter(
                    StravaActivity.athlete_id == self.athlete_id,
                    StravaActivity.start_date >= cutoff,
                    StravaActivity.start_date < end,
                )
                .all()
            )
            return sum(r[0] or 0 for r in rows) / 60  # minutes

        acute  = load(0, 7)
        chronic_weekly = load(0, 28) / 4  # average 7-day load over 28 days
        if chronic_weekly == 0:
            return None
        return round(acute / chronic_weekly, 2)

    def _fatigue_from_acwr(self, acwr: Optional[float]) -> str:
        if acwr is None:    return "low"
        if acwr > 1.5:      return "overreaching"
        if acwr > 1.3:      return "high"
        if acwr > 0.8:      return "moderate"
        return "low"

    def _compute_consistency(self, lookback_days: int) -> float:
        from app.models.strava_activity import StravaActivity
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        sessions = (
            self.db.query(StravaActivity)
            .filter(
                StravaActivity.athlete_id == self.athlete_id,
                StravaActivity.start_date >= cutoff,
            )
            .count()
        )
        target = lookback_days / 7 * 4   # assume 4 sessions/week target
        return min(1.0, round(sessions / target, 2)) if target > 0 else 0.0

    def _compute_hr_trend(self, analyses: list) -> Optional[str]:
        hr_values = [a.avg_hr for a in analyses if a.avg_hr]
        if len(hr_values) < 4:
            return None
        mid = len(hr_values) // 2
        early_avg = mean(hr_values[mid:])   # older
        recent_avg = mean(hr_values[:mid])   # newer (list is desc by date)
        diff = recent_avg - early_avg
        if diff < -3:   return "improving"
        if diff > 3:    return "degrading"
        return "stable"

    def _compute_rhr_trend(self) -> Optional[str]:
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
        diff = mean(values[:2]) - mean(values[-2:])  # recent vs older (lower is better)
        if diff < -1:  return "degrading"
        if diff > 1:   return "improving"
        return "stable"

    # ── Persistence ──────────────────────────────────────────────────────────

    def _upsert(self, state: FitnessState) -> None:
        from app.models.athlete_fitness_state import AthleteFitnessState
        existing = (
            self.db.query(AthleteFitnessState)
            .filter(AthleteFitnessState.athlete_id == self.athlete_id)
            .first()
        )
        fields = {
            "comfort_cadence_indoor":  state.comfort_cadence_indoor,
            "comfort_cadence_outdoor": state.comfort_cadence_outdoor,
            "climbing_cadence":        state.climbing_cadence,
            "current_limiter":         state.current_limiter,
            "limiter_confidence":      state.limiter_confidence,
            "fatigue_level":           state.fatigue_level,
            "weekly_consistency":      state.weekly_consistency,
            "acwr_ratio":              state.acwr_ratio,
            "hr_response_trend":       state.hr_response_trend,
            "rhr_trend":               state.rhr_trend,
            "state_confidence":        state.state_confidence,
            "last_updated_at":         state.last_updated_at,
            "summary_text":            state.summary_text,
        }
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            self.db.add(AthleteFitnessState(athlete_id=self.athlete_id, **fields))
        self.db.commit()

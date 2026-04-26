"""ProgressAnalyzer — tracks progress toward athlete goals and flags adjustment needs."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from statistics import mean
from typing import Optional

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import ProgressInput, ProgressReport, GoalProgress

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a fitness coach summarising goal progress.
Given structured progress data for one or more athlete goals, write 2-3 sentences that:
1. Name which goal is most at-risk and why (with numbers).
2. State the overall trajectory (improving / stable / declining).
3. Give the single most important adjustment if needed.
Be specific. Reference actual numbers. No generic advice."""


class ProgressAnalyzer(BaseSkill[ProgressInput, ProgressReport]):

    async def run(self, input: ProgressInput) -> ProgressReport:
        from app.models.athlete_goal import AthleteGoal, GoalStatus

        query = (
            self.db.query(AthleteGoal)
            .filter(
                AthleteGoal.athlete_id == str(self.athlete_id),
                AthleteGoal.status == GoalStatus.ACTIVE.value,
            )
        )
        if input.goal_id:
            query = query.filter(AthleteGoal.id == input.goal_id)

        goals = query.all()

        if not goals:
            return ProgressReport(
                goals=[],
                overall_trend="no_data",
                summary="No active goals found. Set goals via the coach chat to track progress.",
            )

        goal_progresses = [self._evaluate_goal(g) for g in goals]

        # Overall trend — majority vote
        trends = [gp.trend for gp in goal_progresses if gp.trend]
        overall_trend = self._majority_trend(trends)

        summary = await self._llm_reason(
            _SYSTEM_PROMPT,
            self._progress_payload(goal_progresses),
        )
        if not summary:
            summary = self._fallback_summary(goal_progresses, overall_trend)

        return ProgressReport(
            goals=goal_progresses,
            overall_trend=overall_trend,
            summary=summary,
        )

    # ── Goal evaluation ──────────────────────────────────────────────────────

    def _evaluate_goal(self, goal) -> GoalProgress:
        goal_type = goal.goal_type

        if goal_type in ("weight_loss", "weight_gain"):
            return self._evaluate_weight_goal(goal)
        elif goal_type in ("endurance", "performance"):
            return self._evaluate_activity_goal(goal)
        else:
            return self._evaluate_custom_goal(goal)

    def _evaluate_weight_goal(self, goal) -> GoalProgress:
        from app.models.weekly_measurement import WeeklyMeasurement

        rows = (
            self.db.query(WeeklyMeasurement.weight_kg, WeeklyMeasurement.week_start)
            .filter(
                WeeklyMeasurement.athlete_id == self.athlete_id,
                WeeklyMeasurement.weight_kg.isnot(None),
            )
            .order_by(WeeklyMeasurement.week_start.desc())
            .limit(8)
            .all()
        )

        current_weight: Optional[float] = rows[0][0] if rows else None
        target = goal.target_value
        gap = round(current_weight - target, 2) if (current_weight is not None and target is not None) else None

        trend = self._weight_trend(rows, goal.goal_type)
        eta = self._weight_eta(rows, gap) if gap else None
        adjustment = abs(gap or 0) > 5 and trend not in ("on_track", "ahead")

        return GoalProgress(
            goal_id=goal.id,
            goal_type=goal.goal_type,
            description=goal.description,
            current_value=current_weight,
            target_value=target,
            gap=gap,
            trend=trend,
            eta_weeks=eta,
            adjustment_suggested=adjustment,
            adjustment_note="Consider reviewing weekly calorie deficit and training volume." if adjustment else None,
        )

    def _evaluate_activity_goal(self, goal) -> GoalProgress:
        from app.models.strava_activity import StravaActivity
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=28)
        rows = (
            self.db.query(StravaActivity.moving_time_s, StravaActivity.distance_m)
            .filter(
                StravaActivity.athlete_id == self.athlete_id,
                StravaActivity.start_date >= cutoff,
            )
            .all()
        )

        if not rows:
            return GoalProgress(
                goal_id=goal.id,
                goal_type=goal.goal_type,
                description=goal.description,
                current_value=None,
                target_value=goal.target_value,
                gap=None,
                trend=None,
                eta_weeks=None,
                adjustment_suggested=False,
                adjustment_note=None,
            )

        # Use weekly volume (minutes) as proxy for endurance/performance progress
        weekly_minutes = sum(r[0] or 0 for r in rows) / 60 / 4
        target = goal.target_value  # treat target_value as target weekly minutes

        gap    = round(weekly_minutes - (target or 0), 1) if target else None
        trend  = "on_track" if gap is None or gap >= 0 else "behind"

        return GoalProgress(
            goal_id=goal.id,
            goal_type=goal.goal_type,
            description=goal.description,
            current_value=round(weekly_minutes, 1),
            target_value=target,
            gap=gap,
            trend=trend,
            eta_weeks=None,
            adjustment_suggested=trend == "behind",
            adjustment_note="Increase weekly training volume to close the gap." if trend == "behind" else None,
        )

    def _evaluate_custom_goal(self, goal) -> GoalProgress:
        return GoalProgress(
            goal_id=goal.id,
            goal_type=goal.goal_type,
            description=goal.description,
            current_value=None,
            target_value=goal.target_value,
            gap=None,
            trend=None,
            eta_weeks=None,
            adjustment_suggested=False,
            adjustment_note=None,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _weight_trend(rows: list, goal_type: str) -> Optional[str]:
        weights = [r[0] for r in rows if r[0] is not None]
        if len(weights) < 3:
            return None
        recent = mean(weights[:2])
        older  = mean(weights[-2:])
        diff   = recent - older  # negative = losing weight
        if goal_type == "weight_loss":
            if diff < -0.5:   return "on_track"
            if diff < 0.3:    return "plateau"
            return "behind"
        else:  # weight_gain
            if diff > 0.3:    return "on_track"
            if diff > -0.3:   return "plateau"
            return "behind"

    @staticmethod
    def _weight_eta(rows: list, gap: Optional[float]) -> Optional[float]:
        if gap is None or len(rows) < 3:
            return None
        weights = [r[0] for r in rows if r[0] is not None]
        recent = mean(weights[:2])
        older  = mean(weights[-2:])
        weekly_rate = (older - recent) / max(len(weights) - 1, 1)
        if abs(weekly_rate) < 0.05:
            return None
        return round(abs(gap) / abs(weekly_rate), 1)

    @staticmethod
    def _majority_trend(trends: list[str]) -> str:
        if not trends:
            return "no_data"
        from collections import Counter
        top, _ = Counter(trends).most_common(1)[0]
        mapping = {
            "on_track": "improving",
            "ahead":    "improving",
            "behind":   "declining",
            "plateau":  "stable",
        }
        return mapping.get(top, "stable")

    @staticmethod
    def _progress_payload(goals: list[GoalProgress]) -> str:
        import json
        return json.dumps(
            [
                {
                    "goal_type":   g.goal_type,
                    "description": g.description,
                    "current":     g.current_value,
                    "target":      g.target_value,
                    "gap":         g.gap,
                    "trend":       g.trend,
                    "eta_weeks":   g.eta_weeks,
                }
                for g in goals
            ],
            default=str,
        )

    @staticmethod
    def _fallback_summary(goals: list[GoalProgress], trend: str) -> str:
        n = len(goals)
        behind = [g for g in goals if g.trend in ("behind", "plateau")]
        if not behind:
            return f"All {n} goal(s) are on track. Keep up the current approach."
        names = ", ".join(g.goal_type for g in behind[:2])
        return f"{len(behind)} of {n} goal(s) ({names}) need attention. Overall trend: {trend}."

"""BodyTrendAnalyzer — computes weight, body composition, and RHR trends from weekly measurements."""
from __future__ import annotations

import logging
from statistics import mean
from typing import Optional

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import BodyTrendInput, BodyTrend

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a fitness coach assessing body composition and health trends.
Given structured weekly measurement data, write ONE sentence (≤30 words) summarising
the most important trend and its implication. Be specific — use actual numbers.
No generic advice. No bullet points."""


class BodyTrendAnalyzer(BaseSkill[BodyTrendInput, BodyTrend]):

    async def run(self, input: BodyTrendInput) -> BodyTrend:
        rows = self._load_measurements(input.lookback_weeks)

        if not rows:
            return BodyTrend(
                weeks_analysed=0,
                weight_slope_kg_per_week=None,
                body_fat_trend=None,
                waist_trend=None,
                rhr_trend=None,
                plateau_detected=False,
                assessment="Insufficient data — no weekly measurements found.",
                confidence=0.0,
            )

        weight_slope   = self._slope([r["weight_kg"] for r in rows if r["weight_kg"] is not None])
        body_fat_trend = self._direction([r["body_fat_pct"] for r in rows if r["body_fat_pct"] is not None], invert=False)
        waist_trend    = self._direction([r["waist_cm"] for r in rows if r["waist_cm"] is not None], invert=False)
        rhr_trend      = self._rhr_direction([r["rhr_bpm"] for r in rows if r["rhr_bpm"] is not None])
        plateau        = self._detect_plateau(rows)
        confidence     = self._compute_confidence(rows)

        user_content = (
            f"weeks={len(rows)}, "
            f"weight_slope_kg_per_week={weight_slope}, "
            f"body_fat_trend={body_fat_trend}, "
            f"waist_trend={waist_trend}, "
            f"rhr_trend={rhr_trend}, "
            f"plateau_detected={plateau}"
        )
        assessment = await self._llm_reason(_SYSTEM_PROMPT, user_content)
        if not assessment:
            assessment = self._fallback_assessment(weight_slope, plateau)

        return BodyTrend(
            weeks_analysed=len(rows),
            weight_slope_kg_per_week=weight_slope,
            body_fat_trend=body_fat_trend,
            waist_trend=waist_trend,
            rhr_trend=rhr_trend,
            plateau_detected=plateau,
            plateau_weeks=self._plateau_weeks(rows) if plateau else 0,
            assessment=assessment,
            confidence=confidence,
        )

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_measurements(self, lookback_weeks: int) -> list[dict]:
        from app.models.weekly_measurement import WeeklyMeasurement
        rows = (
            self.db.query(WeeklyMeasurement)
            .filter(WeeklyMeasurement.athlete_id == self.athlete_id)
            .order_by(WeeklyMeasurement.week_start.desc())
            .limit(lookback_weeks)
            .all()
        )
        return [
            {
                "week_start":   r.week_start,
                "weight_kg":    r.weight_kg,
                "body_fat_pct": r.body_fat_pct,
                "waist_cm":     r.waist_cm,
                "rhr_bpm":      r.rhr_bpm,
            }
            for r in rows
        ]

    # ── Stats helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _slope(values: list[float]) -> Optional[float]:
        """OLS slope — positive means increasing over time."""
        n = len(values)
        if n < 2:
            return None
        x = list(range(n))
        # x is newest→oldest (desc order), so we reverse for oldest→newest
        y = list(reversed(values))
        x = list(range(len(y)))
        sx = sum(x); sy = sum(y)
        sxy = sum(xi * yi for xi, yi in zip(x, y))
        sx2 = sum(xi * xi for xi in x)
        denom = n * sx2 - sx * sx
        if denom == 0:
            return None
        return round((n * sxy - sx * sy) / denom, 3)

    @staticmethod
    def _direction(values: list[float], invert: bool = False) -> Optional[str]:
        if len(values) < 3:
            return None
        recent = mean(values[:2])
        older  = mean(values[-2:])
        diff   = recent - older
        if abs(diff) < 0.5:  # noise threshold
            return "stable"
        going_up = diff > 0
        if invert:
            going_up = not going_up
        return "increasing" if going_up else "decreasing"

    def _rhr_direction(self, values: list[float]) -> Optional[str]:
        if len(values) < 3:
            return None
        recent = mean(values[:2])
        older  = mean(values[-2:])
        diff   = recent - older  # positive = RHR rose (worse)
        if abs(diff) < 1:
            return "stable"
        return "degrading" if diff > 0 else "improving"

    def _detect_plateau(self, rows: list[dict]) -> bool:
        weights = [r["weight_kg"] for r in rows[:4] if r["weight_kg"] is not None]
        if len(weights) < 3:
            return False
        slope = self._slope(weights)
        return slope is not None and abs(slope) < 0.1

    def _plateau_weeks(self, rows: list[dict]) -> int:
        count = 0
        weights = [r["weight_kg"] for r in rows if r["weight_kg"] is not None]
        for i in range(len(weights) - 1):
            if abs(weights[i] - weights[i + 1]) < 0.2:
                count += 1
            else:
                break
        return count

    def _compute_confidence(self, rows: list[dict]) -> float:
        if not rows:
            return 0.0
        filled = sum(
            1 for r in rows
            if r["weight_kg"] is not None or r["body_fat_pct"] is not None
        )
        return round(min(1.0, filled / max(len(rows), 1)), 2)

    def _fallback_assessment(self, slope: Optional[float], plateau: bool) -> str:
        if plateau:
            return "Weight has plateaued over the past several weeks — review nutrition adherence."
        if slope is None:
            return "Insufficient measurement data to assess body trend."
        if slope < -0.1:
            return f"Weight trending down at {abs(slope):.2f} kg/week — on track."
        if slope > 0.1:
            return f"Weight trending up at {slope:.2f} kg/week — review calorie intake."
        return "Weight is stable."

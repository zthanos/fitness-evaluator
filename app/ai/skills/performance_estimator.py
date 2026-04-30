"""PerformanceEstimator — translates a goal into required performance metrics
and computes the gap from the athlete's current sport profile.

Responsibility (single):
    Given "ride 70 km in 3 hours", derive what speed that requires,
    find the athlete's best comparable current performance, and return
    the gap — grounded entirely in observed data.

Guardrail:
    Never emit target_watts, W/kg, FTP-derived targets, or race-prediction
    numbers. Only speed, distance, duration, and gap — all from real activities.

Pipeline position:
    goal intent → PerformanceEstimator → CoachSynthesizer
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import PerformanceGoalInput, PerformanceEstimate

logger = logging.getLogger(__name__)

_PARSE_PROMPT = """Extract the performance goal from the user's message.
Return ONLY valid JSON with these keys (null if not mentioned):
{
  "sport_group": "ride" | "run" | "swim" | "strength" | null,
  "target_distance_km": number | null,
  "target_duration_min": number | null
}

Common conversions to apply:
- marathon = 42.195 km
- half marathon = 21.0975 km
- 10K = 10 km
- "3 hours" = 180 min, "1h30" = 90 min
- "cycling" / "bike" / "biking" → ride
- "running" / "jog" → run

No explanation. Only the JSON object."""


class PerformanceEstimator(BaseSkill[PerformanceGoalInput, PerformanceEstimate]):

    async def run(self, input: PerformanceGoalInput) -> PerformanceEstimate:
        # Step 1 — parse goal from natural language
        parsed = await self._parse_goal(input.query)
        sport_group = input.sport_group or parsed.get("sport_group")
        target_km   = parsed.get("target_distance_km")
        target_min  = parsed.get("target_duration_min")

        if not sport_group or (target_km is None and target_min is None):
            return PerformanceEstimate(
                sport_group=sport_group or "unknown",
                parse_success=False,
                data_basis="Could not extract a clear distance/duration target from the goal.",
                confidence=0.0,
            )

        # Step 2 — compute target speed (only if both distance and duration are known)
        target_speed: Optional[float] = None
        if target_km and target_min and target_min > 0:
            target_speed = round(target_km / (target_min / 60), 2)

        # Step 3 — load sport profile
        profile = self._load_profile(sport_group)

        # Step 4 — find best comparable current speed
        current_speed, basis = self._comparable_speed(profile, target_km, target_min)

        # Step 5 — compute gap
        speed_gap_kmh: Optional[float] = None
        speed_gap_pct: Optional[float] = None
        if target_speed is not None and current_speed is not None:
            speed_gap_kmh = round(target_speed - current_speed, 2)
            speed_gap_pct = round((speed_gap_kmh / current_speed) * 100, 1) if current_speed > 0 else None

        # Step 6 — pull limiters from profile
        limiters: list[str] = []
        if profile and profile.current_limiters:
            limiters = profile.current_limiters or []

        confidence = self._score_confidence(profile, target_km, target_min, current_speed)

        data_basis = self._describe_basis(profile, basis, target_km, target_min, target_speed)

        return PerformanceEstimate(
            sport_group=sport_group,
            target_distance_km=target_km,
            target_duration_min=target_min,
            target_speed_kmh=target_speed,
            current_best_comparable_speed_kmh=round(current_speed, 2) if current_speed else None,
            speed_gap_kmh=speed_gap_kmh,
            speed_gap_percent=speed_gap_pct,
            comparable_basis=basis,
            current_limiters=limiters,
            data_basis=data_basis,
            confidence=confidence,
            parse_success=True,
        )

    # ------------------------------------------------------------------
    # Goal parsing
    # ------------------------------------------------------------------

    async def _parse_goal(self, query: str) -> dict:
        raw = await self._llm_reason(_PARSE_PROMPT, query)
        try:
            cleaned = (
                raw.strip()
                .removeprefix("```json").removeprefix("```")
                .removesuffix("```").strip()
            )
            return json.loads(cleaned)
        except Exception:
            logger.warning("PerformanceEstimator: could not parse LLM goal extraction")
            return {}

    # ------------------------------------------------------------------
    # Profile lookup
    # ------------------------------------------------------------------

    def _load_profile(self, sport_group: str):
        try:
            from app.models.athlete_sport_profile import AthleteSportProfile
            return (
                self.db.query(AthleteSportProfile)
                .filter_by(athlete_id=self.athlete_id, sport_group=sport_group)
                .first()
            )
        except Exception as exc:
            logger.warning("PerformanceEstimator: could not load sport profile: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Comparable speed selection
    # ------------------------------------------------------------------

    def _comparable_speed(
        self, profile, target_km: Optional[float], target_min: Optional[float]
    ) -> tuple[Optional[float], Optional[str]]:
        """
        Pick the most relevant current-performance speed from the stored profile.

        Priority:
          1. Matching-duration column (60-min or 120-min best distance)
          2. best_long_speed_kmh  (for efforts > 90 min)
          3. typical_endurance_speed_kmh  (general fallback)
        """
        if profile is None:
            return None, None

        if target_min is not None:
            # 50–70 min target → use best_60min_distance_km (it IS km/h over 1 h)
            if 50 <= target_min <= 70 and profile.best_60min_distance_km:
                return profile.best_60min_distance_km, "best 60-min ride distance (km/h equivalent)"

            # 100–140 min target → use best_120min_distance_km / 2
            if 100 <= target_min <= 140 and profile.best_120min_distance_km:
                speed = profile.best_120min_distance_km / 2
                return speed, "best 120-min ride distance (half = km/h equivalent)"

            # Long efforts (> 90 min) → best long speed
            if target_min > 90 and profile.best_long_speed_kmh:
                return profile.best_long_speed_kmh, "best long-effort speed from activity history"

        # General fallback — typical endurance speed
        if profile.typical_endurance_speed_kmh:
            return profile.typical_endurance_speed_kmh, "typical endurance speed from recent activities"

        return None, None

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _score_confidence(
        self,
        profile,
        target_km: Optional[float],
        target_min: Optional[float],
        current_speed: Optional[float],
    ) -> float:
        if profile is None:
            return 0.1
        base = profile.profile_confidence or 0.5
        # Both sides of the gap are known → full base confidence
        if target_km and target_min and current_speed:
            return round(min(base, 0.95), 2)
        # Only one side known
        if current_speed or (target_km and target_min):
            return round(base * 0.6, 2)
        return 0.2

    # ------------------------------------------------------------------
    # Summary text
    # ------------------------------------------------------------------

    def _describe_basis(
        self,
        profile,
        basis: Optional[str],
        target_km: Optional[float],
        target_min: Optional[float],
        target_speed: Optional[float],
    ) -> str:
        parts = []
        if target_km and target_min:
            parts.append(
                f"Goal: {target_km} km in {target_min:.0f} min "
                f"({target_speed:.1f} km/h required)" if target_speed else
                f"Goal: {target_km} km in {target_min:.0f} min"
            )
        elif target_km:
            parts.append(f"Goal: {target_km} km (no time target)")
        elif target_min:
            parts.append(f"Goal: {target_min:.0f} min effort (no distance target)")

        if profile and basis:
            parts.append(f"Current reference: {basis}")
        elif profile is None:
            parts.append("No sport profile found — run SportProfileBuilder first")

        return ". ".join(parts)

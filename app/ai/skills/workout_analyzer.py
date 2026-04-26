"""WorkoutAnalyzer skill — interprets a single activity's metrics into coaching insight."""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import WorkoutAnalysis, WorkoutAnalyzerInput

logger = logging.getLogger(__name__)

# Cadence benchmarks (rpm) by sport_type / activity_type
_CADENCE_TARGETS: dict[str, float] = {
    "Run":              170,
    "VirtualRun":       170,
    "Ride":             90,
    "VirtualRide":      90,
    "MountainBikeRide": 75,
    "GravelRide":       85,
    "EBikeRide":        80,
}

_CADENCE_BANDS = {
    # (min_pct_of_target, quality)
    0.97: "excellent",
    0.90: "good",
    0.80: "fair",
    0.0:  "poor",
}

_SYSTEM_PROMPT = """You are a precision endurance coach.
You receive structured metrics for one workout and must produce:
1. limiter_hypothesis — the most likely performance limiter (e.g. "aerobic_base",
   "cadence_capacity", "outdoor_transfer", "strength_endurance", "pacing").
2. main_insight — one sentence naming the key finding from this session.
3. next_action — one concrete, specific thing the athlete should do next.

Be direct and specific. Reference actual numbers. No generic advice.
Respond ONLY with a JSON object with keys: limiter_hypothesis, main_insight, next_action."""


class WorkoutAnalyzer(BaseSkill[WorkoutAnalyzerInput, list[WorkoutAnalysis]]):

    def __init__(self, db: Session, athlete_id: int):
        super().__init__(db, athlete_id)

    async def run(self, input: WorkoutAnalyzerInput) -> list[WorkoutAnalysis]:
        from app.models.strava_activity import StravaActivity

        if input.strava_id:
            rows = (
                self.db.query(StravaActivity)
                .filter(
                    StravaActivity.strava_id == input.strava_id,
                    StravaActivity.athlete_id == self.athlete_id,
                )
                .limit(1)
                .all()
            )
        else:
            rows = self._recent_activities(days=90, limit=input.n_recent)

        results = []
        for row in rows:
            analysis = await self._analyse_one(row)
            results.append(analysis)
        return results

    async def _analyse_one(self, row) -> WorkoutAnalysis:
        sport = row.sport_type or row.activity_type
        is_indoor = bool(row.trainer)

        # Cadence quality
        target_rpm = _CADENCE_TARGETS.get(sport) or _CADENCE_TARGETS.get(row.activity_type)
        cadence_quality, hr_response, hr_zone = self._compute_cadence_quality(
            row.avg_cadence, target_rpm
        )
        hr_response, hr_zone = self._compute_hr_response(row.avg_hr, row.max_hr)

        # Effort level from suffer_score or HR
        effort_level = self._compute_effort(row.suffer_score, row.avg_hr, row.max_hr)
        training_purpose = self._infer_purpose(effort_level, sport, is_indoor)

        # Intensity factor (requires FTP — skip if unknown)
        intensity_factor: Optional[float] = None
        if row.weighted_avg_watts:
            ftp = self._get_ftp()
            if ftp:
                intensity_factor = round(row.weighted_avg_watts / ftp, 3)

        # LLM interpretation
        llm_out = await self._llm_interpret(row, sport, is_indoor, cadence_quality,
                                            hr_response, effort_level, target_rpm,
                                            intensity_factor)

        confidence = self._compute_confidence(row)

        return WorkoutAnalysis(
            strava_id=row.strava_id,
            activity_type=row.activity_type,
            sport_type=row.sport_type,
            is_indoor=is_indoor,
            start_date=row.start_date,
            avg_cadence=row.avg_cadence,
            max_cadence=row.max_cadence,
            cadence_quality=cadence_quality,
            cadence_target_rpm=target_rpm,
            avg_hr=row.avg_hr,
            max_hr=row.max_hr,
            hr_zone=hr_zone,
            hr_response=hr_response,
            avg_watts=row.avg_watts,
            weighted_avg_watts=row.weighted_avg_watts,
            intensity_factor=intensity_factor,
            effort_level=effort_level,
            training_purpose=training_purpose,
            suffer_score=row.suffer_score,
            limiter_hypothesis=llm_out.get("limiter_hypothesis"),
            main_insight=llm_out.get("main_insight", ""),
            next_action=llm_out.get("next_action", ""),
            confidence=confidence,
        )

    # ── Computation helpers ──────────────────────────────────────────────────

    def _compute_cadence_quality(
        self, avg_cadence: Optional[float], target: Optional[float]
    ) -> tuple[str, str, Optional[str]]:
        if avg_cadence is None or target is None:
            return "no_data", "no_data", None
        ratio = avg_cadence / target
        for threshold, quality in sorted(_CADENCE_BANDS.items(), reverse=True):
            if ratio >= threshold:
                return quality, "no_data", None
        return "poor", "no_data", None

    def _compute_hr_response(
        self, avg_hr: Optional[int], max_hr: Optional[int]
    ) -> tuple[str, Optional[str]]:
        if avg_hr is None:
            return "no_data", None
        # Simplified zone estimate — uses 220-age max HR approximation
        # Without athlete max HR we use absolute thresholds
        if avg_hr < 115:
            return "controlled", "Z1"
        if avg_hr < 140:
            return "moderate",   "Z2"
        if avg_hr < 160:
            return "high",       "Z3-Z4"
        return "maximal", "Z5"

    def _compute_effort(
        self,
        suffer_score: Optional[int],
        avg_hr: Optional[int],
        max_hr: Optional[int],
    ) -> str:
        if suffer_score is not None:
            if suffer_score < 25:  return "easy"
            if suffer_score < 75:  return "moderate"
            if suffer_score < 150: return "hard"
            return "maximal"
        if avg_hr is not None:
            if avg_hr < 120: return "easy"
            if avg_hr < 145: return "moderate"
            if avg_hr < 165: return "hard"
            return "maximal"
        return "moderate"

    def _infer_purpose(self, effort: str, sport: str, indoor: bool) -> str:
        base = {
            "easy":     "recovery / aerobic base",
            "moderate": "endurance / tempo",
            "hard":     "threshold / lactate",
            "maximal":  "VO2max / race effort",
        }.get(effort, "general fitness")
        if indoor:
            return f"{base} (indoor)"
        return base

    def _get_ftp(self) -> Optional[float]:
        """Return athlete's FTP if stored — placeholder for future expansion."""
        return None

    def _compute_confidence(self, row) -> float:
        """Score 0-1 based on how many key fields are populated."""
        fields = [row.avg_hr, row.avg_cadence, row.avg_watts,
                  row.moving_time_s, row.distance_m]
        filled = sum(1 for f in fields if f is not None)
        return round(filled / len(fields), 2)

    # ── LLM interpretation ───────────────────────────────────────────────────

    async def _llm_interpret(
        self, row, sport, is_indoor, cadence_quality,
        hr_response, effort_level, target_rpm, intensity_factor
    ) -> dict:
        metrics = {
            "sport": sport,
            "indoor": is_indoor,
            "duration_min": round(row.moving_time_s / 60, 1) if row.moving_time_s else None,
            "distance_km": round(row.distance_m / 1000, 2) if row.distance_m else None,
            "elevation_m": row.elevation_m,
            "avg_cadence": row.avg_cadence,
            "max_cadence": row.max_cadence,
            "cadence_target_rpm": target_rpm,
            "cadence_quality": cadence_quality,
            "avg_hr": row.avg_hr,
            "max_hr": row.max_hr,
            "hr_response": hr_response,
            "avg_watts": row.avg_watts,
            "weighted_avg_watts": row.weighted_avg_watts,
            "intensity_factor": intensity_factor,
            "effort_level": effort_level,
            "suffer_score": row.suffer_score,
        }
        raw = await self._llm_reason(_SYSTEM_PROMPT, json.dumps(metrics, default=str))
        try:
            # Strip markdown code fences if present
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(cleaned)
        except Exception:
            logger.warning("WorkoutAnalyzer: could not parse LLM JSON, using fallback")
            return {
                "limiter_hypothesis": None,
                "main_insight": raw[:200] if raw else "Analysis unavailable.",
                "next_action": "Review your recent sessions and discuss with your coach.",
            }

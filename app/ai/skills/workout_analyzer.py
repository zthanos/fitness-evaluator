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

_SYSTEM_PROMPT = """You are a precision endurance coach analysing one of your athlete's sessions.

Speak directly to the athlete — always "you/your", never "the athlete".
Reference their actual numbers from the session AND from their personal baseline (provided below).
Use athlete_demographics (age, weight, resting HR) when relevant — e.g. age informs what "close to max HR" means, weight matters for power-to-weight context.

Produce six fields:

1. limiter_hypothesis — the single most likely limiter token:
   "aerobic_base" | "cadence_capacity" | "outdoor_transfer" | "strength_endurance" | "pacing" | "volume"

2. session_type — one sentence characterising what kind of session this was.
   Include the actual HR and/or power numbers. E.g.:
   "Hard session — avg HR 144 bpm, max 168 bpm, close to your observed max HR, stressing the upper aerobic / threshold range."

3. main_insight — 1-2 sentences on what this session reveals about the athlete's current capabilities or gaps.
   Must reference at least one actual number AND compare against their personal baseline, not generic targets.
   E.g. "You can sustain high cardiovascular effort, but cadence dropped to 63 rpm — well below your indoor typical of 78 rpm."

4. key_limiter — a short human-readable label for the primary limiter (3-8 words).
   E.g. "Cadence control under cardiovascular load."

5. why_it_matters — 1-2 sentences explaining the physiological or performance consequence of this limiter for THIS sport.
   E.g. "When cadence drops while HR stays high, you convert more effort into muscle strain than forward momentum — making climbs and long efforts feel harder than they need to."

6. next_action — one concrete, achievable next step for THIS athlete at their current level.
   Calibrate to their actual baseline numbers, not ideal targets.
   E.g. if their typical cadence is 63 rpm, prescribe a progression step ("add 2×10 min targeting 70 rpm"), not 90 rpm intervals.

No pleasantries. No generic advice. Be sport-specific.
Respond ONLY with valid JSON:
{"limiter_hypothesis": "...", "session_type": "...", "main_insight": "...", "key_limiter": "...", "why_it_matters": "...", "next_action": "..."}"""


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
            session_type=llm_out.get("session_type"),
            main_insight=llm_out.get("main_insight", ""),
            key_limiter=llm_out.get("key_limiter"),
            why_it_matters=llm_out.get("why_it_matters"),
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

        # Use athlete-relative zones from sport profile when available
        profile_max_hr = self._get_max_hr_from_profile()
        effective_max = profile_max_hr or max_hr

        if effective_max and effective_max > 0:
            pct = avg_hr / effective_max
            if pct < 0.60:  return "controlled", "Z1"
            if pct < 0.70:  return "moderate",   "Z2"
            if pct < 0.80:  return "moderate",   "Z3"
            if pct < 0.90:  return "high",        "Z4"
            return "maximal", "Z5"

        # Fallback: absolute thresholds (no max HR data)
        if avg_hr < 115:  return "controlled", "Z1"
        if avg_hr < 140:  return "moderate",   "Z2"
        if avg_hr < 160:  return "high",        "Z3-Z4"
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
        """Return FTP estimate from the athlete's ride sport profile, or None."""
        try:
            from app.models.athlete_sport_profile import AthleteSportProfile
            profile = (
                self.db.query(AthleteSportProfile)
                .filter_by(athlete_id=self.athlete_id, sport_group="ride")
                .first()
            )
            return profile.ftp_estimate_w if profile else None
        except Exception:
            return None

    def _get_max_hr_from_profile(self) -> Optional[int]:
        """Return max_hr_estimate from whichever sport profile has the highest value."""
        try:
            from app.models.athlete_sport_profile import AthleteSportProfile
            rows = (
                self.db.query(AthleteSportProfile.max_hr_estimate)
                .filter(
                    AthleteSportProfile.athlete_id == self.athlete_id,
                    AthleteSportProfile.max_hr_estimate.isnot(None),
                )
                .all()
            )
            vals = [r.max_hr_estimate for r in rows if r.max_hr_estimate]
            return max(vals) if vals else None
        except Exception:
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
        # Determine sport_group for profile lookup
        sport_group = None
        for grp, types in [
            ("ride", {"Ride", "VirtualRide", "MountainBikeRide", "GravelRide", "EBikeRide"}),
            ("run",  {"Run", "VirtualRun", "TrailRun"}),
            ("swim", {"Swim", "OpenWaterSwim"}),
        ]:
            if sport in types or (row.activity_type or "") in types:
                sport_group = grp
                break

        athlete_baseline: dict = {}
        if sport_group:
            try:
                from app.models.athlete_sport_profile import AthleteSportProfile
                profile = (
                    self.db.query(AthleteSportProfile)
                    .filter_by(athlete_id=self.athlete_id, sport_group=sport_group)
                    .first()
                )
                if profile:
                    athlete_baseline = {
                        "your_typical_cadence_rpm":      profile.typical_cadence_rpm,
                        "your_indoor_cadence_rpm":       profile.indoor_cadence_rpm,
                        "your_outdoor_cadence_rpm":      profile.outdoor_cadence_rpm,
                        "your_ftp_estimate_w":           profile.ftp_estimate_w,
                        "your_ftp_confidence":           profile.ftp_confidence,
                        "your_max_hr_estimate":          profile.max_hr_estimate,
                        "your_weekly_volume_km":         profile.weekly_volume_km,
                        "your_typical_speed_kmh":        profile.typical_endurance_speed_kmh,
                        "your_current_limiters":         profile.current_limiters,
                    }
            except Exception:
                pass

        metrics = {
            "sport": sport,
            "indoor": is_indoor,
            "duration_min": round(row.moving_time_s / 60, 1) if row.moving_time_s else None,
            "distance_km": round(row.distance_m / 1000, 2) if row.distance_m else None,
            "elevation_m": row.elevation_m,
            # This session
            "this_session_cadence_rpm": row.avg_cadence,
            "max_cadence": row.max_cadence,
            "cadence_benchmark_rpm": target_rpm,   # sport benchmark, not personal target
            "cadence_quality": cadence_quality,
            "avg_hr": row.avg_hr,
            "max_hr": row.max_hr,
            "hr_response": hr_response,
            "avg_watts": row.avg_watts,
            "weighted_avg_watts": row.weighted_avg_watts,
            "intensity_factor": intensity_factor,
            "effort_level": effort_level,
            "suffer_score": row.suffer_score,
            # Athlete's personal baseline — use this to contextualise gaps
            "athlete_baseline": athlete_baseline or "no profile data yet",
            # Athlete demographics — use for age-appropriate HR context and power-to-weight
            "athlete_demographics": self._get_athlete_demographics() or "not available",
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

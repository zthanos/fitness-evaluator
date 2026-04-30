"""SportProfileBuilder — computes and persists per-sport performance profiles.

Produces one AthleteSportProfile row per sport group (ride | run | swim | strength).
Called after new activities sync, or on demand.

FTP estimation tiers (cycling only, no streams required):
  high   — best weighted_avg_watts from 55-65 min rides (≈ 60-min FTP directly)
  medium — best weighted_avg_watts from 45-90 min rides × 0.95
  low    — best weighted_avg_watts from any ride ≥ 20 min × 0.90

HR zones are athlete-relative: computed as % of max_hr_estimate from actual data.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.strava_activity import StravaActivity
from app.models.athlete_sport_profile import AthleteSportProfile

logger = logging.getLogger(__name__)

_SPORT_GROUPS: dict[str, set[str]] = {
    "ride":     {"Ride", "VirtualRide", "MountainBikeRide", "GravelRide", "EBikeRide"},
    "run":      {"Run", "VirtualRun", "TrailRun"},
    "swim":     {"Swim", "OpenWaterSwim"},
    "strength": {"WeightTraining", "Crossfit", "Yoga", "Pilates", "Workout"},
}

# Minimum gradient (m/km) to classify a ride segment as "climbing"
_CLIMBING_GRADIENT_THRESHOLD = 10.0

# HR zone percentages relative to max HR
_HR_ZONE_PCTS = [
    ("Z1", 0.00, 0.60, "Recovery"),
    ("Z2", 0.60, 0.70, "Aerobic base"),
    ("Z3", 0.70, 0.80, "Tempo"),
    ("Z4", 0.80, 0.90, "Threshold"),
    ("Z5", 0.90, 1.00, "VO2max"),
]


class SportProfileBuilder:

    def __init__(self, db: Session, athlete_id: int):
        self.db = db
        self.athlete_id = athlete_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_all(self) -> list[AthleteSportProfile]:
        """Compute and upsert profiles for every sport group with data."""
        profiles = []
        for sport_group, sport_types in _SPORT_GROUPS.items():
            activities = self._get_activities(sport_types)
            if not activities:
                continue
            profile = self._build_profile(sport_group, activities)
            self._upsert(profile)
            profiles.append(profile)
        self.db.commit()
        logger.info(
            "SportProfileBuilder: upserted %d profiles for athlete %d",
            len(profiles), self.athlete_id,
        )
        return profiles

    def build_sport(self, sport_group: str) -> Optional[AthleteSportProfile]:
        """Compute and upsert profile for a single sport group."""
        sport_types = _SPORT_GROUPS.get(sport_group)
        if not sport_types:
            raise ValueError(f"Unknown sport_group: {sport_group!r}")
        activities = self._get_activities(sport_types)
        if not activities:
            return None
        profile = self._build_profile(sport_group, activities)
        self._upsert(profile)
        self.db.commit()
        return profile

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _build_profile(self, sport_group: str, activities: list) -> AthleteSportProfile:
        now = datetime.utcnow()

        distances_km = [
            a.distance_m / 1000 for a in activities if a.distance_m
        ]
        durations_min = [
            a.moving_time_s / 60 for a in activities if a.moving_time_s
        ]

        # ── Distance & speed ────────────────────────────────────────────
        longest_km = max(distances_km) if distances_km else None

        best_60, best_120 = self._best_duration_distance(activities, 50, 70), \
                             self._best_duration_distance(activities, 100, 140)

        speeds_kmh = self._activity_speeds(activities, min_duration_min=20)
        typical_speed = statistics.median(speeds_kmh) if len(speeds_kmh) >= 3 else (
            speeds_kmh[0] if speeds_kmh else None
        )
        long_speeds = self._activity_speeds(activities, min_duration_min=60)
        best_long_speed = max(long_speeds) if long_speeds else None

        # ── Weekly volume (last 28 days) ─────────────────────────────────
        weekly_km, weekly_min = self._weekly_averages(activities, weeks=4)

        # ── Cadence ─────────────────────────────────────────────────────
        typical_cad  = self._median_cadence(activities)
        indoor_cad   = self._median_cadence([a for a in activities if a.trainer])
        outdoor_cad  = self._median_cadence([a for a in activities if not a.trainer])
        climbing_cad = self._climbing_cadence(activities)

        # ── Power (cycling) ─────────────────────────────────────────────
        ftp_w, ftp_conf = (self._estimate_ftp(activities)
                           if sport_group == "ride" else (None, None))
        baseline_w = self._median_power(activities)
        best_power = self._best_weighted_power(activities)

        # ── Heart rate ──────────────────────────────────────────────────
        max_hr = self._estimate_max_hr(activities)
        hr_zones = self._build_hr_zone_model(max_hr) if max_hr else None

        # ── Running extras (HR-classified pace + distances) ──────────────
        running_extras = None
        if sport_group == "run":
            running_extras = self._running_extras(activities, max_hr)
            if running_extras.get("easy_speed_kmh"):
                typical_speed = running_extras["easy_speed_kmh"]
            if running_extras.get("longest_run_km"):
                longest_km = running_extras["longest_run_km"]

        # ── Pace zones (running) ────────────────────────────────────────
        pace_zones = (self._build_pace_zone_model(best_60, activities, running_extras)
                      if sport_group == "run" else None)

        # ── Coaching insights ────────────────────────────────────────────
        strengths, limiters = self._derive_insights(
            sport_group, longest_km, typical_speed, ftp_w, typical_cad, weekly_km,
            running_extras=running_extras,
        )

        confidence = self._profile_confidence(
            activities, ftp_w, max_hr, typical_cad
        )

        summary = self._build_summary(
            sport_group, longest_km, typical_speed, ftp_w, ftp_conf,
            weekly_km, max_hr, confidence
        )

        return AthleteSportProfile(
            athlete_id=self.athlete_id,
            sport_group=sport_group,
            longest_distance_km=_r(longest_km),
            best_60min_distance_km=_r(best_60),
            best_120min_distance_km=_r(best_120),
            typical_endurance_speed_kmh=_r(typical_speed, 2),
            best_long_speed_kmh=_r(best_long_speed, 2),
            weekly_volume_km=_r(weekly_km, 1),
            weekly_training_time_min=_r(weekly_min, 0),
            typical_cadence_rpm=_r(typical_cad, 1),
            indoor_cadence_rpm=_r(indoor_cad, 1),
            outdoor_cadence_rpm=_r(outdoor_cad, 1),
            climbing_cadence_rpm=_r(climbing_cad, 1),
            ftp_estimate_w=_r(ftp_w, 1),
            ftp_confidence=ftp_conf,
            avg_power_baseline_w=_r(baseline_w, 1),
            best_weighted_power_w=_r(best_power, 1),
            max_hr_estimate=int(max_hr) if max_hr else None,
            hr_zone_model=hr_zones,
            pace_zone_model=pace_zones,
            current_strengths=strengths,
            current_limiters=limiters,
            profile_confidence=_r(confidence, 2),
            last_updated_at=now,
            summary_text=summary,
        )

    # ------------------------------------------------------------------
    # Distance & speed helpers
    # ------------------------------------------------------------------

    def _best_duration_distance(
        self, activities: list, min_min: float, max_min: float
    ) -> Optional[float]:
        """
        Estimate the best distance achievable at target_min (midpoint of range).

        Accepts any activity >= min_min and extrapolates to the target duration
        using average pace.  No upper cap — a 2-hour run contributes a valid
        60-min projection; previously the hard max_min=70 dropped all of them.
        """
        target_min = (min_min + max_min) / 2.0
        candidates = []
        for a in activities:
            if not a.distance_m or not a.moving_time_s:
                continue
            dur_min = a.moving_time_s / 60.0
            if dur_min < min_min:
                continue
            dist_km = a.distance_m / 1000.0
            # project distance to target duration via average pace
            candidates.append(dist_km * (target_min / dur_min))
        return max(candidates) if candidates else None

    def _activity_speeds(
        self, activities: list, min_duration_min: float = 0
    ) -> list[float]:
        speeds = []
        for a in activities:
            if a.distance_m and a.moving_time_s and a.moving_time_s / 60 >= min_duration_min:
                speeds.append((a.distance_m / 1000) / (a.moving_time_s / 3600))
        return speeds

    # ------------------------------------------------------------------
    # Volume helpers
    # ------------------------------------------------------------------

    def _weekly_averages(
        self, activities: list, weeks: int
    ) -> tuple[Optional[float], Optional[float]]:
        from datetime import timezone as _tz
        now = datetime.now(_tz.utc)
        cutoff = now - timedelta(weeks=weeks)
        recent = []
        active_week_indices: set[int] = set()
        for a in activities:
            sd = a.start_date
            if sd is None:
                continue
            if sd.tzinfo is None:
                sd = sd.replace(tzinfo=_tz.utc)
            if sd >= cutoff:
                recent.append(a)
                # bucket by which week ago (0 = this week, 1 = last week, …)
                days_ago = (now - sd).days
                active_week_indices.add(days_ago // 7)
        if not recent:
            return None, None
        active_weeks = len(active_week_indices)  # 1–weeks (weeks that had ≥1 activity)
        total_km  = sum(a.distance_m / 1000 for a in recent if a.distance_m)
        total_min = sum(a.moving_time_s / 60 for a in recent if a.moving_time_s)
        return total_km / active_weeks, total_min / active_weeks

    # ------------------------------------------------------------------
    # Running HR-classification helpers
    # ------------------------------------------------------------------

    def _running_extras(
        self, activities: list, max_hr: Optional[int]
    ) -> dict:
        """Classify runs by HR to derive physiologically meaningful pace metrics."""
        easy_speeds: list[float] = []
        all_distances: list[float] = []
        all_hr_pcts: list[float] = []

        for a in activities:
            if not a.distance_m or not a.moving_time_s:
                continue
            if a.moving_time_s / 60.0 < 15:
                continue
            speed_kmh = (a.distance_m / 1000.0) / (a.moving_time_s / 3600.0)
            all_distances.append(a.distance_m / 1000.0)

            if max_hr and a.avg_hr:
                hr_pct = a.avg_hr / max_hr
                all_hr_pcts.append(hr_pct)
                if hr_pct < 0.75:
                    easy_speeds.append(speed_kmh)
            else:
                easy_speeds.append(speed_kmh)

        easy_speed = statistics.median(easy_speeds) if easy_speeds else None
        # threshold is faster than easy: easy_pace × 0.85 → threshold_speed = easy_speed / 0.85
        threshold_speed = (easy_speed / 0.85) if easy_speed else None

        # Median cardiac load across all runs — key indicator for pace-HR mismatch
        median_hr_pct = statistics.median(all_hr_pcts) if all_hr_pcts else None

        typical_run = (
            statistics.median(all_distances) if len(all_distances) >= 2
            else (all_distances[0] if all_distances else None)
        )
        longest_run = max(all_distances) if all_distances else None
        hr_classified = bool(max_hr and any(a.avg_hr for a in activities))

        return {
            "easy_speed_kmh":      easy_speed,
            "threshold_speed_kmh": threshold_speed,
            "median_hr_pct":       median_hr_pct,
            "typical_run_km":      typical_run,
            "longest_run_km":      longest_run,
            "hr_classified":       hr_classified,
        }

    # ------------------------------------------------------------------
    # Cadence helpers
    # ------------------------------------------------------------------

    def _median_cadence(self, activities: list) -> Optional[float]:
        vals = [a.avg_cadence for a in activities if a.avg_cadence and a.avg_cadence > 0]
        return statistics.median(vals) if vals else None

    def _climbing_cadence(self, activities: list) -> Optional[float]:
        """Median cadence of activities with elevation gradient ≥ threshold."""
        climbing = [
            a for a in activities
            if a.avg_cadence and a.elevation_m and a.distance_m and a.distance_m > 0
            and (a.elevation_m / (a.distance_m / 1000)) >= _CLIMBING_GRADIENT_THRESHOLD
        ]
        return self._median_cadence(climbing)

    # ------------------------------------------------------------------
    # Power & FTP helpers
    # ------------------------------------------------------------------

    def _estimate_ftp(
        self, activities: list
    ) -> tuple[Optional[float], Optional[str]]:
        powered = [a for a in activities if a.weighted_avg_watts and a.moving_time_s]

        # Tier 1 — 55–65 min rides: weighted_avg_watts ≈ FTP directly
        t1 = [a.weighted_avg_watts for a in powered
              if 55 * 60 <= a.moving_time_s <= 65 * 60]
        if t1:
            return max(t1), "high"

        # Tier 2 — 17–23 min: FTP ≈ best power × 0.95 (classic 20-min test)
        t2 = [a.weighted_avg_watts for a in powered
              if 17 * 60 <= a.moving_time_s <= 23 * 60]
        if t2:
            return max(t2) * 0.95, "high"

        # Tier 3 — 45–90 min: reasonable proxy × 0.95
        t3 = [a.weighted_avg_watts for a in powered
              if 45 * 60 <= a.moving_time_s <= 90 * 60]
        if t3:
            return max(t3) * 0.95, "medium"

        # Tier 4 — any ride ≥ 20 min: weak proxy × 0.90
        t4 = [a.weighted_avg_watts for a in powered
              if a.moving_time_s >= 20 * 60]
        if t4:
            return max(t4) * 0.90, "low"

        return None, None

    def _median_power(self, activities: list) -> Optional[float]:
        vals = [a.weighted_avg_watts for a in activities
                if a.weighted_avg_watts and a.weighted_avg_watts > 0]
        return statistics.median(vals) if vals else None

    def _best_weighted_power(self, activities: list) -> Optional[float]:
        vals = [a.weighted_avg_watts for a in activities if a.weighted_avg_watts]
        return max(vals) if vals else None

    # ------------------------------------------------------------------
    # Heart rate helpers
    # ------------------------------------------------------------------

    def _estimate_max_hr(self, activities: list) -> Optional[int]:
        """Best estimate: max of recorded max_hr across last 90 days."""
        cutoff = datetime.utcnow() - timedelta(days=90)
        recent = [a for a in activities
                  if a.max_hr and a.start_date and a.start_date >= cutoff]
        if recent:
            return max(a.max_hr for a in recent)
        # Fall back to all-time max_hr
        all_max = [a.max_hr for a in activities if a.max_hr]
        return max(all_max) if all_max else None

    def _build_hr_zone_model(self, max_hr: int) -> dict:
        zones = {}
        for name, pct_min, pct_max, label in _HR_ZONE_PCTS:
            zones[name] = {
                "label":   label,
                "min_bpm": round(max_hr * pct_min),
                "max_bpm": round(max_hr * pct_max),
                "pct_min": pct_min,
                "pct_max": pct_max,
            }
        return {"max_hr": max_hr, "zones": zones}

    # ------------------------------------------------------------------
    # Pace zone helpers (running)
    # ------------------------------------------------------------------

    def _build_pace_zone_model(
        self, threshold_km: Optional[float], activities: list,
        running_extras: Optional[dict] = None,
    ) -> Optional[dict]:
        """Build running pace zones, preferring HR-derived threshold when available."""
        # Prefer HR-classified threshold speed; fall back to best-60-min projection
        if running_extras and running_extras.get("threshold_speed_kmh"):
            threshold_kmh = running_extras["threshold_speed_kmh"]
        elif threshold_km:
            threshold_kmh = threshold_km
        else:
            return None

        zones = {
            "Z1": {"label": "Recovery",  "pct_of_threshold": (0.0,  0.70)},
            "Z2": {"label": "Easy",      "pct_of_threshold": (0.70, 0.80)},
            "Z3": {"label": "Tempo",     "pct_of_threshold": (0.80, 0.90)},
            "Z4": {"label": "Threshold", "pct_of_threshold": (0.90, 1.00)},
            "Z5": {"label": "VO2max",    "pct_of_threshold": (1.00, 1.15)},
        }
        result: dict = {"threshold_kmh": round(threshold_kmh, 2), "zones": {}}
        for name, meta in zones.items():
            lo_pct, hi_pct = meta["pct_of_threshold"]
            lo_kmh = threshold_kmh * lo_pct
            hi_kmh = threshold_kmh * hi_pct
            lo_pace = (60 / hi_kmh) if hi_kmh else None
            hi_pace = (60 / lo_kmh) if lo_kmh else None
            result["zones"][name] = {
                "label":         meta["label"],
                "min_kmh":       round(lo_kmh, 2),
                "max_kmh":       round(hi_kmh, 2),
                "fast_pace_min_per_km": round(lo_pace, 2) if lo_pace else None,
                "slow_pace_min_per_km": round(hi_pace, 2) if hi_pace else None,
            }

        # Embed running extras so profile_to_dict can surface them without extra queries
        if running_extras:
            easy_spd = running_extras.get("easy_speed_kmh")
            result["easy_speed_kmh"]            = round(easy_spd, 2) if easy_spd else None
            result["easy_pace_min_per_km"]      = round(60 / easy_spd, 2) if easy_spd else None
            result["threshold_pace_min_per_km"] = round(60 / threshold_kmh, 2)
            result["typical_run_km"]            = running_extras.get("typical_run_km")
            result["longest_run_km"]            = running_extras.get("longest_run_km")
            result["hr_classified"]             = running_extras.get("hr_classified", False)
            mhr = running_extras.get("median_hr_pct")
            result["median_hr_pct"]             = round(mhr, 3) if mhr else None

        return result

    # ------------------------------------------------------------------
    # Coaching insights
    # ------------------------------------------------------------------

    def _derive_insights(
        self,
        sport_group: str,
        longest_km: Optional[float],
        typical_speed: Optional[float],
        ftp_w: Optional[float],
        typical_cadence: Optional[float],
        weekly_km: Optional[float],
        running_extras: Optional[dict] = None,
    ) -> tuple[list[str], list[str]]:
        strengths, limiters = [], []

        if sport_group == "ride":
            if longest_km and longest_km >= 100:
                strengths.append(f"Century endurance ({longest_km:.0f} km longest ride)")
            elif longest_km and longest_km >= 60:
                strengths.append(f"Solid ride endurance ({longest_km:.0f} km best)")
            if ftp_w and ftp_w >= 250:
                strengths.append(f"Strong FTP (~{ftp_w:.0f} W) → good sustainable power base")
            elif ftp_w and ftp_w < 180:
                limiters.append(
                    f"Low FTP (~{ftp_w:.0f} W) → limits sustainable power output"
                    " → reduces average speed on longer efforts"
                )
            if typical_cadence and typical_cadence >= 88:
                strengths.append(f"Good cadence efficiency ({typical_cadence:.0f} rpm)")
            elif typical_cadence and typical_cadence < 75:
                limiters.append(
                    f"Low cadence ({typical_cadence:.0f} rpm) → increases muscular fatigue"
                    " → reduces sustainable speed on climbs"
                )

        elif sport_group == "run":
            rx = running_extras or {}
            median_hr_pct = rx.get("median_hr_pct")  # cardiac load at typical pace

            # ── Distance: completion range, not arbitrary race labels ──────
            if longest_km and longest_km >= 21:
                strengths.append(f"Solid endurance (runs up to {longest_km:.0f} km)")
            elif longest_km and longest_km >= 10:
                strengths.append(f"Solid endurance (up to {longest_km:.0f} km)")
            elif longest_km and longest_km >= 5:
                strengths.append(f"Building endurance ({longest_km:.0f} km longest run)")

            # ── Race readiness: separate from completion capability ────────
            # Can cover the distance but pace too slow to race it
            if longest_km and longest_km >= 10 and typical_speed and typical_speed < 7.5:
                easy_pace = 60 / typical_speed
                limiters.append(
                    f"Can complete 10k but race readiness is low (easy pace ~{easy_pace:.1f} min/km)"
                    " → aerobic base needs development before targeting race times"
                )

            # ── Pace-HR mismatch (aerobic efficiency) ─────────────────────
            elif typical_speed and typical_speed < 8:
                easy_pace = 60 / typical_speed
                if median_hr_pct and median_hr_pct > 0.70:
                    limiters.append(
                        f"Easy pace (~{easy_pace:.1f} min/km) at ~{median_hr_pct:.0%} max HR"
                        " → pace-HR mismatch indicates low aerobic efficiency"
                        " → limits ability to sustain faster race pace"
                    )
                else:
                    limiters.append(
                        f"Easy pace building (~{easy_pace:.1f} min/km)"
                        " → aerobic base developing → add Z2 runs to build efficiency"
                    )
            elif typical_speed and typical_speed >= 10:
                easy_pace = 60 / typical_speed
                strengths.append(f"Good aerobic base (easy pace ~{easy_pace:.1f} min/km)")

        # ── Volume ────────────────────────────────────────────────────────
        if sport_group == "ride" and weekly_km is not None:
            if weekly_km < 20:
                limiters.append(
                    f"Low weekly volume ({weekly_km:.0f} km/wk) → insufficient aerobic stimulus"
                    " → slows fitness progression"
                )
            elif weekly_km >= 60:
                strengths.append(f"High weekly training volume ({weekly_km:.0f} km/week)")

        elif sport_group == "run" and weekly_km is not None and weekly_km < 15:
            limiters.append(
                f"Low weekly volume (~{weekly_km:.0f} km/wk) → insufficient aerobic stimulus"
                " → slows pace progression"
            )

        return strengths, limiters

    def _profile_confidence(
        self,
        activities: list,
        ftp_w: Optional[float],
        max_hr: Optional[int],
        typical_cadence: Optional[float],
    ) -> float:
        score = 0.0
        n = len(activities)
        score += min(n / 20, 1.0) * 0.4        # data volume (40%)
        score += (0.2 if ftp_w else 0.0)        # power data (20%)
        score += (0.2 if max_hr else 0.0)       # HR data (20%)
        score += (0.2 if typical_cadence else 0.0)  # cadence data (20%)
        return round(score, 2)

    def _build_summary(
        self,
        sport_group: str,
        longest_km: Optional[float],
        typical_speed: Optional[float],
        ftp_w: Optional[float],
        ftp_conf: Optional[str],
        weekly_km: Optional[float],
        max_hr: Optional[int],
        confidence: float,
    ) -> str:
        parts = [f"{sport_group.title()} profile (confidence {confidence:.0%}):"]
        if longest_km:
            parts.append(f"longest {longest_km:.1f} km")
        if typical_speed:
            parts.append(f"typical speed {typical_speed:.1f} km/h")
        if ftp_w:
            parts.append(f"FTP ~{ftp_w:.0f} W ({ftp_conf})")
        if weekly_km:
            parts.append(f"weekly volume {weekly_km:.0f} km")
        if max_hr:
            parts.append(f"max HR {max_hr} bpm")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _get_activities(self, sport_types: set[str]) -> list:
        return (
            self.db.query(StravaActivity)
            .filter(
                StravaActivity.athlete_id == self.athlete_id,
                StravaActivity.sport_type.in_(sport_types)
                | StravaActivity.activity_type.in_(sport_types),
            )
            .order_by(StravaActivity.start_date.desc())
            .all()
        )

    def _upsert(self, profile: AthleteSportProfile) -> None:
        existing = (
            self.db.query(AthleteSportProfile)
            .filter_by(athlete_id=self.athlete_id, sport_group=profile.sport_group)
            .first()
        )
        if existing:
            for col in AthleteSportProfile.__table__.columns:
                if col.name not in ("id", "athlete_id", "sport_group"):
                    setattr(existing, col.name, getattr(profile, col.name))
        else:
            self.db.add(profile)


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _r(val: Optional[float], decimals: int = 1) -> Optional[float]:
    """Round to N decimals, or return None."""
    return round(val, decimals) if val is not None else None


# ------------------------------------------------------------------
# Shared API helpers (imported by settings.py and dashboard.py)
# ------------------------------------------------------------------

def profile_to_dict(p: "AthleteSportProfile") -> dict:
    d = {
        "sport_group": p.sport_group,
        "profile_confidence": p.profile_confidence,
        "last_updated_at": p.last_updated_at.isoformat() if p.last_updated_at else None,
        "summary_text": p.summary_text,
        "weekly_volume_km": p.weekly_volume_km,
        "weekly_training_time_min": p.weekly_training_time_min,
        "longest_distance_km": p.longest_distance_km,
        "best_60min_distance_km": p.best_60min_distance_km,
        "best_120min_distance_km": p.best_120min_distance_km,
        "typical_endurance_speed_kmh": p.typical_endurance_speed_kmh,
        "best_long_speed_kmh": p.best_long_speed_kmh,
        "typical_cadence_rpm": p.typical_cadence_rpm,
        "indoor_cadence_rpm": p.indoor_cadence_rpm,
        "outdoor_cadence_rpm": p.outdoor_cadence_rpm,
        "climbing_cadence_rpm": p.climbing_cadence_rpm,
        "ftp_estimate_w": p.ftp_estimate_w,
        "ftp_confidence": p.ftp_confidence,
        "avg_power_baseline_w": p.avg_power_baseline_w,
        "max_hr_estimate": p.max_hr_estimate,
        "hr_zone_model": p.hr_zone_model,
        "pace_zone_model": p.pace_zone_model,
        "current_strengths": p.current_strengths or [],
        "current_limiters": p.current_limiters or [],
    }

    # Running-specific fields extracted from pace_zone_model JSON
    if p.sport_group == "run" and p.pace_zone_model:
        pz = p.pace_zone_model
        d["easy_pace_min_per_km"]       = pz.get("easy_pace_min_per_km")
        d["threshold_pace_min_per_km"]  = pz.get("threshold_pace_min_per_km")
        d["typical_run_km"]             = pz.get("typical_run_km")
        d["longest_run_km"]             = pz.get("longest_run_km")
        d["hr_classified"]              = pz.get("hr_classified", False)
        d["median_hr_pct"]              = pz.get("median_hr_pct")
    else:
        d["easy_pace_min_per_km"]       = None
        d["threshold_pace_min_per_km"]  = None
        d["typical_run_km"]             = None
        d["longest_run_km"]             = None
        d["hr_classified"]              = False
        d["median_hr_pct"]              = None

    d["next_focus"] = compute_next_focus(p.sport_group, d)
    return d


def compute_next_focus(sport_group: str, d: dict) -> Optional[str]:
    """Derive a 1–2 sentence 'next focus' action from the top limiter."""
    limiters = d.get("current_limiters") or []
    if not limiters:
        if sport_group == "ride" and (d.get("ftp_estimate_w") or 0) >= 200:
            return (
                "Maintain FTP with 1× weekly threshold session. "
                "Gradually extend long-ride duration to build aerobic ceiling."
            )
        return None
    top = limiters[0].lower()
    if "cadence" in top:
        return (
            "Add cadence drills: target 80–90 rpm on flat segments. "
            "Spin at 90+ rpm for 5-min blocks during easy rides to build neuromuscular efficiency."
        )
    if "ftp" in top or "power" in top:
        return (
            "Add 2× weekly threshold blocks (15–20 min at FTP effort). "
            "Pair with one longer endurance ride per week to translate power into sustained speed."
        )
    if "volume" in top:
        if sport_group == "ride":
            return (
                "Add one extra ride per week — start with 45–60 min easy effort. "
                "Consistent volume is the fastest route to aerobic improvement."
            )
        if sport_group == "run":
            current_vol = d.get("weekly_volume_km") or 0
            target_lo = max(12, round((current_vol * 1.7) / 5) * 5)
            target_hi = target_lo + 5
            return (
                f"Add 2 runs/week: one easy Z2 run (45–60 min) and one longer run (60–75 min). "
                f"Target: increase weekly volume to ~{target_lo}–{target_hi} km."
            )
    if "race readiness" in top or "mismatch" in top or "efficiency" in top:
        return (
            "Add 2 runs/week: one easy Z2 run (45–60 min) and one longer run (60–75 min). "
            "Run easy enough to hold a conversation — this is how aerobic efficiency is built."
        )
    if "pace" in top or "aerobic" in top or "building" in top:
        return (
            "Build aerobic base: 1–2 easy Z2 runs per week (45–60 min each). "
            "Keep HR below 75% max — pace will improve naturally as the engine develops."
        )
    return None


def compute_dominant_sport(profiles: list[dict]) -> dict:
    """Return primary and secondary sport from a list of profile dicts."""
    if not profiles:
        return {"primary": None, "secondary": None}

    def _score(p: dict) -> float:
        conf = p.get("profile_confidence") or 0.0
        time = p.get("weekly_training_time_min") or 0.0
        return conf * max(time, 1.0)

    ranked = sorted(profiles, key=_score, reverse=True)
    return {
        "primary":   ranked[0]["sport_group"] if ranked else None,
        "secondary": ranked[1]["sport_group"] if len(ranked) > 1 else None,
    }

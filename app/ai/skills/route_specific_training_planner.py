"""RouteSpecificTrainingPlanner — generates a training plan tailored to a target route.

Key design principle: the plan prepares the athlete FOR the route, not ON the route.
Training sessions are general (gym, road, track, local paths) but their demands
(distance, elevation, intensity, intervals) are calibrated to what the route requires.

Pipeline:
  RouteProfile + AthleteSportProfile
    → PerformanceEstimator (simple physics: estimates current finish time)
    → build LLM context (route demands vs athlete gaps)
    → LLM generates phased plan (base → specific prep → taper)
    → persist TrainingPlan with route_profile_id link

Phase structure:
  BASE      (~60% of weeks): fix limiters, build volume toward route distance
  SPECIFIC  (~30% of weeks): route-demand sessions (hill repeats at critical gradient,
                              long sessions at route distance, tempo at target pace)
  TAPER     (~10%, min 1wk): drop volume 40-50%, keep 1-2 race-pace sessions
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.skills.training_planner import TrainingPlanner, TrainingPlannerOutput

logger = logging.getLogger(__name__)

# Goal type descriptions surfaced to the LLM
_GOAL_DESCRIPTIONS = {
    "finish":           "Complete the route comfortably — prioritise endurance and pacing strategy",
    "target_time":      "Hit a specific finish time — prioritise speed + sustained power/pace",
    "improve_climbing": "Improve performance on the climbs — prioritise gradient-specific strength and cadence",
    "improve_pace":     "Improve average speed/pace across the full route — prioritise aerobic base and tempo work",
}

_ROUTE_SYSTEM_PROMPT = """\
You are an elite endurance coach generating a ROUTE-SPECIFIC training plan.

CORE PRINCIPLE: The plan prepares the athlete FOR the route, NOT on the route.
Sessions are performed locally (roads, gym, track, trainer) but their demands
exactly replicate what the target route requires.

You will receive a JSON context with:
- route: GPX analysis — distance, elevation, gradient, critical sections
- athlete: sport profile — FTP, cadence, pace, volume, limiters
- athlete_vs_route: structured gap analysis — WHICH dimensions are limited and WHY
- training_prescription: MANDATORY training blocks derived from gap analysis —
  you MUST implement these in the correct phases
- performance_estimate: current finish time estimate at current fitness
- plan_spec: phase structure (base/specific/taper weeks)

MANDATORY: Use training_prescription as the PRIMARY INPUT for session design.
Each block in training_prescription.base, .specific must appear as sessions.
Do NOT ignore "CRITICAL" or "HIGH" priority blocks.

Generate a JSON plan with this EXACT schema:
{
  "title": "route name + goal in ≤50 chars",
  "sport": "cycling" | "running",
  "duration_weeks": <int>,
  "performance_target": {
    "label": "one sentence — the measurable outcome (e.g. 'Sustain 155W for 2.5h at 75+ rpm')",
    "metrics": ["sustain ~155W for 2.5h", "maintain cadence >75 rpm", "complete without stopping"]
  },
  "plan_rationale": {
    "why_it_works": "2-3 sentence explanation connecting the plan structure to the route demands and athlete gaps",
    "strategy": ["increase weekly volume", "improve climbing cadence", "build sustained FTP output"]
  },
  "weeks": [
    {
      "week_number": <int>,
      "phase": "base" | "specific" | "taper",
      "focus": "one sentence — reference BOTH the route demand being trained AND the physiological target",
      "volume_target_hours": <float>,
      "distance_target_km": <float or null — target km for long session this week, progressing toward route distance>,
      "sessions": [
        {
          "day_of_week": <1–7, 1=Monday>,
          "session_type": <see valid types below>,
          "duration_minutes": <int>,
          "intensity": <recovery|easy|moderate|hard|max>,
          "description": "instruction with numbers AND a '→ route connection' suffix explaining WHY this trains for the route"
        }
      ]
    }
  ]
}

PHASE RULES:
• BASE (first 60% of weeks): Implement training_prescription.base blocks. Fix CRITICAL
  limiters. Build volume using weekly_distance_targets progression. Volume ≤10%/week.
• SPECIFIC (middle 30%): Implement training_prescription.specific blocks. Include route-
  demand sessions: hill repeats at route gradient, long sessions at peak distance,
  tempo at target power/pace. Reference training_prescription.key_metrics for targets.
• TAPER (last 10%, min 1 week): Volume drops 40–50%. Keep 1–2 quality sessions at
  race-day intensity. Follow training_prescription.taper rules.

DISTANCE PROGRESSION (use training_prescription.weekly_distance_targets):
• Distance_target_km must increase week-over-week in BASE.
• Peak in late SPECIFIC at weekly_distance_targets.long_session_peak_km.
• TAPER: reduce to ~60% of peak.

GAP-TO-SESSION MAPPING (enforce these regardless of other constraints):
• endurance = limited → at least 1 progressive long session per week in BASE
• climbing = limited → at least 2 hill interval sessions per week in SPECIFIC
• climbing cadence noted → every interval/tempo description must include cadence target
• speed = limited (cycling) → 1 threshold/FTP interval session per week in SPECIFIC
• speed = limited (running) → 1 tempo run per week in SPECIFIC
• All "CRITICAL" priority blocks must appear in EVERY week of their phase.

DESCRIPTION FORMAT (mandatory — every session):
Each description ends with a "→ route connection" explaining WHY this trains for the route:
  "6×3min at FTP (159W), cadence >72 rpm, 3min recovery → replicates muscular demand of 5–8% climbs on route"
  "Long ride 55 km at Z2 (65-70% HR) → builds endurance capacity for the 70 km route effort"
  "Hill repeats 8×90s uphill → develops climbing strength for the rolling terrain sections"
  "Tempo 2×20min at 88% FTP → raises sustained power ceiling for the route's long flat sections"

NEVER DO:
• Never write "ride/run the target route" as a session.
• Never generate generic base plans disconnected from the gap analysis.
• Sessions must be reproducible anywhere — local roads, park, gym, track, indoor trainer.
• Never ignore a CRITICAL priority block from training_prescription.

Valid session_types:
  easy_run tempo_run interval long_run recovery_run
  easy_ride tempo_ride interval_ride long_ride
  swim_technique swim_endurance swim_interval
  rest cross_training strength

Respond with ONLY the JSON — no markdown, no explanation.\
"""


@dataclass
class RouteSpecificPlannerInput:
    route_id: int
    event_date: date
    goal_type: str          # finish | target_time | improve_climbing | improve_pace
    duration_weeks: int = 8
    target_time_min: Optional[int] = None  # only for goal_type == "target_time"
    goal_id: Optional[str] = None


class RouteSpecificTrainingPlanner(TrainingPlanner):
    """Extends TrainingPlanner with route-aware context and phased structure."""

    async def run(self, input: RouteSpecificPlannerInput) -> TrainingPlannerOutput:  # type: ignore[override]
        # ── Load route and athlete profile ────────────────────────────────────
        route = self._load_route(input.route_id)
        sport_profile = self._load_sport_profile(route.sport)

        # ── Gap analysis (deterministic, no LLM) ─────────────────────────────
        from app.services.route_readiness import compute_readiness
        readiness = compute_readiness(route, sport_profile)

        # ── Training block mapping (gap → required session types) ─────────────
        training_blocks = _map_gaps_to_training_blocks(
            readiness, route, sport_profile, route.sport
        )

        # ── Performance estimate (simple physics) ─────────────────────────────
        perf = _estimate_finish(route, sport_profile, input.goal_type, input.target_time_min)

        # ── Build LLM context ─────────────────────────────────────────────────
        weeks_to_event = max(1, (input.event_date - date.today()).days // 7)
        actual_weeks = min(input.duration_weeks, weeks_to_event)

        context = {
            "route": {
                "name":                   route.filename,
                "sport":                  route.sport,
                "distance_km":            route.distance_km,
                "total_elevation_gain_m": route.total_elevation_gain_m,
                "max_gradient_pct":       route.max_gradient_pct,
                "avg_climb_gradient_pct": route.avg_climb_gradient_pct,
                "difficulty":             route.route_difficulty,
                "num_climbs":             len(route.climb_segments or []),
                "critical_sections":      route.critical_sections or [],
                "analysis_summary":       route.analysis_summary,
            },
            "athlete": _sport_profile_context(sport_profile),
            # Structured gap analysis — tells LLM EXACTLY what's limiting the athlete
            "athlete_vs_route": {
                "readiness": {
                    dim: {"level": v["level"], "detail": v["detail"]}
                    for dim, v in readiness["readiness"].items()
                },
                "athlete_difficulty": readiness["athlete_difficulty"],
                "gaps":               readiness["gap_summary"]["gaps"],
                "plan_focus":         readiness["gap_summary"]["plan_focus"],
                "route_demands":      readiness["route_demands"],
            },
            # Mandatory training blocks derived from gaps — LLM MUST include these
            "training_prescription": training_blocks,
            "event": {
                "date":             input.event_date.isoformat(),
                "weeks_available":  weeks_to_event,
                "goal_type":        input.goal_type,
                "goal_description": _GOAL_DESCRIPTIONS.get(input.goal_type, input.goal_type),
                "target_time_min":  input.target_time_min,
            },
            "performance_estimate": perf,
            "plan_spec": {
                "duration_weeks":  actual_weeks,
                "phase_structure": _phase_weeks(actual_weeks),
            },
        }

        context_str = json.dumps(context, default=str)
        raw = await self._llm_reason(_ROUTE_SYSTEM_PROMPT, context_str, max_tokens=6000)

        plan_data = self._parse_plan(raw, actual_weeks)
        # Override sport from route profile — don't rely on LLM to map ride→cycling
        plan_data["sport"] = "cycling" if route.sport == "ride" else "running"
        plan_id = self._save_plan(plan_data, input.goal_id, route_profile_id=input.route_id)

        return TrainingPlannerOutput(
            plan_id=plan_id,
            title=plan_data.get("title", "Route Training Plan"),
            sport=plan_data.get("sport", route.sport),
            weeks=len(plan_data.get("weeks", [])),
            summary=self._summarise(plan_data),
        )

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _load_route(self, route_id: int):
        from app.models.route_profile import RouteProfile
        route = self.db.query(RouteProfile).filter_by(id=route_id, athlete_id=self.athlete_id).first()
        if not route:
            raise ValueError(f"Route profile {route_id} not found for this athlete")
        return route

    def _load_sport_profile(self, route_sport: str):
        """Map route sport (ride|run) to sport group and fetch profile dict."""
        from app.models.athlete_sport_profile import AthleteSportProfile
        from app.ai.skills.sport_profile_builder import profile_to_dict
        profile = (
            self.db.query(AthleteSportProfile)
            .filter_by(athlete_id=self.athlete_id, sport_group=route_sport)
            .first()
        )
        if not profile:
            return {}
        return profile_to_dict(profile)

    # ── Override _save_plan to attach route_profile_id ────────────────────────

    def _save_plan(self, data: dict, goal_id: Optional[str], route_profile_id: Optional[int] = None) -> str:
        from app.models.training_plan import TrainingPlan
        from app.models.training_plan_week import TrainingPlanWeek
        from app.models.training_plan_session import TrainingPlanSession
        from app.services.plan_coordinator import sport_plan_type

        today = date.today()
        duration = len(data.get("weeks", []))
        end_date = today + timedelta(weeks=max(duration, 1))

        plan_metadata = {}
        if data.get("performance_target"):
            plan_metadata["performance_target"] = data["performance_target"]
        if data.get("plan_rationale"):
            plan_metadata["plan_rationale"] = data["plan_rationale"]

        plan = TrainingPlan(
            id=str(uuid.uuid4()),
            user_id=self.athlete_id,
            title=data.get("title", "Route Training Plan")[:255],
            sport=data.get("sport", "other"),
            plan_type=sport_plan_type(data.get("sport", "other")),
            goal_id=goal_id,
            route_profile_id=route_profile_id,
            plan_metadata=plan_metadata or None,
            start_date=today,
            end_date=end_date,
            status="active",
        )
        self.db.add(plan)
        self.db.flush()

        for week_data in data.get("weeks", []):
            dist_target = week_data.get("distance_target_km")
            week = TrainingPlanWeek(
                id=str(uuid.uuid4()),
                plan_id=plan.id,
                week_number=int(week_data.get("week_number", 1)),
                phase=str(week_data.get("phase", ""))[:20] or None,
                focus=str(week_data.get("focus", ""))[:500],
                volume_target=float(week_data.get("volume_target_hours", 0)),
                distance_target_km=float(dist_target) if dist_target else None,
            )
            self.db.add(week)
            self.db.flush()

            for s in week_data.get("sessions", []):
                session = TrainingPlanSession(
                    id=str(uuid.uuid4()),
                    week_id=week.id,
                    day_of_week=s["day_of_week"],
                    session_type=s["session_type"],
                    duration_minutes=s["duration_minutes"],
                    intensity=s["intensity"],
                    description=str(s.get("description", ""))[:1000] if s.get("description") else None,
                    completed=False,
                )
                self.db.add(session)

        self.db.commit()
        return plan.id


# ── Performance estimation (pure functions) ───────────────────────────────────

def _estimate_finish(route, sport_profile: dict, goal_type: str, target_min: Optional[int]) -> dict:
    """Simple physics-based finish time estimate at current fitness level."""
    try:
        if route.sport == "run":
            return _estimate_run(route, sport_profile, goal_type)
        elif route.sport == "ride":
            return _estimate_ride(route, sport_profile, goal_type)
    except Exception as exc:
        logger.warning("Performance estimate failed: %s", exc)
    return {"estimated_finish_min": None, "estimated_finish_str": "unknown", "basis": "error"}


def _estimate_run(route, sp: dict, goal_type: str) -> dict:
    easy_pace = sp.get("easy_pace_min_per_km")
    if not easy_pace and sp.get("typical_endurance_speed_kmh"):
        easy_pace = 60 / sp["typical_endurance_speed_kmh"]
    if not easy_pace:
        return {"estimated_finish_min": None, "estimated_finish_str": "unknown", "basis": "no_pace_data"}

    # For race/target goals, use a pace 85% of easy (threshold estimate)
    race_pace = easy_pace * 0.85 if goal_type in ("target_time", "improve_pace") else easy_pace

    # Naismith's rule: +1 min per 10m elevation gain
    flat_min = route.distance_km * race_pace
    climb_penalty = (route.total_elevation_gain_m or 0) / 10.0
    total_min = flat_min + climb_penalty

    gap = _gap_assessment(goal_type, route, sp)
    return _format_estimate(total_min, "Naismith rule + current pace", gap)


def _estimate_ride(route, sp: dict, goal_type: str) -> dict:
    speed = sp.get("typical_endurance_speed_kmh")
    if not speed:
        return {"estimated_finish_min": None, "estimated_finish_str": "unknown", "basis": "no_speed_data"}

    # Gradient penalty: each 1% gradient cuts effective speed by ~2%
    all_segs = (route.climb_segments or []) + (route.descent_segments or []) + (route.flat_segments or [])
    if all_segs:
        total_min = 0.0
        for seg in all_segs:
            g = abs(seg.get("avg_gradient_pct", 0))
            eff_speed = speed * max(0.3, 1 - 0.02 * g)
            total_min += (seg["length_km"] / eff_speed) * 60
    else:
        total_min = (route.distance_km / speed) * 60

    gap = _gap_assessment(goal_type, route, sp)
    return _format_estimate(total_min, "gradient-adjusted speed from profile", gap)


def _gap_assessment(goal_type: str, route, sp: dict) -> str:
    weekly_km = sp.get("weekly_volume_km") or 0
    route_km  = route.distance_km or 0
    limiters  = sp.get("current_limiters") or []

    if weekly_km < route_km * 0.5:
        return "Volume significantly below route distance — base build is the priority"
    if goal_type == "finish" and weekly_km >= route_km * 0.7:
        return "Volume adequate for completion — focus on specificity and pacing"
    if goal_type in ("target_time", "improve_pace") and limiters:
        return f"Fix top limiter first: {limiters[0].split(' →')[0]}"
    return "Consistent training will close the gap to target"


def _format_estimate(total_min: float, basis: str, assessment: str) -> dict:
    h = int(total_min // 60)
    m = int(total_min % 60)
    return {
        "estimated_finish_min": round(total_min),
        "estimated_finish_str": f"{h}h {m:02d}min" if h else f"{m} min",
        "basis": basis,
        "assessment": assessment,
    }


# ── Context helpers ───────────────────────────────────────────────────────────

def _sport_profile_context(sp: dict) -> dict:
    return {
        "sport":                     sp.get("sport_group"),
        "weekly_volume_km":          sp.get("weekly_volume_km"),
        "weekly_training_time_min":  sp.get("weekly_training_time_min"),
        "longest_distance_km":       sp.get("longest_distance_km"),
        "current_strengths":         sp.get("current_strengths", []),
        "current_limiters":          sp.get("current_limiters", []),
        # Cycling
        "ftp_w":                     sp.get("ftp_estimate_w"),
        "ftp_confidence":            sp.get("ftp_confidence"),
        "typical_speed_kmh":         sp.get("typical_endurance_speed_kmh"),
        "typical_cadence_rpm":       sp.get("typical_cadence_rpm"),
        "outdoor_cadence_rpm":       sp.get("outdoor_cadence_rpm"),
        "climbing_cadence_rpm":      sp.get("climbing_cadence_rpm"),
        # Running
        "easy_pace_min_per_km":      sp.get("easy_pace_min_per_km"),
        "threshold_pace_min_per_km": sp.get("threshold_pace_min_per_km"),
        "typical_run_km":            sp.get("typical_run_km"),
        "longest_run_km":            sp.get("longest_run_km"),
        "median_hr_pct":             sp.get("median_hr_pct"),
        # Both
        "max_hr":                    sp.get("max_hr_estimate"),
        "profile_confidence":        sp.get("profile_confidence"),
    }


def _map_gaps_to_training_blocks(readiness: dict, route, sport_profile: dict, sport: str) -> dict:
    """
    Deterministically convert gap assessment into mandatory training block constraints.
    Injected into the LLM context so it generates truly gap-targeted sessions.
    """
    r        = readiness.get("readiness", {})
    end_lvl  = r.get("endurance", {}).get("level", "moderate")
    clmb_lvl = r.get("climbing",  {}).get("level", "moderate")
    spd_lvl  = r.get("speed",     {}).get("level", "moderate")

    dist_km       = route.distance_km or 0
    gain_m        = route.total_elevation_gain_m or 0
    gain_per_km   = gain_m / dist_km if dist_km else 0
    max_grade     = route.max_gradient_pct or 0

    ftp           = sport_profile.get("ftp_estimate_w")
    climb_cad     = sport_profile.get("climbing_cadence_rpm") or sport_profile.get("outdoor_cadence_rpm") or sport_profile.get("typical_cadence_rpm")
    longest       = sport_profile.get("longest_distance_km") or 0
    weekly_km     = sport_profile.get("weekly_volume_km") or 0
    easy_pace     = sport_profile.get("easy_pace_min_per_km")

    blocks = {"base": [], "specific": [], "taper": [], "weekly_distance_targets": [], "key_metrics": {}}

    # ── Distance progression targets ─────────────────────────────────────────
    # Start from max(current longest, 40% of route) and step toward 90% of route
    start_km = max(longest, dist_km * 0.35, weekly_km)
    end_km   = dist_km * 0.90
    blocks["weekly_distance_targets"] = {
        "long_session_start_km": round(start_km, 0),
        "long_session_peak_km":  round(end_km, 0),
        "note": f"Long session must progress from {start_km:.0f} km to {end_km:.0f} km across BASE/SPECIFIC phases"
    }

    if sport == "ride":
        # ── BASE blocks ──────────────────────────────────────────────────────
        if end_lvl == "limited":
            blocks["base"].append({
                "priority": "CRITICAL",
                "problem": f"Longest ride {longest:.0f} km vs {dist_km:.0f} km route",
                "session_type": "long_ride",
                "sessions_per_week": 1,
                "rule": f"Increase long ride by 15% each week. Start {start_km:.0f} km, reach {end_km:.0f} km in SPECIFIC phase.",
                "description_template": "Long ride {km} km at easy pace (Z2, 65-70% max HR) — builds endurance base toward {route_dist} km route effort",
            })
        else:
            blocks["base"].append({
                "priority": "STANDARD",
                "session_type": "long_ride",
                "sessions_per_week": 1,
                "rule": f"Progressive long ride from {start_km:.0f} km to {end_km:.0f} km",
            })

        if clmb_lvl == "limited":
            cad_str = f"{climb_cad:.0f} rpm" if climb_cad else "unknown"
            target_cad = max(75, (climb_cad or 60) + 12)
            blocks["base"].append({
                "priority": "HIGH",
                "problem": f"Climbing cadence {cad_str} — climbs will be a major limiter",
                "session_type": "easy_ride",
                "sessions_per_week": 1,
                "rule": f"Include cadence drills: 4x 5 min at {target_cad:.0f}+ rpm on flat road. Builds neuromuscular efficiency for climbs.",
                "description_template": f"Cadence drill ride: warm-up then 4x5min at {target_cad:.0f}+ rpm → trains leg speed needed to avoid grinding on route climbs",
            })

        # ── SPECIFIC blocks ──────────────────────────────────────────────────
        if clmb_lvl in ("limited", "moderate") and gain_per_km > 4:
            grade_str = f"{max_grade:.0f}%" if max_grade else f"{gain_per_km:.0f} m/km avg"
            ftp_str   = f"{ftp:.0f}W" if ftp else "FTP"
            target_cad = max(72, (climb_cad or 60) + 10)
            blocks["specific"].append({
                "priority": "CRITICAL" if clmb_lvl == "limited" else "HIGH",
                "problem": f"Route has {gain_per_km:.0f} m/km elevation, max grade {grade_str}",
                "session_type": "interval_ride",
                "sessions_per_week": 2,
                "rule": f"Hill intervals: 6-8 × 3-4 min at {grade_str} or equivalent indoor resistance. "
                        f"Target cadence {target_cad}+ rpm. Power near {ftp_str} (FTP). "
                        "These simulate the exact muscular demand of the route climbs.",
                "description_template": f"Hill intervals: 6×3min at {ftp_str} / {grade_str} gradient, cadence >{target_cad}rpm → directly replicates the climbing demand on the route",
            })

        if spd_lvl == "limited" and ftp:
            blocks["specific"].append({
                "priority": "HIGH",
                "problem": f"Sustained power (FTP {ftp:.0f}W) needs development for route duration",
                "session_type": "tempo_ride",
                "sessions_per_week": 1,
                "rule": f"Tempo blocks: 2-3 × 15-20 min at 85-95% FTP ({ftp*0.90:.0f}-{ftp:.0f}W). "
                        "Develops the ability to sustain power over the route duration.",
                "description_template": f"Tempo ride: 2×20min at {ftp*0.88:.0f}-{ftp*0.95:.0f}W (88-95% FTP) → builds sustained power for route effort",
            })

        # ── Route simulation in late SPECIFIC ───────────────────────────────
        perf_h = (dist_km / (sport_profile.get("typical_endurance_speed_kmh") or 20))
        blocks["specific"].append({
            "priority": "CRITICAL",
            "session_type": "long_ride",
            "sessions_per_week": 1,
            "rule": f"Late SPECIFIC: one long ride at {end_km:.0f} km (~{perf_h:.1f}h) simulating route duration and pacing strategy. "
                    "Must feel sustainable — not max effort.",
            "description_template": f"Route-simulation long ride {end_km:.0f} km at steady Z2-Z3 — practices pacing and nutrition strategy for event day",
        })

        # ── Key metrics for performance target ───────────────────────────────
        if ftp:
            target_power = round(ftp * 0.78)  # ~78% FTP for long effort
            blocks["key_metrics"] = {
                "target_sustained_power_w": target_power,
                "target_cadence_rpm":       int(max(75, (climb_cad or 60) + 12)),
                "target_duration_h":        round(perf_h, 1),
                "note": f"Athlete should sustain ~{target_power}W at {max(75, (climb_cad or 60)+12)} rpm for ~{perf_h:.1f}h",
            }

    else:  # run
        if end_lvl == "limited":
            longest_run = sport_profile.get("longest_run_km") or longest
            blocks["base"].append({
                "priority": "CRITICAL",
                "problem": f"Longest run {longest_run:.0f} km vs {dist_km:.0f} km route",
                "session_type": "long_run",
                "sessions_per_week": 1,
                "rule": f"Progressive long run: start {start_km:.0f} km, add ~10% per week. Peak at {end_km:.0f} km in SPECIFIC.",
            })

        if clmb_lvl in ("limited", "moderate") and gain_per_km > 10:
            blocks["specific"].append({
                "priority": "HIGH" if clmb_lvl == "limited" else "MEDIUM",
                "session_type": "interval",
                "sessions_per_week": 1,
                "rule": f"Hill repeats: 8-10 × 90s-2min uphill at hard effort. Develops climbing strength for {gain_per_km:.0f} m/km terrain.",
            })

        if spd_lvl == "limited" and easy_pace:
            target_pace = easy_pace * 0.88
            blocks["specific"].append({
                "priority": "HIGH",
                "session_type": "tempo_run",
                "sessions_per_week": 1,
                "rule": f"Tempo run: 20-30 min at {target_pace:.1f} min/km (threshold pace). Raises aerobic efficiency.",
            })

        if easy_pace:
            blocks["key_metrics"] = {
                "target_easy_pace_min_per_km": round(easy_pace, 1),
                "target_duration_h":            round((easy_pace * dist_km + gain_m / 10) / 60, 1),
                "median_hr_note":               "Keep runs below 75% max HR for aerobic base sessions",
            }

    # TAPER is always the same
    blocks["taper"].append({
        "rule": "Reduce volume 40-50%. Keep 1-2 quality sessions at race-day intensity. No new training stress. Focus on readiness.",
    })

    return blocks


def _phase_weeks(total_weeks: int) -> dict:
    """Return how many weeks go into each phase."""
    taper = max(1, round(total_weeks * 0.10))
    specific = max(1, round(total_weeks * 0.30))
    base = total_weeks - specific - taper
    return {
        "base_weeks":     max(1, base),
        "specific_weeks": specific,
        "taper_weeks":    taper,
        "description":    (
            f"Weeks 1-{base}: BASE (build volume + fix limiters). "
            f"Weeks {base+1}-{base+specific}: SPECIFIC (route-demand sessions). "
            f"Week {total_weeks}: TAPER (reduce volume, maintain sharpness)."
        ),
    }

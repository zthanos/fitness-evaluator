"""Deterministic route readiness assessment.

Computes how ready an athlete is for a specific route
using route profile + sport profile data — no LLM calls.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_LEVEL_SCORE = {"good": 2, "moderate": 1, "limited": 0}


def compute_readiness(route, sport_profile: dict) -> dict:
    sport = route.sport  # "ride" | "run"

    if sport == "ride":
        endurance = _cycling_endurance(route, sport_profile)
        climbing  = _cycling_climbing(route, sport_profile)
        speed     = _cycling_speed(route, sport_profile)
    else:
        endurance = _running_endurance(route, sport_profile)
        climbing  = _running_climbing(route, sport_profile)
        speed     = _running_speed(route, sport_profile)

    total = sum(_LEVEL_SCORE[d["level"]] for d in [endurance, climbing, speed])

    if total >= 5:
        athlete_difficulty = "easy"
        overall_label = "Well prepared for this route"
    elif total >= 3:
        athlete_difficulty = "moderate"
        overall_label = "Moderate challenge"
    elif total >= 1:
        athlete_difficulty = "hard"
        overall_label = "Significant challenge"
    else:
        athlete_difficulty = "extreme"
        overall_label = "Major challenge — substantial preparation needed"

    return {
        "athlete_difficulty": athlete_difficulty,
        "overall_label": overall_label,
        "readiness": {
            "endurance": endurance,
            "climbing":  climbing,
            "speed":     speed,
        },
        "route_demands":            _route_demands(route, sport),
        "suggested_duration_weeks": _suggest_duration(route, endurance, climbing, speed),
        "gap_summary":              _gap_summary(route, sport_profile, endurance, climbing, speed, sport),
        "estimated_finish":         _estimate_finish(route, sport_profile, sport),
    }


# ── Cycling ───────────────────────────────────────────────────────────────────

def _cycling_endurance(route, sp: dict) -> dict:
    longest  = sp.get("longest_distance_km") or 0
    route_km = route.distance_km or 0
    if not route_km:
        return {"level": "moderate", "detail": "Route distance unknown"}
    ratio = longest / route_km
    if ratio >= 0.70:
        return {"level": "good",     "detail": f"Longest ride {longest:.0f} km covers {ratio*100:.0f}% of route distance"}
    if ratio >= 0.40:
        return {"level": "moderate", "detail": f"Longest ride {longest:.0f} km is {ratio*100:.0f}% of route — some endurance gap"}
    if longest > 0:
        return {"level": "limited",  "detail": f"Longest ride {longest:.0f} km is well below the {route_km:.0f} km route"}
    return {"level": "limited", "detail": "No recent long rides on record"}


def _cycling_climbing(route, sp: dict) -> dict:
    gain_m     = route.total_elevation_gain_m or 0
    dist_km    = route.distance_km or 1
    gain_per_km = gain_m / dist_km
    climb_cad  = sp.get("climbing_cadence_rpm")
    out_cad    = sp.get("outdoor_cadence_rpm") or sp.get("typical_cadence_rpm")
    weekly_km  = sp.get("weekly_volume_km") or 0

    if gain_per_km < 5:
        return {"level": "good", "detail": "Flat route — climbing not a significant factor"}

    if climb_cad:
        if climb_cad >= 80:
            return {"level": "good",     "detail": f"Climbing cadence {climb_cad:.0f} rpm — solid climbing efficiency"}
        if climb_cad >= 68:
            return {"level": "moderate", "detail": f"Climbing cadence {climb_cad:.0f} rpm — room to improve on steep gradients"}
        return     {"level": "limited",  "detail": f"Low climbing cadence ({climb_cad:.0f} rpm) — climbs will be a key limiter"}

    if out_cad:
        if out_cad >= 85:
            return {"level": "good",     "detail": f"Outdoor cadence {out_cad:.0f} rpm — likely handles climbs well"}
        if out_cad >= 70:
            return {"level": "moderate", "detail": f"Outdoor cadence {out_cad:.0f} rpm — climbing efficiency uncertain"}
        return     {"level": "limited",  "detail": f"Low cadence ({out_cad:.0f} rpm) — climbs will be challenging"}

    # No cadence data — proxy via volume vs elevation density
    if gain_per_km > 15 and weekly_km < 50:
        return {"level": "limited",  "detail": f"High elevation ({gain_per_km:.0f} m/km) with low training volume"}
    if gain_per_km > 10:
        return {"level": "moderate", "detail": f"Moderate climbing density ({gain_per_km:.0f} m/km) — no cadence data"}
    return     {"level": "moderate", "detail": f"Mild climbing ({gain_per_km:.0f} m/km) — should be manageable"}


def _cycling_speed(route, sp: dict) -> dict:
    speed  = sp.get("typical_endurance_speed_kmh") or sp.get("best_long_speed_kmh")
    ftp    = sp.get("ftp_estimate_w")
    dist   = route.distance_km or 0
    gain_m = route.total_elevation_gain_m or 0

    if not speed and not ftp:
        return {"level": "moderate", "detail": "Insufficient data to assess speed readiness"}

    if speed and dist:
        gain_per_km = gain_m / dist if dist else 0
        # ~2% speed reduction per 1% average gradient (rough approximation)
        adj_speed  = max(speed * 0.60, speed * (1 - gain_per_km / 10 * 0.02))
        est_h      = dist / adj_speed
        spd_str    = f"{speed:.0f} km/h"
        if est_h <= 3:
            return {"level": "good",     "detail": f"Estimated finish ~{est_h:.1f}h at {spd_str}"}
        if est_h <= 5:
            level = "moderate" if gain_per_km > 10 else "good"
            return {"level": level,      "detail": f"Estimated finish ~{est_h:.1f}h at {spd_str}"}
        return     {"level": "moderate", "detail": f"Estimated finish ~{est_h:.1f}h — sustained effort required"}

    if ftp:
        if ftp >= 220:
            return {"level": "good",     "detail": f"FTP {ftp:.0f}W — solid power base"}
        if ftp >= 160:
            return {"level": "moderate", "detail": f"FTP {ftp:.0f}W — adequate for completion, pace will be conservative"}
        return     {"level": "limited",  "detail": f"FTP {ftp:.0f}W — below typical endurance threshold for this route length"}

    return {"level": "moderate", "detail": "Speed readiness partially assessable"}


# ── Running ───────────────────────────────────────────────────────────────────

def _running_endurance(route, sp: dict) -> dict:
    longest  = sp.get("longest_run_km") or sp.get("longest_distance_km") or 0
    route_km = route.distance_km or 0
    if not route_km:
        return {"level": "moderate", "detail": "Route distance unknown"}
    ratio = longest / route_km if route_km else 0
    if ratio >= 0.60:
        return {"level": "good",     "detail": f"Longest run {longest:.0f} km — solid base for {route_km:.0f} km"}
    if ratio >= 0.30:
        return {"level": "moderate", "detail": f"Longest run {longest:.0f} km — significant step up to {route_km:.0f} km"}
    if longest > 0:
        return {"level": "limited",  "detail": f"Longest run {longest:.0f} km is far below {route_km:.0f} km route"}
    return {"level": "limited", "detail": "No recent long runs on record"}


def _running_climbing(route, sp: dict) -> dict:
    gain_m      = route.total_elevation_gain_m or 0
    dist_km     = route.distance_km or 1
    gain_per_km = gain_m / dist_km
    limiters    = sp.get("current_limiters") or []
    has_climbing_limiter = any(
        k in str(l).lower() for l in limiters for k in ("climb", "hill", "elevation")
    )

    if gain_per_km < 10:
        return {"level": "good", "detail": "Low elevation — climbing is not a key concern"}
    if gain_per_km > 30:
        level  = "limited" if has_climbing_limiter else "moderate"
        detail = f"High elevation density ({gain_per_km:.0f} m/km) — hilly terrain will be demanding"
    elif gain_per_km > 15:
        level  = "moderate"
        detail = f"Moderate elevation ({gain_per_km:.0f} m/km) — climbing fitness will matter"
    else:
        level  = "moderate" if has_climbing_limiter else "good"
        detail = f"Mild elevation ({gain_per_km:.0f} m/km) — manageable"
    return {"level": level, "detail": detail}


def _running_speed(route, sp: dict) -> dict:
    easy_pace    = sp.get("easy_pace_min_per_km")
    median_hr    = sp.get("median_hr_pct")
    dist_km      = route.distance_km or 0
    gain_m       = route.total_elevation_gain_m or 0

    if not easy_pace:
        return {"level": "moderate", "detail": "No pace data available to assess speed readiness"}

    # Naismith: +1 min per 10m elevation gain
    climb_per_km = (gain_m / dist_km / 10) if dist_km else 0
    eff_pace     = easy_pace + climb_per_km
    est_h        = eff_pace * dist_km / 60 if dist_km else 0
    pace_str     = f"{int(easy_pace)}:{int((easy_pace % 1) * 60):02d} /km"

    if median_hr and median_hr > 0.75:
        return {"level": "limited",  "detail": f"Pace {pace_str} but high cardiac load ({median_hr*100:.0f}% max HR) — aerobic efficiency limiter"}
    if est_h <= 3:
        return {"level": "good",     "detail": f"Pace {pace_str} — estimated {est_h:.1f}h finish, comfortable range"}
    if est_h <= 6:
        return {"level": "moderate", "detail": f"Pace {pace_str} — estimated {est_h:.1f}h finish"}
    return         {"level": "limited",  "detail": f"Pace {pace_str} — estimated {est_h:.1f}h, route is a major distance challenge"}


# ── Route demands (deterministic text) ───────────────────────────────────────

def _route_demands(route, sport: str) -> list[str]:
    demands    = []
    dist_km    = route.distance_km or 0
    gain_m     = route.total_elevation_gain_m or 0
    gain_per_km = gain_m / dist_km if dist_km else 0
    max_grade  = route.max_gradient_pct or 0

    # Distance
    if sport == "ride":
        if dist_km > 100:  demands.append(f"Very long effort ({dist_km:.0f} km) — strong endurance base required")
        elif dist_km > 60: demands.append(f"Long steady effort ({dist_km:.0f} km) — sustained power and smart pacing")
        elif dist_km > 30: demands.append(f"Medium distance ({dist_km:.0f} km) — aerobic endurance focus")
        else:              demands.append(f"Shorter route ({dist_km:.0f} km) — intensity over endurance")
    else:
        if dist_km > 42:   demands.append(f"Ultra distance ({dist_km:.0f} km) — ultra endurance base required")
        elif dist_km > 21: demands.append(f"Long run ({dist_km:.0f} km) — requires high weekly mileage")
        elif dist_km > 10: demands.append(f"Medium run ({dist_km:.0f} km) — mix of endurance and pace work")
        else:              demands.append(f"Short route ({dist_km:.0f} km) — speed and efficiency focused")

    # Terrain
    if gain_per_km > 20:   demands.append(f"Very hilly terrain ({gain_per_km:.0f} m/km) — climbing strength essential")
    elif gain_per_km > 10: demands.append(f"Rolling terrain with notable climbs ({gain_per_km:.0f} m/km)")
    elif gain_per_km > 5:  demands.append(f"Mild undulation ({gain_per_km:.0f} m/km) — moderate climbing effort")
    else:                  demands.append("Mostly flat — pacing and sustained effort are key")

    # Max gradient
    if max_grade > 15:  demands.append(f"Steep sections up to {max_grade:.0f}% — low-gear strategy needed")
    elif max_grade > 8: demands.append(f"Challenging climbs (up to {max_grade:.0f}% gradient)")

    # Total gain
    if gain_m > 2000:    demands.append(f"High total gain ({gain_m:.0f} m) — significant cumulative fatigue")
    elif gain_m > 800:   demands.append(f"Moderate total gain ({gain_m:.0f} m) — climbing efficiency matters")

    return demands


# ── Suggested duration ────────────────────────────────────────────────────────

def _suggest_duration(route, endurance: dict, climbing: dict, speed: dict) -> int:
    base = 6
    for dim in (endurance, climbing, speed):
        if dim["level"] == "limited":  base += 2
        elif dim["level"] == "moderate": base += 1
    dist = route.distance_km or 0
    if dist > 100: base += 2
    elif dist > 60: base += 1
    return min(24, max(4, base))


# ── Gap summary ───────────────────────────────────────────────────────────────

def _gap_summary(route, sp: dict, endurance: dict, climbing: dict, speed: dict, sport: str) -> dict:
    gaps  = []
    focus = []

    weekly_km = sp.get("weekly_volume_km") or 0
    dist_km   = route.distance_km or 0

    if sport == "ride":
        if weekly_km < dist_km * 0.5:
            gaps.append(f"Low weekly volume ({weekly_km:.0f} km/wk vs {dist_km:.0f} km route)")
            focus.append("Building weekly cycling volume")
    else:
        if weekly_km < dist_km * 0.3:
            gaps.append(f"Low weekly mileage ({weekly_km:.0f} km/wk)")
            focus.append("Increasing weekly running mileage")

    if endurance["level"] == "limited":
        gaps.append("Longest effort well below route distance")
        focus.append("Progressive long session build-up")
    elif endurance["level"] == "moderate":
        focus.append("Extending long session distance gradually")

    if climbing["level"] == "limited":
        gaps.append("Limited climbing efficiency")
        focus.append("Hill repeats and climbing cadence work" if sport == "ride" else "Hill running and elevation training")
    elif climbing["level"] == "moderate" and (route.total_elevation_gain_m or 0) > 300:
        focus.append("Targeted hill work")

    if speed["level"] == "limited":
        if sport == "ride":
            gaps.append("Speed / sustained power below route demand")
            focus.append("Threshold intervals and FTP development")
        else:
            gaps.append("Running pace or aerobic efficiency needs improvement")
            focus.append("Easy aerobic volume + tempo sessions")
    elif speed["level"] == "moderate":
        focus.append("Tempo work to lift cruising speed" if sport == "ride" else "Pace-specific training")

    if not gaps:
        gaps = ["No critical gaps — route is within current fitness range"]
    if not focus:
        focus = ["Maintain fitness with route-specific sessions", "Practice pacing strategy"]

    return {"gaps": gaps, "plan_focus": focus}


# ── Finish time estimate ──────────────────────────────────────────────────────

def _estimate_finish(route, sp: dict, sport: str) -> Optional[dict]:
    """Return estimated finish time at current fitness — used to anchor target time input."""
    try:
        dist_km = route.distance_km or 0
        gain_m  = route.total_elevation_gain_m or 0
        if not dist_km:
            return None

        if sport == "ride":
            speed = sp.get("typical_endurance_speed_kmh")
            if not speed:
                return None
            # Gradient penalty per segment if available
            all_segs = (route.climb_segments or []) + (route.descent_segments or []) + (route.flat_segments or [])
            if all_segs:
                total_min = sum(
                    (seg["length_km"] / max(0.5, speed * max(0.3, 1 - 0.02 * abs(seg.get("avg_gradient_pct", 0))))) * 60
                    for seg in all_segs
                )
            else:
                total_min = (dist_km / speed) * 60
        else:
            easy_pace = sp.get("easy_pace_min_per_km")
            if not easy_pace:
                return None
            # Naismith: +1 min per 10m gain
            total_min = easy_pace * dist_km + gain_m / 10.0

        h = int(total_min // 60)
        m = int(total_min % 60)
        return {
            "total_minutes": round(total_min),
            "hours":         h,
            "minutes":       m,
            "display":       f"{h}h {m:02d}min" if h else f"{m} min",
        }
    except Exception:
        return None

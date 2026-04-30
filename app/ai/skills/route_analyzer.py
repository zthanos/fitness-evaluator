"""RouteAnalyzer — parses a GPX file and extracts structured route intelligence.

Produces a RouteAnalysis dataclass (pure, no DB) that feeds:
  - RouteProfile persistence (API layer)
  - RouteSpecificTrainingPlanner (skill layer)

Handles both recorded tracks (<trk>) and planned routes (<rte>).
Works without elevation data; gradient analysis is skipped when unavailable.
"""
from __future__ import annotations

import hashlib
import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Gradient classification thresholds (%)
_CLIMB_PCT    = 3.0
_DESCENT_PCT  = -3.0
_CRITICAL_PCT = 8.0     # gradient to flag as "critical"
_CRITICAL_KM  = 0.3     # minimum length for a critical section

# Gradient smoothing window (meters)
_SMOOTH_WINDOW_M = 250

# Minimum segment length to keep (merges shorter ones into neighbours)
_MIN_SEGMENT_KM = 0.20

# Elevation profile sampling interval
_PROFILE_INTERVAL_KM = 0.5

# Maximum points to process (truncate for huge GPX files)
_MAX_POINTS = 20_000


# ── Internal point representation ────────────────────────────────────────────

@dataclass
class _Pt:
    lat: float
    lon: float
    elev: Optional[float]
    cum_m: float = 0.0  # cumulative distance from start


# ── Public result ─────────────────────────────────────────────────────────────

@dataclass
class RouteAnalysis:
    sport: str
    filename: Optional[str]
    gpx_hash: str

    distance_km: float
    total_elevation_gain_m: float
    total_elevation_loss_m: float
    max_elevation_m: Optional[float]
    min_elevation_m: Optional[float]
    max_gradient_pct: Optional[float]
    avg_climb_gradient_pct: Optional[float]

    difficulty_score: float
    route_difficulty: str

    climb_segments:    list[dict]
    descent_segments:  list[dict]
    flat_segments:     list[dict]
    critical_sections: list[dict]
    elevation_profile: list[dict]  # [{dist_km, elev_m}]

    has_elevation: bool
    analysis_summary: str


# ── Public entry point ────────────────────────────────────────────────────────

def analyze(gpx_content: bytes, sport: str, filename: Optional[str] = None) -> RouteAnalysis:
    """Parse *gpx_content* and return a RouteAnalysis.  Raises ValueError on bad input."""
    try:
        import gpxpy
    except ImportError:
        raise RuntimeError("gpxpy is not installed — add gpxpy>=1.6.2 to dependencies")

    gpx_hash = hashlib.sha256(gpx_content).hexdigest()

    try:
        gpx = gpxpy.parse(gpx_content)
    except Exception as exc:
        raise ValueError(f"Invalid GPX file: {exc}") from exc

    points = _extract_points(gpx)
    if not points:
        raise ValueError("GPX file contains no track or route points")

    # Truncate very large files
    if len(points) > _MAX_POINTS:
        step = len(points) // _MAX_POINTS
        points = points[::step]
        logger.warning("GPX has %d points; downsampled to %d", len(points) * step, len(points))

    _compute_distances(points)

    distance_km = points[-1].cum_m / 1000.0
    has_elevation = any(p.elev is not None for p in points)

    # ── Elevation metrics ─────────────────────────────────────────────────────
    elev_gain = elev_loss = 0.0
    max_elev = min_elev = None

    if has_elevation:
        elevs = [p.elev for p in points if p.elev is not None]
        max_elev = max(elevs)
        min_elev = min(elevs)
        for i in range(1, len(points)):
            prev_e = points[i - 1].elev
            curr_e = points[i].elev
            if prev_e is not None and curr_e is not None:
                delta = curr_e - prev_e
                if delta > 0:
                    elev_gain += delta
                else:
                    elev_loss += abs(delta)

    # ── Gradient & segments ───────────────────────────────────────────────────
    gradients: list[float] = []
    max_gradient: Optional[float] = None
    avg_climb_gradient: Optional[float] = None
    all_segments: list[dict] = []

    if has_elevation and distance_km > 0.05:
        gradients = _smooth_gradients(points)
        max_gradient = max((abs(g) for g in gradients), default=None)
        # avg gradient only over climbing portions
        climb_grads = [g for g in gradients if g >= _CLIMB_PCT]
        avg_climb_gradient = statistics.mean(climb_grads) if climb_grads else None
        all_segments = _segment(points, gradients)

    climb_segs   = [s for s in all_segments if s["type"] == "climb"]
    descent_segs = [s for s in all_segments if s["type"] == "descent"]
    flat_segs    = [s for s in all_segments if s["type"] == "flat"]
    critical     = _critical_sections(all_segments)

    # ── Elevation profile ─────────────────────────────────────────────────────
    profile = _elevation_profile(points) if has_elevation else []

    # ── Difficulty ────────────────────────────────────────────────────────────
    score, label = _difficulty(distance_km, elev_gain, max_gradient or 0)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = _build_summary(
        sport, filename, distance_km, elev_gain, label,
        max_gradient, avg_climb_gradient, critical,
    )

    return RouteAnalysis(
        sport=sport,
        filename=filename,
        gpx_hash=gpx_hash,
        distance_km=round(distance_km, 2),
        total_elevation_gain_m=round(elev_gain, 1),
        total_elevation_loss_m=round(elev_loss, 1),
        max_elevation_m=round(max_elev, 1) if max_elev is not None else None,
        min_elevation_m=round(min_elev, 1) if min_elev is not None else None,
        max_gradient_pct=round(max_gradient, 1) if max_gradient is not None else None,
        avg_climb_gradient_pct=round(avg_climb_gradient, 1) if avg_climb_gradient is not None else None,
        difficulty_score=score,
        route_difficulty=label,
        climb_segments=climb_segs,
        descent_segments=descent_segs,
        flat_segments=flat_segs,
        critical_sections=critical,
        elevation_profile=profile,
        has_elevation=has_elevation,
        analysis_summary=summary,
    )


# ── GPX extraction ────────────────────────────────────────────────────────────

def _extract_points(gpx) -> list[_Pt]:
    pts: list[_Pt] = []
    for track in gpx.tracks:
        for seg in track.segments:
            for p in seg.points:
                pts.append(_Pt(p.latitude, p.longitude, p.elevation))
    if not pts:
        for route in gpx.routes:
            for p in route.points:
                pts.append(_Pt(p.latitude, p.longitude, p.elevation))
    return pts


def _compute_distances(pts: list[_Pt]) -> None:
    cum = 0.0
    for i, p in enumerate(pts):
        if i > 0:
            cum += _haversine(pts[i - 1], p)
        p.cum_m = cum


def _haversine(a: _Pt, b: _Pt) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi   = math.radians(b.lat - a.lat)
    dlambda = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


# ── Gradient helpers ──────────────────────────────────────────────────────────

def _smooth_gradients(pts: list[_Pt]) -> list[float]:
    """Forward-window gradient (%) smoothed over _SMOOTH_WINDOW_M."""
    n = len(pts)
    grads = []
    j = 0
    for i, p in enumerate(pts):
        # Advance j so the window is roughly _SMOOTH_WINDOW_M ahead
        while j < n - 1 and pts[j].cum_m - p.cum_m < _SMOOTH_WINDOW_M:
            j += 1
        dist = pts[j].cum_m - p.cum_m
        if dist < 5 or p.elev is None or pts[j].elev is None:
            grads.append(0.0)
        else:
            g = (pts[j].elev - p.elev) / dist * 100.0
            grads.append(max(-40.0, min(40.0, g)))
    return grads


# ── Segmentation ──────────────────────────────────────────────────────────────

def _seg_type(g: float) -> str:
    if g >= _CLIMB_PCT:
        return "climb"
    if g <= _DESCENT_PCT:
        return "descent"
    return "flat"


def _segment(pts: list[_Pt], grads: list[float]) -> list[dict]:
    if not pts:
        return []

    segments: list[dict] = []
    cur_type = _seg_type(grads[0])
    start_i = 0

    def _flush(s: int, e: int, t: str) -> Optional[dict]:
        if e <= s:
            return None
        dist_m = pts[e].cum_m - pts[s].cum_m
        elevs = [p.elev for p in pts[s:e + 1] if p.elev is not None]
        gs = grads[s:e]
        avg_g = statistics.mean(gs) if gs else 0.0
        max_g = max(gs, key=abs) if gs else 0.0
        elev_delta = (elevs[-1] - elevs[0]) if len(elevs) >= 2 else 0.0
        return {
            "type":               t,
            "start_km":           round(pts[s].cum_m / 1000, 2),
            "end_km":             round(pts[e].cum_m / 1000, 2),
            "length_km":          round(dist_m / 1000, 2),
            "elevation_change_m": round(elev_delta, 1),
            "avg_gradient_pct":   round(avg_g, 1),
            "max_gradient_pct":   round(max_g, 1),
        }

    for i in range(1, len(pts)):
        t = _seg_type(grads[i])
        if t != cur_type:
            seg = _flush(start_i, i - 1, cur_type)
            if seg:
                segments.append(seg)
            cur_type = t
            start_i = i

    seg = _flush(start_i, len(pts) - 1, cur_type)
    if seg:
        segments.append(seg)

    # Merge very short segments into the previous one (avoids noise spikes)
    merged: list[dict] = []
    for seg in segments:
        if seg["length_km"] < _MIN_SEGMENT_KM and merged:
            prev = merged[-1]
            prev["end_km"]             = seg["end_km"]
            prev["length_km"]          = round(prev["length_km"] + seg["length_km"], 2)
            prev["elevation_change_m"] = round(prev["elevation_change_m"] + seg["elevation_change_m"], 1)
        else:
            merged.append(seg)

    return merged


def _critical_sections(segments: list[dict]) -> list[dict]:
    critical: list[dict] = []
    for seg in segments:
        if seg["type"] == "climb" and seg["avg_gradient_pct"] >= _CRITICAL_PCT and seg["length_km"] >= _CRITICAL_KM:
            critical.append({
                "type":               "steep_climb",
                "start_km":           seg["start_km"],
                "end_km":             seg["end_km"],
                "length_km":          seg["length_km"],
                "avg_gradient_pct":   seg["avg_gradient_pct"],
                "max_gradient_pct":   seg["max_gradient_pct"],
                "elevation_gain_m":   seg["elevation_change_m"],
                "description": (
                    f"{seg['length_km']:.1f} km climb averaging {seg['avg_gradient_pct']:.0f}%"
                    f" (max {seg['max_gradient_pct']:.0f}%)"
                ),
            })
        elif seg["type"] == "descent" and seg["avg_gradient_pct"] <= -_CRITICAL_PCT and seg["length_km"] >= _CRITICAL_KM:
            critical.append({
                "type":              "steep_descent",
                "start_km":          seg["start_km"],
                "end_km":            seg["end_km"],
                "length_km":         seg["length_km"],
                "avg_gradient_pct":  seg["avg_gradient_pct"],
                "max_gradient_pct":  seg["max_gradient_pct"],
                "elevation_loss_m":  abs(seg["elevation_change_m"]),
                "description": (
                    f"{seg['length_km']:.1f} km descent averaging {abs(seg['avg_gradient_pct']):.0f}%"
                ),
            })
    return critical


# ── Elevation profile ─────────────────────────────────────────────────────────

def _elevation_profile(pts: list[_Pt]) -> list[dict]:
    profile: list[dict] = []
    next_km = 0.0
    for p in pts:
        km = p.cum_m / 1000.0
        if km >= next_km and p.elev is not None:
            profile.append({"dist_km": round(km, 2), "elev_m": round(p.elev, 1)})
            next_km += _PROFILE_INTERVAL_KM
    last = pts[-1]
    if last.elev is not None:
        last_km = round(last.cum_m / 1000, 2)
        if not profile or profile[-1]["dist_km"] < last_km - 0.1:
            profile.append({"dist_km": last_km, "elev_m": round(last.elev, 1)})
    return profile


# ── Difficulty ────────────────────────────────────────────────────────────────

def _difficulty(distance_km: float, elev_gain_m: float, max_gradient: float) -> tuple[float, str]:
    gain_per_km = elev_gain_m / distance_km if distance_km else 0.0
    score = (
        min(gain_per_km / 10.0, 40.0)   # 0–40 pts: density of climbing
        + min(max_gradient / 2.0, 30.0)  # 0–30 pts: steepest gradient
        + min(distance_km / 5.0, 30.0)   # 0–30 pts: sheer distance
    )
    score = round(min(score, 100.0), 1)
    if score < 25:
        label = "easy"
    elif score < 50:
        label = "moderate"
    elif score < 75:
        label = "hard"
    else:
        label = "extreme"
    return score, label


# ── Summary text ──────────────────────────────────────────────────────────────

def _build_summary(
    sport: str,
    filename: Optional[str],
    distance_km: float,
    elev_gain_m: float,
    difficulty: str,
    max_gradient: Optional[float],
    avg_climb_gradient: Optional[float],
    critical: list[dict],
) -> str:
    name = filename.removesuffix(".gpx").replace("_", " ").replace("-", " ") if filename else "route"
    parts = [
        f"{sport.title()} route '{name}': {distance_km:.1f} km,"
        f" {elev_gain_m:.0f} m elevation gain ({difficulty} difficulty)."
    ]
    if max_gradient is not None:
        parts.append(f"Max gradient {max_gradient:.0f}%.")
        if avg_climb_gradient:
            parts.append(f"Average climbing gradient {avg_climb_gradient:.1f}%.")
    if critical:
        descs = [c["description"] for c in critical]
        parts.append(f"Critical sections: {'; '.join(descs)}.")
    return " ".join(parts)

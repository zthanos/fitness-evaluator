"""Pydantic schemas for all skill inputs and outputs."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── WorkoutAnalyzer ───────────────────────────────────────────────────────────

class WorkoutAnalyzerInput(BaseModel):
    strava_id: Optional[int] = None      # analyse a specific activity
    n_recent: int = 1                    # or the last N activities


class WorkoutAnalysis(BaseModel):
    strava_id: int
    activity_type: str
    sport_type: Optional[str]
    is_indoor: bool
    start_date: datetime

    # Cadence
    avg_cadence: Optional[float]
    max_cadence: Optional[float]
    cadence_quality: Literal["excellent", "good", "fair", "poor", "no_data"]
    cadence_target_rpm: Optional[float]   # benchmark for this activity type

    # Heart rate
    avg_hr: Optional[int]
    max_hr: Optional[int]
    hr_zone: Optional[str]                # Z1-Z5 estimate
    hr_response: Literal["controlled", "moderate", "high", "maximal", "no_data"]

    # Power (if available)
    avg_watts: Optional[float]
    weighted_avg_watts: Optional[float]
    intensity_factor: Optional[float]     # w_avg / FTP if FTP known

    # Effort summary
    effort_level: Literal["easy", "moderate", "hard", "maximal"]
    training_purpose: Optional[str]       # e.g. "endurance base", "threshold", "recovery"
    suffer_score: Optional[int]

    # Coach interpretation
    limiter_hypothesis: Optional[str]     # token: "outdoor_transfer" | "aerobic_base" | "cadence_capacity" …
    session_type: Optional[str]           # 1 sentence: character of this session with actual numbers
    main_insight: str                     # 1-2 sentences: what this reveals about the athlete
    key_limiter: Optional[str]            # human label: "Cadence control under load"
    why_it_matters: Optional[str]         # 1-2 sentences: physiological/perf impact of this limiter
    next_action: str

    confidence: float = Field(ge=0.0, le=1.0)


# ── FitnessStateBuilder ───────────────────────────────────────────────────────

class FitnessStateInput(BaseModel):
    lookback_days: int = 28


class FitnessState(BaseModel):
    athlete_id: int

    # Cadence profile
    comfort_cadence_indoor: Optional[float]
    comfort_cadence_outdoor: Optional[float]
    climbing_cadence: Optional[float]

    # Current limiter
    current_limiter: Optional[str]
    limiter_confidence: float = Field(ge=0.0, le=1.0, default=0.0)

    # Load & recovery
    fatigue_level: Literal["low", "moderate", "high", "overreaching"]
    weekly_consistency: float = Field(ge=0.0, le=1.0)  # sessions_done / target
    acwr_ratio: Optional[float]

    # HR trends
    hr_response_trend: Optional[Literal["improving", "stable", "degrading"]]
    rhr_trend: Optional[Literal["improving", "stable", "degrading"]]

    # Meta
    state_confidence: float = Field(ge=0.0, le=1.0)
    last_updated_at: datetime
    summary_text: Optional[str]           # generated view, not primary truth

    # Composite score and classification
    fitness_score: Optional[float] = None          # 0-100
    athlete_classification: Optional[str] = None   # e.g. "Recreational Runner"


# ── RecoveryAnalyzer ──────────────────────────────────────────────────────────

class RecoveryInput(BaseModel):
    lookback_days: int = 28


class RecoveryStatus(BaseModel):
    acwr_ratio: Optional[float]
    acute_load_min: float         # last 7 days moving time
    chronic_load_min: float       # 28-day weekly avg
    rhr_bpm: Optional[float]
    rhr_trend: Optional[Literal["improving", "stable", "degrading"]]
    fatigue_level: Literal["low", "moderate", "high", "overreaching"]
    rest_recommended: bool
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)


# ── BodyTrendAnalyzer ─────────────────────────────────────────────────────────

class BodyTrendInput(BaseModel):
    lookback_weeks: int = 8


class BodyTrend(BaseModel):
    weeks_analysed: int
    weight_slope_kg_per_week: Optional[float]   # negative = losing
    body_fat_trend: Optional[Literal["decreasing", "stable", "increasing"]]
    waist_trend: Optional[Literal["decreasing", "stable", "increasing"]]
    rhr_trend: Optional[Literal["improving", "stable", "degrading"]]
    plateau_detected: bool
    plateau_weeks: int = 0
    assessment: str
    confidence: float = Field(ge=0.0, le=1.0)


# ── NutritionEvaluator ───────────────────────────────────────────────────────

class NutritionInput(BaseModel):
    week_start: Optional[str] = None   # ISO date; defaults to current week


class NutritionEvaluation(BaseModel):
    days_logged: int
    avg_calories: Optional[float]
    avg_protein_g: Optional[float]
    avg_carbs_g: Optional[float]
    avg_fat_g: Optional[float]
    avg_fasting_hrs: Optional[float]
    calorie_target: Optional[float]
    protein_target_g: Optional[float]
    calorie_adherence_pct: Optional[float]
    protein_adherence_pct: Optional[float]
    fasting_consistency_pct: Optional[float]
    assessment: Literal["on_track", "minor_gaps", "significant_gaps", "insufficient_data"]
    notes: str


# ── ProgressAnalyzer ─────────────────────────────────────────────────────────

class ProgressInput(BaseModel):
    goal_id: Optional[str] = None   # None = all active goals


class GoalProgress(BaseModel):
    goal_id: str
    goal_type: str
    description: str
    current_value: Optional[float]
    target_value: Optional[float]
    gap: Optional[float]
    trend: Optional[Literal["on_track", "behind", "ahead", "plateau"]]
    eta_weeks: Optional[float]
    adjustment_suggested: bool
    adjustment_note: Optional[str]


class ProgressReport(BaseModel):
    goals: list[GoalProgress]
    overall_trend: Literal["improving", "stable", "declining", "no_data"]
    summary: str


# ── GoalManager ───────────────────────────────────────────────────────────────

class GoalManagerInput(BaseModel):
    action: Literal["suggest_adjustment", "summarise"]
    goal_id: Optional[str] = None


class GoalSuggestion(BaseModel):
    action: Literal["keep", "adjust", "replace"]
    rationale: str
    new_target_value: Optional[float]
    new_target_date: Optional[str]


# ── PerformanceEstimator ─────────────────────────────────────────────────────

class PerformanceGoalInput(BaseModel):
    query: str                              # natural language goal, e.g. "ride 70 km in 3 hours"
    sport_group: Optional[str] = None      # override auto-detection: ride | run | swim | strength


class PerformanceEstimate(BaseModel):
    sport_group: str                                    # ride | run | swim | strength
    target_distance_km: Optional[float] = None
    target_duration_min: Optional[float] = None
    target_speed_kmh: Optional[float] = None            # derived: distance / (duration / 60)
    current_best_comparable_speed_kmh: Optional[float] = None
    speed_gap_kmh: Optional[float] = None               # positive = need to be faster
    speed_gap_percent: Optional[float] = None           # (target − current) / current × 100
    comparable_basis: Optional[str] = None              # e.g. "best 120-min ride speed"
    current_limiters: list[str] = Field(default_factory=list)
    data_basis: str = ""                                # what data was used
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    parse_success: bool = False


# ── CoachSynthesizer ─────────────────────────────────────────────────────────

class CoachInput(BaseModel):
    workout_analysis: Optional[WorkoutAnalysis] = None
    fitness_state: Optional[FitnessState] = None
    recovery_status: Optional[RecoveryStatus] = None
    body_trend: Optional[BodyTrend] = None
    nutrition_eval: Optional[NutritionEvaluation] = None
    progress_report: Optional[ProgressReport] = None
    performance_estimate: Optional[PerformanceEstimate] = None
    sport_profile: Optional[dict] = None   # key fields from AthleteSportProfile for the relevant sport
    user_question: str = ""


class CoachResponse(BaseModel):
    headline: str
    body: str
    next_action: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)

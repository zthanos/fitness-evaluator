"""CoachSynthesizer — fuses all skill outputs into a single focused coaching response."""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import CoachInput, CoachResponse

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an elite endurance coach delivering a personal post-analysis brief.

CRITICAL RULES:
- Always speak directly to the athlete. Use "you" and "your" — NEVER "the athlete".
- Reference the athlete's actual numbers from their profile (e.g. their typical cadence, their FTP estimate, their best ride speed) — not generic benchmarks.
- If the sport profile shows the athlete's typical cadence is 63 rpm, that context matters: frame the 90 rpm target as a development gap, not a failure.
- Use athlete_demographics when relevant: age informs HR zone interpretation (e.g. 168 bpm at age 42 is very close to estimated max), weight informs power-to-weight context.
- Be specific to the sport discussed (ride vs run vs swim — tailor the language accordingly).

Produce a coaching response with:
1. headline — one punchy sentence (≤15 words) capturing the single most important finding, addressed to the athlete.
2. body — 2-4 sentences of specific, evidence-based coaching commentary using "you/your". Reference actual numbers from their data. Address their question directly.
3. next_action — one concrete, specific, actionable step calibrated to this athlete's current level. Not generic ("train harder"). Specific and achievable ("add 2×10 min at your current comfortable cadence, targeting 70 rpm, before next ride").
4. confidence — 0.0–1.0 reflecting data richness.
5. evidence_refs — list of up to 3 short strings naming the specific data points used
   (e.g. ["your avg cadence this ride: 63 rpm", "your typical cadence: 63 rpm", "your ACWR=1.42"]).

Respond ONLY with valid JSON:
{"headline": "...", "body": "...", "next_action": "...", "confidence": 0.0, "evidence_refs": [...]}"""


class CoachSynthesizer(BaseSkill[CoachInput, CoachResponse]):

    async def run(self, input: CoachInput) -> CoachResponse:
        payload = self._build_payload(input)
        raw = await self._llm_reason(_SYSTEM_PROMPT, json.dumps(payload, default=str))
        return self._parse(raw, input)

    # ── Payload assembly ─────────────────────────────────────────────────────

    def _build_payload(self, inp: CoachInput) -> dict:
        payload: dict = {}

        # Always include athlete demographics — age matters for HR context,
        # weight matters for power-to-weight and load management
        demographics = self._get_athlete_demographics()
        if demographics:
            payload["athlete_demographics"] = demographics

        if inp.user_question:
            payload["user_question"] = inp.user_question

        if inp.workout_analysis:
            wa = inp.workout_analysis
            payload["latest_workout"] = {
                "sport": wa.sport_type or wa.activity_type,
                "indoor": wa.is_indoor,
                "date": wa.start_date.isoformat(),
                "avg_cadence": wa.avg_cadence,
                "cadence_quality": wa.cadence_quality,
                "cadence_target_rpm": wa.cadence_target_rpm,
                "avg_hr": wa.avg_hr,
                "hr_zone": wa.hr_zone,
                "hr_response": wa.hr_response,
                "effort_level": wa.effort_level,
                "intensity_factor": wa.intensity_factor,
                "suffer_score": wa.suffer_score,
                "limiter_hypothesis": wa.limiter_hypothesis,
                "main_insight": wa.main_insight,
                "next_action": wa.next_action,
                "confidence": wa.confidence,
            }

        if inp.fitness_state:
            fs = inp.fitness_state
            payload["fitness_state"] = {
                "comfort_cadence_indoor": fs.comfort_cadence_indoor,
                "comfort_cadence_outdoor": fs.comfort_cadence_outdoor,
                "climbing_cadence": fs.climbing_cadence,
                "current_limiter": fs.current_limiter,
                "limiter_confidence": fs.limiter_confidence,
                "fatigue_level": fs.fatigue_level,
                "weekly_consistency": fs.weekly_consistency,
                "acwr_ratio": fs.acwr_ratio,
                "hr_response_trend": fs.hr_response_trend,
                "rhr_trend": fs.rhr_trend,
                "state_confidence": fs.state_confidence,
                "fitness_score": fs.fitness_score,
                "athlete_classification": fs.athlete_classification,
                "summary": fs.summary_text,
            }

        if inp.recovery_status:
            rs = inp.recovery_status
            payload["recovery"] = {
                "fatigue_level": rs.fatigue_level,
                "acwr_ratio": rs.acwr_ratio,
                "rhr_bpm": rs.rhr_bpm,
                "rhr_trend": rs.rhr_trend,
                "rest_recommended": rs.rest_recommended,
                "recommendation": rs.recommendation,
            }

        if inp.body_trend:
            bt = inp.body_trend
            payload["body_trend"] = {
                "weight_slope_kg_per_week": bt.weight_slope_kg_per_week,
                "body_fat_trend": bt.body_fat_trend,
                "rhr_trend": bt.rhr_trend,
                "plateau_detected": bt.plateau_detected,
                "assessment": bt.assessment,
            }

        if inp.nutrition_eval:
            ne = inp.nutrition_eval
            payload["nutrition"] = {
                "days_logged": ne.days_logged,
                "avg_calories": ne.avg_calories,
                "avg_protein_g": ne.avg_protein_g,
                "calorie_adherence_pct": ne.calorie_adherence_pct,
                "protein_adherence_pct": ne.protein_adherence_pct,
                "assessment": ne.assessment,
                "notes": ne.notes,
            }

        if inp.progress_report:
            pr = inp.progress_report
            payload["progress"] = {
                "overall_trend": pr.overall_trend,
                "summary": pr.summary,
                "goals": [
                    {
                        "goal_type": g.goal_type,
                        "description": g.description,
                        "trend": g.trend,
                        "gap": g.gap,
                        "eta_weeks": g.eta_weeks,
                    }
                    for g in pr.goals
                ],
            }

        if inp.sport_profile:
            payload["athlete_sport_profile"] = inp.sport_profile

        if inp.performance_estimate:
            pe = inp.performance_estimate
            payload["performance_goal"] = {
                "sport_group":                      pe.sport_group,
                "target_distance_km":               pe.target_distance_km,
                "target_duration_min":              pe.target_duration_min,
                "target_speed_kmh":                 pe.target_speed_kmh,
                "current_best_comparable_speed_kmh": pe.current_best_comparable_speed_kmh,
                "speed_gap_kmh":                    pe.speed_gap_kmh,
                "speed_gap_percent":                pe.speed_gap_percent,
                "comparable_basis":                 pe.comparable_basis,
                "current_limiters":                 pe.current_limiters,
                "data_basis":                       pe.data_basis,
                "confidence":                       pe.confidence,
            }

        return payload

    # ── Response parsing ─────────────────────────────────────────────────────

    def _parse(self, raw: str, inp: CoachInput) -> CoachResponse:
        try:
            cleaned = (
                raw.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            data = json.loads(cleaned)
            return CoachResponse(
                headline=data.get("headline", "Analysis complete."),
                body=data.get("body", raw[:500] if raw else "No analysis available."),
                next_action=data.get("next_action", "Review recent sessions with your coach."),
                confidence=float(data.get("confidence", 0.5)),
                evidence_refs=data.get("evidence_refs", []),
            )
        except Exception:
            logger.warning("CoachSynthesizer: could not parse LLM JSON, using fallback")
            return CoachResponse(
                headline="Workout analysis complete.",
                body=raw[:500] if raw else "Analysis could not be generated.",
                next_action="Review your recent session data.",
                confidence=0.3,
                evidence_refs=[],
            )

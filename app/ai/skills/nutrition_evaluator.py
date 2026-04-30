"""NutritionEvaluator — scores weekly nutrition adherence against athlete targets."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from statistics import mean
from typing import Optional

from app.ai.skills.base_skill import BaseSkill
from app.ai.skills.schemas import NutritionInput, NutritionEvaluation

logger = logging.getLogger(__name__)


class NutritionEvaluator(BaseSkill[NutritionInput, NutritionEvaluation]):

    async def run(self, input: NutritionInput) -> NutritionEvaluation:
        week_start = self._resolve_week(input.week_start)
        logs = self._load_logs(week_start)
        targets = self._load_targets()

        if not logs:
            return NutritionEvaluation(
                days_logged=0,
                avg_calories=None,
                avg_protein_g=None,
                avg_carbs_g=None,
                avg_fat_g=None,
                avg_fasting_hrs=None,
                calorie_target=targets.get("calories"),
                protein_target_g=targets.get("protein_g"),
                calorie_adherence_pct=None,
                protein_adherence_pct=None,
                fasting_consistency_pct=None,
                assessment="insufficient_data",
                notes="No nutrition logs found for this week. Log meals daily to enable coaching.",
            )

        avg_cal   = self._avg([l["calories_in"] for l in logs if l["calories_in"] is not None])
        avg_pro   = self._avg([l["protein_g"] for l in logs if l["protein_g"] is not None])
        avg_carbs = self._avg([l["carbs_g"] for l in logs if l["carbs_g"] is not None])
        avg_fat   = self._avg([l["fat_g"] for l in logs if l["fat_g"] is not None])
        avg_fast  = self._avg([l["fasting_hours"] for l in logs if l["fasting_hours"] is not None])

        cal_target  = targets.get("calories")
        pro_target  = targets.get("protein_g")
        fast_target = targets.get("fasting_hrs")

        cal_adh  = self._adherence(avg_cal,  cal_target)
        pro_adh  = self._adherence(avg_pro,  pro_target)
        fast_con = self._fasting_consistency(logs, fast_target)

        assessment = self._assess(cal_adh, pro_adh, len(logs))
        notes = self._notes(avg_cal, cal_target, avg_pro, pro_target, len(logs), assessment)

        return NutritionEvaluation(
            days_logged=len(logs),
            avg_calories=round(avg_cal, 0) if avg_cal is not None else None,
            avg_protein_g=round(avg_pro, 1) if avg_pro is not None else None,
            avg_carbs_g=round(avg_carbs, 1) if avg_carbs is not None else None,
            avg_fat_g=round(avg_fat, 1) if avg_fat is not None else None,
            avg_fasting_hrs=round(avg_fast, 1) if avg_fast is not None else None,
            calorie_target=cal_target,
            protein_target_g=pro_target,
            calorie_adherence_pct=cal_adh,
            protein_adherence_pct=pro_adh,
            fasting_consistency_pct=fast_con,
            assessment=assessment,
            notes=notes,
        )

    # ── Data loading ─────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_week(week_start_str: Optional[str]) -> date:
        if week_start_str:
            return date.fromisoformat(week_start_str)
        today = date.today()
        return today - timedelta(days=today.weekday())  # Monday of current week

    def _load_logs(self, week_start: date) -> list[dict]:
        from app.models.daily_log import DailyLog
        week_end = week_start + timedelta(days=7)
        rows = (
            self.db.query(DailyLog)
            .filter(
                DailyLog.athlete_id == self.athlete_id,
                DailyLog.log_date >= week_start,
                DailyLog.log_date < week_end,
            )
            .all()
        )
        return [
            {
                "calories_in":    r.calories_in,
                "protein_g":      r.protein_g,
                "carbs_g":        r.carbs_g,
                "fat_g":          r.fat_g,
                "fasting_hours":  r.fasting_hours,
            }
            for r in rows
        ]

    def _load_targets(self) -> dict:
        from app.models.plan_targets import PlanTargets
        row = (
            self.db.query(PlanTargets)
            .filter(PlanTargets.athlete_id == self.athlete_id)
            .order_by(PlanTargets.effective_from.desc())
            .first()
        )
        if not row:
            return {}
        return {
            "calories":    row.target_calories,
            "protein_g":   row.target_protein_g,
            "fasting_hrs": row.target_fasting_hrs,
        }

    # ── Computation ───────────────────────────────────────────────────────────

    @staticmethod
    def _avg(values: list[float]) -> Optional[float]:
        return mean(values) if values else None

    @staticmethod
    def _adherence(actual: Optional[float], target: Optional[float]) -> Optional[float]:
        if actual is None or target is None or target == 0:
            return None
        return round(min(actual / target * 100, 200.0), 1)  # cap at 200%

    @staticmethod
    def _fasting_consistency(logs: list[dict], target_hrs: Optional[float]) -> Optional[float]:
        if not target_hrs or not logs:
            return None
        days_met = sum(
            1 for l in logs
            if l["fasting_hours"] is not None and l["fasting_hours"] >= target_hrs
        )
        return round(days_met / len(logs) * 100, 1)

    @staticmethod
    def _assess(cal_adh: Optional[float], pro_adh: Optional[float], days: int) -> str:
        if days < 3:
            return "insufficient_data"
        gaps = 0
        if cal_adh is not None and (cal_adh < 80 or cal_adh > 120):
            gaps += 1
        if pro_adh is not None and pro_adh < 80:
            gaps += 1
        if gaps == 0:
            return "on_track"
        if gaps == 1:
            return "minor_gaps"
        return "significant_gaps"

    @staticmethod
    def _notes(
        avg_cal: Optional[float], cal_target: Optional[float],
        avg_pro: Optional[float], pro_target: Optional[float],
        days: int, assessment: str,
    ) -> str:
        if assessment == "insufficient_data":
            return f"Only {days} day(s) logged — aim for 7 days to get accurate coaching."
        parts = []
        if avg_cal is not None and cal_target is not None:
            diff = round(avg_cal - cal_target)
            sign = "+" if diff >= 0 else ""
            parts.append(f"Calories {sign}{diff} vs target ({int(cal_target)} kcal)")
        if avg_pro is not None and pro_target is not None:
            diff = round(avg_pro - pro_target, 1)
            sign = "+" if diff >= 0 else ""
            parts.append(f"Protein {sign}{diff}g vs target ({int(pro_target)}g)")
        if not parts:
            return f"{days} days logged; targets not configured."
        return "; ".join(parts) + "."

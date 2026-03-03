# app/schemas/eval_output.py
from pydantic import BaseModel, Field
from typing import Optional, List


class NutritionAnalysis(BaseModel):
    avg_daily_calories: Optional[float] = None
    avg_protein_g: Optional[float] = None
    avg_adherence_score: Optional[float] = None
    commentary: str


class TrainingAnalysis(BaseModel):
    total_run_km: Optional[float] = None
    strength_sessions: Optional[int] = None
    total_active_minutes: Optional[float] = None
    commentary: str


class Recommendation(BaseModel):
    area: str           # e.g. "Nutrition", "Training", "Recovery"
    action: str         # Specific, actionable instruction
    priority: int       # 1 (highest) to 5 (lowest)


class EvalOutput(BaseModel):
    overall_score: int = Field(..., ge=1, le=10)
    summary: str        = Field(..., min_length=50, max_length=500)
    wins: List[str]     = Field(..., min_length=1)
    misses: List[str]
    nutrition_analysis: NutritionAnalysis
    training_analysis: TrainingAnalysis
    recommendations: List[Recommendation] = Field(..., max_length=5)
    data_confidence: float = Field(..., ge=0.0, le=1.0)

"""MealAnalyzerSkill — vision-based meal photo analysis via LM Studio."""
from __future__ import annotations

import base64
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.70  # items below this are flagged needs_confirmation


# ── Output contract ───────────────────────────────────────────────────────────

class DetectedMealItem(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    needs_confirmation: bool = False
    clarification_question: Optional[str] = None


class MealAnalysisResult(BaseModel):
    items: list[DetectedMealItem] = []
    overall_confidence: float = 0.0
    notes: Optional[str] = None
    error: Optional[str] = None


# ── Skill ─────────────────────────────────────────────────────────────────────

class MealAnalyzerSkill:
    """Stateless vision skill — no DB, no athlete context needed."""

    SYSTEM_PROMPT = """You are a professional nutritionist analyzing a meal photo.
Your task is to identify all visible food items and estimate their nutritional content.

For each item provide:
- name: specific food name (e.g. "grilled chicken breast", not just "meat")
- quantity: estimated amount (numeric)
- unit: "g", "ml", "cup", "piece", etc.
- calories, protein_g, carbs_g, fat_g: per the estimated quantity
- confidence: 0.0–1.0 (how certain you are about this item and its portion)
- needs_confirmation: true if confidence < 0.7 or portion is ambiguous
- clarification_question: a question to ask the user when needs_confirmation is true

Use standard nutritional databases for macro estimates.
If an item is partially obscured or unrecognizable, still include it with low confidence.
Respond ONLY with valid JSON matching this schema, no markdown fences, no commentary:

{
  "items": [
    {
      "name": "string",
      "quantity": number_or_null,
      "unit": "string_or_null",
      "calories": number_or_null,
      "protein_g": number_or_null,
      "carbs_g": number_or_null,
      "fat_g": number_or_null,
      "confidence": 0.0–1.0,
      "needs_confirmation": true|false,
      "clarification_question": "string_or_null"
    }
  ],
  "overall_confidence": 0.0–1.0,
  "notes": "string_or_null"
}"""

    def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> MealAnalysisResult:
        """
        Analyze a meal image and return detected items with nutritional estimates.

        Args:
            image_bytes: Raw image bytes (JPEG, PNG, WEBP)
            mime_type: MIME type of the image

        Returns:
            MealAnalysisResult with detected items and confidence scores
        """
        from app.config import get_settings
        settings = get_settings()

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        try:
            raw_json = self._call_vision_model(settings, data_url)
            return self._parse_response(raw_json)
        except Exception as exc:
            logger.error("MealAnalyzerSkill failed: %s", exc)
            return MealAnalysisResult(error=f"Analysis failed: {exc}")

    def _call_vision_model(self, settings, data_url: str) -> str:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        base_url = settings.LM_STUDIO_ENDPOINT
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"

        llm = ChatOpenAI(
            base_url=base_url,
            api_key="lm-studio",
            model=settings.LM_STUDIO_MODEL,
            temperature=0.2,
            max_tokens=2000,
        )

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": "Analyze this meal photo and return the JSON nutritional breakdown."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]),
        ]

        response = llm.invoke(messages)
        return response.content

    def _parse_response(self, raw: str) -> MealAnalysisResult:
        # Strip markdown fences if the model added them anyway
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(text)

        items = []
        for item_data in data.get("items", []):
            item = DetectedMealItem(
                name=item_data.get("name", "Unknown"),
                quantity=item_data.get("quantity"),
                unit=item_data.get("unit"),
                calories=item_data.get("calories"),
                protein_g=item_data.get("protein_g"),
                carbs_g=item_data.get("carbs_g"),
                fat_g=item_data.get("fat_g"),
                confidence=float(item_data.get("confidence", 0.5)),
                needs_confirmation=bool(item_data.get("needs_confirmation", False)),
                clarification_question=item_data.get("clarification_question"),
            )
            # Enforce threshold regardless of what the model said
            if item.confidence < CONFIDENCE_THRESHOLD:
                item.needs_confirmation = True
            items.append(item)

        overall_confidence = float(data.get("overall_confidence", 0.5))
        if items:
            overall_confidence = sum(i.confidence for i in items) / len(items)

        return MealAnalysisResult(
            items=items,
            overall_confidence=round(overall_confidence, 3),
            notes=data.get("notes"),
        )

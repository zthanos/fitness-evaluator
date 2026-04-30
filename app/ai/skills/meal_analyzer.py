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

## Priority rule
If the user has listed specific food items with quantities (e.g. "1 cup Greek yogurt 2%, 1 medium banana"),
treat that list as GROUND TRUTH for names and portions.
Use the photo only to visually confirm those items are present.
Do NOT override the user's stated quantities with your own visual estimates.
If an item the user mentioned is not visible in the photo, still include it — mark confidence 0.9
and set needs_confirmation=false (the user knows what they put in the meal).

If NO item list is provided, identify all visible food items and estimate portions from the photo.

## Output fields (per item)
- name: specific food name (e.g. "Greek yogurt 2%", not just "yogurt")
- quantity: numeric amount
- unit: "g", "ml", "cup", "tbsp", "piece", etc.
- calories, protein_g, carbs_g, fat_g: calculated for the given quantity using standard nutritional data
- confidence: 0.0–1.0
- needs_confirmation: true only when the portion is genuinely ambiguous AND the user has not specified it
- clarification_question: ask only when needs_confirmation is true

## Nutritional accuracy
Use USDA / standard nutritional database values. Be precise with units:
- 1 cup Greek yogurt 2% ≈ 245g → ~140 kcal, 20g protein, 8g carbs, 4g fat
- 1 medium banana ≈ 118g → ~105 kcal, 1.3g protein, 27g carbs, 0.4g fat
- 1 tbsp honey ≈ 21g → ~64 kcal, 0g protein, 17g carbs, 0g fat

Respond ONLY with valid JSON — no markdown fences, no commentary:

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

    def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg", user_context: str | None = None) -> MealAnalysisResult:
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
            raw_json = self._call_vision_model(settings, data_url, user_context)
            return self._parse_response(raw_json)
        except Exception as exc:
            logger.error("MealAnalyzerSkill failed: %s", exc)
            return MealAnalysisResult(error=f"Analysis failed: {exc}")

    def _call_vision_model(self, settings, data_url: str, user_context: str | None = None) -> str:
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

        if user_context:
            user_text = (
                f"The user has described this meal:\n{user_context}\n\n"
                "Use these items and quantities as ground truth. "
                "Calculate precise macros for each and return the JSON breakdown."
            )
        else:
            user_text = "Analyze this meal photo and estimate all food items with quantities. Return the JSON breakdown."

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": user_text},
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

"""LLM-based intent classifier — replaces the brittle keyword-matching approach."""
from __future__ import annotations

import logging
from typing import Optional

from app.ai.retrieval.intent_router import Intent, IntentRouter

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a query router for a fitness coaching app.
Classify the user message into exactly one category. Reply with ONLY the category name — nothing else.

Categories:
workout_analysis   – asking about a specific workout or training session (effort, cadence, HR, performance)
recovery_check     – asking about recovery, fatigue, or whether to train today
progress_check     – asking about progress toward goals or body composition trends
plan_generation    – requesting a training plan, programme, or schedule
nutrition_check    – asking about diet, calories, protein, food, or fuelling
activity_list      – listing or ranking activities (longest, fastest, biggest, most elevation, how many, etc.)
general            – conversational or anything that doesn't fit the above"""

_FALLBACK_ROUTER = IntentRouter()


async def classify_intent(query: str) -> Intent:
    """
    Classify a user query using the LLM.

    Falls back to keyword matching if the LLM call fails or returns an
    unrecognised category, so routing is always available.
    """
    try:
        from app.services.llm_client import LLMClient
        from app.config import get_settings
        settings = get_settings()
        # Use the tool-calling subagent (instruction-following model) when available —
        # it reliably outputs just the category name, unlike reasoning models that
        # may prepend chain-of-thought before answering.
        client = LLMClient(
            base_url=settings.tool_agent_base_url,
            model_name=settings.tool_agent_model,
        )
        result = await client.chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": query},
            ],
            max_tokens=16,
            temperature=0.0,
        )
        raw = (result.get("content") or "").strip().lower().replace("-", "_")
        # Strip any trailing punctuation or whitespace
        raw = raw.split()[0] if raw.split() else ""
        intent = Intent(raw)
        logger.debug("LLM classified %r → %s", query, intent.value)
        return intent
    except Exception as exc:
        logger.debug("LLM intent classification failed (%s), falling back to keywords", exc)
        return _FALLBACK_ROUTER.classify(query)

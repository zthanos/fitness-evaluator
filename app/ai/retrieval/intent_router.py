"""Intent classification for query routing in RAG system."""

from enum import Enum


class Intent(Enum):
    """Query intent types for targeted data retrieval."""

    WORKOUT_ANALYSIS  = "workout_analysis"    # → analyze_recent_workout
    RECOVERY_CHECK    = "recovery_check"      # → evaluate_recovery
    PROGRESS_CHECK    = "progress_check"      # → evaluate_progress
    PLAN_GENERATION   = "plan_generation"     # → generate_plan
    NUTRITION_CHECK   = "nutrition_check"     # → NutritionEvaluator (via evaluate_progress)
    ACTIVITY_LIST     = "activity_list"       # → query_activities
    PERFORMANCE_GOAL  = "performance_goal"    # → evaluate_performance_goal
    RECENT_PERFORMANCE = "recent_performance"
    TREND_ANALYSIS    = "trend_analysis"
    GOAL_PROGRESS     = "goal_progress"
    RECOVERY_STATUS   = "recovery_status"
    TRAINING_PLAN     = "training_plan"
    COMPARISON        = "comparison"
    GENERAL           = "general"


# Maps Intent → preferred tool name (hint only; LLM still decides)
INTENT_TOOL_HINT: dict[Intent, str] = {
    Intent.WORKOUT_ANALYSIS:  "analyze_recent_workout",
    Intent.RECOVERY_CHECK:    "evaluate_recovery",
    Intent.PROGRESS_CHECK:    "evaluate_progress",
    Intent.PLAN_GENERATION:   "generate_plan",
    Intent.NUTRITION_CHECK:   "evaluate_progress",
    Intent.GOAL_PROGRESS:     "evaluate_progress",
    Intent.RECOVERY_STATUS:   "evaluate_recovery",
    Intent.TRAINING_PLAN:     "generate_plan",
    Intent.ACTIVITY_LIST:     "query_activities",
    Intent.PERFORMANCE_GOAL:  "evaluate_performance_goal",
}


class IntentRouter:
    """Classifies user queries into intents for targeted retrieval."""

    # Keyword mappings — checked top-to-bottom; first match wins.
    INTENT_KEYWORDS: dict[Intent, list[str]] = {
        # Skill-pipeline intents (checked first — more specific)
        Intent.PERFORMANCE_GOAL: [
            "can i ride", "can i run", "can i complete", "can i do",
            "am i ready for", "am i ready to", "ready for a",
            "want to ride", "want to run", "want to complete",
            "planning to ride", "planning to run", "planning to do",
            "goal of riding", "goal of running",
            "finish a marathon", "finish a half", "finish a century",
            "in 3 hours", "in 4 hours", "in 2 hours", "in 1 hour",
            "in x hours", "within 3h", "within 4h",
            "how far am i", "how much faster", "what do i need",
            "achieve my goal", "hit my goal", "reach my goal",
        ],
        Intent.ACTIVITY_LIST: [
            "longest", "shortest", "biggest", "list my", "show me my",
            "which are my", "what are my", "my rides", "my runs", "my workouts",
            "my activities", "all my", "best ride", "best run", "fastest",
            "slowest", "top ride", "top run", "furthest", "farthest",
            "most elevation", "most distance", "how many rides", "how many runs",
            "how many activities", "my sessions", "past rides", "past runs",
        ],
        Intent.WORKOUT_ANALYSIS: [
            "analyse my", "analyze my", "last ride", "last run", "last workout",
            "last session", "how was my ride", "how was my run", "how did my ride",
            "how did my run", "how did my workout", "cadence", "power output",
            "effort", "my performance", "limiter", "what's my fitness",
        ],
        Intent.RECOVERY_CHECK: [
            "should i train", "can i train", "am i recovered", "how recovered",
            "ready to train", "should i rest", "take a rest", "rest day",
            "acwr", "acute", "chronic", "workload ratio",
            "overreaching", "overtrained",
        ],
        Intent.PROGRESS_CHECK: [
            "am i on track", "on track", "how far", "gap to goal",
            "eta", "weight trend", "losing weight", "gaining weight",
            "body composition", "plateau",
        ],
        Intent.PLAN_GENERATION: [
            "create a plan", "make me a plan", "build a plan", "generate a plan",
            "training programme", "training program", "next 4 weeks", "next 8 weeks",
            "structured programme", "what should i do this week",
            "design a plan", "give me a plan",
        ],
        Intent.NUTRITION_CHECK: [
            "nutrition", "diet", "calories", "protein", "macros", "eating",
            "fasting", "food", "meal", "intake", "deficit", "surplus",
            "eat", "eating", "what should i eat", "fuelling", "fueling",
            "carbs", "fat intake", "calorie",
        ],
        # Legacy intents (broader fallbacks)
        Intent.RECENT_PERFORMANCE: [
            "recent", "last week", "this week", "latest", "yesterday",
            "today", "past few days", "last few days",
        ],
        Intent.TREND_ANALYSIS: [
            "trend", "over time", "improvement", "pattern",
            "change", "evolution", "history", "tracking",
        ],
        Intent.GOAL_PROGRESS: [
            "goal", "target", "objective", "aim", "milestone",
            "achievement", "reach", "accomplish",
        ],
        Intent.RECOVERY_STATUS: [
            "recovery", "rest", "tired", "fatigue", "fresh",
            "rested", "sore", "exhausted", "energy",
        ],
        Intent.TRAINING_PLAN: [
            "plan", "schedule", "upcoming", "next week", "future",
            "planned", "calendar", "coming",
        ],
        Intent.COMPARISON: [
            "compare", "versus", "vs", "difference", "better", "worse",
            "than", "against", "relative to",
        ],
    }

    def classify(self, query: str) -> Intent:
        """
        Classify query into an intent using keyword matching.

        Returns:
            Intent enum value (GENERAL if no keywords match)
        """
        query_lower = query.lower()
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return intent
        return Intent.GENERAL

    def tool_hint(self, intent: Intent) -> str | None:
        """Return the preferred tool name for an intent, or None for general."""
        return INTENT_TOOL_HINT.get(intent)

"""Intent classification for query routing in RAG system."""

from enum import Enum


class Intent(Enum):
    """Query intent types for targeted data retrieval."""
    
    RECENT_PERFORMANCE = "recent_performance"
    TREND_ANALYSIS = "trend_analysis"
    GOAL_PROGRESS = "goal_progress"
    RECOVERY_STATUS = "recovery_status"
    TRAINING_PLAN = "training_plan"
    COMPARISON = "comparison"
    GENERAL = "general"


class IntentRouter:
    """Classifies user queries into intents for targeted retrieval."""
    
    # Keyword mappings for each intent (priority order matters)
    INTENT_KEYWORDS = {
        Intent.RECENT_PERFORMANCE: [
            "recent", "last week", "this week", "latest", "yesterday",
            "today", "past few days", "last few days"
        ],
        Intent.TREND_ANALYSIS: [
            "trend", "over time", "progress", "improvement", "pattern",
            "change", "evolution", "history", "tracking"
        ],
        Intent.GOAL_PROGRESS: [
            "goal", "target", "objective", "aim", "milestone",
            "achievement", "reach", "accomplish"
        ],
        Intent.RECOVERY_STATUS: [
            "recovery", "rest", "tired", "fatigue", "fresh",
            "rested", "sore", "exhausted", "energy"
        ],
        Intent.TRAINING_PLAN: [
            "plan", "schedule", "upcoming", "next week", "future",
            "planned", "calendar", "next", "coming"
        ],
        Intent.COMPARISON: [
            "compare", "versus", "vs", "difference", "better", "worse",
            "than", "against", "relative to"
        ]
    }
    
    def classify(self, query: str) -> Intent:
        """
        Classify query into an intent using keyword matching.
        
        Args:
            query: User query string
            
        Returns:
            Intent enum value (GENERAL if no keywords match)
        """
        query_lower = query.lower()
        
        # Check each intent in priority order
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return intent
        
        # Fallback to general intent
        return Intent.GENERAL

"""Athlete Behavior Summary Generator

Generates condensed summaries of athlete training patterns, preferences, trends,
and past feedback for inclusion in chat context.

Target: 150-200 tokens per summary
Update frequency: Weekly (with caching, configurable TTL)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Protocol, runtime_checkable
from sqlalchemy.orm import Session
from sqlalchemy import desc
import tiktoken

from app.models.strava_activity import StravaActivity
from app.models.athlete_goal import AthleteGoal, GoalStatus
from app.models.evaluation import Evaluation


@runtime_checkable
class AthleteBehaviorSummaryProtocol(Protocol):
    """Protocol for athlete behavior summary generators.

    Allows easy substitution for testing without database dependencies.
    """

    def generate_summary(self, athlete_id: int, force_refresh: bool = False) -> str:
        """Generate athlete behavior summary."""
        ...

    def clear_cache(self, athlete_id: Optional[int] = None) -> None:
        """Clear cache for specific athlete or all athletes."""
        ...

    def set_cached_summary(self, athlete_id: int, summary: str) -> None:
        """Pre-populate cache with a summary (useful for testing)."""
        ...


class AthleteBehaviorSummary:
    """Generates athlete behavior summaries for chat context."""

    def __init__(self, db: Session, cache_ttl_days: int = 7):
        """
        Initialize athlete behavior summary generator.

        Args:
            db: SQLAlchemy database session
            cache_ttl_days: Number of days before cache expires (default: 7)
        """
        self.db = db
        self.cache_ttl_days = cache_ttl_days
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self._cache: Dict[int, Dict[str, Any]] = {}

    def generate_summary(
        self,
        athlete_id: int,
        force_refresh: bool = False
    ) -> str:
        """
        Generate athlete behavior summary.

        Args:
            athlete_id: Athlete ID
            force_refresh: Force cache refresh (default: False)

        Returns:
            Condensed summary string (150-200 tokens)
        """
        # Check cache first
        if not force_refresh and self._is_cache_valid(athlete_id):
            return self._cache[athlete_id]["summary"]

        # Gather data components
        activity_patterns = self._get_activity_patterns(athlete_id)
        training_preferences = self._get_training_preferences(athlete_id)
        recent_trends = self._get_recent_trends(athlete_id)
        past_feedback = self._get_past_feedback(athlete_id)
        active_goals = self._get_active_goals(athlete_id)

        # Build summary
        summary_parts = []

        # Activity patterns
        if activity_patterns:
            summary_parts.append(f"**Training Patterns**: {activity_patterns}")

        # Training preferences
        if training_preferences:
            summary_parts.append(f"**Preferences**: {training_preferences}")

        # Recent trends
        if recent_trends:
            summary_parts.append(f"**Recent Trends**: {recent_trends}")

        # Active goals
        if active_goals:
            summary_parts.append(f"**Active Goals**: {active_goals}")

        # Past feedback
        if past_feedback:
            summary_parts.append(f"**Past Feedback**: {past_feedback}")

        # Combine and condense
        full_summary = " | ".join(summary_parts)

        # Condense to target token range (150-200 tokens)
        condensed_summary = self._condense_to_token_budget(
            full_summary,
            min_tokens=150,
            max_tokens=200
        )

        # Update cache
        self._update_cache(athlete_id, condensed_summary)

        return condensed_summary

    def _get_activity_patterns(self, athlete_id: int) -> str:
        """
        Extract activity patterns from last 30 days.

        Returns:
            Summary of activity patterns (e.g., "runs 4x/week, prefers morning")
        """
        # Query activities from last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        activities = self.db.query(StravaActivity).filter(
            StravaActivity.athlete_id == athlete_id,
            StravaActivity.start_date >= thirty_days_ago
        ).all()

        if not activities:
            return ""

        # Calculate frequency by activity type
        activity_counts = {}
        time_of_day_counts = {"morning": 0, "afternoon": 0, "evening": 0}

        for activity in activities:
            # Count by type
            activity_type = activity.activity_type.lower()
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1

            # Determine time of day
            hour = activity.start_date.hour
            if 5 <= hour < 12:
                time_of_day_counts["morning"] += 1
            elif 12 <= hour < 17:
                time_of_day_counts["afternoon"] += 1
            else:
                time_of_day_counts["evening"] += 1

        # Build pattern description
        patterns = []

        # Most common activity type
        if activity_counts:
            most_common = max(activity_counts.items(), key=lambda x: x[1])
            activity_type, count = most_common
            weekly_avg = round(count * 7 / 30, 1)
            patterns.append(f"{activity_type} {weekly_avg}x/week")

        # Preferred time of day
        if time_of_day_counts:
            preferred_time = max(time_of_day_counts.items(), key=lambda x: x[1])[0]
            patterns.append(f"prefers {preferred_time}")

        return ", ".join(patterns)

    def _get_training_preferences(self, athlete_id: int) -> str:
        """
        Extract training preferences from activity history.

        Returns:
            Summary of preferences (e.g., "favors steady pace, avoids high intensity")
        """
        # Query recent activities (last 60 days for better preference detection)
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)

        activities = self.db.query(StravaActivity).filter(
            StravaActivity.athlete_id == athlete_id,
            StravaActivity.start_date >= sixty_days_ago
        ).all()

        if not activities:
            return ""

        preferences = []

        # Analyze distance preferences
        distances = [a.distance_m / 1000 for a in activities if a.distance_m]
        if distances:
            avg_distance = sum(distances) / len(distances)
            if avg_distance < 5:
                preferences.append("short distances")
            elif avg_distance < 15:
                preferences.append("medium distances")
            else:
                preferences.append("long distances")

        # Analyze heart rate patterns (if available)
        hr_activities = [a for a in activities if a.avg_hr and a.max_hr]
        if hr_activities:
            # Calculate average HR intensity (avg_hr / max_hr ratio)
            intensity_ratios = [a.avg_hr / a.max_hr for a in hr_activities]
            avg_intensity = sum(intensity_ratios) / len(intensity_ratios)

            if avg_intensity < 0.7:
                preferences.append("low-moderate intensity")
            elif avg_intensity < 0.85:
                preferences.append("moderate-high intensity")
            else:
                preferences.append("high intensity")

        return ", ".join(preferences) if preferences else ""

    def _get_recent_trends(self, athlete_id: int) -> str:
        """
        Identify recent trends in volume and intensity.

        Returns:
            Summary of trends (e.g., "increasing volume steadily, stable intensity")
        """
        # Query activities from last 60 days, grouped by week
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)

        activities = self.db.query(StravaActivity).filter(
            StravaActivity.athlete_id == athlete_id,
            StravaActivity.start_date >= sixty_days_ago
        ).order_by(StravaActivity.start_date).all()

        if len(activities) < 4:  # Need at least 4 activities to detect trends
            return ""

        # Split into two periods: first half and second half
        mid_point = len(activities) // 2
        first_half = activities[:mid_point]
        second_half = activities[mid_point:]

        trends = []

        # Volume trend (total distance)
        first_volume = sum(a.distance_m or 0 for a in first_half) / 1000
        second_volume = sum(a.distance_m or 0 for a in second_half) / 1000

        if second_volume > first_volume * 1.15:
            trends.append("increasing volume")
        elif second_volume < first_volume * 0.85:
            trends.append("decreasing volume")
        else:
            trends.append("stable volume")

        # Intensity trend (average heart rate)
        first_hr = [a.avg_hr for a in first_half if a.avg_hr]
        second_hr = [a.avg_hr for a in second_half if a.avg_hr]

        if first_hr and second_hr:
            avg_first_hr = sum(first_hr) / len(first_hr)
            avg_second_hr = sum(second_hr) / len(second_hr)

            if avg_second_hr > avg_first_hr * 1.05:
                trends.append("increasing intensity")
            elif avg_second_hr < avg_first_hr * 0.95:
                trends.append("decreasing intensity")
            else:
                trends.append("stable intensity")

        return ", ".join(trends)

    def _get_past_feedback(self, athlete_id: int) -> str:
        """
        Extract past feedback from evaluations.

        Returns:
            Summary of feedback (e.g., "responds well to structured plans")
        """
        # Query recent evaluations (last 90 days)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)

        evaluations = self.db.query(Evaluation).filter(
            Evaluation.athlete_id == athlete_id,
            Evaluation.created_at >= ninety_days_ago
        ).order_by(desc(Evaluation.created_at)).limit(3).all()

        if not evaluations:
            return ""

        feedback_items = []

        # Extract key strengths from most recent evaluation
        if evaluations and evaluations[0].strengths:
            strengths = evaluations[0].strengths
            if isinstance(strengths, list) and strengths:
                # Take first strength as representative
                feedback_items.append(strengths[0])

        # Extract improvement areas from most recent evaluation
        if evaluations and evaluations[0].improvements:
            improvements = evaluations[0].improvements
            if isinstance(improvements, list) and improvements:
                # Take first improvement as representative
                feedback_items.append(f"working on: {improvements[0]}")

        # Condense to avoid verbosity
        if len(feedback_items) > 2:
            feedback_items = feedback_items[:2]

        return "; ".join(feedback_items) if feedback_items else ""

    def _get_active_goals(self, athlete_id: int) -> str:
        """
        Get active goals summary.

        Returns:
            Summary of active goals (e.g., "targeting marathon in 3 months")
        """
        # Query active goals
        goals = self.db.query(AthleteGoal).filter(
            AthleteGoal.athlete_id == str(athlete_id),
            AthleteGoal.status == GoalStatus.ACTIVE.value
        ).order_by(AthleteGoal.target_date).limit(2).all()

        if not goals:
            return ""

        goal_summaries = []
        for goal in goals:
            # Extract key info
            goal_type = goal.goal_type.replace("_", " ")

            # Add time context if target date exists
            if goal.target_date:
                days_until = (goal.target_date - datetime.utcnow().date()).days
                if days_until > 0:
                    if days_until < 30:
                        time_context = f"in {days_until} days"
                    elif days_until < 90:
                        weeks = days_until // 7
                        time_context = f"in {weeks} weeks"
                    else:
                        months = days_until // 30
                        time_context = f"in {months} months"

                    goal_summaries.append(f"{goal_type} {time_context}")
                else:
                    goal_summaries.append(f"{goal_type} (overdue)")
            else:
                goal_summaries.append(goal_type)

        return ", ".join(goal_summaries)

    def _condense_to_token_budget(
        self,
        text: str,
        min_tokens: int = 150,
        max_tokens: int = 200
    ) -> str:
        """
        Condense text to fit within token budget.

        Args:
            text: Input text
            min_tokens: Minimum token count
            max_tokens: Maximum token count

        Returns:
            Condensed text within token budget
        """
        tokens = self.encoding.encode(text)
        token_count = len(tokens)

        # If within budget, return as-is
        if min_tokens <= token_count <= max_tokens:
            return text

        # If too short, return as-is (can't expand)
        if token_count < min_tokens:
            return text

        # If too long, truncate to max_tokens
        if token_count > max_tokens:
            truncated_tokens = tokens[:max_tokens]
            truncated_text = self.encoding.decode(truncated_tokens)

            # Try to end at a sentence or phrase boundary
            for delimiter in [". ", " | ", ", "]:
                last_delimiter = truncated_text.rfind(delimiter)
                if last_delimiter > len(truncated_text) * 0.8:  # Keep at least 80%
                    return truncated_text[:last_delimiter + len(delimiter)].strip()

            return truncated_text.strip()

        return text

    def _is_cache_valid(self, athlete_id: int) -> bool:
        """
        Check if cached summary is still valid.

        Cache is valid for cache_ttl_days (default: 7 days, weekly update frequency).

        Args:
            athlete_id: Athlete ID

        Returns:
            True if cache is valid, False otherwise
        """
        if athlete_id not in self._cache:
            return False

        cache_entry = self._cache[athlete_id]
        cache_age = datetime.utcnow() - cache_entry["timestamp"]

        # Cache valid for configured TTL
        return cache_age.days < self.cache_ttl_days

    def _update_cache(self, athlete_id: int, summary: str) -> None:
        """
        Update cache with new summary.

        Args:
            athlete_id: Athlete ID
            summary: Generated summary
        """
        self._cache[athlete_id] = {
            "summary": summary,
            "timestamp": datetime.utcnow()
        }

    def clear_cache(self, athlete_id: Optional[int] = None) -> None:
        """
        Clear cache for specific athlete or all athletes.

        Args:
            athlete_id: Athlete ID to clear (None = clear all)
        """
        if athlete_id is None:
            self._cache.clear()
        elif athlete_id in self._cache:
            del self._cache[athlete_id]

    def set_cached_summary(self, athlete_id: int, summary: str) -> None:
        """
        Pre-populate cache with a summary.

        Useful for testing or injecting pre-computed summaries
        without requiring database access.

        Args:
            athlete_id: Athlete ID
            summary: Pre-computed summary string
        """
        self._update_cache(athlete_id, summary)


def generate_summary(athlete_id: int, db: Session) -> str:
    """
    Convenience function to generate athlete behavior summary.

    Args:
        athlete_id: Athlete ID
        db: SQLAlchemy database session

    Returns:
        Condensed summary string (150-200 tokens)
    """
    generator = AthleteBehaviorSummary(db)
    return generator.generate_summary(athlete_id)

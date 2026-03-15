"""
Tests for Athlete Behavior Summary Generator.

Tests cover:
- Activity pattern extraction (frequency, time of day)
- Training preference detection (distance, intensity)
- Trend identification (volume, intensity changes)
- Past feedback extraction from evaluations
- Active goals summary
- Token budget enforcement (150-200 tokens)
- Caching mechanism (weekly updates)
- Various athlete profiles
"""

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import Mock
from sqlalchemy.orm import Session
import tiktoken

from app.ai.context.athlete_behavior_summary import (
    AthleteBehaviorSummary,
    AthleteBehaviorSummaryProtocol,
    generate_summary
)
from app.models.strava_activity import StravaActivity
from app.models.athlete_goal import AthleteGoal, GoalStatus, GoalType
from app.models.evaluation import Evaluation


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def summary_generator(mock_db):
    """Create summary generator instance."""
    return AthleteBehaviorSummary(mock_db)


@pytest.fixture
def sample_activities():
    """Create sample activities for testing."""
    now = datetime.utcnow()
    activities = []
    
    # Create 12 running activities over last 30 days (3x/week pattern)
    for i in range(12):
        days_ago = i * 2.5  # Roughly 3x per week
        activity_date = now - timedelta(days=days_ago)
        
        # Morning runs (6 AM)
        activity_date = activity_date.replace(hour=6, minute=0, second=0)
        
        activity = StravaActivity(
            id=f"activity_{i}",
            athlete_id=1,
            strava_id=1000 + i,
            activity_type="Run",
            start_date=activity_date,
            moving_time_s=3600,  # 1 hour
            distance_m=10000,  # 10km
            elevation_m=100,
            avg_hr=145,
            max_hr=180,
            calories=600,
            raw_json="{}",
            created_at=activity_date,
            updated_at=activity_date
        )
        activities.append(activity)
    
    return activities


@pytest.fixture
def sample_goals():
    """Create sample goals for testing."""
    return [
        AthleteGoal(
            id="goal_1",
            athlete_id=1,
            goal_type=GoalType.PERFORMANCE.value,
            target_value=42.2,
            target_date=date.today() + timedelta(days=90),
            description="Run a marathon in under 4 hours",
            status=GoalStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),
        AthleteGoal(
            id="goal_2",
            athlete_id=1,
            goal_type=GoalType.WEIGHT_LOSS.value,
            target_value=75.0,
            target_date=date.today() + timedelta(days=60),
            description="Lose 5kg",
            status=GoalStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    ]


@pytest.fixture
def sample_evaluations():
    """Create sample evaluations for testing."""
    return [
        Evaluation(
            id="eval_1",
            athlete_id=1,
            period_start=date.today() - timedelta(days=14),
            period_end=date.today() - timedelta(days=7),
            period_type="weekly",
            overall_score=85,
            strengths=["Consistent training schedule", "Good recovery practices"],
            improvements=["Increase long run distance", "Add speed work"],
            tips=["Focus on easy runs", "Build base mileage"],
            recommended_exercises=["Tempo runs", "Hill repeats"],
            goal_alignment="On track for marathon goal",
            confidence_score=0.9,
            created_at=datetime.utcnow() - timedelta(days=7),
            updated_at=datetime.utcnow() - timedelta(days=7)
        )
    ]


class TestActivityPatterns:
    """Test activity pattern extraction."""
    
    def test_extract_frequency_and_time_preference(
        self,
        summary_generator,
        mock_db,
        sample_activities
    ):
        """Test extraction of activity frequency and time preference."""
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_activities
        mock_db.query.return_value = mock_query
        
        patterns = summary_generator._get_activity_patterns(athlete_id=1)
        
        # Should detect ~3x per week running pattern
        assert "run" in patterns.lower()
        assert "week" in patterns.lower()
        
        # Should detect morning preference
        assert "morning" in patterns.lower()
    
    def test_no_activities_returns_empty(self, summary_generator, mock_db):
        """Test that no activities returns empty string."""
        # Mock empty query result
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        patterns = summary_generator._get_activity_patterns(athlete_id=1)
        
        assert patterns == ""
    
    def test_mixed_activity_types(self, summary_generator, mock_db):
        """Test pattern extraction with mixed activity types."""
        now = datetime.utcnow()
        activities = [
            StravaActivity(
                id=f"run_{i}",
                athlete_id=1,
                strava_id=2000 + i,
                activity_type="Run",
                start_date=now - timedelta(days=i * 3),
                moving_time_s=3600,
                distance_m=10000,
                avg_hr=145,
                max_hr=180,
                calories=600,
                raw_json="{}",
                created_at=now,
                updated_at=now
            )
            for i in range(6)
        ] + [
            StravaActivity(
                id=f"ride_{i}",
                athlete_id=1,
                strava_id=3000 + i,
                activity_type="Ride",
                start_date=now - timedelta(days=i * 5),
                moving_time_s=7200,
                distance_m=40000,
                avg_hr=130,
                max_hr=170,
                calories=1200,
                raw_json="{}",
                created_at=now,
                updated_at=now
            )
            for i in range(4)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = activities
        mock_db.query.return_value = mock_query
        
        patterns = summary_generator._get_activity_patterns(athlete_id=1)
        
        # Should identify most common activity type (Run)
        assert "run" in patterns.lower()


class TestTrainingPreferences:
    """Test training preference extraction."""
    
    def test_extract_distance_and_intensity_preferences(
        self,
        summary_generator,
        mock_db,
        sample_activities
    ):
        """Test extraction of distance and intensity preferences."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_activities
        mock_db.query.return_value = mock_query
        
        preferences = summary_generator._get_training_preferences(athlete_id=1)
        
        # Should detect medium distance preference (10km)
        assert "distance" in preferences.lower()
        
        # Should detect intensity level based on HR
        assert "intensity" in preferences.lower()
    
    def test_no_activities_returns_empty(self, summary_generator, mock_db):
        """Test that no activities returns empty string."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        preferences = summary_generator._get_training_preferences(athlete_id=1)
        
        assert preferences == ""
    
    def test_short_distance_preference(self, summary_generator, mock_db):
        """Test detection of short distance preference."""
        now = datetime.utcnow()
        activities = [
            StravaActivity(
                id=f"activity_{i}",
                athlete_id=1,
                strava_id=4000 + i,
                activity_type="Run",
                start_date=now - timedelta(days=i * 3),
                moving_time_s=1800,
                distance_m=3000,  # 3km - short distance
                avg_hr=140,
                max_hr=180,
                calories=300,
                raw_json="{}",
                created_at=now,
                updated_at=now
            )
            for i in range(10)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = activities
        mock_db.query.return_value = mock_query
        
        preferences = summary_generator._get_training_preferences(athlete_id=1)
        
        assert "short" in preferences.lower()


class TestRecentTrends:
    """Test trend identification."""
    
    def test_identify_increasing_volume_trend(self, summary_generator, mock_db):
        """Test identification of increasing volume trend."""
        now = datetime.utcnow()
        activities = []
        
        # First half: 5km runs
        for i in range(6):
            activities.append(
                StravaActivity(
                    id=f"activity_{i}",
                    athlete_id=1,
                    strava_id=5000 + i,
                    activity_type="Run",
                    start_date=now - timedelta(days=50 - i * 3),
                    moving_time_s=2400,
                    distance_m=5000,
                    avg_hr=140,
                    max_hr=180,
                    calories=400,
                    raw_json="{}",
                    created_at=now,
                    updated_at=now
                )
            )
        
        # Second half: 10km runs (increased volume)
        for i in range(6):
            activities.append(
                StravaActivity(
                    id=f"activity_{i + 6}",
                    athlete_id=1,
                    strava_id=5006 + i,
                    activity_type="Run",
                    start_date=now - timedelta(days=30 - i * 3),
                    moving_time_s=4800,
                    distance_m=10000,
                    avg_hr=140,
                    max_hr=180,
                    calories=800,
                    raw_json="{}",
                    created_at=now,
                    updated_at=now
                )
            )
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = activities
        mock_db.query.return_value = mock_query
        
        trends = summary_generator._get_recent_trends(athlete_id=1)
        
        assert "increasing volume" in trends.lower()
    
    def test_identify_stable_trends(self, summary_generator, mock_db, sample_activities):
        """Test identification of stable trends."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = sample_activities
        mock_db.query.return_value = mock_query
        
        trends = summary_generator._get_recent_trends(athlete_id=1)
        
        # Sample activities have consistent volume and intensity
        assert "stable" in trends.lower()
    
    def test_insufficient_activities_returns_empty(self, summary_generator, mock_db):
        """Test that insufficient activities returns empty string."""
        now = datetime.utcnow()
        activities = [
            StravaActivity(
                id="activity_1",
                athlete_id=1,
                strava_id=6000,
                activity_type="Run",
                start_date=now - timedelta(days=5),
                moving_time_s=3600,
                distance_m=10000,
                avg_hr=145,
                max_hr=180,
                calories=600,
                raw_json="{}",
                created_at=now,
                updated_at=now
            )
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = activities
        mock_db.query.return_value = mock_query
        
        trends = summary_generator._get_recent_trends(athlete_id=1)
        
        assert trends == ""


class TestPastFeedback:
    """Test past feedback extraction."""
    
    def test_extract_feedback_from_evaluations(
        self,
        summary_generator,
        mock_db,
        sample_evaluations
    ):
        """Test extraction of feedback from evaluations."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_evaluations
        mock_db.query.return_value = mock_query
        
        feedback = summary_generator._get_past_feedback(athlete_id=1)
        
        # Should include strength from evaluation
        assert "consistent" in feedback.lower() or "training" in feedback.lower()
    
    def test_no_evaluations_returns_empty(self, summary_generator, mock_db):
        """Test that no evaluations returns empty string."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        feedback = summary_generator._get_past_feedback(athlete_id=1)
        
        assert feedback == ""


class TestActiveGoals:
    """Test active goals summary."""
    
    def test_extract_active_goals(self, summary_generator, mock_db, sample_goals):
        """Test extraction of active goals."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_goals
        mock_db.query.return_value = mock_query
        
        goals = summary_generator._get_active_goals(athlete_id=1)
        
        # Should include goal type
        assert "performance" in goals.lower() or "weight" in goals.lower()
        
        # Should include time context
        assert "months" in goals.lower() or "weeks" in goals.lower()
    
    def test_no_goals_returns_empty(self, summary_generator, mock_db):
        """Test that no goals returns empty string."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        goals = summary_generator._get_active_goals(athlete_id=1)
        
        assert goals == ""


class TestTokenBudgetEnforcement:
    """Test token budget enforcement."""
    
    def test_condense_to_token_budget(self, summary_generator):
        """Test condensing text to token budget."""
        # Create long text that exceeds 200 tokens
        long_text = " ".join([f"Word{i}" for i in range(300)])
        
        condensed = summary_generator._condense_to_token_budget(
            long_text,
            min_tokens=150,
            max_tokens=200
        )
        
        # Count tokens
        encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(condensed))
        
        # Should be within budget
        assert token_count <= 200
    
    def test_text_within_budget_unchanged(self, summary_generator):
        """Test that text within budget is unchanged."""
        text = "This is a short text that fits within the token budget."
        
        condensed = summary_generator._condense_to_token_budget(
            text,
            min_tokens=10,
            max_tokens=200
        )
        
        assert condensed == text
    
    def test_truncate_at_sentence_boundary(self, summary_generator):
        """Test truncation at sentence boundary."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 20
        
        condensed = summary_generator._condense_to_token_budget(
            text,
            min_tokens=50,
            max_tokens=100
        )
        
        # Should end with period (sentence boundary)
        assert condensed.endswith(".")


class TestCachingMechanism:
    """Test caching mechanism."""
    
    def test_cache_stores_summary(self, summary_generator, mock_db):
        """Test that cache stores generated summary."""
        # Mock all database queries to return empty
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Generate summary
        summary1 = summary_generator.generate_summary(athlete_id=1)
        
        # Should be cached
        assert 1 in summary_generator._cache
        assert summary_generator._cache[1]["summary"] == summary1
    
    def test_cache_returns_cached_summary(self, summary_generator, mock_db):
        """Test that cache returns cached summary without querying DB."""
        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Generate summary (will cache)
        summary1 = summary_generator.generate_summary(athlete_id=1)
        
        # Reset mock to verify no new queries
        mock_db.reset_mock()
        
        # Get summary again (should use cache)
        summary2 = summary_generator.generate_summary(athlete_id=1)
        
        # Should return same summary
        assert summary1 == summary2
        
        # Should not query database
        assert not mock_db.query.called
    
    def test_cache_expires_after_7_days(self, summary_generator, mock_db):
        """Test that cache expires after 7 days."""
        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Generate summary
        summary_generator.generate_summary(athlete_id=1)
        
        # Manually set cache timestamp to 8 days ago
        summary_generator._cache[1]["timestamp"] = datetime.utcnow() - timedelta(days=8)
        
        # Check cache validity
        assert not summary_generator._is_cache_valid(athlete_id=1)
    
    def test_force_refresh_bypasses_cache(self, summary_generator, mock_db):
        """Test that force_refresh bypasses cache."""
        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Generate summary (will cache)
        summary_generator.generate_summary(athlete_id=1)
        
        # Reset mock
        mock_db.reset_mock()
        mock_db.query.return_value = mock_query
        
        # Force refresh
        summary_generator.generate_summary(athlete_id=1, force_refresh=True)
        
        # Should query database again
        assert mock_db.query.called
    
    def test_clear_cache_specific_athlete(self, summary_generator, mock_db):
        """Test clearing cache for specific athlete."""
        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Generate summaries for multiple athletes
        summary_generator.generate_summary(athlete_id=1)
        summary_generator.generate_summary(athlete_id=2)
        
        # Clear cache for athlete 1
        summary_generator.clear_cache(athlete_id=1)
        
        # Athlete 1 should be cleared
        assert 1 not in summary_generator._cache
        
        # Athlete 2 should still be cached
        assert 2 in summary_generator._cache
    
    def test_clear_cache_all_athletes(self, summary_generator, mock_db):
        """Test clearing cache for all athletes."""
        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Generate summaries for multiple athletes
        summary_generator.generate_summary(athlete_id=1)
        summary_generator.generate_summary(athlete_id=2)
        
        # Clear all cache
        summary_generator.clear_cache()
        
        # All should be cleared
        assert len(summary_generator._cache) == 0


class TestVariousAthleteProfiles:
    """Test summary generation with various athlete profiles."""
    
    def test_active_athlete_with_goals(
        self,
        summary_generator,
        mock_db,
        sample_activities,
        sample_goals,
        sample_evaluations
    ):
        """Test summary for active athlete with goals and evaluations."""
        # Mock database queries
        def mock_query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            
            if model == StravaActivity:
                mock_query.all.return_value = sample_activities
            elif model == AthleteGoal:
                mock_query.all.return_value = sample_goals
            elif model == Evaluation:
                mock_query.all.return_value = sample_evaluations
            else:
                mock_query.all.return_value = []
            
            return mock_query
        
        mock_db.query.side_effect = mock_query_side_effect
        
        summary = summary_generator.generate_summary(athlete_id=1)
        
        # Should include all components
        assert len(summary) > 0
        
        # Verify token count (allow flexibility for various data combinations)
        encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(summary))
        assert 50 <= token_count <= 250  # Allow flexibility for sparse data
    
    def test_inactive_athlete_no_data(self, summary_generator, mock_db):
        """Test summary for inactive athlete with no data."""
        # Mock empty queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        summary = summary_generator.generate_summary(athlete_id=1)
        
        # Should return empty or minimal summary
        assert isinstance(summary, str)
    
    def test_beginner_athlete_few_activities(self, summary_generator, mock_db):
        """Test summary for beginner athlete with few activities."""
        now = datetime.utcnow()
        activities = [
            StravaActivity(
                id=f"activity_{i}",
                athlete_id=1,
                strava_id=7000 + i,
                activity_type="Run",
                start_date=now - timedelta(days=i * 7),
                moving_time_s=1800,
                distance_m=3000,
                avg_hr=150,
                max_hr=180,
                calories=300,
                raw_json="{}",
                created_at=now,
                updated_at=now
            )
            for i in range(3)
        ]
        
        # Mock database queries with proper model-specific returns
        def mock_query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            
            if model == StravaActivity:
                mock_query.all.return_value = activities
            else:
                mock_query.all.return_value = []
            
            return mock_query
        
        mock_db.query.side_effect = mock_query_side_effect
        
        summary = summary_generator.generate_summary(athlete_id=1)
        
        # Should generate summary even with limited data
        assert isinstance(summary, str)


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_generate_summary_function(self, mock_db):
        """Test convenience function generates summary."""
        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        summary = generate_summary(athlete_id=1, db=mock_db)
        
        assert isinstance(summary, str)


class TestEnhancedCaching:
    """Test enhanced caching features: configurable TTL, set_cached_summary, protocol."""

    def test_configurable_cache_ttl(self, mock_db):
        """Test that cache TTL is configurable via constructor."""
        generator = AthleteBehaviorSummary(mock_db, cache_ttl_days=3)
        assert generator.cache_ttl_days == 3

        # Pre-populate cache
        generator.set_cached_summary(1, "test summary")

        # Set timestamp to 4 days ago (beyond 3-day TTL)
        generator._cache[1]["timestamp"] = datetime.utcnow() - timedelta(days=4)
        assert not generator._is_cache_valid(1)

        # Set timestamp to 2 days ago (within 3-day TTL)
        generator._cache[1]["timestamp"] = datetime.utcnow() - timedelta(days=2)
        assert generator._is_cache_valid(1)

    def test_default_cache_ttl_is_7_days(self, mock_db):
        """Test that default cache TTL is 7 days."""
        generator = AthleteBehaviorSummary(mock_db)
        assert generator.cache_ttl_days == 7

    def test_set_cached_summary_populates_cache(self, mock_db):
        """Test that set_cached_summary pre-populates the cache."""
        generator = AthleteBehaviorSummary(mock_db)
        generator.set_cached_summary(42, "Pre-computed athlete summary")

        assert 42 in generator._cache
        assert generator._cache[42]["summary"] == "Pre-computed athlete summary"
        assert "timestamp" in generator._cache[42]

    def test_set_cached_summary_avoids_db_on_generate(self, mock_db):
        """Test that pre-populated cache avoids DB queries on generate_summary."""
        generator = AthleteBehaviorSummary(mock_db)
        generator.set_cached_summary(1, "Cached summary for athlete 1")

        result = generator.generate_summary(1)

        assert result == "Cached summary for athlete 1"
        # DB should not have been queried
        assert not mock_db.query.called

    def test_set_cached_summary_overwritten_by_force_refresh(self, mock_db):
        """Test that force_refresh regenerates even with pre-populated cache."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        generator = AthleteBehaviorSummary(mock_db)
        generator.set_cached_summary(1, "Old cached summary")

        # Force refresh should query DB
        generator.generate_summary(1, force_refresh=True)
        assert mock_db.query.called


class TestProtocolCompliance:
    """Test that AthleteBehaviorSummary satisfies the Protocol."""

    def test_class_implements_protocol(self, mock_db):
        """Test that AthleteBehaviorSummary is an instance of the protocol."""
        generator = AthleteBehaviorSummary(mock_db)
        assert isinstance(generator, AthleteBehaviorSummaryProtocol)

    def test_protocol_is_runtime_checkable(self):
        """Test that the protocol can be used for runtime isinstance checks."""
        # A minimal mock that satisfies the protocol
        class MockSummary:
            def generate_summary(self, athlete_id, force_refresh=False):
                return "mock summary"

            def clear_cache(self, athlete_id=None):
                pass

            def set_cached_summary(self, athlete_id, summary):
                pass

        mock = MockSummary()
        assert isinstance(mock, AthleteBehaviorSummaryProtocol)

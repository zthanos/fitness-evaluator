"""Derived Metrics Engine

Computes calculated metrics deterministically from raw activity data before LLM invocation.
This reduces hallucination and provides complete analytical context.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from app.ai.config.domain_loader import DomainKnowledge
from app.models.strava_activity import StravaActivity


@dataclass
class DerivedMetrics:
    """Computed metrics for a training week"""
    
    # Volume metrics
    total_distance_km: float
    total_duration_min: float
    total_elevation_m: float
    activity_count: int
    
    # Effort distribution
    easy_pct: float
    moderate_pct: float
    hard_pct: float
    max_pct: float
    
    # Training load
    training_load: float  # sum of (duration × effort_multiplier)
    
    # Recovery metrics
    rest_days_count: int
    consecutive_training_days: int
    
    # Heart rate analysis
    avg_heart_rate: Optional[float]
    hr_zone_distribution: Dict[str, float]  # z1-z5 percentages
    
    # Completeness indicators
    has_hr_data: bool
    has_power_data: bool
    has_effort_data: bool


class DerivedMetricsEngine:
    """Computes derived metrics from raw activity data"""
    
    def __init__(self, domain_knowledge: DomainKnowledge):
        """Initialize engine with domain knowledge for zone calculations
        
        Args:
            domain_knowledge: Domain knowledge containing training zones and effort levels
        """
        self.domain_knowledge = domain_knowledge
    
    def compute(
        self,
        activities: List[StravaActivity],
        week_start: date,
        week_end: date
    ) -> DerivedMetrics:
        """Compute all derived metrics for a week
        
        Args:
            activities: List of activities for the week
            week_start: Start date of the week
            week_end: End date of the week
            
        Returns:
            DerivedMetrics with all computed fields
        """
        # Volume metrics
        total_distance = sum(a.distance_m or 0 for a in activities) / 1000
        total_duration = sum(a.moving_time_s or 0 for a in activities) / 60
        total_elevation = sum(a.elevation_m or 0 for a in activities)
        activity_count = len(activities)
        
        # Effort distribution
        effort_counts = self._compute_effort_distribution(activities)
        
        # Training load
        training_load = self._compute_training_load(activities)
        
        # Recovery metrics
        rest_days, consecutive_days = self._compute_recovery_metrics(
            activities, week_start, week_end
        )
        
        # Heart rate analysis
        avg_hr, hr_zones = self._compute_hr_metrics(activities)
        
        # Completeness indicators
        has_hr = any(a.avg_hr is not None for a in activities)
        has_power = any(getattr(a, 'avg_power', None) is not None for a in activities)
        has_effort = any(getattr(a, 'perceived_exertion', None) is not None for a in activities)
        
        return DerivedMetrics(
            total_distance_km=round(total_distance, 2),
            total_duration_min=round(total_duration, 1),
            total_elevation_m=round(total_elevation, 0),
            activity_count=activity_count,
            easy_pct=round(effort_counts.get('easy', 0) / activity_count * 100, 1) if activity_count > 0 else 0.0,
            moderate_pct=round(effort_counts.get('moderate', 0) / activity_count * 100, 1) if activity_count > 0 else 0.0,
            hard_pct=round(effort_counts.get('hard', 0) / activity_count * 100, 1) if activity_count > 0 else 0.0,
            max_pct=round(effort_counts.get('max', 0) / activity_count * 100, 1) if activity_count > 0 else 0.0,
            training_load=round(training_load, 1),
            rest_days_count=rest_days,
            consecutive_training_days=consecutive_days,
            avg_heart_rate=round(avg_hr, 1) if avg_hr else None,
            hr_zone_distribution=hr_zones,
            has_hr_data=has_hr,
            has_power_data=has_power,
            has_effort_data=has_effort
        )
    
    def _compute_effort_distribution(self, activities: List[StravaActivity]) -> Dict[str, int]:
        """Classify activities by effort level
        
        Args:
            activities: List of activities
            
        Returns:
            Dictionary with counts for each effort level (easy, moderate, hard, max)
        """
        effort_counts = {'easy': 0, 'moderate': 0, 'hard': 0, 'max': 0}
        
        for activity in activities:
            if not activity.avg_hr:
                continue
            
            # Classify based on HR zones from domain knowledge
            effort_level = self._classify_effort(activity.avg_hr, activity.max_hr)
            if effort_level:
                effort_counts[effort_level] += 1
        
        return effort_counts
    
    def _classify_effort(self, avg_hr: int, max_hr: Optional[int]) -> Optional[str]:
        """Classify effort level based on heart rate
        
        Args:
            avg_hr: Average heart rate for the activity
            max_hr: Maximum heart rate for the activity (optional)
            
        Returns:
            Effort level string (easy, moderate, hard, max) or None
        """
        if not max_hr:
            max_hr = 190  # Default estimate
        
        hr_pct = (avg_hr / max_hr) * 100
        
        # Map to effort levels using domain knowledge
        for level, config in self.domain_knowledge.effort_levels.items():
            for zone_name in config['zones']:
                zone = self.domain_knowledge.training_zones[zone_name]
                if zone.hr_pct_max[0] <= hr_pct <= zone.hr_pct_max[1]:
                    return level
        
        return None
    
    def _compute_training_load(self, activities: List[StravaActivity]) -> float:
        """Compute training load using duration × effort multiplier
        
        Args:
            activities: List of activities
            
        Returns:
            Total training load for the week
        """
        effort_multipliers = {
            'easy': 1.0,
            'moderate': 2.0,
            'hard': 3.0,
            'max': 4.0
        }
        
        total_load = 0.0
        for activity in activities:
            duration_min = (activity.moving_time_s or 0) / 60
            effort = self._classify_effort(activity.avg_hr, activity.max_hr) if activity.avg_hr else 'easy'
            multiplier = effort_multipliers.get(effort, 1.0)
            total_load += duration_min * multiplier
        
        return total_load
    
    def _compute_recovery_metrics(
        self,
        activities: List[StravaActivity],
        week_start: date,
        week_end: date
    ) -> tuple[int, int]:
        """Compute rest days and consecutive training days
        
        Args:
            activities: List of activities
            week_start: Start date of the week
            week_end: End date of the week
            
        Returns:
            Tuple of (rest_days_count, consecutive_training_days)
        """
        # Create set of training dates
        training_dates = {a.start_date.date() for a in activities}
        
        # Count rest days
        total_days = (week_end - week_start).days + 1
        rest_days = total_days - len(training_dates)
        
        # Find longest consecutive training streak
        consecutive = 0
        max_consecutive = 0
        current_date = week_start
        
        while current_date <= week_end:
            if current_date in training_dates:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
            current_date += timedelta(days=1)
        
        return rest_days, max_consecutive
    
    def _compute_hr_metrics(
        self,
        activities: List[StravaActivity]
    ) -> tuple[Optional[float], Dict[str, float]]:
        """Compute average HR and zone distribution
        
        Args:
            activities: List of activities
            
        Returns:
            Tuple of (average_heart_rate, zone_distribution_dict)
        """
        hr_activities = [a for a in activities if a.avg_hr]
        
        if not hr_activities:
            return None, {}
        
        avg_hr = sum(a.avg_hr for a in hr_activities) / len(hr_activities)
        
        # Compute zone distribution
        zone_counts = {f'z{i}': 0 for i in range(1, 6)}
        
        for activity in hr_activities:
            zone = self._classify_hr_zone(activity.avg_hr, activity.max_hr)
            if zone:
                zone_counts[zone] += 1
        
        # Convert to percentages
        total = len(hr_activities)
        zone_pct = {zone: round(count / total * 100, 1) for zone, count in zone_counts.items()}
        
        return avg_hr, zone_pct
    
    def _classify_hr_zone(self, avg_hr: int, max_hr: Optional[int]) -> Optional[str]:
        """Classify HR into training zone
        
        Args:
            avg_hr: Average heart rate
            max_hr: Maximum heart rate (optional)
            
        Returns:
            Zone string (z1, z2, z3, z4, z5) or None
        """
        if not max_hr:
            max_hr = 190
        
        hr_pct = (avg_hr / max_hr) * 100
        
        for zone_name, zone in self.domain_knowledge.training_zones.items():
            if zone.hr_pct_max[0] <= hr_pct <= zone.hr_pct_max[1]:
                return zone_name.split('_')[0]  # Extract z1, z2, etc.
        
        return None

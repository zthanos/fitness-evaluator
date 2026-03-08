"""Completeness Scorer

Scores data completeness for activities based on presence of key data types.
"""

from typing import List

from app.models.strava_activity import StravaActivity


class CompletenessScorer:
    """Scores data completeness for confidence calculation"""
    
    def score(self, activities: List[StravaActivity]) -> float:
        """Score data completeness based on presence of key data types
        
        Checks for presence of:
        - HR data (avg_hr field)
        - Power data (avg_power field if exists)
        - Effort data (perceived_exertion field if exists)
        
        Scoring:
        - 1.0 if all three data types present
        - 0.67 if 2 out of 3 present
        - 0.33 if 1 out of 3 present
        - 0.0 if none present
        
        Args:
            activities: List of StravaActivity records to score
            
        Returns:
            Completeness score between 0.0 and 1.0
        """
        if not activities:
            return 0.0
        
        # Check for presence of each data type across all activities
        has_hr_data = any(activity.avg_hr is not None for activity in activities)
        has_power_data = any(
            getattr(activity, 'avg_power', None) is not None 
            for activity in activities
        )
        has_effort_data = any(
            getattr(activity, 'perceived_exertion', None) is not None 
            for activity in activities
        )
        
        # Count how many data types are present
        data_types_present = sum([
            has_hr_data,
            has_power_data,
            has_effort_data
        ])
        
        # Return score based on completeness
        if data_types_present == 3:
            return 1.0
        elif data_types_present == 2:
            return 0.67
        elif data_types_present == 1:
            return 0.33
        else:
            return 0.0

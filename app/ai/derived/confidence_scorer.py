"""Confidence Scorer

Computes system-based confidence scores for AI responses based on data quality metrics.
"""

from datetime import date, datetime
from typing import List, Dict, Any

from app.ai.context.builder import Context
from app.ai.derived.metrics_engine import DerivedMetrics


class ConfidenceScorer:
    """Computes system-based confidence scores for AI responses"""
    
    def compute_system_confidence(
        self,
        context: Context,
        metrics: DerivedMetrics
    ) -> float:
        """Compute system confidence score based on data quality
        
        Computes a weighted confidence score based on:
        - Data completeness (40% weight): presence of HR, power, effort data
        - Data recency (30% weight): days since last activity
        - Retrieval quality (30% weight): number of evidence cards
        
        Args:
            context: Context object containing retrieved data
            metrics: DerivedMetrics with completeness indicators
            
        Returns:
            System confidence score between 0.0 and 1.0
        """
        # Compute data completeness score (40% weight)
        completeness_score = self._compute_data_completeness(metrics)
        
        # Compute data recency score (30% weight)
        recency_score = self._compute_data_recency(context.retrieved_data)
        
        # Compute retrieval quality score (30% weight)
        quality_score = self._compute_retrieval_quality(context.retrieved_data)
        
        # Weighted average
        system_confidence = (
            0.4 * completeness_score +
            0.3 * recency_score +
            0.3 * quality_score
        )
        
        return round(system_confidence, 3)

    def compute_hybrid_confidence(
        self,
        system_score: float,
        llm_score: float
    ) -> float:
        """Compute hybrid confidence score combining system and LLM scores

        Combines system-based confidence (from compute_system_confidence) with
        LLM self-assessed confidence using a weighted average:
        - System score: 70% weight (more reliable, based on data quality)
        - LLM score: 30% weight (subjective, based on model's self-assessment)

        Args:
            system_score: System confidence score (0.0 to 1.0)
            llm_score: LLM self-assessed confidence score (0.0 to 1.0)

        Returns:
            Hybrid confidence score between 0.0 and 1.0, rounded to 3 decimal places

        Raises:
            ValueError: If either score is not between 0.0 and 1.0
        """
        # Validate input scores
        if not (0.0 <= system_score <= 1.0):
            raise ValueError(
                f"system_score must be between 0.0 and 1.0, got {system_score}"
            )
        if not (0.0 <= llm_score <= 1.0):
            raise ValueError(
                f"llm_score must be between 0.0 and 1.0, got {llm_score}"
            )

        # Compute weighted average: 70% system, 30% LLM
        hybrid_confidence = (0.7 * system_score) + (0.3 * llm_score)

        return round(hybrid_confidence, 3)

    
    def _compute_data_completeness(self, metrics: DerivedMetrics) -> float:
        """Compute data completeness score based on available data types
        
        Scoring:
        - 1.0 if all three data types present (HR, power, effort)
        - 0.67 if 2 out of 3 present
        - 0.33 if 1 out of 3 present
        - 0.0 if none present
        
        Args:
            metrics: DerivedMetrics with has_hr_data, has_power_data, has_effort_data
            
        Returns:
            Completeness score between 0.0 and 1.0
        """
        data_types_present = sum([
            metrics.has_hr_data,
            metrics.has_power_data,
            metrics.has_effort_data
        ])
        
        if data_types_present == 3:
            return 1.0
        elif data_types_present == 2:
            return 0.67
        elif data_types_present == 1:
            return 0.33
        else:
            return 0.0
    
    def _compute_data_recency(self, retrieved_data: List[Dict[str, Any]]) -> float:
        """Compute data recency score based on days since last activity
        
        Scoring:
        - 1.0 if 0-7 days since last activity
        - 0.7 if 8-14 days since last activity
        - 0.4 if 15+ days since last activity
        - 0.0 if no activities
        
        Args:
            retrieved_data: List of evidence cards from context
            
        Returns:
            Recency score between 0.0 and 1.0
        """
        # Filter for activity evidence cards
        activities = [
            item for item in retrieved_data
            if item.get('type') == 'activity' and item.get('date')
        ]
        
        if not activities:
            return 0.0
        
        # Find most recent activity date
        most_recent_date = None
        for activity in activities:
            activity_date_str = activity.get('date')
            if activity_date_str:
                # Parse ISO format date string
                if 'T' in activity_date_str:
                    activity_date = datetime.fromisoformat(activity_date_str).date()
                else:
                    activity_date = date.fromisoformat(activity_date_str)
                
                if most_recent_date is None or activity_date > most_recent_date:
                    most_recent_date = activity_date
        
        if most_recent_date is None:
            return 0.0
        
        # Calculate days since last activity
        days_since = (date.today() - most_recent_date).days
        
        if days_since <= 7:
            return 1.0
        elif days_since <= 14:
            return 0.7
        else:
            return 0.4
    
    def _compute_retrieval_quality(self, retrieved_data: List[Dict[str, Any]]) -> float:
        """Compute retrieval quality score based on evidence card count
        
        Scoring:
        - 1.0 if 5+ evidence cards
        - 0.7 if 3-4 evidence cards
        - 0.4 if 1-2 evidence cards
        - 0.0 if no evidence cards
        
        Args:
            retrieved_data: List of evidence cards from context
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        card_count = len(retrieved_data)
        
        if card_count >= 5:
            return 1.0
        elif card_count >= 3:
            return 0.7
        elif card_count >= 1:
            return 0.4
        else:
            return 0.0

"""RAG Retriever for intent-based data retrieval."""

from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

from sqlalchemy.orm import Session

from app.ai.retrieval.intent_router import Intent
from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.models.athlete_goal import AthleteGoal


class RAGRetriever:
    """Retrieves relevant data using intent-specific policies."""
    
    def __init__(
        self,
        db: Session,
        policies_path: Optional[str] = None
    ):
        """
        Initialize RAG retriever.
        
        Args:
            db: SQLAlchemy database session
            policies_path: Optional path to retrieval_policies.yaml
                          (defaults to app/ai/config/)
        """
        self.db = db
        
        # Set default policies path if not provided
        if policies_path is None:
            policies_path = str(Path(__file__).parent.parent / "config" / "retrieval_policies.yaml")
        
        self.policies_path = policies_path
        self._policies_cache: Optional[Dict[str, Any]] = None
    
    def retrieve(
        self,
        query: str,
        athlete_id: int,
        intent: Intent,
        generate_cards: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve data based on intent-specific policy.

        Args:
            query: User query string (for future semantic search)
            athlete_id: Athlete ID for filtering
            intent: Classified intent
            generate_cards: If True, generate evidence cards for retrieved data
                          (default: True per requirement 4.1.3)

        Returns:
            List of dictionaries containing retrieved data or evidence cards
            
        Requirements: 4.1.3 - Generate evidence cards when retrieving activities
        """
        # Load policy for intent
        policy = self._load_policy(intent)

        # Extract policy parameters
        days_back = policy.get("days_back")
        max_records = policy.get("max_records", 20)
        data_types = policy.get("data_types", [])

        # Retrieve data based on policy
        results = []

        if "activities" in data_types:
            activities = self._query_activities(athlete_id, days_back, max_records)
            results.extend(activities)

        if "metrics" in data_types:
            metrics = self._query_metrics(athlete_id, days_back, max_records)
            results.extend(metrics)

        if "logs" in data_types:
            logs = self._query_logs(athlete_id, days_back, max_records)
            results.extend(logs)

        if "goals" in data_types:
            goals = self._query_goals(athlete_id)
            results.extend(goals)

        # Limit total results to max_records
        results = results[:max_records]

        # Generate evidence cards if requested
        if generate_cards:
            results = self.generate_evidence_cards(results, query)

        return results

    def generate_evidence_cards(
        self,
        retrieved_data: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Generate evidence cards for retrieved data.
        
        Args:
            retrieved_data: List of retrieved data dictionaries
            query: User query string (for context)
            
        Returns:
            List of evidence card dictionaries with fields:
                - claim_text: Descriptive text about the data point
                - source_type: Type of source (activity/goal/metric/log)
                - source_id: Database record ID
                - source_date: ISO format date
                - relevance_score: Float 0.0-1.0 (default 1.0)
        """
        evidence_cards = []
        
        for record in retrieved_data:
            # Extract common fields
            source_type = record.get("type")
            source_id = record.get("id")
            
            # Generate claim text based on record type
            if source_type == "activity":
                claim_text = self._generate_activity_claim(record)
                source_date = record.get("date")
            elif source_type == "metric":
                claim_text = self._generate_metric_claim(record)
                source_date = record.get("week_start")
            elif source_type == "log":
                claim_text = self._generate_log_claim(record)
                source_date = record.get("date")
            elif source_type == "goal":
                claim_text = self._generate_goal_claim(record)
                source_date = record.get("target_date")
            else:
                # Skip unknown types
                continue
            
            # Create evidence card
            evidence_card = {
                "claim_text": claim_text,
                "source_type": source_type,
                "source_id": source_id,
                "source_date": source_date,
                "relevance_score": 1.0  # Default relevance score
            }
            
            evidence_cards.append(evidence_card)
        
        return evidence_cards
    
    def _generate_activity_claim(self, activity: Dict[str, Any]) -> str:
        """Generate descriptive claim text for an activity."""
        activity_type = activity.get("activity_type", "Activity")
        date = activity.get("date", "")
        distance = activity.get("distance_km")
        duration = activity.get("duration_min")
        
        parts = [f"{activity_type} on {date}"]
        
        if distance:
            parts.append(f"{distance} km")
        if duration:
            parts.append(f"{duration} min")
        
        return " - ".join(parts)
    
    def _generate_metric_claim(self, metric: Dict[str, Any]) -> str:
        """Generate descriptive claim text for a metric."""
        week_start = metric.get("week_start", "")
        weight = metric.get("weight_kg")
        rhr = metric.get("rhr_bpm")
        
        parts = [f"Metrics for week starting {week_start}"]
        
        details = []
        if weight:
            details.append(f"weight: {weight} kg")
        if rhr:
            details.append(f"RHR: {rhr} bpm")
        
        if details:
            parts.append(" - ".join(details))
        
        return " - ".join(parts)
    
    def _generate_log_claim(self, log: Dict[str, Any]) -> str:
        """Generate descriptive claim text for a daily log."""
        date = log.get("date", "")
        calories = log.get("calories_in")
        protein = log.get("protein_g")
        
        parts = [f"Nutrition log for {date}"]
        
        details = []
        if calories:
            details.append(f"{calories} cal")
        if protein:
            details.append(f"{protein}g protein")
        
        if details:
            parts.append(" - ".join(details))
        
        return " - ".join(parts)
    
    def _generate_goal_claim(self, goal: Dict[str, Any]) -> str:
        """Generate descriptive claim text for a goal."""
        goal_type = goal.get("goal_type", "Goal")
        target_value = goal.get("target_value")
        target_date = goal.get("target_date")
        description = goal.get("description", "")
        
        parts = [goal_type]
        
        if target_value:
            parts.append(f"target: {target_value}")
        if target_date:
            parts.append(f"by {target_date}")
        if description:
            parts.append(description)
        
        return " - ".join(parts)

    
    def _load_policy(self, intent: Intent) -> Dict[str, Any]:
        """
        Load retrieval policy for the given intent from YAML.
        
        Args:
            intent: Intent enum value
            
        Returns:
            Policy dictionary with days_back, max_records, data_types
        """
        # Load policies from YAML (cache for performance)
        if self._policies_cache is None:
            with open(self.policies_path, 'r') as f:
                self._policies_cache = yaml.safe_load(f)
        
        # Get policy for intent (use intent value as key)
        intent_key = intent.value
        policy = self._policies_cache.get(intent_key, {})
        
        # Validate policy has required fields
        if not policy:
            raise ValueError(f"No policy found for intent: {intent_key}")
        
        return policy
    
    def _query_activities(
        self,
        athlete_id: int,
        days_back: Optional[int],
        max_records: int
    ) -> List[Dict[str, Any]]:
        """
        Query activities based on days_back parameter.
        
        Args:
            athlete_id: Athlete ID for filtering
            days_back: Days to look back (positive=past, negative=future, null=all time)
            max_records: Maximum number of records to return
            
        Returns:
            List of activity dictionaries
        """
        query = self.db.query(StravaActivity).filter(
            StravaActivity.athlete_id == athlete_id
        )
        
        # Apply date filtering based on days_back
        if days_back is not None:
            if days_back > 0:
                # Look back N days from today
                start_date = datetime.now() - timedelta(days=days_back)
                query = query.filter(StravaActivity.start_date >= start_date)
            elif days_back < 0:
                # Look forward N days from today (for planned activities)
                end_date = datetime.now() + timedelta(days=abs(days_back))
                query = query.filter(StravaActivity.start_date <= end_date)
        # If days_back is null, no date filter (all time)
        
        # Order by date descending and limit
        activities = query.order_by(StravaActivity.start_date.desc()).limit(max_records).all()
        
        # Format as dictionaries
        return [self._format_activity(activity) for activity in activities]
    
    def _query_metrics(
        self,
        athlete_id: int,
        days_back: Optional[int],
        max_records: int
    ) -> List[Dict[str, Any]]:
        """
        Query weekly metrics based on days_back parameter.
        
        Args:
            athlete_id: Athlete ID for filtering (currently unused, single athlete)
            days_back: Days to look back (positive=past, negative=future, null=all time)
            max_records: Maximum number of records to return
            
        Returns:
            List of metric dictionaries
        """
        query = self.db.query(WeeklyMeasurement)
        
        # Apply date filtering based on days_back
        if days_back is not None:
            if days_back > 0:
                # Look back N days from today
                start_date = (datetime.now() - timedelta(days=days_back)).date()
                query = query.filter(WeeklyMeasurement.week_start >= start_date)
            elif days_back < 0:
                # Look forward N days from today
                end_date = (datetime.now() + timedelta(days=abs(days_back))).date()
                query = query.filter(WeeklyMeasurement.week_start <= end_date)
        # If days_back is null, no date filter (all time)
        
        # Order by date descending and limit
        metrics = query.order_by(WeeklyMeasurement.week_start.desc()).limit(max_records).all()
        
        # Format as dictionaries
        return [self._format_metric(metric) for metric in metrics]
    
    def _query_logs(
        self,
        athlete_id: int,
        days_back: Optional[int],
        max_records: int
    ) -> List[Dict[str, Any]]:
        """
        Query daily logs based on days_back parameter.
        
        Args:
            athlete_id: Athlete ID for filtering (currently unused, single athlete)
            days_back: Days to look back (positive=past, negative=future, null=all time)
            max_records: Maximum number of records to return
            
        Returns:
            List of log dictionaries
        """
        query = self.db.query(DailyLog)
        
        # Apply date filtering based on days_back
        if days_back is not None:
            if days_back > 0:
                # Look back N days from today
                start_date = (datetime.now() - timedelta(days=days_back)).date()
                query = query.filter(DailyLog.log_date >= start_date)
            elif days_back < 0:
                # Look forward N days from today
                end_date = (datetime.now() + timedelta(days=abs(days_back))).date()
                query = query.filter(DailyLog.log_date <= end_date)
        # If days_back is null, no date filter (all time)
        
        # Order by date descending and limit
        logs = query.order_by(DailyLog.log_date.desc()).limit(max_records).all()
        
        # Format as dictionaries
        return [self._format_log(log) for log in logs]
    
    def _query_goals(
        self,
        athlete_id: int
    ) -> List[Dict[str, Any]]:
        """
        Query active athlete goals.
        
        Args:
            athlete_id: Athlete ID for filtering
            
        Returns:
            List of goal dictionaries
        """
        # Query active goals only
        goals = self.db.query(AthleteGoal).filter(
            AthleteGoal.status == "active"
        ).all()
        
        # If athlete_id is provided, filter by it (for future multi-athlete support)
        if athlete_id:
            goals = [g for g in goals if g.athlete_id is None or g.athlete_id == str(athlete_id)]
        
        # Format as dictionaries
        return [self._format_goal(goal) for goal in goals]
    
    def _format_activity(self, activity: StravaActivity) -> Dict[str, Any]:
        """Format activity as dictionary."""
        return {
            "type": "activity",
            "id": activity.id,
            "date": activity.start_date.isoformat(),
            "activity_type": activity.activity_type,
            "distance_km": round(activity.distance_m / 1000, 2) if activity.distance_m else None,
            "duration_min": round(activity.moving_time_s / 60, 1) if activity.moving_time_s else None,
            "elevation_m": activity.elevation_m,
            "avg_hr": activity.avg_hr,
            "max_hr": activity.max_hr,
            "calories": activity.calories
        }
    
    def _format_metric(self, metric: WeeklyMeasurement) -> Dict[str, Any]:
        """Format metric as dictionary."""
        return {
            "type": "metric",
            "id": metric.id,
            "week_start": metric.week_start.isoformat(),
            "weight_kg": metric.weight_kg,
            "body_fat_pct": metric.body_fat_pct,
            "waist_cm": metric.waist_cm,
            "rhr_bpm": metric.rhr_bpm,
            "sleep_avg_hrs": metric.sleep_avg_hrs,
            "energy_level_avg": metric.energy_level_avg
        }
    
    def _format_log(self, log: DailyLog) -> Dict[str, Any]:
        """Format log as dictionary."""
        return {
            "type": "log",
            "id": log.id,
            "date": log.log_date.isoformat(),
            "calories_in": log.calories_in,
            "protein_g": log.protein_g,
            "carbs_g": log.carbs_g,
            "fat_g": log.fat_g,
            "adherence_score": log.adherence_score,
            "fasting_hours": log.fasting_hours
        }
    
    def _format_goal(self, goal: AthleteGoal) -> Dict[str, Any]:
        """Format goal as dictionary."""
        return {
            "type": "goal",
            "id": goal.id,
            "goal_type": goal.goal_type,
            "target_value": goal.target_value,
            "target_date": goal.target_date.isoformat() if goal.target_date else None,
            "description": goal.description,
            "status": goal.status
        }

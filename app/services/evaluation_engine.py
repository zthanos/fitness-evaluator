"""Evaluation Engine Service

Generates structured coaching evaluations for configurable time periods.
Gathers activities, metrics, and logs, then uses LangChain LLM for analysis.
"""
import logging
import json
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

try:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from app.models.strava_activity import StravaActivity
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.daily_log import DailyLog
from app.schemas.evaluation_schemas import EvaluationReport
from app.config import get_settings

logger = logging.getLogger(__name__)


class EvaluationEngine:
    """
    Evaluation engine for generating structured coaching evaluations.
    
    Gathers data from activities, metrics, and logs for a specified period,
    then uses LangChain LLM to generate structured evaluation reports.
    """
    
    def __init__(self, db_session: Session, llm_client=None):
        """
        Initialize evaluation engine.
        
        Args:
            db_session: SQLAlchemy database session
            llm_client: LangChain LLM client (optional, will be created if not provided)
        """
        self.db = db_session
        self.settings = get_settings()
        
        # Initialize LangChain LLM if not provided
        if llm_client is None:
            if not LANGCHAIN_AVAILABLE:
                error_msg = (
                    "LangChain is not available. Install with: "
                    "uv pip install langchain-core langchain-ollama langchain-openai"
                )
                logger.error("LangChain initialization failed: Missing dependencies")
                raise ImportError(error_msg)
            
            llm_type = self.settings.LLM_TYPE.lower()
            
            try:
                if llm_type in ["lm-studio", "openai"]:
                    base_url = self.settings.llm_base_url
                    if base_url.endswith('/v1'):
                        base_url = base_url[:-3]
                    
                    self.llm = ChatOpenAI(
                        base_url=base_url,
                        api_key="lm-studio",
                        model=self.settings.OLLAMA_MODEL,
                        temperature=0.1,
                    )
                else:
                    self.llm = ChatOllama(
                        base_url=self.settings.llm_base_url,
                        model=self.settings.OLLAMA_MODEL,
                        temperature=0.1,
                    )
                
                # Bind structured output schema
                self.llm_with_structure = self.llm.with_structured_output(EvaluationReport)
                
                logger.info(
                    "LangChain initialized for EvaluationEngine",
                    extra={
                        "backend": llm_type,
                        "model": self.settings.OLLAMA_MODEL,
                        "temperature": 0.1
                    }
                )
            except Exception as e:
                logger.error(f"LangChain initialization failed: {e}")
                raise
        else:
            self.llm_with_structure = llm_client
    
    def _gather_activities(self, athlete_id: int, start: date, end: date) -> List[Dict[str, Any]]:
        """
        Gather all activities for the specified period.
        
        Args:
            athlete_id: Athlete identifier
            start: Period start date
            end: Period end date (inclusive)
            
        Returns:
            List of activity dictionaries with relevant fields
        """
        logger.info(
            f"Gathering activities for period {start} to {end}",
            extra={"athlete_id": athlete_id, "start": start, "end": end}
        )
        
        # Query activities within date range
        activities = self.db.query(StravaActivity).filter(
            StravaActivity.start_date >= datetime.combine(start, datetime.min.time()),
            StravaActivity.start_date <= datetime.combine(end, datetime.max.time())
        ).order_by(StravaActivity.start_date).all()
        
        # Convert to dictionaries with relevant fields
        activity_list = []
        for activity in activities:
            activity_list.append({
                'id': activity.id,
                'strava_id': activity.strava_id,
                'type': activity.activity_type,
                'start_date': activity.start_date.isoformat(),
                'distance_m': activity.distance_m,
                'distance_km': round(activity.distance_m / 1000, 2) if activity.distance_m else None,
                'moving_time_s': activity.moving_time_s,
                'moving_time_min': round(activity.moving_time_s / 60, 1) if activity.moving_time_s else None,
                'elevation_m': activity.elevation_m,
                'avg_hr': activity.avg_hr,
                'max_hr': activity.max_hr,
                'calories': activity.calories
            })
        
        logger.info(
            f"Gathered {len(activity_list)} activities",
            extra={"athlete_id": athlete_id, "count": len(activity_list)}
        )
        
        return activity_list
    
    def _gather_metrics(self, athlete_id: int, start: date, end: date) -> List[Dict[str, Any]]:
        """
        Gather all body metrics for the specified period.
        
        Args:
            athlete_id: Athlete identifier
            start: Period start date
            end: Period end date (inclusive)
            
        Returns:
            List of metric dictionaries with relevant fields
        """
        logger.info(
            f"Gathering metrics for period {start} to {end}",
            extra={"athlete_id": athlete_id, "start": start, "end": end}
        )
        
        # Query measurements within date range
        measurements = self.db.query(WeeklyMeasurement).filter(
            WeeklyMeasurement.week_start >= start,
            WeeklyMeasurement.week_start <= end
        ).order_by(WeeklyMeasurement.week_start).all()
        
        # Convert to dictionaries with relevant fields
        metric_list = []
        for measurement in measurements:
            metric_list.append({
                'id': measurement.id,
                'week_start': measurement.week_start.isoformat(),
                'weight_kg': measurement.weight_kg,
                'weight_prev_kg': measurement.weight_prev_kg,
                'weight_change_kg': round(measurement.weight_kg - measurement.weight_prev_kg, 2) 
                    if measurement.weight_kg and measurement.weight_prev_kg else None,
                'body_fat_pct': measurement.body_fat_pct,
                'waist_cm': measurement.waist_cm,
                'waist_prev_cm': measurement.waist_prev_cm,
                'waist_change_cm': round(measurement.waist_cm - measurement.waist_prev_cm, 2)
                    if measurement.waist_cm and measurement.waist_prev_cm else None,
                'sleep_avg_hrs': measurement.sleep_avg_hrs,
                'rhr_bpm': measurement.rhr_bpm,
                'energy_level_avg': measurement.energy_level_avg
            })
        
        logger.info(
            f"Gathered {len(metric_list)} measurements",
            extra={"athlete_id": athlete_id, "count": len(metric_list)}
        )
        
        return metric_list
    
    def _gather_logs(self, athlete_id: int, start: date, end: date) -> List[Dict[str, Any]]:
        """
        Gather all daily logs for the specified period.
        
        Args:
            athlete_id: Athlete identifier
            start: Period start date
            end: Period end date (inclusive)
            
        Returns:
            List of log dictionaries with relevant fields
        """
        logger.info(
            f"Gathering logs for period {start} to {end}",
            extra={"athlete_id": athlete_id, "start": start, "end": end}
        )
        
        # Query logs within date range
        logs = self.db.query(DailyLog).filter(
            DailyLog.log_date >= start,
            DailyLog.log_date <= end
        ).order_by(DailyLog.log_date).all()
        
        # Convert to dictionaries with relevant fields
        log_list = []
        for log in logs:
            log_list.append({
                'id': log.id,
                'log_date': log.log_date.isoformat(),
                'fasting_hours': log.fasting_hours,
                'calories_in': log.calories_in,
                'protein_g': log.protein_g,
                'carbs_g': log.carbs_g,
                'fat_g': log.fat_g,
                'adherence_score': log.adherence_score,
                'notes': log.notes
            })
        
        logger.info(
            f"Gathered {len(log_list)} daily logs",
            extra={"athlete_id": athlete_id, "count": len(log_list)}
        )
        
        return log_list
    
    def _build_context(self, activities: List[Dict], metrics: List[Dict], logs: List[Dict]) -> Dict[str, Any]:
        """
        Build context dictionary for LLM prompt.
        
        Args:
            activities: List of activity dictionaries
            metrics: List of metric dictionaries
            logs: List of log dictionaries
            
        Returns:
            Context dictionary with aggregated data and statistics
        """
        # Calculate activity statistics
        total_activities = len(activities)
        total_distance_km = sum(a.get('distance_km', 0) or 0 for a in activities)
        total_time_min = sum(a.get('moving_time_min', 0) or 0 for a in activities)
        total_elevation_m = sum(a.get('elevation_m', 0) or 0 for a in activities)
        
        # Calculate nutrition statistics
        total_logs = len(logs)
        avg_calories = sum(l.get('calories_in', 0) or 0 for l in logs) / total_logs if total_logs > 0 else 0
        avg_protein = sum(l.get('protein_g', 0) or 0 for l in logs) / total_logs if total_logs > 0 else 0
        avg_adherence = sum(l.get('adherence_score', 0) or 0 for l in logs) / total_logs if total_logs > 0 else 0
        
        # Calculate weight change
        weight_change = None
        if len(metrics) >= 2:
            first_weight = metrics[0].get('weight_kg')
            last_weight = metrics[-1].get('weight_kg')
            if first_weight and last_weight:
                weight_change = round(last_weight - first_weight, 2)
        
        context = {
            'activities': activities,
            'metrics': metrics,
            'logs': logs,
            'statistics': {
                'total_activities': total_activities,
                'total_distance_km': round(total_distance_km, 2),
                'total_time_min': round(total_time_min, 1),
                'total_elevation_m': round(total_elevation_m, 0),
                'total_logs': total_logs,
                'avg_calories': round(avg_calories, 0),
                'avg_protein_g': round(avg_protein, 1),
                'avg_adherence_score': round(avg_adherence, 1),
                'weight_change_kg': weight_change
            }
        }
        
        logger.info(
            "Built evaluation context",
            extra={
                "activities": total_activities,
                "metrics": len(metrics),
                "logs": total_logs
            }
        )
        
        return context

    
    async def generate_evaluation(
        self,
        athlete_id: int,
        period_start: date,
        period_end: date,
        period_type: str = "weekly"
    ) -> EvaluationReport:
        """
        Generate evaluation report for the specified period.
        
        Args:
            athlete_id: Athlete identifier
            period_start: Start date of evaluation period
            period_end: End date of evaluation period (inclusive)
            period_type: Type of period (weekly, bi-weekly, monthly)
            
        Returns:
            EvaluationReport: Validated evaluation report
            
        Raises:
            ValueError: If evaluation generation fails
        """
        logger.info(
            f"Generating evaluation for athlete {athlete_id}",
            extra={
                "athlete_id": athlete_id,
                "period_start": period_start,
                "period_end": period_end,
                "period_type": period_type
            }
        )
        
        # Gather all data for the period
        activities = self._gather_activities(athlete_id, period_start, period_end)
        metrics = self._gather_metrics(athlete_id, period_start, period_end)
        logs = self._gather_logs(athlete_id, period_start, period_end)
        
        # Build context for LLM
        context = self._build_context(activities, metrics, logs)
        context['period_start'] = period_start.isoformat()
        context['period_end'] = period_end.isoformat()
        context['period_type'] = period_type
        
        # Load system prompt
        system_prompt = self._load_evaluation_prompt()
        
        # Prepare messages for LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(context, indent=2, default=str))
        ]
        
        # Generate evaluation with retry logic
        for attempt in range(3):
            try:
                logger.info(
                    f"Invoking LLM for evaluation (attempt {attempt + 1}/3)",
                    extra={
                        "athlete_id": athlete_id,
                        "attempt": attempt + 1
                    }
                )
                
                result = await self.llm_with_structure.ainvoke(messages)
                
                logger.info(
                    "Evaluation generated successfully",
                    extra={
                        "athlete_id": athlete_id,
                        "overall_score": result.overall_score,
                        "confidence_score": result.confidence_score
                    }
                )
                
                return result
                
            except Exception as e:
                logger.warning(
                    f"Evaluation generation failed (attempt {attempt + 1}/3): {e}",
                    extra={
                        "athlete_id": athlete_id,
                        "attempt": attempt + 1,
                        "error": str(e)
                    }
                )
                
                if attempt == 2:
                    logger.error(
                        "Evaluation generation failed after 3 attempts",
                        extra={
                            "athlete_id": athlete_id,
                            "error": str(e)
                        }
                    )
                    raise ValueError(f"Failed to generate evaluation: {str(e)}")
    
    def _load_evaluation_prompt(self) -> str:
        """
        Load evaluation prompt template.
        
        Returns:
            str: System prompt for evaluation generation
        """
        try:
            with open('app/prompts/evaluation_prompt.txt', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Evaluation prompt file not found, using default prompt")
            return self._get_default_evaluation_prompt()
    
    def _get_default_evaluation_prompt(self) -> str:
        """
        Get default evaluation prompt.
        
        Returns:
            str: Default system prompt for evaluation
        """
        return """You are an expert fitness coach analyzing athlete performance data.

Analyze the provided data and generate a comprehensive evaluation report with:

1. Overall Score (0-100): Rate the athlete's overall performance based on:
   - Consistency with training and nutrition logging
   - Progress toward goals
   - Quality of training sessions
   - Adherence to nutrition targets

2. Strengths: List specific achievements and positive outcomes (at least 1)
   - Be specific and reference actual data points
   - Highlight consistency, improvements, or exceptional performances

3. Areas for Improvement: List specific areas needing attention
   - Be constructive and actionable
   - Reference specific gaps or concerns from the data

4. Actionable Tips: Provide specific, practical coaching advice
   - Make tips concrete and implementable
   - Prioritize the most impactful changes

5. Recommended Exercises: Suggest specific exercises or activities
   - Base recommendations on the athlete's current training
   - Consider gaps in their current routine

6. Goal Alignment: Assess progress toward stated goals
   - Reference specific goals if provided
   - Evaluate whether current activities support goal achievement

7. Confidence Score (0.0-1.0): Rate data completeness
   - 1.0 = Complete data for entire period
   - 0.5 = Partial data with some gaps
   - 0.0 = Minimal or no data

Provide specific, evidence-based insights. Reference actual numbers from the data when making assessments."""

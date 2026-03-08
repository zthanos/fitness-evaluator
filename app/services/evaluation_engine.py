"""Evaluation Engine Service

Generates structured coaching evaluations using Context Engineering architecture.
Migrated to use ContextBuilder, DerivedMetricsEngine, LLM adapter, and evidence mapping.
"""
import logging
import json
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session

# Context Engineering imports
from app.ai.context.evaluation_context import EvaluationContextBuilder
from app.ai.derived.metrics_engine import DerivedMetricsEngine
from app.ai.adapter.langchain_adapter import LangChainAdapter
from app.ai.contracts.evaluation_contract import WeeklyEvalContract
from app.ai.prompts.system_loader import SystemInstructionsLoader
from app.ai.prompts.task_loader import TaskInstructionsLoader
from app.ai.config.domain_loader import DomainKnowledgeLoader
from app.ai.retrieval.evidence_mapper import EvidenceMapper
from app.ai.telemetry.invocation_logger import InvocationLogger

# Legacy imports for backward compatibility
from app.models.strava_activity import StravaActivity
from app.schemas.evaluation_schemas import EvaluationReport
from app.config import get_settings

logger = logging.getLogger(__name__)


class EvaluationEngine:
    """
    Evaluation engine using Context Engineering architecture.
    
    Migrated to use:
    - EvaluationContextBuilder for context assembly
    - DerivedMetricsEngine for metric computation
    - LangChainAdapter for LLM invocation with fallback
    - EvidenceMapper for claim-to-source linking
    - InvocationLogger for telemetry
    
    Maintains existing function signatures for backward compatibility.
    """
    
    def __init__(self, db_session: Session, llm_client=None):
        """
        Initialize evaluation engine with Context Engineering components.
        
        Args:
            db_session: SQLAlchemy database session
            llm_client: Optional LLM adapter (creates LangChainAdapter if not provided)
        """
        self.db = db_session
        self.settings = get_settings()
        
        # Initialize Context Engineering components
        self.system_loader = SystemInstructionsLoader()
        self.task_loader = TaskInstructionsLoader()
        self.domain_loader = DomainKnowledgeLoader()
        self.evidence_mapper = EvidenceMapper()
        self.invocation_logger = InvocationLogger()
        
        # Load domain knowledge once at initialization
        self.domain_knowledge = self.domain_loader.load()
        
        # Initialize derived metrics engine
        self.metrics_engine = DerivedMetricsEngine(self.domain_knowledge)
        
        # Initialize LLM adapter
        if llm_client is None:
            # Create LangChainAdapter with settings from config
            self.llm_adapter = LangChainAdapter(
                primary_model=self.settings.OLLAMA_MODEL,
                fallback_model="llama3.1:8b-instruct",
                base_url=self.settings.llm_base_url,
                temperature=0.1,  # Lower temperature for evaluation
                max_tokens=2000,
                invocation_logger=self.invocation_logger
            )
            
            logger.info(
                "Context Engineering initialized for EvaluationEngine",
                extra={
                    "primary_model": self.settings.OLLAMA_MODEL,
                    "fallback_model": "llama3.1:8b-instruct",
                    "temperature": 0.1
                }
            )
        else:
            self.llm_adapter = llm_client
    
    
    async def generate_evaluation(
        self,
        athlete_id: int,
        period_start: date,
        period_end: date,
        period_type: str = "weekly"
    ) -> EvaluationReport:
        """
        Generate evaluation report using Context Engineering architecture.
        
        This method maintains the existing function signature for backward compatibility
        while using the new CE components internally.
        
        Args:
            athlete_id: Athlete identifier
            period_start: Start date of evaluation period
            period_end: End date of evaluation period (inclusive)
            period_type: Type of period (weekly, bi-weekly, monthly)
            
        Returns:
            EvaluationReport: Validated evaluation report (converted from WeeklyEvalContract)
            
        Raises:
            ValueError: If evaluation generation fails
        """
        logger.info(
            f"Generating evaluation for athlete {athlete_id} using Context Engineering",
            extra={
                "athlete_id": athlete_id,
                "period_start": period_start,
                "period_end": period_end,
                "period_type": period_type
            }
        )
        
        # Compute week_id from period_start (ISO week format: YYYY-WW)
        week_id = period_start.strftime("%Y-W%W")
        
        # Step 1: Build context using EvaluationContextBuilder
        context_builder = EvaluationContextBuilder(self.db, token_budget=8000)
        
        # Load system instructions
        system_instructions = self.system_loader.load(version="1.0.0")
        context_builder.add_system_instructions(system_instructions)
        
        # Load task instructions with runtime parameters
        task_params = {
            "athlete_id": athlete_id,
            "week_id": week_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat()
        }
        task_instructions = self.task_loader.load(
            operation="weekly_eval",
            version="1.0.0",
            params=task_params
        )
        context_builder.add_task_instructions(task_instructions)
        
        # Add domain knowledge
        domain_knowledge_dict = {
            "training_zones": {
                name: {
                    "hr_pct_max": zone.hr_pct_max,
                    "rpe": zone.rpe,
                    "description": zone.description
                }
                for name, zone in self.domain_knowledge.training_zones.items()
            },
            "effort_levels": self.domain_knowledge.effort_levels,
            "recovery_guidelines": self.domain_knowledge.recovery_guidelines,
            "nutrition_targets": self.domain_knowledge.nutrition_targets
        }
        context_builder.add_domain_knowledge(domain_knowledge_dict)
        
        # Gather data (activities, metrics, logs, goals)
        context_builder.gather_data(
            athlete_id=athlete_id,
            week_id=week_id,
            period_start=period_start,
            period_end=period_end
        )
        
        # Step 2: Compute derived metrics
        # Query activities for metrics computation
        activities = self.db.query(StravaActivity).filter(
            StravaActivity.week_id == week_id
        ).all()
        
        derived_metrics = self.metrics_engine.compute(
            activities=activities,
            week_start=period_start,
            week_end=period_end
        )
        
        # Add derived metrics to context as additional retrieved data
        metrics_card = {
            "type": "derived_metrics",
            "total_distance_km": derived_metrics.total_distance_km,
            "total_duration_min": derived_metrics.total_duration_min,
            "total_elevation_m": derived_metrics.total_elevation_m,
            "activity_count": derived_metrics.activity_count,
            "easy_pct": derived_metrics.easy_pct,
            "moderate_pct": derived_metrics.moderate_pct,
            "hard_pct": derived_metrics.hard_pct,
            "max_pct": derived_metrics.max_pct,
            "training_load": derived_metrics.training_load,
            "rest_days_count": derived_metrics.rest_days_count,
            "consecutive_training_days": derived_metrics.consecutive_training_days,
            "avg_heart_rate": derived_metrics.avg_heart_rate,
            "hr_zone_distribution": derived_metrics.hr_zone_distribution,
            "has_hr_data": derived_metrics.has_hr_data,
            "has_power_data": derived_metrics.has_power_data,
            "has_effort_data": derived_metrics.has_effort_data
        }
        context_builder.add_retrieved_data([metrics_card])
        
        # Build and validate context
        try:
            context = context_builder.build()
            logger.info(
                f"Context built successfully: {context.token_count} tokens",
                extra={
                    "athlete_id": athlete_id,
                    "token_count": context.token_count,
                    "token_budget": 8000
                }
            )
        except Exception as e:
            logger.error(
                f"Context building failed: {e}",
                extra={"athlete_id": athlete_id, "error": str(e)}
            )
            raise ValueError(f"Failed to build evaluation context: {str(e)}")
        
        # Step 3: Invoke LLM with automatic fallback
        try:
            logger.info(
                f"Invoking LLM for evaluation",
                extra={"athlete_id": athlete_id}
            )
            
            llm_response = self.llm_adapter.invoke(
                context=context,
                contract=WeeklyEvalContract,
                operation_type="weekly_eval",
                athlete_id=athlete_id
            )
            
            weekly_eval_contract = llm_response.parsed_output
            
            logger.info(
                "Evaluation generated successfully",
                extra={
                    "athlete_id": athlete_id,
                    "model_used": llm_response.model_used,
                    "latency_ms": llm_response.latency_ms,
                    "confidence_score": weekly_eval_contract.confidence_score
                }
            )
            
        except Exception as e:
            logger.error(
                f"LLM invocation failed: {e}",
                extra={"athlete_id": athlete_id, "error": str(e)}
            )
            raise ValueError(f"Failed to generate evaluation: {str(e)}")
        
        # Step 4: Map evidence to claims
        try:
            evidence_cards = self.evidence_mapper.map_claims_to_evidence(
                response=weekly_eval_contract,
                retrieved_data=context._retrieved_data
            )
            
            logger.info(
                f"Evidence mapping complete: {len(evidence_cards)} cards generated",
                extra={"athlete_id": athlete_id, "evidence_count": len(evidence_cards)}
            )
        except Exception as e:
            logger.warning(
                f"Evidence mapping failed: {e}",
                extra={"athlete_id": athlete_id, "error": str(e)}
            )
            evidence_cards = []
        
        # Step 5: Convert WeeklyEvalContract to EvaluationReport for backward compatibility
        evaluation_report = self._convert_to_evaluation_report(
            weekly_eval_contract,
            evidence_cards
        )
        
        return evaluation_report
    
    def _convert_to_evaluation_report(
        self,
        contract: WeeklyEvalContract,
        evidence_cards: list
    ) -> EvaluationReport:
        """
        Convert WeeklyEvalContract to EvaluationReport for backward compatibility.
        
        Args:
            contract: WeeklyEvalContract from LLM
            evidence_cards: List of evidence card dictionaries
            
        Returns:
            EvaluationReport matching the schema
        """
        # Extract tips and exercises from recommendations
        tips = []
        recommended_exercises = []
        
        for rec in contract.recommendations:
            if rec.category == "training":
                recommended_exercises.append(rec.text)
            else:
                tips.append(rec.text)
        
        # Ensure we have at least some content
        if not tips:
            tips = [rec.text for rec in contract.recommendations[:3]]
        if not recommended_exercises:
            recommended_exercises = ["Continue current training routine"]
        
        # Create EvaluationReport
        return EvaluationReport(
            overall_score=int(contract.confidence_score * 100),  # Convert 0.0-1.0 to 0-100
            strengths=contract.strengths,
            improvements=contract.areas_for_improvement,
            tips=tips,
            recommended_exercises=recommended_exercises,
            goal_alignment=contract.overall_assessment,  # Full assessment text
            confidence_score=contract.confidence_score
        )

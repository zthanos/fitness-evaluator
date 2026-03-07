# app/services/eval_service.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.services.prompt_engine import build_contract, hash_contract
from app.services.langchain_eval_service import LangChainEvaluationService
from app.schemas.eval_output import EvalOutput
from app.models.weekly_eval import WeeklyEval
from app.models.daily_log import DailyLog
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.plan_targets import PlanTargets
from app.models.strava_activity import StravaActivity
import logging

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db

    async def evaluate_week(self, week_id: str, force_refresh: bool = False) -> WeeklyEval:
        """
        Perform a complete fitness evaluation for the given week.
        
        Implements idempotency through contract hashing - if an evaluation exists
        with matching input_hash, returns cached result without calling LLM.
        
        Args:
            week_id: String UUID of the week to evaluate
            force_refresh: If True, bypass cache and regenerate evaluation
            
        Returns:
            WeeklyEval model instance with the evaluation results
            
        Raises:
            ValueError: If contract building or evaluation fails
        """
        logger.info(
            f"Starting evaluation for week_id={week_id}",
            extra={"week_id": week_id, "force_refresh": force_refresh}
        )
        
        # Build the contract from all relevant data
        try:
            contract = build_contract(week_id, self.db)
        except ValueError as e:
            logger.error(
                f"Contract building failed: {e}",
                extra={"week_id": week_id, "error": str(e)}
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error building contract: {e}",
                extra={
                    "week_id": week_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise ValueError(f"Failed to build contract: {str(e)}")
        
        # Compute contract hash for idempotency
        input_hash = hash_contract(contract)
        
        # Check for existing evaluation with matching input_hash (cache hit)
        if not force_refresh:
            existing_eval = self.db.query(WeeklyEval).filter(
                WeeklyEval.week_id == week_id,
                WeeklyEval.input_hash == input_hash
            ).first()
            
            if existing_eval:
                logger.info(
                    "Cache hit - returning existing evaluation",
                    extra={
                        "week_id": week_id,
                        "input_hash": input_hash[:8] + "...",
                        "generated_at": str(existing_eval.generated_at)
                    }
                )
                return existing_eval
        
        logger.info(
            "Cache miss - generating new evaluation",
            extra={"week_id": week_id, "input_hash": input_hash[:8] + "..."}
        )
        
        # Initialize LangChainEvaluationService
        try:
            langchain_service = LangChainEvaluationService()
        except ImportError as e:
            logger.error(
                f"LangChain initialization failed: {e}",
                extra={"week_id": week_id, "error": str(e)}
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error initializing LangChain: {e}",
                extra={
                    "week_id": week_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise ValueError(f"Failed to initialize LangChain service: {str(e)}")
        
        # Generate evaluation using LangChain (cache miss)
        try:
            eval_data = await langchain_service.generate_evaluation(contract)
        except ValueError as e:
            # ValueError already has descriptive message from LangChainEvaluationService
            logger.error(
                f"Evaluation generation failed: {e}",
                extra={
                    "week_id": week_id,
                    "input_hash": input_hash[:8] + "...",
                    "error": str(e)
                }
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during evaluation: {e}",
                extra={
                    "week_id": week_id,
                    "input_hash": input_hash[:8] + "...",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise ValueError(f"Failed to generate evaluation: {str(e)}")
        
        # Create or update WeeklyEval record
        weekly_eval = self.db.query(WeeklyEval).filter(WeeklyEval.week_id == week_id).first()
        
        if not weekly_eval:
            weekly_eval = WeeklyEval(week_id=week_id)
            self.db.add(weekly_eval)
            logger.info(f"Creating new WeeklyEval record for week_id={week_id}")
        else:
            logger.info(f"Updating existing WeeklyEval record for week_id={week_id}")
        
        # Update the evaluation with results
        weekly_eval.input_hash = input_hash
        weekly_eval.raw_llm_response = eval_data.model_dump_json()
        weekly_eval.parsed_output_json = eval_data.model_dump()
        weekly_eval.generated_at = datetime.now()
        
        # Collect evidence for traceability
        try:
            from app.services.evidence_collector import collect_evidence
            evidence = collect_evidence(eval_data, week_id, self.db)
            weekly_eval.evidence_map_json = evidence
            logger.info(
                "Evidence collection completed",
                extra={"week_id": week_id, "evidence_items": len(evidence) if isinstance(evidence, dict) else 0}
            )
        except Exception as e:
            logger.warning(
                f"Evidence collection failed: {e}",
                extra={
                    "week_id": week_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            # Continue without evidence - it's not critical
            weekly_eval.evidence_map_json = {}
        
        try:
            self.db.commit()
            logger.info(
                "Evaluation stored successfully",
                extra={
                    "week_id": week_id,
                    "input_hash": input_hash[:8] + "...",
                    "overall_score": eval_data.overall_score
                }
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Database commit failed: {e}",
                extra={
                    "week_id": week_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise ValueError(f"Failed to store evaluation: {str(e)}")
        
        return weekly_eval

    def get_evaluation(self, week_id: str) -> WeeklyEval | None:
        """
        Retrieve a previously generated evaluation for the given week.
        
        Args:
            week_id: String UUID of the week to retrieve
            
        Returns:
            WeeklyEval model instance or None if not found
        """
        return self.db.query(WeeklyEval).filter(WeeklyEval.week_id == week_id).first()

    def get_latest_evaluations(self, limit: int = 10) -> list[WeeklyEval]:
        """
        Retrieve the latest evaluations.
        
        Args:
            limit: Maximum number of evaluations to return
            
        Returns:
            List of WeeklyEval model instances
        """
        return self.db.query(WeeklyEval).order_by(WeeklyEval.created_at.desc()).limit(limit).all()

# app/services/eval_service.py
from datetime import datetime, timedelta
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
        
        # Collect evidence for traceability using EvidenceMapper
        try:
            from app.ai.retrieval.evidence_mapper import EvidenceMapper
            from datetime import timedelta
            
            # Get the WeeklyMeasurement to derive week_start
            weekly_measurement = self.db.query(WeeklyMeasurement).filter(
                WeeklyMeasurement.id == week_id
            ).first()
            
            if weekly_measurement:
                week_start = weekly_measurement.week_start
                week_end = week_start + timedelta(days=7)
                
                # Calculate ISO week_id for activity queries
                iso_calendar = week_start.isocalendar()
                iso_week_id = f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"
                
                # Query source data for the week
                daily_logs = self.db.query(DailyLog).filter(
                    DailyLog.log_date >= week_start,
                    DailyLog.log_date < week_end
                ).all()
                
                strava_activities = self.db.query(StravaActivity).filter(
                    StravaActivity.week_id == iso_week_id
                ).all()
                
                # Format as evidence cards (retrieved_data format)
                retrieved_data = []
                
                # Add activity cards
                for activity in strava_activities:
                    retrieved_data.append({
                        "type": "activity",
                        "id": activity.id,
                        "date": activity.start_date.isoformat() if activity.start_date else None,
                        "activity_type": activity.activity_type,
                        "distance_km": round(activity.distance_m / 1000, 2) if activity.distance_m else None,
                        "duration_min": round(activity.moving_time_s / 60, 1) if activity.moving_time_s else None,
                        "elevation_m": activity.elevation_m,
                        "avg_hr": activity.avg_hr,
                        "max_hr": activity.max_hr
                    })
                
                # Add log cards
                for log in daily_logs:
                    retrieved_data.append({
                        "type": "log",
                        "id": log.id,
                        "date": log.log_date.isoformat() if log.log_date else None,
                        "calories_in": log.calories_in,
                        "protein_g": log.protein_g,
                        "carbs_g": log.carbs_g,
                        "fat_g": log.fat_g,
                        "adherence_score": log.adherence_score
                    })
                
                # Add metric card
                retrieved_data.append({
                    "type": "metric",
                    "id": weekly_measurement.id,
                    "week_start": weekly_measurement.week_start.isoformat(),
                    "weight_kg": weekly_measurement.weight_kg,
                    "body_fat_pct": weekly_measurement.body_fat_pct,
                    "waist_cm": weekly_measurement.waist_cm,
                    "rhr_bpm": weekly_measurement.rhr_bpm,
                    "sleep_avg_hrs": weekly_measurement.sleep_avg_hrs
                })
                
                # Use EvidenceMapper to map claims to evidence
                evidence_mapper = EvidenceMapper()
                evidence_cards = evidence_mapper.map_claims_to_evidence(eval_data, retrieved_data)
                
                # Store evidence cards as JSON array
                weekly_eval.evidence_map_json = {"evidence_cards": evidence_cards}
                
                logger.info(
                    "Evidence collection completed using EvidenceMapper",
                    extra={"week_id": week_id, "evidence_cards_count": len(evidence_cards)}
                )
            else:
                logger.warning(
                    f"No WeeklyMeasurement found for week_id={week_id}, skipping evidence collection"
                )
                weekly_eval.evidence_map_json = {"evidence_cards": []}
                
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
            weekly_eval.evidence_map_json = {"evidence_cards": []}
        
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

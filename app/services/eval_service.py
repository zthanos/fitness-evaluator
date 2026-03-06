# app/services/eval_service.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.services.prompt_engine import build_contract, hash_contract
from app.services.llm_client import generate_evaluation
from app.schemas.eval_output import EvalOutput
from app.models.weekly_eval import WeeklyEval
from app.models.daily_log import DailyLog
from app.models.weekly_measurement import WeeklyMeasurement
from app.models.plan_targets import PlanTargets
from app.models.strava_activity import StravaActivity


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db

    async def evaluate_week(self, week_id: str) -> WeeklyEval:
        """
        Perform a complete fitness evaluation for the given week.
        
        Args:
            week_id: String UUID of the week to evaluate
            
        Returns:
            WeeklyEval model instance with the evaluation results
        """
        # Build the contract from all relevant data
        contract = build_contract(week_id, self.db)

        # Generate evaluation from LLM
        try:
            raw_response = await generate_evaluation(contract)

            # Parse and validate the response
            eval_data = EvalOutput.model_validate_json(raw_response)

        except Exception as e:
            raise ValueError(f"Failed to generate or validate evaluation: {str(e)}")
        
        # Create or update WeeklyEval record
        weekly_eval = self.db.query(WeeklyEval).filter(WeeklyEval.week_id == week_id).first()
        
        if not weekly_eval:
            weekly_eval = WeeklyEval(week_id=week_id)
            self.db.add(weekly_eval)
        
        # Update the evaluation with results
        weekly_eval.input_hash = hash_contract(contract)
        weekly_eval.raw_llm_response = raw_response
        weekly_eval.parsed_output_json = eval_data.model_dump()
        weekly_eval.generated_at = datetime.now()
        
        # Collect evidence for traceability
        from app.services.evidence_collector import collect_evidence
        evidence = collect_evidence(eval_data, week_id, self.db)
        weekly_eval.evidence_map_json = evidence
        
        self.db.commit()
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

"""LangChain-based Evaluation Service with Context Engineering

Uses Context Engineering architecture for structured evaluation generation.
Integrates OutputValidator for schema enforcement and ConfidenceScorer
for hybrid confidence computation.
"""
import json
import logging
from typing import Dict, Any

try:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from app.config import get_settings
from app.schemas.eval_output import EvalOutput
from app.ai.contracts.evaluation_contract import WeeklyEvalContract
from app.ai.validators.output_validator import OutputValidator, OutputValidationError
from app.ai.derived.confidence_scorer import ConfidenceScorer
from app.ai.context.builder import Context
from app.ai.derived.metrics_engine import DerivedMetrics
from app.ai.prompts.system_loader import SystemInstructionsLoader
from app.ai.prompts.task_loader import TaskInstructionsLoader
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class LangChainEvaluationService:
    """
    LangChain-based evaluation service with Context Engineering integration.
    
    Uses OutputValidator for reliable schema enforcement and ConfidenceScorer
    for hybrid confidence computation. Supports both Ollama and LM Studio backends.
    
    Requirements: 5.3.2, 5.3.4
    """
    
    def __init__(self):
        """
        Initialize LangChain evaluation service with CE components.
        
        Raises:
            ImportError: If LangChain is not available
        """
        if not LANGCHAIN_AVAILABLE:
            error_msg = (
                "LangChain is not available. Install with: "
                "uv pip install langchain-core langchain-ollama langchain-openai"
            )
            logger.error(
                "LangChain initialization failed: Missing dependencies",
                extra={"error": "ImportError", "solution": error_msg}
            )
            raise ImportError(error_msg)
        
        self.settings = get_settings()
        
        # Initialize CE components
        self.output_validator = OutputValidator()
        self.confidence_scorer = ConfidenceScorer()
        self.system_loader = SystemInstructionsLoader()
        self.task_loader = TaskInstructionsLoader()
        
        # Determine which LLM backend to use
        llm_type = self.settings.LLM_TYPE.lower()
        
        try:
            if llm_type in ["lm-studio", "openai"]:
                # Use OpenAI-compatible endpoint (LM Studio)
                logger.info("Initializing LangChain with LM Studio/OpenAI backend")
                base_url = self.settings.llm_base_url
                # Remove /v1 if it's already in the URL since ChatOpenAI handles it
                if base_url.endswith('/v1'):
                    base_url = base_url[:-3]
                
                self.llm = ChatOpenAI(
                    base_url=base_url,
                    api_key="lm-studio",  # LM Studio doesn't require a real key
                    model=self.settings.OLLAMA_MODEL,
                    temperature=0.1,  # Low temperature for consistent outputs
                )
                logger.info(f"Using LM Studio base_url: {base_url}")
            else:
                # Use Ollama backend (default)
                logger.info("Initializing LangChain with Ollama backend")
                self.llm = ChatOllama(
                    base_url=self.settings.llm_base_url,
                    model=self.settings.OLLAMA_MODEL,
                    temperature=0.1,  # Low temperature for consistent outputs
                )
            
            # Bind structured output schema - use WeeklyEvalContract
            self.llm_with_structure = self.llm.with_structured_output(WeeklyEvalContract)
            
            logger.info(
                "LangChain initialized successfully with CE components",
                extra={
                    "backend": llm_type,
                    "endpoint": self.settings.llm_base_url,
                    "model": self.settings.OLLAMA_MODEL,
                    "temperature": 0.1,
                    "output_contract": "WeeklyEvalContract"
                }
            )
        except Exception as e:
            logger.error(
                "LangChain initialization failed",
                extra={
                    "backend": llm_type,
                    "endpoint": self.settings.llm_base_url,
                    "model": self.settings.OLLAMA_MODEL,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    async def generate_evaluation(
        self,
        contract: Dict[str, Any],
        context: Context = None,
        metrics: DerivedMetrics = None
    ) -> EvalOutput:
        """
        Generate evaluation with Context Engineering validation and confidence scoring.
        
        Uses OutputValidator for schema enforcement and ConfidenceScorer for
        hybrid confidence computation. Maintains backward compatibility by
        returning EvalOutput schema.
        
        Args:
            contract: Evaluation contract with all input data
            context: Optional Context object for confidence scoring
            metrics: Optional DerivedMetrics for confidence scoring
            
        Returns:
            EvalOutput: Validated evaluation output (legacy schema)
            
        Raises:
            ValueError: If validation fails after retries
        
        Requirements: 5.3.2, 5.3.4
        """
        from app.services.prompt_engine import hash_contract
        contract_hash = hash_contract(contract)
        
        # Load system and task instructions using CE loaders
        system_instructions = self.system_loader.load(version="1.0.0")
        task_instructions = self.task_loader.load(
            operation="weekly_eval",
            version="1.0.0",
            params={
                "week_start": contract.get("week", {}).get("start", ""),
                "week_end": contract.get("week", {}).get("end", "")
            }
        )
        
        messages = [
            SystemMessage(content=system_instructions),
            HumanMessage(content=f"{task_instructions}\n\n# Input Data\n{json.dumps(contract, indent=2, default=str)}")
        ]
        
        # Retry logic with OutputValidator
        for attempt in range(3):
            try:
                logger.info(
                    f"Invoking LLM with CE validation (attempt {attempt + 1}/3)",
                    extra={
                        "backend": self.settings.LLM_TYPE,
                        "model": self.settings.OLLAMA_MODEL,
                        "contract_hash": contract_hash,
                        "attempt": attempt + 1,
                        "output_contract": "WeeklyEvalContract"
                    }
                )
                
                # Invoke LLM with structured output
                result = await self.llm_with_structure.ainvoke(messages)
                
                # Compute hybrid confidence if context and metrics provided
                if context and metrics:
                    system_confidence = self.confidence_scorer.compute_system_confidence(
                        context, metrics
                    )
                    llm_confidence = result.confidence_score
                    hybrid_confidence = self.confidence_scorer.compute_hybrid_confidence(
                        system_confidence, llm_confidence
                    )
                    
                    logger.info(
                        "Hybrid confidence computed",
                        extra={
                            "contract_hash": contract_hash,
                            "system_confidence": system_confidence,
                            "llm_confidence": llm_confidence,
                            "hybrid_confidence": hybrid_confidence
                        }
                    )
                    
                    # Update result with hybrid confidence
                    result.confidence_score = hybrid_confidence
                
                logger.info(
                    "LLM invocation successful with CE validation",
                    extra={
                        "contract_hash": contract_hash,
                        "attempt": attempt + 1,
                        "confidence_score": result.confidence_score
                    }
                )
                
                # Convert WeeklyEvalContract to EvalOutput for backward compatibility
                eval_output = self._convert_to_eval_output(result)
                return eval_output
                
            except ValidationError as e:
                logger.warning(
                    f"Schema validation failed (attempt {attempt + 1}/3)",
                    extra={
                        "contract_hash": contract_hash,
                        "attempt": attempt + 1,
                        "validation_errors": e.errors()
                    }
                )
                
                if attempt == 2:
                    logger.error(
                        "Schema validation failed after 3 attempts",
                        extra={
                            "contract_hash": contract_hash,
                            "validation_errors": e.errors()
                        }
                    )
                    raise ValueError(
                        f"Schema validation failed after 3 attempts. "
                        f"Contract hash: {contract_hash[:8]}... "
                        f"Errors: {e.errors()}"
                    )
                
                # Add schema guidance for retry
                messages.append(AIMessage(content="Schema validation failed"))
                messages.append(
                    HumanMessage(
                        content=f"Please ensure response matches: {WeeklyEvalContract.model_json_schema()}"
                    )
                )
                
            except Exception as e:
                logger.error(
                    "LLM invocation failed",
                    extra={
                        "backend": self.settings.LLM_TYPE,
                        "model": self.settings.OLLAMA_MODEL,
                        "endpoint": self.settings.llm_base_url,
                        "contract_hash": contract_hash,
                        "attempt": attempt + 1,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                raise ValueError(
                    f"LLM evaluation failed: {str(e)} "
                    f"(Backend: {self.settings.LLM_TYPE}, "
                    f"Model: {self.settings.OLLAMA_MODEL}, "
                    f"Contract hash: {contract_hash[:8]}...)"
                )
    
    def _convert_to_eval_output(self, weekly_eval: WeeklyEvalContract) -> EvalOutput:
        """
        Convert WeeklyEvalContract to EvalOutput for backward compatibility.
        
        Maps the new CE contract schema to the legacy EvalOutput schema
        to maintain existing API contracts.
        
        Args:
            weekly_eval: WeeklyEvalContract instance from LLM
            
        Returns:
            EvalOutput: Legacy schema instance
        """
        from app.schemas.eval_output import (
            NutritionAnalysis,
            TrainingAnalysis,
            Recommendation as LegacyRecommendation
        )
        
        # Convert recommendations
        legacy_recommendations = []
        for rec in weekly_eval.recommendations:
            legacy_recommendations.append(
                LegacyRecommendation(
                    area=rec.category.capitalize(),
                    action=rec.text,
                    priority=rec.priority
                )
            )
        
        # Create placeholder nutrition and training analysis
        # (These fields don't exist in WeeklyEvalContract but are required by EvalOutput)
        nutrition_analysis = NutritionAnalysis(
            commentary="See overall assessment and recommendations for nutrition insights."
        )
        training_analysis = TrainingAnalysis(
            commentary="See overall assessment and recommendations for training insights."
        )
        
        # Map to EvalOutput schema
        return EvalOutput(
            overall_score=8,  # Default score (WeeklyEvalContract doesn't have numeric score)
            summary=weekly_eval.overall_assessment[:500],  # Truncate to max length
            wins=weekly_eval.strengths,
            misses=weekly_eval.areas_for_improvement,
            nutrition_analysis=nutrition_analysis,
            training_analysis=training_analysis,
            recommendations=legacy_recommendations,
            data_confidence=weekly_eval.confidence_score
        )

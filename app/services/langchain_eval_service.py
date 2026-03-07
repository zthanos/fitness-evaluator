"""LangChain-based Evaluation Service with Structured Output

Uses LangChain to generate fitness evaluations with structured output parsing.
Supports both Ollama and LM Studio (OpenAI-compatible) backends.
Provides reliable structured output validation using Pydantic schemas.
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
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class LangChainEvaluationService:
    """
    LangChain-based evaluation service with structured output parsing.
    
    Uses LangChain's with_structured_output for reliable EvalOutput generation.
    Supports both Ollama and LM Studio backends with consistent configuration.
    """
    
    def __init__(self):
        """
        Initialize LangChain evaluation service.
        
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
            
            # Bind structured output schema
            self.llm_with_structure = self.llm.with_structured_output(EvalOutput)
            
            logger.info(
                "LangChain initialized successfully",
                extra={
                    "backend": llm_type,
                    "endpoint": self.settings.llm_base_url,
                    "model": self.settings.OLLAMA_MODEL,
                    "temperature": 0.1
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
    
    async def generate_evaluation(self, contract: Dict[str, Any]) -> EvalOutput:
        """
        Generate evaluation with structured output parsing.
        
        Args:
            contract: Evaluation contract with all input data
            
        Returns:
            EvalOutput: Validated evaluation output
            
        Raises:
            ValueError: If validation fails after retries
        """
        from app.services.prompt_engine import hash_contract
        contract_hash = hash_contract(contract)
        
        prompt = self._load_prompt_template()
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=json.dumps(contract, indent=2, default=str))
        ]
        
        # Retry logic for invalid responses
        raw_response = None
        for attempt in range(3):
            try:
                logger.info(
                    f"Invoking LLM (attempt {attempt + 1}/3)",
                    extra={
                        "backend": self.settings.LLM_TYPE,
                        "model": self.settings.OLLAMA_MODEL,
                        "contract_hash": contract_hash,
                        "attempt": attempt + 1
                    }
                )
                result = await self.llm_with_structure.ainvoke(messages)
                logger.info(
                    "LLM invocation successful, validation passed",
                    extra={
                        "contract_hash": contract_hash,
                        "attempt": attempt + 1
                    }
                )
                return result
            except ValidationError as e:
                # Store raw response for logging if available
                raw_response = str(result) if 'result' in locals() else "N/A"
                
                logger.warning(
                    f"Schema validation failed (attempt {attempt + 1}/3)",
                    extra={
                        "contract_hash": contract_hash,
                        "attempt": attempt + 1,
                        "validation_errors": e.errors(),
                        "raw_response": raw_response[:500]  # Truncate for logging
                    }
                )
                
                if attempt == 2:
                    logger.error(
                        "Schema validation failed after 3 attempts",
                        extra={
                            "contract_hash": contract_hash,
                            "validation_errors": e.errors(),
                            "raw_response": raw_response
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
                        content=f"Please ensure response matches: {EvalOutput.model_json_schema()}"
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
    
    def _load_prompt_template(self) -> str:
        """
        Load evaluation prompt template.
        
        Returns:
            str: Prompt template content
        """
        try:
            with open('app/prompts/evaluation_prompt.txt', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Evaluation prompt file not found, using default prompt")
            return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """
        Get default evaluation prompt.
        
        Returns:
            str: Default prompt template
        """
        return """You are an expert fitness coach analyzing weekly performance data.

Analyze the provided data and generate a comprehensive evaluation with:
1. Overall score (1-10) based on adherence to targets and progress
2. Summary of the week's performance (50-500 characters)
3. Wins: List of achievements and positive outcomes
4. Misses: List of areas that need improvement
5. Nutrition analysis: Average calories, protein, adherence score with commentary
6. Training analysis: Total run km, strength sessions, active minutes with commentary
7. Recommendations: Maximum 5 specific, actionable recommendations with priority (1-5)
8. Data confidence: Score (0.0-1.0) based on completeness of input data

Provide specific, actionable insights based on the data provided."""

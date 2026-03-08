"""
Output validator for LLM response validation against Pydantic schemas.

This module provides validation of LLM responses against output contracts,
ensuring that AI-generated responses conform to expected schemas with
detailed error reporting for debugging and retry logic.
"""

import json
from typing import Type, List, Dict, Any
from pydantic import BaseModel, ValidationError


class OutputValidationError(Exception):
    """
    Exception raised when LLM output fails validation against contract schema.
    
    This exception captures detailed validation errors and the original
    response for debugging purposes.
    
    Attributes:
        errors: List of validation error details from Pydantic
        original_response: The raw response string that failed validation
    """
    
    def __init__(self, errors: List[Dict[str, Any]], original_response: str):
        """
        Initialize OutputValidationError.
        
        Args:
            errors: List of validation error details
            original_response: The raw response that failed validation
        """
        self.errors = errors
        self.original_response = original_response
        
        # Format error message
        error_summary = self._format_errors(errors)
        message = (
            f"Output validation failed with {len(errors)} error(s):\n"
            f"{error_summary}\n\n"
            f"Original response:\n{original_response[:500]}..."
        )
        super().__init__(message)
    
    def _format_errors(self, errors: List[Dict[str, Any]]) -> str:
        """Format validation errors for display."""
        formatted = []
        for error in errors:
            loc = " -> ".join(str(x) for x in error.get('loc', []))
            msg = error.get('msg', 'Unknown error')
            error_type = error.get('type', 'unknown')
            formatted.append(f"  - {loc}: {msg} (type: {error_type})")
        return "\n".join(formatted)


class OutputValidator:
    """
    Validator for LLM responses against Pydantic output contracts.
    
    This class provides validation of LLM-generated responses against
    Pydantic schemas, with detailed error reporting for debugging and
    support for retry logic with guidance.
    
    Requirements: 3.2.4, 3.2.5
    """
    
    def validate(
        self,
        response: str,
        contract: Type[BaseModel]
    ) -> BaseModel:
        """
        Validate LLM response against Pydantic contract schema.
        
        This method parses the response string as JSON and validates it
        against the provided Pydantic contract. On success, it returns
        the validated contract instance. On failure, it raises
        OutputValidationError with detailed error information.
        
        Args:
            response: The raw LLM response string (expected to be JSON)
            contract: The Pydantic model class to validate against
        
        Returns:
            Validated instance of the contract model
        
        Raises:
            OutputValidationError: If JSON parsing fails or validation fails
        
        Example:
            >>> validator = OutputValidator()
            >>> response = '{"overall_assessment": "Good week", ...}'
            >>> result = validator.validate(response, WeeklyEvalContract)
        """
        # Handle JSON parsing errors
        try:
            parsed_data = json.loads(response)
        except json.JSONDecodeError as e:
            raise OutputValidationError(
                errors=[{
                    'loc': ['__root__'],
                    'msg': f'Invalid JSON: {str(e)}',
                    'type': 'json_decode_error'
                }],
                original_response=response
            )
        
        # Handle Pydantic validation errors
        try:
            validated_instance = contract.model_validate(parsed_data)
            return validated_instance
        except ValidationError as e:
            # Extract error details from Pydantic ValidationError
            error_details = []
            for error in e.errors():
                error_details.append({
                    'loc': error['loc'],
                    'msg': error['msg'],
                    'type': error['type']
                })
            
            raise OutputValidationError(
                errors=error_details,
                original_response=response
            )

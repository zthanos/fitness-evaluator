"""
Task Instructions Loader

This module provides the TaskInstructionsLoader class for loading and rendering
versioned Jinja2 templates for AI task-specific instructions.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import tiktoken
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class TaskInstructionsLoader:
    """
    Loads and renders versioned task instruction templates.
    
    Task instructions specify analytical objectives and output schema for each
    operation type (weekly_eval, chat_response, goal_analysis). Templates are
    stored as versioned Jinja2 files and can be rendered with runtime parameters.
    """
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the TaskInstructionsLoader.
        
        Args:
            templates_dir: Directory containing task instruction templates.
                          Defaults to app/ai/prompts/tasks/
        """
        if templates_dir is None:
            # Default to app/ai/prompts/tasks/
            current_file = Path(__file__)
            templates_dir = current_file.parent / "tasks"
        
        self.templates_dir = Path(templates_dir)
        
        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=False,  # We're generating prompts, not HTML
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Initialize tiktoken encoding for token counting
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def load(
        self,
        operation: str,
        version: str = "1.0.0",
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Load and render a task instructions template with runtime parameters.
        
        Args:
            operation: Operation type (e.g., "weekly_eval", "chat_response")
            version: Version string (e.g., "1.0.0")
            params: Runtime parameters to inject into template (e.g., athlete_id, week_id)
        
        Returns:
            Rendered task instructions as a string
        
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template is missing required fields
        """
        template_name = f"{operation}_v{version}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            raise FileNotFoundError(
                f"Task instructions template not found: {template_name} "
                f"in directory {self.templates_dir}"
            )
        
        # Render template with runtime parameters
        params = params or {}
        rendered = template.render(**params)
        
        # Validate required fields
        self._validate_template(rendered, template_name)
        
        return rendered
    
    def validate_token_limit(self, rendered: str, max_tokens: int = 800) -> bool:
        """
        Validate that rendered instructions fit within token budget.
        
        Args:
            rendered: Rendered template content
            max_tokens: Maximum allowed tokens (default: 800)
        
        Returns:
            True if within limit, False otherwise
        """
        token_count = len(self.encoding.encode(rendered))
        return token_count <= max_tokens
    
    def _validate_template(self, rendered: str, template_name: str) -> None:
        """
        Validate that rendered template contains required fields.
        
        Args:
            rendered: Rendered template content
            template_name: Name of the template (for error messages)
        
        Raises:
            ValueError: If required fields are missing
        """
        required_fields = [
            "objective",
            "input_description",
            "output_schema_reference"
        ]
        
        missing_fields = []
        rendered_lower = rendered.lower()
        
        for field in required_fields:
            # Check if field keyword appears in the rendered template
            # We look for the field name as a word (case-insensitive)
            field_variants = [
                field,
                field.replace("_", " "),
                field.replace("_", "-")
            ]
            
            if not any(variant in rendered_lower for variant in field_variants):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(
                f"Template {template_name} is missing required fields: "
                f"{', '.join(missing_fields)}. "
                f"Required fields: {', '.join(required_fields)}"
            )

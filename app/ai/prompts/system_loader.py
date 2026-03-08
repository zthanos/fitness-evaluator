"""
System Instructions Loader

This module provides the SystemInstructionsLoader class for loading and rendering
versioned Jinja2 templates for AI coach system instructions.
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class SystemInstructionsLoader:
    """
    Loads and renders versioned system instruction templates.
    
    System instructions define the AI coach persona, behavioral constraints,
    and output format expectations. Templates are stored as versioned Jinja2
    files and can be rendered with configuration variables.
    """
    
    def __init__(self, templates_dir: Optional[Path] = None, config_dir: Optional[Path] = None):
        """
        Initialize the SystemInstructionsLoader.
        
        Args:
            templates_dir: Directory containing system instruction templates.
                          Defaults to app/ai/prompts/system/
            config_dir: Directory containing configuration files.
                       Defaults to app/ai/config/
        """
        if templates_dir is None:
            # Default to app/ai/prompts/system/
            current_file = Path(__file__)
            templates_dir = current_file.parent / "system"
        
        if config_dir is None:
            # Default to app/ai/config/
            current_file = Path(__file__)
            config_dir = current_file.parent.parent / "config"
        
        self.templates_dir = Path(templates_dir)
        self.config_dir = Path(config_dir)
        
        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=False,  # We're generating prompts, not HTML
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def load(self, version: str = "1.0.0") -> str:
        """
        Load and render a system instructions template.
        
        Args:
            version: Version string (e.g., "1.0.0")
        
        Returns:
            Rendered system instructions as a string
        
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template is missing required sections
        """
        template_name = f"coach_persona_v{version}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            raise FileNotFoundError(
                f"System instructions template not found: {template_name} "
                f"in directory {self.templates_dir}"
            )
        
        # Load configuration variables
        config_vars = self._load_config()
        
        # Render template with configuration
        rendered = template.render(**config_vars)
        
        # Validate required sections
        self._validate_template(rendered, template_name)
        
        return rendered
    
    def list_versions(self) -> List[str]:
        """
        List available system instruction versions.
        
        Returns:
            List of version strings (e.g., ["1.0.0", "1.1.0"])
        """
        if not self.templates_dir.exists():
            return []
        
        versions = []
        for file_path in self.templates_dir.glob("coach_persona_v*.j2"):
            # Extract version from filename: coach_persona_v1.0.0.j2 -> 1.0.0
            filename = file_path.stem  # Remove .j2 extension
            if filename.startswith("coach_persona_v"):
                version = filename.replace("coach_persona_v", "")
                versions.append(version)
        
        # Sort versions (simple string sort works for semantic versioning)
        return sorted(versions)
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration variables from coach_persona.yaml.
        
        Returns:
            Dictionary of configuration variables
        """
        config_file = self.config_dir / "coach_persona.yaml"
        
        if not config_file.exists():
            # Return default configuration if file doesn't exist
            return {
                "coach_name": "AI Coach",
                "certifications": [
                    "Exercise Physiology",
                    "Sports Nutrition",
                    "Strength and Conditioning"
                ],
                "tone": "supportive and data-driven",
                "max_recommendations": 5
            }
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config or {}
        except Exception as e:
            raise ValueError(f"Failed to load configuration from {config_file}: {e}")
    
    def _validate_template(self, rendered: str, template_name: str) -> None:
        """
        Validate that rendered template contains required sections.
        
        Args:
            rendered: Rendered template content
            template_name: Name of the template (for error messages)
        
        Raises:
            ValueError: If required sections are missing
        """
        required_sections = [
            "persona",
            "behavioral_constraints",
            "output_format"
        ]
        
        missing_sections = []
        rendered_lower = rendered.lower()
        
        for section in required_sections:
            # Check if section keyword appears in the rendered template
            # We look for the section name as a word (case-insensitive)
            if section.replace("_", " ") not in rendered_lower and section not in rendered_lower:
                missing_sections.append(section)
        
        if missing_sections:
            raise ValueError(
                f"Template {template_name} is missing required sections: "
                f"{', '.join(missing_sections)}. "
                f"Required sections: {', '.join(required_sections)}"
            )

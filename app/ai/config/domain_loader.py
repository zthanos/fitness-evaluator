"""Domain Knowledge Loader

Loads sport science reference values from domain_knowledge.yaml.
Provides structured access to training zones, effort levels, recovery guidelines,
and nutrition targets.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml


@dataclass
class TrainingZone:
    """Training zone definition with heart rate and RPE ranges"""
    name: str
    hr_pct_max: Tuple[int, int]
    rpe: Tuple[int, int]
    description: str


@dataclass
class DomainKnowledge:
    """Complete domain knowledge structure"""
    training_zones: Dict[str, TrainingZone]
    effort_levels: Dict[str, Any]
    recovery_guidelines: Dict[str, int]
    nutrition_targets: Dict[str, Any]


class DomainKnowledgeLoader:
    """Loads and validates domain knowledge from YAML configuration"""
    
    def __init__(self, config_path: str = None):
        """Initialize loader with optional custom config path
        
        Args:
            config_path: Path to domain_knowledge.yaml (defaults to app/ai/config/)
        """
        if config_path is None:
            # Default to app/ai/config/domain_knowledge.yaml
            self.config_path = Path(__file__).parent / "domain_knowledge.yaml"
        else:
            self.config_path = Path(config_path)
    
    def load(self) -> DomainKnowledge:
        """Load and parse domain knowledge from YAML
        
        Returns:
            DomainKnowledge instance with all reference values
            
        Raises:
            FileNotFoundError: If domain_knowledge.yaml is not found
            ValueError: If YAML structure is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Domain knowledge file not found: {self.config_path}"
            )
        
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Validate schema before parsing
        self.validate_schema(data)
        
        # Parse training zones
        training_zones = {}
        for zone_name, zone_data in data['training_zones'].items():
            training_zones[zone_name] = TrainingZone(
                name=zone_name,
                hr_pct_max=tuple(zone_data['hr_pct_max']),
                rpe=tuple(zone_data['rpe']),
                description=zone_data['description']
            )
        
        return DomainKnowledge(
            training_zones=training_zones,
            effort_levels=data['effort_levels'],
            recovery_guidelines=data['recovery_guidelines'],
            nutrition_targets=data['nutrition_targets']
        )
    
    def validate_schema(self, data: Dict[str, Any] = None) -> bool:
        """Validate YAML structure on application startup
        
        Args:
            data: Optional pre-loaded YAML data (loads from file if None)
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If required sections or fields are missing
        """
        if data is None:
            if not self.config_path.exists():
                raise ValueError(
                    f"Domain knowledge file not found: {self.config_path}"
                )
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)
        
        # Check required top-level sections
        required_sections = [
            'training_zones',
            'effort_levels',
            'recovery_guidelines',
            'nutrition_targets'
        ]
        
        for section in required_sections:
            if section not in data:
                raise ValueError(
                    f"Missing required section in domain knowledge: {section}"
                )
        
        # Validate training_zones structure
        if not isinstance(data['training_zones'], dict):
            raise ValueError("training_zones must be a dictionary")
        
        for zone_name, zone_data in data['training_zones'].items():
            required_zone_fields = ['hr_pct_max', 'rpe', 'description']
            for field in required_zone_fields:
                if field not in zone_data:
                    raise ValueError(
                        f"Missing required field '{field}' in training zone '{zone_name}'"
                    )
            
            # Validate hr_pct_max is a list of 2 integers
            if not isinstance(zone_data['hr_pct_max'], list) or len(zone_data['hr_pct_max']) != 2:
                raise ValueError(
                    f"hr_pct_max must be a list of 2 integers in zone '{zone_name}'"
                )
            
            # Validate rpe is a list of 2 integers
            if not isinstance(zone_data['rpe'], list) or len(zone_data['rpe']) != 2:
                raise ValueError(
                    f"rpe must be a list of 2 integers in zone '{zone_name}'"
                )
        
        # Validate effort_levels structure
        if not isinstance(data['effort_levels'], dict):
            raise ValueError("effort_levels must be a dictionary")
        
        for level_name, level_data in data['effort_levels'].items():
            if 'zones' not in level_data:
                raise ValueError(
                    f"Missing 'zones' field in effort level '{level_name}'"
                )
            if 'target_pct' not in level_data:
                raise ValueError(
                    f"Missing 'target_pct' field in effort level '{level_name}'"
                )
        
        # Validate recovery_guidelines structure
        if not isinstance(data['recovery_guidelines'], dict):
            raise ValueError("recovery_guidelines must be a dictionary")
        
        required_recovery_fields = [
            'rest_days_per_week',
            'max_consecutive_training_days',
            'hard_sessions_per_week',
            'recovery_week_frequency'
        ]
        
        for field in required_recovery_fields:
            if field not in data['recovery_guidelines']:
                raise ValueError(
                    f"Missing required field '{field}' in recovery_guidelines"
                )
        
        # Validate nutrition_targets structure
        if not isinstance(data['nutrition_targets'], dict):
            raise ValueError("nutrition_targets must be a dictionary")
        
        required_nutrition_fields = [
            'protein_g_per_kg',
            'carbs_pct_calories',
            'fat_pct_calories'
        ]
        
        for field in required_nutrition_fields:
            if field not in data['nutrition_targets']:
                raise ValueError(
                    f"Missing required field '{field}' in nutrition_targets"
                )
            
            # Validate each is a list of 2 numbers
            if not isinstance(data['nutrition_targets'][field], list) or \
               len(data['nutrition_targets'][field]) != 2:
                raise ValueError(
                    f"nutrition_targets.{field} must be a list of 2 numbers"
                )
        
        return True

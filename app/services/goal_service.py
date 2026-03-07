"""Goal Service

Handles athlete goal management with LLM tool calling integration.
Provides methods for saving, retrieving, and updating goals.
"""
from datetime import date, datetime
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from app.models.athlete_goal import AthleteGoal, GoalType, GoalStatus
import uuid


class GoalService:
    """
    Service for managing athlete goals with LLM tool calling support.
    
    This service provides the backend for LLM-assisted goal setting,
    where the LLM asks clarifying questions and calls tools to save
    structured goal data.
    """
    
    def __init__(self, db: Session):
        """
        Initialize GoalService.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def save_goal(
        self,
        goal_type: str,
        description: str,
        target_value: Optional[float] = None,
        target_date: Optional[str] = None,
        athlete_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save a new athlete goal (called by LLM tool).
        
        This method is designed to be called by the LLM through tool calling.
        It validates the goal parameters and persists the goal to the database.
        
        Args:
            goal_type: Type of goal (weight_loss, weight_gain, performance, etc.)
            description: Detailed goal description from conversation
            target_value: Optional numeric target (e.g., target weight in kg)
            target_date: Optional target completion date (YYYY-MM-DD format)
            athlete_id: Optional athlete identifier (for future multi-athlete support)
        
        Returns:
            Dict with success status, goal_id, and message
        
        Raises:
            ValueError: If goal_type is invalid or validation fails
        """
        # Validate goal_type
        valid_types = [gt.value for gt in GoalType]
        if goal_type not in valid_types:
            raise ValueError(
                f"Invalid goal_type '{goal_type}'. Must be one of: {', '.join(valid_types)}"
            )
        
        # Validate description
        if not description or len(description.strip()) < 10:
            raise ValueError("Description must be at least 10 characters long")
        
        # Parse target_date if provided
        parsed_target_date = None
        if target_date:
            try:
                parsed_target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
                
                # Validate target_date is in the future
                if parsed_target_date <= date.today():
                    raise ValueError("Target date must be in the future")
            except ValueError as e:
                if "does not match format" in str(e):
                    raise ValueError("Target date must be in YYYY-MM-DD format")
                raise
        
        # Validate target_value for weight goals
        if goal_type in [GoalType.WEIGHT_LOSS.value, GoalType.WEIGHT_GAIN.value]:
            if target_value is None:
                raise ValueError(f"target_value is required for {goal_type} goals")
            if target_value < 30 or target_value > 300:
                raise ValueError("Target weight must be between 30kg and 300kg")
        
        # Create goal
        goal = AthleteGoal(
            id=str(uuid.uuid4()),
            athlete_id=athlete_id,
            goal_type=goal_type,
            target_value=target_value,
            target_date=parsed_target_date,
            description=description.strip(),
            status=GoalStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        
        return {
            'success': True,
            'goal_id': goal.id,
            'message': f"Goal '{goal_type}' successfully saved with ID {goal.id}",
            'goal': goal.to_dict()
        }
    
    def get_active_goals(self, athlete_id: Optional[str] = None) -> list[AthleteGoal]:
        """
        Retrieve all active goals for an athlete.
        
        Args:
            athlete_id: Optional athlete identifier
        
        Returns:
            List of active AthleteGoal objects
        """
        query = self.db.query(AthleteGoal).filter(
            AthleteGoal.status == GoalStatus.ACTIVE.value
        )
        
        if athlete_id:
            query = query.filter(AthleteGoal.athlete_id == athlete_id)
        
        return query.order_by(AthleteGoal.created_at.desc()).all()
    
    def get_goal_by_id(self, goal_id: str) -> Optional[AthleteGoal]:
        """
        Retrieve a specific goal by ID.
        
        Args:
            goal_id: Goal identifier
        
        Returns:
            AthleteGoal object or None if not found
        """
        return self.db.query(AthleteGoal).filter(AthleteGoal.id == goal_id).first()
    
    def update_goal_status(
        self,
        goal_id: str,
        status: str
    ) -> Dict[str, Any]:
        """
        Update the status of a goal.
        
        Args:
            goal_id: Goal identifier
            status: New status (active, completed, abandoned)
        
        Returns:
            Dict with success status and message
        
        Raises:
            ValueError: If goal not found or status is invalid
        """
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            raise ValueError(f"Goal with ID {goal_id} not found")
        
        # Validate status
        valid_statuses = [gs.value for gs in GoalStatus]
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
            )
        
        goal.status = status
        goal.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(goal)
        
        return {
            'success': True,
            'message': f"Goal status updated to '{status}'",
            'goal': goal.to_dict()
        }
    
    def delete_goal(self, goal_id: str) -> Dict[str, Any]:
        """
        Delete a goal.
        
        Args:
            goal_id: Goal identifier
        
        Returns:
            Dict with success status and message
        
        Raises:
            ValueError: If goal not found
        """
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            raise ValueError(f"Goal with ID {goal_id} not found")
        
        self.db.delete(goal)
        self.db.commit()
        
        return {
            'success': True,
            'message': f"Goal {goal_id} deleted successfully"
        }
    
    @staticmethod
    def get_tool_definition() -> Dict[str, Any]:
        """
        Get the LLM tool definition for save_athlete_goal.
        
        This definition is used by the LLM to understand how to call
        the save_goal method through tool calling.
        
        Returns:
            Tool definition dict compatible with Ollama function calling
        """
        return {
            'type': 'function',
            'function': {
                'name': 'save_athlete_goal',
                'description': (
                    'Save a new fitness goal for the athlete. Use this tool after gathering '
                    'sufficient information about the athlete\'s goal through conversation. '
                    'Ask clarifying questions about timeframe, specific targets, and any constraints '
                    'before calling this tool.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'goal_type': {
                            'type': 'string',
                            'enum': ['weight_loss', 'weight_gain', 'performance', 'endurance', 'strength', 'custom'],
                            'description': 'The type of fitness goal'
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Detailed description of the goal including context from the conversation'
                        },
                        'target_value': {
                            'type': 'number',
                            'description': 'Optional numeric target (e.g., target weight in kg for weight goals)'
                        },
                        'target_date': {
                            'type': 'string',
                            'description': 'Optional target completion date in YYYY-MM-DD format'
                        }
                    },
                    'required': ['goal_type', 'description']
                }
            }
        }

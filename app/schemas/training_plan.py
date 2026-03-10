"""Training Plan Dataclasses

Python dataclasses for in-memory representation of training plans.
These are used for parsing AI-generated plans and for data transfer.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List


@dataclass
class TrainingSession:
    """
    Individual training session within a week.
    
    Attributes:
        day_of_week: Day of week (1=Monday, 7=Sunday)
        session_type: Type of session (e.g., "easy_run", "interval", "rest")
        duration_minutes: Planned duration in minutes
        intensity: Intensity level (recovery, easy, moderate, hard, max)
        description: Detailed session description
        completed: Whether session has been completed
        matched_activity_id: Reference to matched Strava activity
    """
    day_of_week: int
    session_type: str
    duration_minutes: int
    intensity: str
    description: str
    completed: bool = False
    matched_activity_id: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate session data integrity."""
        errors = []
        
        # Validate day_of_week
        if not (1 <= self.day_of_week <= 7):
            errors.append("day_of_week must be between 1 and 7")
        
        # Validate session_type
        valid_session_types = [
            'easy_run', 'tempo_run', 'interval', 'long_run', 'recovery_run',
            'easy_ride', 'tempo_ride', 'interval_ride', 'long_ride',
            'swim_technique', 'swim_endurance', 'swim_interval',
            'rest', 'cross_training', 'strength'
        ]
        if self.session_type not in valid_session_types:
            errors.append(f"Invalid session_type: {self.session_type}. Must be one of {valid_session_types}")
        
        # Validate duration_minutes
        if self.duration_minutes < 0:
            errors.append("duration_minutes must be >= 0")
        
        # Validate intensity
        valid_intensities = ['recovery', 'easy', 'moderate', 'hard', 'max']
        if self.intensity not in valid_intensities:
            errors.append(f"Invalid intensity: {self.intensity}. Must be one of {valid_intensities}")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        return True


@dataclass
class TrainingWeek:
    """
    Single week within a training plan.
    
    Attributes:
        week_number: Week number within the plan (1-indexed)
        focus: Weekly focus description (e.g., "Base building", "Intensity")
        volume_target: Target training volume in hours
        sessions: List of training sessions for this week
    """
    week_number: int
    focus: str
    volume_target: float
    sessions: List[TrainingSession] = field(default_factory=list)
    
    def validate(self) -> bool:
        """Validate week data integrity."""
        errors = []
        
        # Validate week_number
        if self.week_number < 1:
            errors.append("week_number must be >= 1")
        
        # Validate volume_target
        if self.volume_target < 0:
            errors.append("volume_target must be >= 0")
        
        # Validate sessions
        for session in self.sessions:
            try:
                session.validate()
            except ValueError as e:
                errors.append(f"Session validation failed: {e}")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        return True


@dataclass
class TrainingPlan:
    """
    Complete training plan with multiple weeks.
    
    Attributes:
        id: Unique identifier (UUID, optional for new plans)
        user_id: Reference to athlete
        title: Plan title (e.g., "Marathon Training")
        sport: Primary sport (running, cycling, swimming, triathlon, other)
        goal_id: Reference to linked athlete goal (optional)
        start_date: Plan start date
        end_date: Plan end date
        status: Current status (draft, active, completed, abandoned)
        weeks: List of training weeks
        created_at: Timestamp when plan was created (optional)
        updated_at: Timestamp when plan was last updated (optional)
    """
    user_id: int
    title: str
    sport: str
    start_date: date
    end_date: date
    status: str
    weeks: List[TrainingWeek] = field(default_factory=list)
    id: Optional[str] = None
    goal_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def validate(self) -> bool:
        """Validate training plan data integrity."""
        errors = []
        
        # Validate status
        valid_statuses = ['draft', 'active', 'completed', 'abandoned']
        if self.status not in valid_statuses:
            errors.append(f"Invalid status: {self.status}. Must be one of {valid_statuses}")
        
        # Validate dates
        if self.start_date >= self.end_date:
            errors.append("start_date must be before end_date")
        
        # Validate sport
        valid_sports = ['running', 'cycling', 'swimming', 'triathlon', 'other']
        if self.sport not in valid_sports:
            errors.append(f"Invalid sport: {self.sport}. Must be one of {valid_sports}")
        
        # Validate title
        if not self.title or len(self.title.strip()) == 0:
            errors.append("title cannot be empty")
        
        # Validate weeks
        for week in self.weeks:
            try:
                week.validate()
            except ValueError as e:
                errors.append(f"Week {week.week_number} validation failed: {e}")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        return True

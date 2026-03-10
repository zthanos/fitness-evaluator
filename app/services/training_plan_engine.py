"""Training Plan Engine

Handles generation, storage, and retrieval of training plans.
Integrates with LLM for activity-aware plan generation.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.schemas.training_plan import TrainingPlan, TrainingWeek, TrainingSession
from app.models.training_plan import TrainingPlan as TrainingPlanModel
from app.models.training_plan_week import TrainingPlanWeek as TrainingPlanWeekModel
from app.models.training_plan_session import TrainingPlanSession as TrainingPlanSessionModel
from app.services.training_plan_parser import parse_plan, pretty_print
from app.ai.tools.get_recent_activities import get_recent_activities
from app.ai.tools.get_weekly_metrics import get_weekly_metrics


class TrainingPlanEngine:
    """
    Training Plan Engine
    
    Manages training plan lifecycle:
    - Generation with LLM (activity-aware)
    - Parsing AI-generated text to structured data
    - Database persistence
    - Retrieval with user_id scoping
    - Plan iteration and updates
    """
    
    def __init__(self, db: Session, llm_client: Any = None):
        """
        Initialize Training Plan Engine.
        
        Args:
            db: SQLAlchemy database session
            llm_client: LLM client for plan generation (optional)
        """
        self.db = db
        self.llm_client = llm_client
    
    async def generate_plan(
        self,
        user_id: int,
        sport: str,
        duration_weeks: int,
        goal_id: Optional[str] = None,
        goal_description: Optional[str] = None,
        start_date: Optional[date] = None
    ) -> TrainingPlan:
        """
        Generate activity-aware training plan using LLM.
        
        Retrieves recent activities and weekly metrics to inform plan generation.
        Generates plans with progressive volume increases based on current training load.
        
        Args:
            user_id: Athlete user ID
            sport: Primary sport (running, cycling, swimming, triathlon, other)
            duration_weeks: Plan duration in weeks
            goal_id: Linked goal ID (optional)
            goal_description: Goal description for context (optional)
            start_date: Plan start date (defaults to next Monday)
            
        Returns:
            Structured TrainingPlan object (not yet saved to database)
            
        Raises:
            ValueError: If LLM client is not configured or generation fails
            
        Requirements: 8.1, 8.2, 8.3, 8.4, 20.2
        """
        # Validate user_id is present (Requirement 20.2)
        if user_id is None:
            raise ValueError("user_id is required for plan generation")
        
        if not self.llm_client:
            raise ValueError("LLM client not configured for plan generation")
        
        # Default start date to next Monday
        if not start_date:
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            start_date = today + timedelta(days=days_until_monday)
        
        # Retrieve recent activities (last 28 days)
        recent_activities = get_recent_activities.invoke({
            "athlete_id": user_id,
            "days_back": 28
        })
        
        # Retrieve weekly metrics (last 4 weeks)
        weekly_metrics = []
        for i in range(4):
            week_date = date.today() - timedelta(weeks=i)
            year, week_num, _ = week_date.isocalendar()
            week_id = f"{year}-W{week_num:02d}"
            
            metrics = get_weekly_metrics.invoke({
                "athlete_id": user_id,
                "week_id": week_id
            })
            if metrics:
                weekly_metrics.append(metrics)
        
        # Build activity-aware prompt
        prompt = self._build_generation_prompt(
            sport=sport,
            duration_weeks=duration_weeks,
            goal_description=goal_description,
            recent_activities=recent_activities,
            weekly_metrics=weekly_metrics,
            start_date=start_date
        )
        
        # Generate plan with LLM
        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are an expert endurance coach creating personalized training plans."},
                {"role": "user", "content": prompt}
            ]
        )
        
        plan_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse generated plan
        plan = parse_plan(plan_text, user_id)
        
        # Set goal_id if provided
        if goal_id:
            plan.goal_id = goal_id
        
        return plan
    
    def _build_generation_prompt(
        self,
        sport: str,
        duration_weeks: int,
        goal_description: Optional[str],
        recent_activities: List[Dict[str, Any]],
        weekly_metrics: List[Dict[str, Any]],
        start_date: date
    ) -> str:
        """
        Build activity-aware prompt for LLM plan generation.
        
        Incorporates recent activity data and metrics to ensure progressive volume increases.
        
        Args:
            sport: Primary sport
            duration_weeks: Plan duration
            goal_description: Goal description
            recent_activities: Recent activity data
            weekly_metrics: Weekly metrics data
            start_date: Plan start date
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            f"Create a {duration_weeks}-week {sport} training plan starting on {start_date.isoformat()}."
        ]
        
        if goal_description:
            prompt_parts.append(f"\nGoal: {goal_description}")
        
        # Add activity context
        if recent_activities:
            prompt_parts.append("\n\nRecent Training History (last 28 days):")
            
            # Calculate training load metrics
            total_activities = len(recent_activities)
            total_duration_min = sum(a.get('duration_min', 0) or 0 for a in recent_activities)
            total_distance_km = sum(a.get('distance_km', 0) or 0 for a in recent_activities)
            avg_weekly_duration = total_duration_min / 4
            avg_weekly_distance = total_distance_km / 4
            
            prompt_parts.append(f"- Total activities: {total_activities}")
            prompt_parts.append(f"- Average weekly duration: {avg_weekly_duration:.1f} minutes")
            prompt_parts.append(f"- Average weekly distance: {avg_weekly_distance:.1f} km")
            
            # Add sample activities
            prompt_parts.append("\nRecent activities:")
            for activity in recent_activities[:5]:  # Show last 5
                activity_type = activity.get('activity_type', 'Unknown')
                duration = activity.get('duration_min', 0) or 0
                distance = activity.get('distance_km', 0) or 0
                date_str = activity.get('date', '')[:10]
                prompt_parts.append(f"- {date_str}: {activity_type}, {duration:.0f} min, {distance:.1f} km")
        else:
            prompt_parts.append("\n\nNo recent training history available. Create a beginner-friendly plan.")
        
        # Add metrics context
        if weekly_metrics:
            prompt_parts.append("\n\nRecent Body Metrics:")
            latest_metrics = weekly_metrics[0]
            if latest_metrics.get('weight_kg'):
                prompt_parts.append(f"- Weight: {latest_metrics['weight_kg']} kg")
            if latest_metrics.get('rhr_bpm'):
                prompt_parts.append(f"- Resting HR: {latest_metrics['rhr_bpm']} bpm")
            if latest_metrics.get('sleep_avg_hrs'):
                prompt_parts.append(f"- Average sleep: {latest_metrics['sleep_avg_hrs']} hours")
        
        # Add format instructions
        prompt_parts.append("\n\nGenerate the plan in this exact format:")
        prompt_parts.append("""
# Training Plan: [Title]
Sport: [sport]
Duration: [X] weeks
Start Date: [YYYY-MM-DD]

## Week 1: [Focus]
Volume Target: [X] hours

### Monday - [Session Type]
Duration: [X] minutes
Intensity: [easy/moderate/hard/recovery/max]
Description: [details]

### Tuesday - [Session Type]
Duration: [X] minutes
Intensity: [easy/moderate/hard/recovery/max]
Description: [details]

[Continue for all days and weeks...]
""")
        
        prompt_parts.append("\nIMPORTANT:")
        prompt_parts.append("- Use progressive volume increases (10% rule)")
        prompt_parts.append("- Base initial volume on recent training history")
        prompt_parts.append("- Include recovery weeks every 3-4 weeks")
        prompt_parts.append("- Use valid session types: easy_run, tempo_run, interval, long_run, recovery_run, easy_ride, tempo_ride, interval_ride, long_ride, swim_technique, swim_endurance, swim_interval, rest, cross_training, strength")
        prompt_parts.append("- Use valid intensities: recovery, easy, moderate, hard, max")
        
        return "\n".join(prompt_parts)
    
    def save_plan(self, plan: TrainingPlan) -> str:
        """
        Persist training plan to database.
        
        Converts dataclass to SQLAlchemy models and saves with proper relationships.
        All operations are user-scoped for security.
        
        Args:
            plan: TrainingPlan dataclass to persist
            
        Returns:
            Plan ID (UUID string)
            
        Raises:
            ValueError: If plan validation fails or user_id is missing
            
        Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 20.2
        """
        # Validate user_id is present (Requirement 20.2)
        if plan.user_id is None:
            raise ValueError("user_id is required for plan persistence")
        
        # Validate plan before saving
        plan.validate()
        
        # Create plan model
        plan_model = TrainingPlanModel(
            user_id=plan.user_id,
            title=plan.title,
            sport=plan.sport,
            goal_id=plan.goal_id,
            start_date=plan.start_date,
            end_date=plan.end_date,
            status=plan.status
        )
        
        # If plan has an ID, use it (for updates)
        if plan.id:
            plan_model.id = plan.id
        
        self.db.add(plan_model)
        self.db.flush()  # Get the ID without committing
        
        # Create week models
        for week in plan.weeks:
            week_model = TrainingPlanWeekModel(
                plan_id=plan_model.id,
                week_number=week.week_number,
                focus=week.focus,
                volume_target=week.volume_target
            )
            self.db.add(week_model)
            self.db.flush()
            
            # Create session models
            for session in week.sessions:
                session_model = TrainingPlanSessionModel(
                    week_id=week_model.id,
                    day_of_week=session.day_of_week,
                    session_type=session.session_type,
                    duration_minutes=session.duration_minutes,
                    intensity=session.intensity,
                    description=session.description,
                    completed=session.completed,
                    matched_activity_id=session.matched_activity_id
                )
                self.db.add(session_model)
        
        self.db.commit()
        return plan_model.id
    
    def get_plan(self, plan_id: str, user_id: int) -> Optional[TrainingPlan]:
        """
        Retrieve training plan with user_id scoping.
        
        Converts SQLAlchemy models to dataclass for easy manipulation.
        
        Args:
            plan_id: Plan UUID
            user_id: User ID for security scoping
            
        Returns:
            TrainingPlan dataclass or None if not found
            
        Requirements: 20.2
        """
        # Validate user_id is present (Requirement 20.2)
        if user_id is None:
            print(f"[TrainingPlanEngine] SECURITY VIOLATION: user_id is None in get_plan for plan_id={plan_id}")
            raise ValueError("user_id is required for plan retrieval")
        
        # Query with user_id scoping for security
        plan_model = self.db.query(TrainingPlanModel).filter(
            and_(
                TrainingPlanModel.id == plan_id,
                TrainingPlanModel.user_id == user_id
            )
        ).first()
        
        if not plan_model:
            return None
        
        # Convert to dataclass
        return self._model_to_dataclass(plan_model)
    
    def list_plans(self, user_id: int) -> List[TrainingPlan]:
        """
        List all training plans for a user.
        
        Args:
            user_id: User ID for security scoping
            
        Returns:
            List of TrainingPlan dataclasses
            
        Requirements: 20.2
        """
        # Validate user_id is present (Requirement 20.2)
        if user_id is None:
            print("[TrainingPlanEngine] SECURITY VIOLATION: user_id is None in list_plans")
            raise ValueError("user_id is required for plan listing")
        
        # Query with user_id scoping
        plan_models = self.db.query(TrainingPlanModel).filter(
            TrainingPlanModel.user_id == user_id
        ).order_by(TrainingPlanModel.created_at.desc()).all()
        
        # Convert to dataclasses
        return [self._model_to_dataclass(plan) for plan in plan_models]
    
    def _model_to_dataclass(self, plan_model: TrainingPlanModel) -> TrainingPlan:
        """
        Convert SQLAlchemy model to dataclass.
        
        Args:
            plan_model: TrainingPlanModel instance
            
        Returns:
            TrainingPlan dataclass
        """
        # Convert weeks
        weeks = []
        for week_model in plan_model.weeks:
            # Convert sessions
            sessions = []
            for session_model in week_model.sessions:
                session = TrainingSession(
                    day_of_week=session_model.day_of_week,
                    session_type=session_model.session_type,
                    duration_minutes=session_model.duration_minutes,
                    intensity=session_model.intensity,
                    description=session_model.description,
                    completed=session_model.completed,
                    matched_activity_id=session_model.matched_activity_id
                )
                sessions.append(session)
            
            week = TrainingWeek(
                week_number=week_model.week_number,
                focus=week_model.focus,
                volume_target=week_model.volume_target,
                sessions=sessions
            )
            weeks.append(week)
        
        # Create plan dataclass
        plan = TrainingPlan(
            id=plan_model.id,
            user_id=plan_model.user_id,
            title=plan_model.title,
            sport=plan_model.sport,
            goal_id=plan_model.goal_id,
            start_date=plan_model.start_date,
            end_date=plan_model.end_date,
            status=plan_model.status,
            weeks=weeks,
            created_at=plan_model.created_at,
            updated_at=plan_model.updated_at
        )
        
        return plan
    
    async def iterate_plan(
        self,
        plan_id: str,
        user_id: int,
        modification_request: str
    ) -> TrainingPlan:
        """
        Generate an updated version of an existing plan.
        
        Retrieves the existing plan and generates a new version incorporating
        the requested modifications while preserving the plan structure.
        
        Args:
            plan_id: Existing plan ID
            user_id: User ID for security scoping
            modification_request: Description of requested changes
            
        Returns:
            Updated TrainingPlan object (not yet saved to database)
            
        Raises:
            ValueError: If plan not found or LLM client not configured or user_id missing
            
        Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 20.2
        """
        # Validate user_id is present (Requirement 20.2)
        if user_id is None:
            print(f"[TrainingPlanEngine] SECURITY VIOLATION: user_id is None in iterate_plan for plan_id={plan_id}")
            raise ValueError("user_id is required for plan iteration")
        
        if not self.llm_client:
            raise ValueError("LLM client not configured for plan generation")
        
        # Retrieve existing plan
        existing_plan = self.get_plan(plan_id, user_id)
        if not existing_plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        # Retrieve recent activities and metrics for context
        recent_activities = get_recent_activities.invoke({
            "athlete_id": user_id,
            "days_back": 28
        })
        
        weekly_metrics = []
        for i in range(4):
            week_date = date.today() - timedelta(weeks=i)
            year, week_num, _ = week_date.isocalendar()
            week_id = f"{year}-W{week_num:02d}"
            
            metrics = get_weekly_metrics.invoke({
                "athlete_id": user_id,
                "week_id": week_id
            })
            if metrics:
                weekly_metrics.append(metrics)
        
        # Build iteration prompt
        prompt = self._build_iteration_prompt(
            existing_plan=existing_plan,
            modification_request=modification_request,
            recent_activities=recent_activities,
            weekly_metrics=weekly_metrics
        )
        
        # Generate updated plan with LLM
        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are an expert endurance coach updating training plans based on athlete feedback."},
                {"role": "user", "content": prompt}
            ]
        )
        
        plan_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse generated plan
        updated_plan = parse_plan(plan_text, user_id)
        
        # Preserve original plan metadata
        updated_plan.id = existing_plan.id
        updated_plan.goal_id = existing_plan.goal_id
        updated_plan.created_at = existing_plan.created_at
        
        return updated_plan
    
    def _build_iteration_prompt(
        self,
        existing_plan: TrainingPlan,
        modification_request: str,
        recent_activities: List[Dict[str, Any]],
        weekly_metrics: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for plan iteration.
        
        Includes existing plan details and modification request.
        
        Args:
            existing_plan: Current training plan
            modification_request: Requested changes
            recent_activities: Recent activity data
            weekly_metrics: Weekly metrics data
            
        Returns:
            Formatted prompt string
        """
        # Format existing plan
        existing_plan_text = pretty_print(existing_plan)
        
        prompt_parts = [
            f"Update the following training plan based on the athlete's request:",
            f"\n## Current Plan\n",
            existing_plan_text,
            f"\n## Modification Request\n",
            modification_request
        ]
        
        # Add activity context
        if recent_activities:
            prompt_parts.append("\n\nRecent Training History (last 28 days):")
            
            total_activities = len(recent_activities)
            total_duration_min = sum(a.get('duration_min', 0) or 0 for a in recent_activities)
            total_distance_km = sum(a.get('distance_km', 0) or 0 for a in recent_activities)
            avg_weekly_duration = total_duration_min / 4
            avg_weekly_distance = total_distance_km / 4
            
            prompt_parts.append(f"- Total activities: {total_activities}")
            prompt_parts.append(f"- Average weekly duration: {avg_weekly_duration:.1f} minutes")
            prompt_parts.append(f"- Average weekly distance: {avg_weekly_distance:.1f} km")
        
        # Add metrics context
        if weekly_metrics:
            prompt_parts.append("\n\nRecent Body Metrics:")
            latest_metrics = weekly_metrics[0]
            if latest_metrics.get('weight_kg'):
                prompt_parts.append(f"- Weight: {latest_metrics['weight_kg']} kg")
            if latest_metrics.get('rhr_bpm'):
                prompt_parts.append(f"- Resting HR: {latest_metrics['rhr_bpm']} bpm")
            if latest_metrics.get('sleep_avg_hrs'):
                prompt_parts.append(f"- Average sleep: {latest_metrics['sleep_avg_hrs']} hours")
        
        # Add format instructions
        prompt_parts.append("\n\nGenerate the updated plan in this exact format:")
        prompt_parts.append("""
# Training Plan: [Title]
Sport: [sport]
Duration: [X] weeks
Start Date: [YYYY-MM-DD]

## Week 1: [Focus]
Volume Target: [X] hours

### Monday - [Session Type]
Duration: [X] minutes
Intensity: [easy/moderate/hard/recovery/max]
Description: [details]

### Tuesday - [Session Type]
Duration: [X] minutes
Intensity: [easy/moderate/hard/recovery/max]
Description: [details]

[Continue for all days and weeks...]
""")
        
        prompt_parts.append("\nIMPORTANT:")
        prompt_parts.append("- Incorporate the requested modifications")
        prompt_parts.append("- Maintain progressive volume increases (10% rule)")
        prompt_parts.append("- Keep the same sport and overall structure unless requested to change")
        prompt_parts.append("- Use valid session types: easy_run, tempo_run, interval, long_run, recovery_run, easy_ride, tempo_ride, interval_ride, long_ride, swim_technique, swim_endurance, swim_interval, rest, cross_training, strength")
        prompt_parts.append("- Use valid intensities: recovery, easy, moderate, hard, max")
        
        return "\n".join(prompt_parts)
    
    def update_plan(self, updated_plan: TrainingPlan) -> str:
        """
        Update an existing training plan in-place.
        
        Preserves the original plan ID and created_at timestamp.
        Updates the updated_at timestamp to current time.
        
        Args:
            updated_plan: TrainingPlan dataclass with updated data
            
        Returns:
            Plan ID (UUID string)
            
        Raises:
            ValueError: If plan validation fails or plan doesn't exist or user_id missing
            
        Requirements: 10.4, 10.5, 20.2
        """
        if not updated_plan.id:
            raise ValueError("Cannot update plan without an ID")
        
        # Validate user_id is present (Requirement 20.2)
        if updated_plan.user_id is None:
            print(f"[TrainingPlanEngine] SECURITY VIOLATION: user_id is None in update_plan for plan_id={updated_plan.id}")
            raise ValueError("user_id is required for plan update")
        
        # Validate plan before updating
        updated_plan.validate()
        
        # Query existing plan to verify it exists
        existing_plan_model = self.db.query(TrainingPlanModel).filter(
            and_(
                TrainingPlanModel.id == updated_plan.id,
                TrainingPlanModel.user_id == updated_plan.user_id
            )
        ).first()
        
        if not existing_plan_model:
            raise ValueError(f"Plan not found: {updated_plan.id}")
        
        # Delete existing weeks and sessions (cascade will handle sessions)
        for week in existing_plan_model.weeks:
            self.db.delete(week)
        
        # Update plan fields
        existing_plan_model.title = updated_plan.title
        existing_plan_model.sport = updated_plan.sport
        existing_plan_model.goal_id = updated_plan.goal_id
        existing_plan_model.start_date = updated_plan.start_date
        existing_plan_model.end_date = updated_plan.end_date
        existing_plan_model.status = updated_plan.status
        # updated_at will be automatically updated by TimestampMixin
        
        self.db.flush()
        
        # Create new week models
        for week in updated_plan.weeks:
            week_model = TrainingPlanWeekModel(
                plan_id=existing_plan_model.id,
                week_number=week.week_number,
                focus=week.focus,
                volume_target=week.volume_target
            )
            self.db.add(week_model)
            self.db.flush()
            
            # Create session models
            for session in week.sessions:
                session_model = TrainingPlanSessionModel(
                    week_id=week_model.id,
                    day_of_week=session.day_of_week,
                    session_type=session.session_type,
                    duration_minutes=session.duration_minutes,
                    intensity=session.intensity,
                    description=session.description,
                    completed=session.completed,
                    matched_activity_id=session.matched_activity_id
                )
                self.db.add(session_model)
        
        self.db.commit()
        return existing_plan_model.id

    
    def pretty_print(self, plan: TrainingPlan) -> str:
        """
        Format TrainingPlan object to human-readable text.
        
        Wrapper around the training_plan_parser.pretty_print function.
        
        Args:
            plan: TrainingPlan dataclass
            
        Returns:
            Formatted plan text
        """
        return pretty_print(plan)
    
    def parse_plan(self, plan_text: str, user_id: int) -> TrainingPlan:
        """
        Parse AI-generated plan text into structured object.
        
        Wrapper around the training_plan_parser.parse_plan function.
        
        Args:
            plan_text: AI-generated plan text
            user_id: User ID to assign to the plan
            
        Returns:
            TrainingPlan dataclass
            
        Raises:
            ValueError: If plan format is invalid
        """
        return parse_plan(plan_text, user_id)

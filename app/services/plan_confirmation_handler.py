"""Plan Confirmation Handler

Manages the training plan generation flow with athlete confirmation:
1. Present generated plan for review
2. Wait for athlete confirmation
3. Regenerate on modification requests
4. Save on confirmation

Requirements: 9.1, 9.2, 9.3, 9.4
"""
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from enum import Enum
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.schemas.training_plan import TrainingPlan
    from app.services.training_plan_engine import TrainingPlanEngine
    from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class PlanState(Enum):
    """States in the plan confirmation flow."""
    GENERATING = "generating"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    MODIFYING = "modifying"
    SAVED = "saved"


class PlanConfirmationHandler:
    """
    Handles training plan generation flow with confirmation.
    
    Flow:
    1. Generate plan based on athlete requirements
    2. Present plan to athlete for review
    3. Wait for confirmation or modification request
    4. If modifications requested, regenerate with changes
    5. If confirmed, save plan to database
    
    Requirements: 9.1, 9.2, 9.3, 9.4
    """

    
    def __init__(self, db: Session, llm_client: 'LLMClient'):
        """
        Initialize plan confirmation handler.
        
        Args:
            db: SQLAlchemy database session
            llm_client: LLM client for plan generation
        """
        # Lazy import to avoid circular dependency
        from app.services.training_plan_engine import TrainingPlanEngine
        
        self.db = db
        self.plan_engine = TrainingPlanEngine(db, llm_client)
        
        # Track pending plans per user session
        self.pending_plans: Dict[str, Dict[str, Any]] = {}
    
    async def generate_and_present_plan(
        self,
        user_id: int,
        session_id: int,
        sport: str,
        duration_weeks: int,
        goal_id: Optional[str] = None,
        goal_description: Optional[str] = None,
        start_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a training plan and present it for review.
        
        Args:
            user_id: Athlete user ID
            session_id: Chat session ID
            sport: Primary sport
            duration_weeks: Plan duration in weeks
            goal_id: Linked goal ID (optional)
            goal_description: Goal description (optional)
            start_date: Plan start date (optional)
        
        Returns:
            Dict with plan details and presentation message
        
        Requirements: 9.1
        """
        try:
            logger.info(
                f"Generating plan for user {user_id}",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "sport": sport,
                    "duration_weeks": duration_weeks
                }
            )
            
            # Generate plan
            plan = await self.plan_engine.generate_plan(
                user_id=user_id,
                sport=sport,
                duration_weeks=duration_weeks,
                goal_id=goal_id,
                goal_description=goal_description,
                start_date=start_date
            )

            
            # Store pending plan
            pending_key = f"{user_id}:{session_id}"
            self.pending_plans[pending_key] = {
                'plan': plan,
                'state': PlanState.AWAITING_CONFIRMATION,
                'user_id': user_id,
                'session_id': session_id
            }
            
            # Format plan for presentation
            plan_text = self.plan_engine.pretty_print(plan)
            
            # Create presentation message
            presentation = self._format_plan_presentation(plan, plan_text)
            
            logger.info(
                f"Plan generated and presented for confirmation",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "plan_title": plan.title
                }
            )
            
            return {
                'success': True,
                'plan': plan,
                'plan_text': plan_text,
                'presentation': presentation,
                'state': PlanState.AWAITING_CONFIRMATION.value
            }
            
        except Exception as e:
            logger.error(
                f"Error generating plan: {str(e)}",
                extra={"user_id": user_id, "session_id": session_id},
                exc_info=True
            )
            raise
    
    def _format_plan_presentation(self, plan: 'TrainingPlan', plan_text: str) -> str:
        """
        Format plan for presentation to athlete.
        
        Args:
            plan: TrainingPlan object
            plan_text: Formatted plan text
        
        Returns:
            Presentation message with plan and confirmation prompt
        """
        presentation_parts = [
            f"🎯 I've created a personalized training plan for you!\n",
            f"**{plan.title}**",
            f"Sport: {plan.sport.title()}",
            f"Duration: {len(plan.weeks)} weeks",
            f"Start Date: {plan.start_date.isoformat()}\n",
            "---\n",
            plan_text,
            "\n---\n",
            "**What would you like to do?**",
            "- Type **'confirm'** or **'save'** to save this plan",
            "- Type **'modify'** or **'change'** followed by what you'd like to adjust",
            "- Type **'regenerate'** to create a completely new plan\n",
            "For example: 'modify - add more rest days' or 'change the intensity in week 3'"
        ]
        
        return "\n".join(presentation_parts)

    
    async def handle_confirmation_response(
        self,
        user_id: int,
        session_id: int,
        response: str
    ) -> Dict[str, Any]:
        """
        Handle athlete's response to plan presentation.
        
        Processes confirmation, modification requests, or regeneration.
        
        Args:
            user_id: Athlete user ID
            session_id: Chat session ID
            response: Athlete's response text
        
        Returns:
            Dict with action taken and result
        
        Requirements: 9.2, 9.3, 9.4
        """
        pending_key = f"{user_id}:{session_id}"
        
        # Check if there's a pending plan
        if pending_key not in self.pending_plans:
            return {
                'success': False,
                'message': "No pending plan found. Please generate a new plan first."
            }
        
        pending_data = self.pending_plans[pending_key]
        plan = pending_data['plan']
        response_lower = response.lower().strip()
        
        # Check for confirmation (Requirement 9.2, 9.4)
        if any(keyword in response_lower for keyword in ['confirm', 'save', 'yes', 'looks good', 'perfect']):
            return await self._confirm_and_save_plan(user_id, session_id, plan)
        
        # Check for modification request (Requirement 9.3)
        if any(keyword in response_lower for keyword in ['modify', 'change', 'adjust', 'update']):
            modification_request = self._extract_modification_request(response)
            return await self._modify_plan(user_id, session_id, plan, modification_request)
        
        # Check for regeneration
        if 'regenerate' in response_lower or 'new plan' in response_lower:
            return {
                'success': True,
                'action': 'regenerate',
                'message': "I'll create a completely new plan. Please provide the details again."
            }
        
        # Unclear response
        return {
            'success': False,
            'action': 'unclear',
            'message': """I'm not sure what you'd like to do with the plan. Please respond with:
- **'confirm'** or **'save'** to save this plan
- **'modify'** followed by what you'd like to change
- **'regenerate'** to create a new plan"""
        }

    
    async def _confirm_and_save_plan(
        self,
        user_id: int,
        session_id: int,
        plan: 'TrainingPlan'
    ) -> Dict[str, Any]:
        """
        Confirm and save the plan to database.
        
        Args:
            user_id: Athlete user ID
            session_id: Chat session ID
            plan: TrainingPlan to save
        
        Returns:
            Dict with save result
        
        Requirements: 9.4
        """
        try:
            # Save plan
            plan_id = self.plan_engine.save_plan(plan)
            
            # Remove from pending
            pending_key = f"{user_id}:{session_id}"
            if pending_key in self.pending_plans:
                self.pending_plans[pending_key]['state'] = PlanState.SAVED
                del self.pending_plans[pending_key]
            
            logger.info(
                f"Plan confirmed and saved",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "plan_id": plan_id
                }
            )
            
            return {
                'success': True,
                'action': 'saved',
                'plan_id': plan_id,
                'message': f"✅ Perfect! Your training plan '{plan.title}' has been saved. You can view it in your Plans section and start training!"
            }
            
        except Exception as e:
            logger.error(
                f"Error saving plan: {str(e)}",
                extra={"user_id": user_id, "session_id": session_id},
                exc_info=True
            )
            return {
                'success': False,
                'action': 'error',
                'message': f"I encountered an error saving your plan: {str(e)}. Please try again."
            }

    
    async def _modify_plan(
        self,
        user_id: int,
        session_id: int,
        current_plan: 'TrainingPlan',
        modification_request: str
    ) -> Dict[str, Any]:
        """
        Regenerate plan with requested modifications.
        
        Args:
            user_id: Athlete user ID
            session_id: Chat session ID
            current_plan: Current TrainingPlan
            modification_request: Description of requested changes
        
        Returns:
            Dict with modified plan
        
        Requirements: 9.3
        """
        try:
            logger.info(
                f"Modifying plan",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "modification": modification_request
                }
            )
            
            # Use plan iteration to generate modified version
            modified_plan = await self.plan_engine.iterate_plan(
                plan_id=current_plan.id if current_plan.id else "temp",
                user_id=user_id,
                modification_request=modification_request
            )
            
            # Update pending plan
            pending_key = f"{user_id}:{session_id}"
            self.pending_plans[pending_key] = {
                'plan': modified_plan,
                'state': PlanState.AWAITING_CONFIRMATION,
                'user_id': user_id,
                'session_id': session_id
            }
            
            # Format modified plan
            plan_text = self.plan_engine.pretty_print(modified_plan)
            presentation = self._format_plan_presentation(modified_plan, plan_text)
            
            logger.info(
                f"Plan modified and presented",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "plan_title": modified_plan.title
                }
            )
            
            return {
                'success': True,
                'action': 'modified',
                'plan': modified_plan,
                'plan_text': plan_text,
                'presentation': f"I've updated the plan based on your feedback:\n\n{presentation}",
                'state': PlanState.AWAITING_CONFIRMATION.value
            }
            
        except Exception as e:
            logger.error(
                f"Error modifying plan: {str(e)}",
                extra={"user_id": user_id, "session_id": session_id},
                exc_info=True
            )
            return {
                'success': False,
                'action': 'error',
                'message': f"I encountered an error modifying the plan: {str(e)}. Please try again."
            }

    
    def _extract_modification_request(self, response: str) -> str:
        """
        Extract modification request from athlete's response.
        
        Args:
            response: Athlete's response text
        
        Returns:
            Extracted modification request
        """
        # Remove common trigger words
        trigger_words = ['modify', 'change', 'adjust', 'update', 'can you', 'please']
        
        # Clean response
        cleaned = response.lower()
        for word in trigger_words:
            cleaned = cleaned.replace(word, '')
        
        # Remove leading/trailing punctuation and whitespace
        cleaned = cleaned.strip(' ,-:;')
        
        # If nothing left, return original
        if not cleaned:
            return response
        
        return cleaned
    
    def has_pending_plan(self, user_id: int, session_id: int) -> bool:
        """
        Check if there's a pending plan for the user session.
        
        Args:
            user_id: Athlete user ID
            session_id: Chat session ID
        
        Returns:
            True if pending plan exists, False otherwise
        """
        pending_key = f"{user_id}:{session_id}"
        return pending_key in self.pending_plans
    
    def get_pending_plan(self, user_id: int, session_id: int) -> Optional['TrainingPlan']:
        """
        Get pending plan for the user session.
        
        Args:
            user_id: Athlete user ID
            session_id: Chat session ID
        
        Returns:
            TrainingPlan if exists, None otherwise
        """
        pending_key = f"{user_id}:{session_id}"
        if pending_key in self.pending_plans:
            return self.pending_plans[pending_key]['plan']
        return None
    
    def clear_pending_plan(self, user_id: int, session_id: int) -> None:
        """
        Clear pending plan for the user session.
        
        Args:
            user_id: Athlete user ID
            session_id: Chat session ID
        """
        pending_key = f"{user_id}:{session_id}"
        if pending_key in self.pending_plans:
            del self.pending_plans[pending_key]
            logger.info(
                f"Cleared pending plan",
                extra={"user_id": user_id, "session_id": session_id}
            )

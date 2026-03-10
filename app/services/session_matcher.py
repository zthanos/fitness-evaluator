"""Session Matcher Service

Automatically matches Strava activities to planned training sessions.
Uses confidence scoring based on time proximity, sport type, duration, and intensity.
Triggers adherence recalculation after successful matches.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from app.models.strava_activity import StravaActivity
from app.models.training_plan_session import TrainingPlanSession
from app.models.training_plan_week import TrainingPlanWeek
from app.models.training_plan import TrainingPlan
from app.services.adherence_calculator import AdherenceCalculator
import logging

logger = logging.getLogger(__name__)


class SessionMatcher:
    """
    Session Matcher for automatic activity-to-session matching.
    
    Matches imported Strava activities to planned training sessions using
    a confidence-based algorithm that considers:
    - Time proximity (within 24 hours)
    - Sport type match
    - Duration similarity
    - Intensity alignment
    
    Sessions are matched when confidence exceeds 80%.
    """
    
    def __init__(self, db: Session):
        """
        Initialize SessionMatcher.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def find_candidate_sessions(
        self,
        activity: StravaActivity,
        user_id: int
    ) -> List[TrainingPlanSession]:
        """
        Find candidate training sessions within 24 hours of activity.
        
        Queries unmatched sessions from active plans for the user,
        filtering by time proximity to the activity.
        
        Args:
            activity: Strava activity to match
            user_id: User ID for scoping
            
        Returns:
            List of candidate TrainingPlanSession objects
            
        Requirements: 14.1, 20.2
        """
        # Validate user_id is present (Requirement 20.2)
        if user_id is None:
            logger.error(f"SECURITY VIOLATION: user_id is None in find_candidate_sessions for activity {activity.id}")
            raise ValueError("user_id is required for session matching")
        
        # Calculate time window (24 hours before and after activity)
        activity_time = activity.start_date
        time_window_start = activity_time - timedelta(hours=24)
        time_window_end = activity_time + timedelta(hours=24)
        
        # Query unmatched sessions in active plans within time window
        # We need to join through week -> plan to filter by user_id and status
        candidates = (
            self.db.query(TrainingPlanSession)
            .join(TrainingPlanWeek, TrainingPlanSession.week_id == TrainingPlanWeek.id)
            .join(TrainingPlan, TrainingPlanWeek.plan_id == TrainingPlan.id)
            .filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.status == 'active',
                TrainingPlanSession.completed == False,
                TrainingPlanSession.matched_activity_id == None
            )
            .options(
                joinedload(TrainingPlanSession.week)
                .joinedload(TrainingPlanWeek.plan)
            )
            .all()
        )
        
        # Filter by time proximity (need to calculate scheduled date)
        filtered_candidates = []
        for session in candidates:
            scheduled_date = self._calculate_scheduled_date(session)
            if scheduled_date:
                time_diff = abs((activity_time - scheduled_date).total_seconds() / 3600)
                if time_diff <= 24:
                    filtered_candidates.append(session)
        
        return filtered_candidates
    
    def _calculate_scheduled_date(self, session: TrainingPlanSession) -> Optional[datetime]:
        """
        Calculate the scheduled datetime for a session.
        
        Args:
            session: Training plan session
            
        Returns:
            Scheduled datetime or None if cannot be calculated
        """
        try:
            # Get the plan start date
            plan = session.week.plan
            start_date = plan.start_date
            
            # Calculate the date for this session
            # Week 1 starts on start_date
            # day_of_week: 1=Monday, 7=Sunday
            week_offset = session.week.week_number - 1
            day_offset = session.day_of_week - 1
            
            # Calculate total days from start
            total_days = (week_offset * 7) + day_offset
            
            # Calculate scheduled date (assume noon for comparison)
            scheduled_date = datetime.combine(
                start_date,
                datetime.min.time().replace(hour=12)
            ) + timedelta(days=total_days)
            
            return scheduled_date
        except Exception as e:
            logger.error(f"Error calculating scheduled date for session {session.id}: {e}")
            return None
    
    def calculate_match_confidence(
        self,
        activity: StravaActivity,
        session: TrainingPlanSession
    ) -> float:
        """
        Calculate match confidence score (0-100).
        
        Scoring breakdown:
        - Time proximity: 40 points max
          - Within 2 hours: 40 points
          - Within 12 hours: 30 points
          - Within 24 hours: 20 points
        - Sport type match: 30 points max
        - Duration similarity: 20 points max
          - Within ±20%: 20 points
          - Within ±40%: 10 points
        - Intensity alignment: 10 points max
        
        Args:
            activity: Strava activity
            session: Training plan session
            
        Returns:
            Confidence score 0-100
        """
        score = 0.0
        
        # 1. Time proximity score (40 points max)
        scheduled_date = self._calculate_scheduled_date(session)
        if scheduled_date:
            time_diff_hours = abs((activity.start_date - scheduled_date).total_seconds() / 3600)
            if time_diff_hours <= 2:
                score += 40
            elif time_diff_hours <= 12:
                score += 30
            elif time_diff_hours <= 24:
                score += 20
        
        # 2. Sport type match score (30 points max)
        if self._sport_types_match(activity.activity_type, session.session_type):
            score += 30
        
        # 3. Duration similarity score (20 points max)
        if activity.moving_time_s and session.duration_minutes:
            activity_minutes = activity.moving_time_s / 60
            planned_minutes = session.duration_minutes
            duration_ratio = activity_minutes / planned_minutes if planned_minutes > 0 else 0
            
            if 0.8 <= duration_ratio <= 1.2:  # Within ±20%
                score += 20
            elif 0.6 <= duration_ratio <= 1.4:  # Within ±40%
                score += 10
        
        # 4. Intensity alignment score (10 points max)
        if self._intensities_match(activity, session.intensity):
            score += 10
        
        return score
    
    def _sport_types_match(self, activity_type: str, session_type: str) -> bool:
        """
        Check if activity type matches session type.
        
        Args:
            activity_type: Strava activity type (e.g., "Run", "Ride", "Swim")
            session_type: Session type (e.g., "easy_run", "tempo_ride")
            
        Returns:
            True if types match
        """
        activity_type_lower = activity_type.lower()
        session_type_lower = session_type.lower()
        
        # Extract sport from session_type (e.g., "easy_run" -> "run")
        sport_mapping = {
            'run': ['run', 'running'],
            'ride': ['ride', 'cycling', 'bike'],
            'swim': ['swim', 'swimming'],
        }
        
        for sport, keywords in sport_mapping.items():
            if sport in session_type_lower:
                # Check if activity type matches any keyword
                return any(keyword in activity_type_lower for keyword in keywords)
        
        return False
    
    def _intensities_match(self, activity: StravaActivity, session_intensity: str) -> bool:
        """
        Check if activity intensity aligns with session intensity.
        
        Uses heart rate data if available to estimate intensity.
        
        Args:
            activity: Strava activity
            session_intensity: Planned intensity (recovery, easy, moderate, hard, max)
            
        Returns:
            True if intensities align
        """
        # If no heart rate data, assume match (benefit of doubt)
        if not activity.avg_hr or not activity.max_hr:
            return True
        
        # Estimate intensity from heart rate
        # This is a simplified heuristic
        hr_ratio = activity.avg_hr / activity.max_hr if activity.max_hr > 0 else 0
        
        intensity_ranges = {
            'recovery': (0.0, 0.65),
            'easy': (0.60, 0.75),
            'moderate': (0.70, 0.85),
            'hard': (0.80, 0.95),
            'max': (0.90, 1.0),
        }
        
        if session_intensity in intensity_ranges:
            min_hr, max_hr = intensity_ranges[session_intensity]
            return min_hr <= hr_ratio <= max_hr
        
        return True
    
    def match_activity(self, activity: StravaActivity, user_id: int) -> Optional[str]:
        """
        Match activity to a planned session.
        
        Finds candidate sessions, calculates confidence for each,
        and updates the best match if confidence > 80%.
        After successful match, recalculates adherence scores.
        
        Args:
            activity: Strava activity to match
            user_id: User ID for scoping
            
        Returns:
            Matched session ID if confidence > 80%, None otherwise
            
        Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 20.2
        """
        import time
        start_time = time.time()
        
        # Validate user_id is present (Requirement 20.2)
        if user_id is None:
            logger.error(f"SECURITY VIOLATION: user_id is None in match_activity for activity {activity.id}")
            raise ValueError("user_id is required for activity matching")
        
        try:
            # Find candidate sessions
            candidates = self.find_candidate_sessions(activity, user_id)
            
            if not candidates:
                logger.info(f"No candidate sessions found for activity {activity.id}")
                return None
            
            # Calculate confidence for each candidate
            best_match = None
            best_confidence = 0.0
            
            for session in candidates:
                confidence = self.calculate_match_confidence(activity, session)
                logger.debug(
                    f"Session {session.id} confidence: {confidence:.1f} "
                    f"(type={session.session_type}, duration={session.duration_minutes}min)"
                )
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = session
            
            # Update session if confidence exceeds threshold
            if best_match and best_confidence > 80:
                best_match.completed = True
                best_match.matched_activity_id = activity.id
                self.db.commit()
                
                # Log matching latency (Requirement 14.5)
                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Matched activity {activity.id} to session {best_match.id} "
                    f"with confidence {best_confidence:.1f} in {latency_ms:.0f}ms"
                )
                
                # Warn if latency exceeds target (5 seconds per Requirement 14.5)
                if latency_ms > 5000:
                    logger.warning(
                        f"PERFORMANCE WARNING: Session matching exceeded 5s target: {latency_ms:.0f}ms "
                        f"for activity {activity.id}"
                    )
                
                # Recalculate and log adherence scores (Requirement 15.4)
                self._update_adherence_scores(best_match)
                
                return best_match.id
            else:
                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"No match found for activity {activity.id} "
                    f"(best confidence: {best_confidence:.1f}) in {latency_ms:.0f}ms"
                )
                return None
                
        except Exception as e:
            logger.error(f"Error matching activity {activity.id}: {e}")
            self.db.rollback()
            raise
    
    def _update_adherence_scores(self, session: TrainingPlanSession) -> None:
        """
        Recalculate and log adherence scores after session match.
        
        Per requirement 15.4: Update adherence scores within 10 seconds
        after the Session_Matcher updates session completion status.
        
        Args:
            session: Matched training plan session
        """
        try:
            # Get the full plan with all weeks and sessions
            plan = (
                self.db.query(TrainingPlan)
                .filter(TrainingPlan.id == session.week.plan_id)
                .options(
                    joinedload(TrainingPlan.weeks)
                    .joinedload(TrainingPlanWeek.sessions)
                )
                .first()
            )
            
            if not plan:
                logger.warning(f"Could not find plan for session {session.id}")
                return
            
            # Calculate updated adherence scores
            session_adherence = AdherenceCalculator.calculate_session_adherence(session)
            week_adherence = AdherenceCalculator.calculate_week_adherence(session.week)
            plan_adherence = AdherenceCalculator.calculate_plan_adherence(plan)
            
            logger.info(
                f"Adherence updated for plan {plan.id}: "
                f"session={session_adherence:.1f}%, "
                f"week {session.week.week_number}={week_adherence:.1f}%, "
                f"overall={plan_adherence:.1f}%"
            )
            
        except Exception as e:
            logger.error(f"Error updating adherence scores for session {session.id}: {e}")

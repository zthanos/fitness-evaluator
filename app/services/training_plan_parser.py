"""Training Plan Parser and Pretty-Printer

Converts between AI-generated text and structured TrainingPlan objects.
Implements round-trip property: parse(print(plan)) produces equivalent object.
"""
from datetime import date, timedelta
from typing import List, Optional
import re

from app.schemas.training_plan import TrainingPlan, TrainingWeek, TrainingSession


def parse_plan(plan_text: str, user_id: int) -> TrainingPlan:
    """
    Parse AI-generated training plan text into structured object.
    
    Expected format:
    # Training Plan: [Title]
    Sport: [sport]
    Duration: [X] weeks
    Start Date: [YYYY-MM-DD]
    
    ## Week 1: [Focus]
    Volume Target: [X] hours
    
    ### Monday - [Session Type]
    Duration: [X] minutes
    Intensity: [easy/moderate/hard]
    Description: [details]
    
    Args:
        plan_text: AI-generated plan text
        user_id: User ID for the plan
        
    Returns:
        Structured TrainingPlan object
        
    Raises:
        ValueError: If plan format is invalid with descriptive message
    """
    lines = [line.rstrip() for line in plan_text.strip().split('\n')]
    
    # Parse header
    title = _extract_title(lines)
    sport = _extract_field(lines, 'Sport')
    duration_weeks = _extract_field(lines, 'Duration', field_type='int')
    start_date = _extract_field(lines, 'Start Date', field_type='date')
    
    # Parse weeks
    weeks = _parse_weeks(lines)
    
    # Validate required fields
    if not title:
        raise ValueError("Invalid plan format: missing title (expected '# Training Plan: [Title]')")
    if not sport:
        raise ValueError("Invalid plan format: missing sport (expected 'Sport: [sport]')")
    if duration_weeks is None:
        raise ValueError("Invalid plan format: missing duration (expected 'Duration: [X] weeks')")
    if not start_date:
        raise ValueError("Invalid plan format: missing start date (expected 'Start Date: YYYY-MM-DD')")
    if not weeks:
        raise ValueError("Invalid plan format: no weeks found (expected '## Week N: [Focus]')")
    
    # Calculate end date
    end_date = start_date + timedelta(weeks=duration_weeks)
    
    # Create plan
    plan = TrainingPlan(
        user_id=user_id,
        title=title,
        sport=sport,
        start_date=start_date,
        end_date=end_date,
        status='draft',
        weeks=weeks
    )
    
    # Validate the plan
    try:
        plan.validate()
    except ValueError as e:
        raise ValueError(f"Invalid plan format: {e}")
    
    return plan


def pretty_print(plan: TrainingPlan) -> str:
    """
    Format TrainingPlan object to human-readable markdown.
    
    Inverse of parse_plan() - satisfies round-trip property:
    parse(print(plan)) produces equivalent object.
    
    Args:
        plan: Structured TrainingPlan object
        
    Returns:
        Human-readable markdown text
    """
    lines = []
    
    # Calculate duration from date difference
    duration_weeks = (plan.end_date - plan.start_date).days // 7
    
    # Header
    lines.append(f"# Training Plan: {plan.title}")
    lines.append(f"Sport: {plan.sport}")
    lines.append(f"Duration: {duration_weeks} weeks")
    lines.append(f"Start Date: {plan.start_date.isoformat()}")
    lines.append("")
    
    # Weeks
    for week in plan.weeks:
        # Format focus (handle empty focus)
        focus_text = week.focus if week.focus else ""
        lines.append(f"## Week {week.week_number}: {focus_text}")
        
        # Format volume target with proper precision
        # Round to avoid floating point precision issues
        volume_rounded = round(week.volume_target, 10)
        lines.append(f"Volume Target: {volume_rounded} hours")
        lines.append("")
        
        # Sessions
        for session in week.sessions:
            day_name = _get_day_name(session.day_of_week)
            session_name = session.session_type.replace('_', ' ').title()
            lines.append(f"### {day_name} - {session_name}")
            lines.append(f"Duration: {session.duration_minutes} minutes")
            lines.append(f"Intensity: {session.intensity}")
            lines.append(f"Description: {session.description}")
            lines.append("")
    
    return "\n".join(lines)


# Helper functions

def _extract_title(lines: List[str]) -> Optional[str]:
    """Extract title from header line."""
    for line in lines:
        if line.startswith('# Training Plan:'):
            title = line.replace('# Training Plan:', '').strip()
            return title if title else None
    return None


def _extract_field(lines: List[str], field_name: str, field_type: str = 'str') -> Optional[any]:
    """Extract a field value from lines."""
    pattern = re.compile(f'^{re.escape(field_name)}:\\s*(.+)$', re.IGNORECASE)
    
    for line in lines:
        match = pattern.match(line)
        if match:
            value = match.group(1).strip()
            
            if field_type == 'int':
                # Extract number from text like "12 weeks"
                num_match = re.search(r'(\d+)', value)
                if num_match:
                    return int(num_match.group(1))
                raise ValueError(f"Invalid {field_name}: expected number, got '{value}'")
            
            elif field_type == 'date':
                try:
                    return date.fromisoformat(value)
                except ValueError:
                    raise ValueError(f"Invalid {field_name}: expected YYYY-MM-DD format, got '{value}'")
            
            elif field_type == 'float':
                # Extract number from text like "30.5 hours"
                num_match = re.search(r'(\d+\.?\d*)', value)
                if num_match:
                    return float(num_match.group(1))
                raise ValueError(f"Invalid {field_name}: expected number, got '{value}'")
            
            else:  # str
                return value
    
    return None


def _parse_weeks(lines: List[str]) -> List[TrainingWeek]:
    """Parse all weeks from lines."""
    weeks = []
    current_week = None
    current_session = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Week header: ## Week 1: Base Building
        if line.startswith('## Week'):
            # Save previous week
            if current_week:
                if current_session:
                    current_week.sessions.append(current_session)
                    current_session = None
                weeks.append(current_week)
            
            # Parse new week
            current_week = _parse_week_header(line)
            
            # Look ahead for volume target
            if i + 1 < len(lines) and lines[i + 1].startswith('Volume Target:'):
                i += 1
                current_week.volume_target = _extract_field([lines[i]], 'Volume Target', field_type='float')
        
        # Session header: ### Monday - Easy Run
        elif line.startswith('### '):
            # Save previous session
            if current_session and current_week:
                current_week.sessions.append(current_session)
            
            # Parse new session
            current_session = _parse_session_header(line)
        
        # Session details
        elif current_session:
            if line.startswith('Duration:'):
                duration = _extract_field([line], 'Duration', field_type='int')
                if duration is not None:
                    current_session.duration_minutes = duration
            
            elif line.startswith('Intensity:'):
                intensity = _extract_field([line], 'Intensity')
                if intensity:
                    current_session.intensity = intensity.lower()
            
            elif line.startswith('Description:'):
                description = _extract_field([line], 'Description')
                if description:
                    current_session.description = description
        
        i += 1
    
    # Save last week and session
    if current_session and current_week:
        current_week.sessions.append(current_session)
    if current_week:
        weeks.append(current_week)
    
    return weeks


def _parse_week_header(line: str) -> TrainingWeek:
    """Parse week header line."""
    # Pattern: ## Week 1: Base Building (focus can be empty)
    match = re.match(r'^##\s+Week\s+(\d+):\s*(.*)$', line)
    if not match:
        raise ValueError(f"Invalid week header format: '{line}' (expected '## Week N: [Focus]')")
    
    week_number = int(match.group(1))
    focus = match.group(2).strip()
    
    # Default to empty string if focus is empty
    if not focus:
        focus = ""
    
    return TrainingWeek(
        week_number=week_number,
        focus=focus,
        volume_target=0.0,  # Will be set later
        sessions=[]
    )


def _parse_session_header(line: str) -> TrainingSession:
    """Parse session header line."""
    # Pattern: ### Monday - Easy Run
    match = re.match(r'^###\s+(\w+)\s+-\s+(.+)$', line)
    if not match:
        raise ValueError(f"Invalid session header format: '{line}' (expected '### [Day] - [Type]')")
    
    day_name = match.group(1).strip()
    session_type_raw = match.group(2).strip()
    
    # Convert day name to number
    day_of_week = _parse_day_name(day_name)
    
    # Convert session type to snake_case
    session_type = session_type_raw.lower().replace(' ', '_')
    
    return TrainingSession(
        day_of_week=day_of_week,
        session_type=session_type,
        duration_minutes=0,  # Will be set later
        intensity='easy',  # Will be set later
        description='',  # Will be set later
        completed=False
    )


def _parse_day_name(day_name: str) -> int:
    """Convert day name to day_of_week number (1=Monday, 7=Sunday)."""
    day_map = {
        'monday': 1,
        'tuesday': 2,
        'wednesday': 3,
        'thursday': 4,
        'friday': 5,
        'saturday': 6,
        'sunday': 7
    }
    
    day_lower = day_name.lower()
    if day_lower not in day_map:
        raise ValueError(f"Invalid day name: '{day_name}' (expected Monday-Sunday)")
    
    return day_map[day_lower]


def _get_day_name(day_of_week: int) -> str:
    """Convert day_of_week number to day name."""
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    if not (1 <= day_of_week <= 7):
        raise ValueError(f"Invalid day_of_week: {day_of_week} (expected 1-7)")
    return day_names[day_of_week - 1]

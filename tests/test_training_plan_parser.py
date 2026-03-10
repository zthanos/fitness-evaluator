"""Tests for Training Plan Parser and Pretty-Printer

Tests parsing AI-generated text into structured objects and formatting back to text.
Includes property-based tests for round-trip property.
"""
import pytest
from datetime import date, timedelta
from hypothesis import given, strategies as st, assume

from app.services.training_plan_parser import parse_plan, pretty_print
from app.schemas.training_plan import TrainingPlan, TrainingWeek, TrainingSession


# Unit Tests

class TestParsePlan:
    """Test parse_plan function."""
    
    def test_parse_valid_plan(self):
        """Test parsing a valid training plan."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
Start Date: 2024-01-01

## Week 1: Base Building
Volume Target: 30 hours

### Monday - Easy Run
Duration: 45 minutes
Intensity: easy
Description: Easy pace, focus on form

### Wednesday - Tempo Run
Duration: 60 minutes
Intensity: moderate
Description: 20 min warmup, 30 min tempo, 10 min cooldown

### Saturday - Long Run
Duration: 90 minutes
Intensity: easy
Description: Long slow distance run

## Week 2: Building Volume
Volume Target: 35 hours

### Tuesday - Interval
Duration: 50 minutes
Intensity: hard
Description: 5x800m at 5K pace with 2 min recovery
"""
        
        plan = parse_plan(plan_text, user_id=1)
        
        assert plan.title == "Marathon Training"
        assert plan.sport == "running"
        assert plan.user_id == 1
        assert plan.start_date == date(2024, 1, 1)
        assert plan.end_date == date(2024, 3, 25)  # 12 weeks later
        assert plan.status == "draft"
        assert len(plan.weeks) == 2
        
        # Check week 1
        week1 = plan.weeks[0]
        assert week1.week_number == 1
        assert week1.focus == "Base Building"
        assert week1.volume_target == 30.0
        assert len(week1.sessions) == 3
        
        # Check first session
        session1 = week1.sessions[0]
        assert session1.day_of_week == 1  # Monday
        assert session1.session_type == "easy_run"
        assert session1.duration_minutes == 45
        assert session1.intensity == "easy"
        assert session1.description == "Easy pace, focus on form"
        assert session1.completed is False
        
        # Check week 2
        week2 = plan.weeks[1]
        assert week2.week_number == 2
        assert week2.focus == "Building Volume"
        assert week2.volume_target == 35.0
        assert len(week2.sessions) == 1
    
    def test_parse_missing_title(self):
        """Test parsing fails with missing title."""
        plan_text = """Sport: running
Duration: 12 weeks
Start Date: 2024-01-01
"""
        
        with pytest.raises(ValueError, match="missing title"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_missing_sport(self):
        """Test parsing fails with missing sport."""
        plan_text = """# Training Plan: Marathon Training
Duration: 12 weeks
Start Date: 2024-01-01
"""
        
        with pytest.raises(ValueError, match="missing sport"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_missing_duration(self):
        """Test parsing fails with missing duration."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Start Date: 2024-01-01
"""
        
        with pytest.raises(ValueError, match="missing duration"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_missing_start_date(self):
        """Test parsing fails with missing start date."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
"""
        
        with pytest.raises(ValueError, match="missing start date"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_invalid_date_format(self):
        """Test parsing fails with invalid date format."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
Start Date: 01/01/2024
"""
        
        with pytest.raises(ValueError, match="expected YYYY-MM-DD format"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_no_weeks(self):
        """Test parsing fails with no weeks."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
Start Date: 2024-01-01
"""
        
        with pytest.raises(ValueError, match="no weeks found"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_invalid_week_header(self):
        """Test parsing fails with invalid week header."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
Start Date: 2024-01-01

## Week One: Base Building
"""
        
        with pytest.raises(ValueError, match="Invalid week header format"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_invalid_session_header(self):
        """Test parsing fails with invalid session header."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
Start Date: 2024-01-01

## Week 1: Base Building
Volume Target: 30 hours

### Monday Easy Run
Duration: 45 minutes
Intensity: easy
Description: Easy pace
"""
        
        with pytest.raises(ValueError, match="Invalid session header format"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_invalid_day_name(self):
        """Test parsing fails with invalid day name."""
        plan_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
Start Date: 2024-01-01

## Week 1: Base Building
Volume Target: 30 hours

### Moonday - Easy Run
Duration: 45 minutes
Intensity: easy
Description: Easy pace
"""
        
        with pytest.raises(ValueError, match="Invalid day name"):
            parse_plan(plan_text, user_id=1)
    
    def test_parse_all_days_of_week(self):
        """Test parsing all days of the week."""
        plan_text = """# Training Plan: Weekly Plan
Sport: running
Duration: 1 weeks
Start Date: 2024-01-01

## Week 1: Full Week
Volume Target: 10 hours

### Monday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Monday run

### Tuesday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Tuesday run

### Wednesday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Wednesday run

### Thursday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Thursday run

### Friday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Friday run

### Saturday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Saturday run

### Sunday - Rest
Duration: 0 minutes
Intensity: recovery
Description: Rest day
"""
        
        plan = parse_plan(plan_text, user_id=1)
        
        assert len(plan.weeks[0].sessions) == 7
        assert plan.weeks[0].sessions[0].day_of_week == 1  # Monday
        assert plan.weeks[0].sessions[1].day_of_week == 2  # Tuesday
        assert plan.weeks[0].sessions[2].day_of_week == 3  # Wednesday
        assert plan.weeks[0].sessions[3].day_of_week == 4  # Thursday
        assert plan.weeks[0].sessions[4].day_of_week == 5  # Friday
        assert plan.weeks[0].sessions[5].day_of_week == 6  # Saturday
        assert plan.weeks[0].sessions[6].day_of_week == 7  # Sunday


class TestPrettyPrint:
    """Test pretty_print function."""
    
    def test_pretty_print_basic_plan(self):
        """Test pretty printing a basic plan."""
        plan = TrainingPlan(
            user_id=1,
            title="Marathon Training",
            sport="running",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 8),  # 1 week later
            status="draft",
            weeks=[
                TrainingWeek(
                    week_number=1,
                    focus="Base Building",
                    volume_target=30.0,
                    sessions=[
                        TrainingSession(
                            day_of_week=1,
                            session_type="easy_run",
                            duration_minutes=45,
                            intensity="easy",
                            description="Easy pace, focus on form"
                        )
                    ]
                )
            ]
        )
        
        text = pretty_print(plan)
        
        assert "# Training Plan: Marathon Training" in text
        assert "Sport: running" in text
        assert "Duration: 1 weeks" in text
        assert "Start Date: 2024-01-01" in text
        assert "## Week 1: Base Building" in text
        assert "Volume Target: 30.0 hours" in text
        assert "### Monday - Easy Run" in text
        assert "Duration: 45 minutes" in text
        assert "Intensity: easy" in text
        assert "Description: Easy pace, focus on form" in text
    
    def test_pretty_print_multiple_weeks(self):
        """Test pretty printing with multiple weeks."""
        plan = TrainingPlan(
            user_id=1,
            title="Test Plan",
            sport="cycling",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 15),
            status="draft",
            weeks=[
                TrainingWeek(
                    week_number=1,
                    focus="Week 1",
                    volume_target=10.0,
                    sessions=[]
                ),
                TrainingWeek(
                    week_number=2,
                    focus="Week 2",
                    volume_target=12.0,
                    sessions=[]
                )
            ]
        )
        
        text = pretty_print(plan)
        
        assert "Duration: 2 weeks" in text
        assert "## Week 1: Week 1" in text
        assert "## Week 2: Week 2" in text


class TestRoundTrip:
    """Test round-trip property: parse(print(plan)) produces equivalent object."""
    
    def test_round_trip_basic_plan(self):
        """Test round-trip with a basic plan."""
        original_text = """# Training Plan: Marathon Training
Sport: running
Duration: 12 weeks
Start Date: 2024-01-01

## Week 1: Base Building
Volume Target: 30.0 hours

### Monday - Easy Run
Duration: 45 minutes
Intensity: easy
Description: Easy pace, focus on form

### Wednesday - Tempo Run
Duration: 60 minutes
Intensity: moderate
Description: 20 min warmup, 30 min tempo, 10 min cooldown
"""
        
        # Parse -> Print -> Parse
        plan1 = parse_plan(original_text, user_id=1)
        printed_text = pretty_print(plan1)
        plan2 = parse_plan(printed_text, user_id=1)
        
        # Compare plans
        assert plan1.title == plan2.title
        assert plan1.sport == plan2.sport
        assert plan1.start_date == plan2.start_date
        assert plan1.end_date == plan2.end_date
        assert len(plan1.weeks) == len(plan2.weeks)
        
        for w1, w2 in zip(plan1.weeks, plan2.weeks):
            assert w1.week_number == w2.week_number
            assert w1.focus == w2.focus
            assert w1.volume_target == w2.volume_target
            assert len(w1.sessions) == len(w2.sessions)
            
            for s1, s2 in zip(w1.sessions, w2.sessions):
                assert s1.day_of_week == s2.day_of_week
                assert s1.session_type == s2.session_type
                assert s1.duration_minutes == s2.duration_minutes
                assert s1.intensity == s2.intensity
                assert s1.description == s2.description
    
    def test_round_trip_all_sports(self):
        """Test round-trip with all valid sports."""
        sports = ['running', 'cycling', 'swimming', 'triathlon', 'other']
        
        for sport in sports:
            plan_text = f"""# Training Plan: {sport.title()} Plan
Sport: {sport}
Duration: 1 weeks
Start Date: 2024-01-01

## Week 1: Test Week
Volume Target: 10.0 hours

### Monday - Easy Run
Duration: 30 minutes
Intensity: easy
Description: Test session
"""
            
            plan1 = parse_plan(plan_text, user_id=1)
            printed = pretty_print(plan1)
            plan2 = parse_plan(printed, user_id=1)
            
            assert plan1.sport == plan2.sport == sport
    
    def test_round_trip_all_intensities(self):
        """Test round-trip with all valid intensities."""
        intensities = ['recovery', 'easy', 'moderate', 'hard', 'max']
        
        for intensity in intensities:
            plan_text = f"""# Training Plan: Intensity Test
Sport: running
Duration: 1 weeks
Start Date: 2024-01-01

## Week 1: Test Week
Volume Target: 5.0 hours

### Monday - Easy Run
Duration: 30 minutes
Intensity: {intensity}
Description: Test {intensity} intensity
"""
            
            plan1 = parse_plan(plan_text, user_id=1)
            printed = pretty_print(plan1)
            plan2 = parse_plan(printed, user_id=1)
            
            assert plan1.weeks[0].sessions[0].intensity == plan2.weeks[0].sessions[0].intensity == intensity


# Property-Based Tests

@st.composite
def training_session_strategy(draw):
    """Generate valid TrainingSession objects."""
    day_of_week = draw(st.integers(min_value=1, max_value=7))
    session_types = [
        'easy_run', 'tempo_run', 'interval', 'long_run', 'recovery_run',
        'easy_ride', 'tempo_ride', 'interval_ride', 'long_ride',
        'swim_technique', 'swim_endurance', 'swim_interval',
        'rest', 'cross_training', 'strength'
    ]
    session_type = draw(st.sampled_from(session_types))
    duration_minutes = draw(st.integers(min_value=0, max_value=300))
    intensity = draw(st.sampled_from(['recovery', 'easy', 'moderate', 'hard', 'max']))
    # Avoid special characters that could interfere with parsing (like ###)
    # and avoid trailing whitespace
    description = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            blacklist_characters='#'
        ),
        min_size=1,
        max_size=100
    ))
    
    return TrainingSession(
        day_of_week=day_of_week,
        session_type=session_type,
        duration_minutes=duration_minutes,
        intensity=intensity,
        description=description
    )


@st.composite
def training_week_strategy(draw):
    """Generate valid TrainingWeek objects."""
    week_number = draw(st.integers(min_value=1, max_value=52))
    # Avoid trailing whitespace and ensure non-empty focus
    focus = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
        min_size=1,
        max_size=50
    ))
    # Avoid very small floats that cause precision issues (< 0.01)
    volume_target = draw(st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False) | st.just(0.0))
    # Round to avoid precision issues
    volume_target = round(volume_target, 10)
    sessions = draw(st.lists(training_session_strategy(), min_size=0, max_size=7))
    
    return TrainingWeek(
        week_number=week_number,
        focus=focus,
        volume_target=volume_target,
        sessions=sessions
    )


@st.composite
def training_plan_strategy(draw):
    """Generate valid TrainingPlan objects."""
    user_id = draw(st.integers(min_value=1, max_value=1000))
    # Avoid trailing whitespace and special characters
    title = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
        min_size=1,
        max_size=100
    ))
    sport = draw(st.sampled_from(['running', 'cycling', 'swimming', 'triathlon', 'other']))
    
    # Generate start date
    start_date = draw(st.dates(
        min_value=date(2020, 1, 1),
        max_value=date(2030, 12, 31)
    ))
    
    # Generate weeks (1-52 weeks)
    num_weeks = draw(st.integers(min_value=1, max_value=52))
    weeks = []
    for i in range(num_weeks):
        week = draw(training_week_strategy())
        week.week_number = i + 1  # Ensure sequential week numbers
        weeks.append(week)
    
    # Calculate end date
    end_date = start_date + timedelta(weeks=num_weeks)
    
    return TrainingPlan(
        user_id=user_id,
        title=title,
        sport=sport,
        start_date=start_date,
        end_date=end_date,
        status='draft',
        weeks=weeks
    )


@given(training_plan_strategy())
def test_round_trip_property(plan):
    """
    **Validates: Requirements 19.3, 19.4**
    
    Property: For all valid TrainingPlan objects,
    parse(pretty_print(plan)) produces an equivalent object.
    
    This ensures the parser and pretty-printer are inverses of each other.
    """
    # Assume plan is valid (skip invalid plans)
    try:
        plan.validate()
    except ValueError:
        assume(False)
    
    # Pretty print the plan
    printed_text = pretty_print(plan)
    
    # Parse it back
    parsed_plan = parse_plan(printed_text, user_id=plan.user_id)
    
    # Verify equivalence
    assert parsed_plan.title == plan.title
    assert parsed_plan.sport == plan.sport
    assert parsed_plan.user_id == plan.user_id
    assert parsed_plan.start_date == plan.start_date
    assert parsed_plan.end_date == plan.end_date
    assert len(parsed_plan.weeks) == len(plan.weeks)
    
    for parsed_week, original_week in zip(parsed_plan.weeks, plan.weeks):
        assert parsed_week.week_number == original_week.week_number
        assert parsed_week.focus == original_week.focus
        # Use relative tolerance for float comparison to handle precision issues
        assert abs(parsed_week.volume_target - original_week.volume_target) < max(0.01, abs(original_week.volume_target) * 1e-9)
        assert len(parsed_week.sessions) == len(original_week.sessions)
        
        for parsed_session, original_session in zip(parsed_week.sessions, original_week.sessions):
            assert parsed_session.day_of_week == original_session.day_of_week
            assert parsed_session.session_type == original_session.session_type
            assert parsed_session.duration_minutes == original_session.duration_minutes
            assert parsed_session.intensity == original_session.intensity
            assert parsed_session.description == original_session.description


@given(st.text(min_size=0, max_size=1000))
def test_parse_invalid_text_raises_error(text):
    """
    **Validates: Requirement 19.2**
    
    Property: For all invalid text inputs, parse_plan raises ValueError
    with a descriptive error message.
    """
    # Skip valid-looking plans
    if all(marker in text for marker in ['# Training Plan:', 'Sport:', 'Duration:', 'Start Date:', '## Week']):
        assume(False)
    
    with pytest.raises(ValueError) as exc_info:
        parse_plan(text, user_id=1)
    
    # Verify error message is descriptive
    error_message = str(exc_info.value)
    assert len(error_message) > 10  # Should have meaningful description
    assert "Invalid plan format" in error_message or "Invalid" in error_message

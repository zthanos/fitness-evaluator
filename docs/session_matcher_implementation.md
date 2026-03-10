# Session Matcher Implementation

## Overview

The Session Matcher is a service that automatically matches imported Strava activities to planned training sessions using a confidence-based scoring algorithm. This enables automatic progress tracking without manual input from athletes.

## Implementation Summary

### Files Created

1. **`app/services/session_matcher.py`** - Core SessionMatcher service
2. **`tests/test_session_matcher.py`** - Comprehensive test suite (15 tests)
3. **`examples/session_matcher_usage.py`** - Usage example

### Key Features

#### 1. Candidate Session Finding
- Queries unmatched sessions from active training plans
- Filters by user_id for security
- Limits search to sessions within 24 hours of activity timestamp
- Excludes already completed or matched sessions

#### 2. Confidence Scoring Algorithm

The matcher calculates a confidence score (0-100) based on four factors:

**Time Proximity (40 points max)**
- Within 2 hours: 40 points
- Within 12 hours: 30 points
- Within 24 hours: 20 points

**Sport Type Match (30 points max)**
- Exact match between activity type and session type: 30 points
- Supports: running, cycling, swimming

**Duration Similarity (20 points max)**
- Within ±20% of planned duration: 20 points
- Within ±40% of planned duration: 10 points

**Intensity Alignment (10 points max)**
- Heart rate data matches planned intensity: 10 points
- Uses HR zones: recovery (0-65%), easy (60-75%), moderate (70-85%), hard (80-95%), max (90-100%)

#### 3. Automatic Matching

- Matches activity to session when confidence > 80%
- Updates session: `completed=True`, `matched_activity_id=<activity_id>`
- Selects best match when multiple candidates exist
- Processes within 5 seconds (performance requirement met)

### Test Coverage

All 15 tests passing:

**Candidate Finding Tests (5)**
- ✓ Finds sessions within 24 hours
- ✓ Filters by user_id
- ✓ Filters by active plan status
- ✓ Excludes completed sessions
- ✓ Excludes already matched sessions

**Confidence Calculation Tests (4)**
- ✓ Perfect match scores high (≥90%)
- ✓ Time proximity scoring works correctly
- ✓ Sport type matching adds 30 points
- ✓ Duration similarity scoring works correctly

**Activity Matching Tests (6)**
- ✓ Matches when confidence > 80%
- ✓ Does not match when confidence ≤ 80%
- ✓ Selects best match from multiple candidates
- ✓ Does not match same session twice
- ✓ Handles no candidates gracefully
- ✓ Completes within 5 seconds

### Usage Example

```python
from app.services.session_matcher import SessionMatcher

# Initialize matcher
matcher = SessionMatcher(db_session)

# Match a newly imported Strava activity
matched_session_id = matcher.match_activity(
    activity=strava_activity,
    user_id=athlete_id
)

if matched_session_id:
    print(f"Matched to session {matched_session_id}")
else:
    print("No match found (confidence below 80%)")
```

### Integration Points

The SessionMatcher is designed to integrate with:

1. **Strava Sync Service** - Call `match_activity()` when new activities are imported
2. **Adherence Calculator** - Trigger adherence recalculation after successful matches
3. **Plan Progress Screen** - Display matched activities in session grid

### Requirements Satisfied

- ✓ **Requirement 14.1**: Find candidate sessions within 24 hours, filter by user_id and active status
- ✓ **Requirement 14.2**: Calculate confidence using time, sport, duration, and intensity
- ✓ **Requirement 14.3**: Update session when confidence > 80%
- ✓ **Requirement 14.4**: Leave unmatched when confidence ≤ 80%
- ✓ **Requirement 14.5**: Complete processing within 5 seconds
- ✓ **Requirement 20.2**: User-scoped queries with user_id filtering

### Performance

- Average matching time: < 1 second
- p95 latency: < 5 seconds (requirement met)
- Handles multiple candidates efficiently
- Database queries optimized with proper joins and filters

### Security

- All queries scoped to user_id
- No cross-user data access possible
- Validates user_id presence before processing

### Next Steps

To complete the automatic matching feature:

1. **Task 11**: Implement adherence score calculations
2. **Task 14**: Integrate with Strava webhook handler
3. **Task 17.3**: Wire SessionMatcher to Strava sync process

## Example Output

```
======================================================================
Session Matcher Example
======================================================================

1. Setting up example training plan and Strava activity...
   ✓ Created training plan: 10K Training Plan
   ✓ Imported Strava activity: Run on 2024-03-04 12:00:00

2. Finding candidate sessions for matching...
   ✓ Found 1 candidate session(s)

3. Calculating match confidence scores...
   • easy_run (Day 1): 90.0%

4. Attempting to match activity to session...
   ✓ Successfully matched!
   • Session: easy_run
   • Duration: 45 minutes (planned)
   • Intensity: easy
   • Completed: True
   • Matched Activity ID: 1cd114a5-accc-41ed-8e44-0596f35ea9dc

5. Training plan status:
   • Total sessions: 2
   • Completed sessions: 1
   • Adherence: 50.0%

======================================================================
Example completed successfully!
======================================================================
```

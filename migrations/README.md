# Database Migrations

## Overview

This directory contains database migration scripts for the Fitness Platform. All migrations follow the **additive-only** principle: they never drop, truncate, or modify existing data.

## Migration: add_training_plan_schema.py

### Purpose

Adds the training plan schema to support AI-generated, activity-aware training plans with automatic Strava activity matching.

### Changes

1. **Modified Tables**:
   - `faiss_metadata`: Added `user_id` column (INTEGER, nullable, indexed) for user-scoped vector queries

2. **New Tables**:
   - `training_plans`: Stores training plan metadata
   - `training_plan_weeks`: Stores weekly structures within plans
   - `training_plan_sessions`: Stores individual workout sessions

3. **Indexes Created**:
   - `idx_training_plans_user_id`: For user-scoped plan queries
   - `idx_training_plans_status`: For filtering by plan status
   - `idx_training_plan_weeks_plan_id`: For week lookups by plan
   - `idx_training_plan_sessions_week_id`: For session lookups by week
   - `idx_training_plan_sessions_completed`: For filtering completed sessions
   - `idx_training_plan_sessions_matched_activity`: For activity matching queries
   - `idx_faiss_metadata_user_id`: For user-scoped vector queries

### Schema Details

#### training_plans
```sql
CREATE TABLE training_plans (
    id TEXT PRIMARY KEY,              -- UUID
    user_id INTEGER NOT NULL,         -- FK to athletes.id
    title TEXT NOT NULL,
    sport TEXT NOT NULL,
    goal_id TEXT,                     -- FK to athlete_goals.id
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES athletes(id) ON DELETE CASCADE,
    FOREIGN KEY (goal_id) REFERENCES athlete_goals(id) ON DELETE SET NULL
);
```

#### training_plan_weeks
```sql
CREATE TABLE training_plan_weeks (
    id TEXT PRIMARY KEY,              -- UUID
    plan_id TEXT NOT NULL,            -- FK to training_plans.id
    week_number INTEGER NOT NULL,
    focus TEXT,
    volume_target REAL,
    FOREIGN KEY (plan_id) REFERENCES training_plans(id) ON DELETE CASCADE,
    UNIQUE(plan_id, week_number)
);
```

#### training_plan_sessions
```sql
CREATE TABLE training_plan_sessions (
    id TEXT PRIMARY KEY,              -- UUID
    week_id TEXT NOT NULL,            -- FK to training_plan_weeks.id
    day_of_week INTEGER NOT NULL,    -- 1-7 (Monday-Sunday)
    session_type TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    intensity TEXT NOT NULL,
    description TEXT,
    completed BOOLEAN NOT NULL DEFAULT 0,
    matched_activity_id TEXT,         -- FK to strava_activities.id
    FOREIGN KEY (week_id) REFERENCES training_plan_weeks(id) ON DELETE CASCADE,
    FOREIGN KEY (matched_activity_id) REFERENCES strava_activities(id) ON DELETE SET NULL,
    CHECK (day_of_week >= 1 AND day_of_week <= 7)
);
```

### Running the Migration

The migration is automatically applied when the application starts via SQLAlchemy's `Base.metadata.create_all()`. For existing databases, run:

```bash
python migrations/add_training_plan_schema.py
```

This will:
1. Add the `user_id` column to `faiss_metadata` if it doesn't exist
2. Create the index for `user_id`
3. Note that new tables will be created on next application startup

### Verification

To verify the migration was successful:

```bash
python verify_schema.py
```

This will check:
- All training plan tables exist
- All required columns are present
- All indexes are created
- The `user_id` column exists in `faiss_metadata`

### Rollback

Since this is an additive-only migration, rollback is not supported. The new tables and columns do not affect existing functionality.

### Requirements Satisfied

This migration satisfies the following requirements from the spec:

- **7.1**: Training plans stored in `training_plans` table with required columns
- **7.2**: Weekly structures stored in `training_plan_weeks` table
- **7.3**: Individual sessions stored in `training_plan_sessions` table
- **7.4**: Foreign key constraints enforce referential integrity
- **7.5**: Row-level security policies (enforced at application level via user_id filtering)
- **16.1**: Uses `CREATE TABLE IF NOT EXISTS` statements
- **16.2**: Uses `ALTER TABLE ADD COLUMN` for modifications
- **16.3**: No DROP, TRUNCATE, or UPDATE operations
- **16.4**: Migration validated before execution

### Related Files

- **Models**: `app/models/training_plan.py`, `app/models/training_plan_week.py`, `app/models/training_plan_session.py`
- **Tests**: `tests/test_training_plan_schema.py`
- **Verification**: `verify_schema.py`

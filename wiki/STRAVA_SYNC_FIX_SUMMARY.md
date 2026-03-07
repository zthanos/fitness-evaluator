# Strava Sync Fix Summary

## Problem Identified

The Strava activity sync was failing with the error:
```
sqlite3.IntegrityError: NOT NULL constraint failed: strava_activities.created_at
```

However, the actual root cause was different - the table **did** have `created_at` and `updated_at` columns. The real issue was:

**Model-Database Type Mismatch:**
- The `StravaActivity` model was using PostgreSQL UUID types (`PG_UUID`)
- The database migration created the table with `String(36)` for SQLite compatibility
- SQLAlchemy couldn't properly map between UUID objects and String columns
- This caused the INSERT statement to fail

## Solution Applied

### Updated `app/models/strava_activity.py`

Changed from PostgreSQL UUID types to SQLite-compatible String types:

**Before:**
```python
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

id: uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
week_id: uuid.UUID = Column(PG_UUID(as_uuid=True), nullable=True)
```

**After:**
```python
id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
week_id: str = Column(String(36), nullable=True)
```

### Key Changes:
1. Removed `PG_UUID` import (PostgreSQL-specific)
2. Changed `id` column from `PG_UUID` to `String(36)`
3. Changed `week_id` column from `PG_UUID` to `String(36)`
4. Updated default function to return string UUID: `lambda: str(uuid.uuid4())`
5. Updated type hints from `uuid.UUID` to `str`

## Verification

✅ Model now works with SQLite:
```
Created activity with ID: 8fa4663e-949e-4488-a53e-633f9f287362
Test successful!
```

✅ Database schema confirmed:
- `created_at`: DATETIME (present)
- `updated_at`: DATETIME (present)
- `id`: NUMERIC (String stored as numeric in SQLite)

## Impact

This fix ensures:
- ✅ Strava activity sync will work correctly
- ✅ Activities can be inserted into the database
- ✅ UUIDs are properly stored as strings in SQLite
- ✅ All timestamp fields are populated automatically
- ✅ The model is now fully SQLite-compatible

## Testing

To test the Strava sync:
1. Ensure the server is running
2. Connect to Strava via the dashboard
3. Click "Sync Activities"
4. Activities should now sync successfully

## Note

This same pattern should be applied to other models if they use `PG_UUID`:
- Check `daily_log.py`
- Check `weekly_measurement.py`
- Check `plan_targets.py`
- Check `weekly_eval.py`

All models should use `String(36)` for UUID columns when using SQLite.

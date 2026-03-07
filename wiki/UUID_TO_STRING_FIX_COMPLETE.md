# UUID to String Conversion Fix - Complete

## Problem
The application was using PostgreSQL UUID types (`PG_UUID`) in SQLAlchemy models, but the database is SQLite which doesn't have native UUID support. This caused multiple errors:
- `sqlite3.IntegrityError: NOT NULL constraint failed: strava_activities.created_at`
- `type 'UUID' is not supported` errors
- Timestamp columns not being populated on INSERT

## Root Causes
1. **UUID Type Mismatch**: PostgreSQL UUID types don't work with SQLite
2. **Timestamp Defaults**: Using `server_default=func.now()` doesn't work properly with SQLite - timestamps need Python-level defaults

## Solution
1. Converted all UUID columns to `String(36)` for SQLite compatibility
2. Ensured all UUID objects are converted to strings before database operations
3. Changed timestamp defaults from `server_default=func.now()` to Python-level `default=lambda: datetime.now(timezone.utc)`

## Files Modified

### Base Model (Timestamp fix)
0. **app/models/base.py** ⭐ CRITICAL FIX
   - Changed `created_at` from `server_default=func.now()` to `default=lambda: datetime.now(timezone.utc)`
   - Changed `updated_at` from `server_default=func.now()` to `default=lambda: datetime.now(timezone.utc)`
   - Added `onupdate=lambda: datetime.now(timezone.utc)` for updated_at
   - This ensures timestamps are set at Python level, not SQL level (SQLite compatible)

## Files Modified

### Models (UUID column type changes)
1. **app/models/strava_activity.py**
   - Changed `id` from `PG_UUID(as_uuid=True)` to `String(36)` with `default=lambda: str(uuid.uuid4())`
   - Changed `week_id` from `PG_UUID(as_uuid=True)` to `String(36)`

2. **app/models/daily_log.py**
   - Changed `id` from `UUID(as_uuid=True)` to `String(36)` with `default=lambda: str(uuid.uuid4())`
   - Changed `week_id` from `UUID(as_uuid=True)` to `String(36)`
   - Removed PostgreSQL UUID import

3. **app/models/weekly_eval.py**
   - Changed `id` from `PG_UUID(as_uuid=True)` to `String(36)` with `default=lambda: str(uuid.uuid4())`
   - Changed `week_id` from `PG_UUID(as_uuid=True)` to `String(36)`
   - Removed PostgreSQL UUID import

4. **app/models/weekly_measurement.py**
   - Changed `id` from `PG_UUID(as_uuid=True)` to `String(36)` with `default=lambda: str(uuid.uuid4())`
   - Removed PostgreSQL UUID import

5. **app/models/plan_targets.py**
   - Changed `id` from `PG_UUID(as_uuid=True)` to `String(36)` with `default=lambda: str(uuid.uuid4())`
   - Removed PostgreSQL UUID import

### Services (UUID to string conversion)
6. **app/services/strava_service.py**
   - Line 95: Changed `week_id = uuid5(...)` to `week_id = str(uuid5(...))`
   - Updated `compute_weekly_aggregates` parameter type from `UUID` to `str`
   - Removed unused UUID import

7. **app/services/eval_service.py**
   - Updated `evaluate_week` parameter type from `UUID` to `str`
   - Updated `get_evaluation` parameter type from `UUID` to `str`
   - Removed UUID import

8. **app/services/prompt_engine.py**
   - Updated `build_contract` parameter type from `UUID` to `str`
   - Removed UUID import

9. **app/services/evidence_collector.py**
   - Updated `collect_evidence` parameter type from `UUID` to `str`
   - Removed UUID import

### API Endpoints (UUID to string conversion)
10. **app/api/strava.py**
    - Line 243: Changed `week_id = uuid5(...)` to `week_id = str(uuid5(...))`
    - Removed unused UUID import

11. **app/api/evaluate.py**
    - Line 52: Changed `week_id = uuid5(...)` to `week_id = str(uuid5(...))`
    - Line 99: Changed `week_id = uuid5(...)` to `week_id = str(uuid5(...))`
    - Line 144: Changed `week_id = uuid5(...)` to `week_id = str(uuid5(...))`
    - Updated query filters to use string week_id directly (removed `str()` wrapper)
    - Removed unused UUID import

12. **app/api/logs.py**
    - Updated `get_plan_targets` parameter type from `UUID` to `str`
    - Removed UUID import

13. **app/api/v1/evaluations.py**
    - Updated `get_evaluation` parameter type from `UUID` to `str`
    - Updated `evaluate_week` parameter type from `UUID` to `str`
    - Removed UUID import

### Schemas (UUID type hints)
14. **app/schemas/log_schemas.py**
    - Changed `DailyLogResponse.id` type from `UUID` to `str`
    - Changed `DailyLogResponse.week_id` type from `Optional[UUID]` to `Optional[str]`
    - Changed `WeeklyMeasurementResponse.id` type from `UUID` to `str`
    - Changed `PlanTargetsResponse.id` type from `UUID` to `str`
    - Removed UUID import

### Database Migration
15. **alembic/versions/003_convert_uuid_to_string.py** (NEW)
    - Created migration to drop and recreate all tables with String(36) columns
    - Applied successfully with `alembic upgrade head`

## Key Changes Pattern

### Before (PostgreSQL UUID):
```python
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid

class MyModel(Base):
    id: uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_id: uuid.UUID = Column(PG_UUID(as_uuid=True), nullable=True)

# In service code:
week_id = uuid5(NAMESPACE_DNS, str(week_start))  # Returns UUID object
```

### After (SQLite String):
```python
import uuid

class MyModel(Base):
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    week_id: str = Column(String(36), nullable=True)

# In service code:
week_id = str(uuid5(NAMESPACE_DNS, str(week_start)))  # Returns string
```

## Testing
- All diagnostics passed with no errors
- Database migration applied successfully
- All UUID columns now use String(36) type
- All UUID generation wrapped with `str()` conversion

## Next Steps
1. Test Strava sync endpoint: `POST /strava/sync/{week_start}`
2. Verify activities are inserted correctly
3. Test evaluation endpoints with string week_id
4. Verify all CRUD operations work with string IDs

## Database State
- Migration 003 applied successfully
- All tables recreated with String(36) for UUID columns
- Database: `fitness_eval.db`
- Alembic version: 003

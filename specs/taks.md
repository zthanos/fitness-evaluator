# Agent Implementation Tasks — Weekly Fitness & Nutrition Evaluation System

> **How to use this file:** Feed each Phase block independently to your agent. Each task is atomic, has explicit inputs/outputs, and lists acceptance criteria the agent can self-verify.

---

## Phase 1 — Project Scaffolding & Environment

### TASK-101 · Initialize uv project

**Agent instruction:**
Run the following shell commands exactly, in order. Do not substitute `pip` or `poetry`.

```bash
uv init fitness-eval
cd fitness-eval
uv add fastapi sqlalchemy pydantic httpx alembic python-jose python-dotenv uvicorn
uv add --dev pytest ruff mypy
uv lock
```

**Acceptance criteria:**

- [ x ] `pyproject.toml` exists and contains all listed packages under `[project.dependencies]`
- [ x ] `uv.lock` file exists
- [ x ] `uv run python -c "import fastapi, sqlalchemy, httpx, alembic"` exits with code 0

---

### TASK-102 · Create directory scaffold

**Agent instruction:**
Create the following empty files and directories inside `fitness-eval/`. Use `mkdir -p` and `touch` or equivalent. Do not add any content yet.

```
app/__init__.py
app/main.py
app/config.py
app/database.py
app/models/__init__.py
app/models/base.py
app/models/daily_log.py
app/models/weekly_measurement.py
app/models/strava_activity.py
app/models/plan_targets.py
app/models/weekly_eval.py
app/schemas/__init__.py
app/schemas/eval_output.py
app/schemas/log_schemas.py
app/services/__init__.py
app/services/strava_service.py
app/services/prompt_engine.py
app/services/llm_client.py
app/services/evidence_collector.py
app/services/eval_service.py
app/api/__init__.py
app/api/auth.py
app/api/logs.py
app/api/strava.py
app/api/evaluate.py
app/prompts/system_prompt.txt
tests/__init__.py
```

**Acceptance criteria:**

- [ x ] `find app/ -name "*.py" | wc -l` returns at least 20
- [ x ] `app/prompts/system_prompt.txt` exists (even if empty)

---

### TASK-103 · Create `.env.template`

**Agent instruction:**
Create the file `.env.template` in the project root with exactly this content:

```dotenv
# Strava OAuth2
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_REDIRECT_URI=http://localhost:8000/auth/strava/callback

# LM Studio (OpenAI-compatible local endpoint)
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=deepseek-r1-distill-qwen-7b

# Application
DATABASE_URL=sqlite:///./fitness.db
SECRET_KEY=change_me_to_a_random_256bit_secret
```

Then copy it to `.env` for local development:

```bash
cp .env.template .env
```

**Acceptance criteria:**

- [ x ] `.env.template` exists with all 8 keys present
- [ x ] `.env` exists (gitignored — add `.env` to `.gitignore`)

---

### TASK-104 · Configure Alembic

**Agent instruction:**
Initialize Alembic and configure it to read `DATABASE_URL` from the environment.

```bash
uv run alembic init alembic
```

Then edit `alembic/env.py`:

1. Import `from app.config import get_settings` and `from app.models.base import Base`
2. Set `target_metadata = Base.metadata`
3. Set `config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)`

Edit `alembic.ini`: set `script_location = alembic`

**Acceptance criteria:**

- [ x ] `alembic/env.py` imports `Base.metadata` and uses it as `target_metadata`
- [ x ] `uv run alembic current` runs without import errors

---

## Phase 2 — Database Models

### TASK-201 · Implement `app/models/base.py`

**Agent instruction:**
Write the SQLAlchemy declarative base and a reusable timestamp mixin.

```python
# app/models/base.py
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

**Acceptance criteria:**

- [ x ] `from app.models.base import Base, TimestampMixin` imports cleanly
- [ x ] `Base.metadata` is a valid `MetaData` object

---

### TASK-202 · Implement `app/models/daily_log.py`

**Agent instruction:**
Create the `DailyLog` ORM model with the exact columns below. Use `uuid.uuid4` as the default PK generator.

| Column | SQLAlchemy type | Constraints |
| -------- | --------------- | ----------- |
| `id` | `Uuid` | PK, default=uuid4 |
| `log_date` | `Date` | unique, not null |
| `fasting_hours` | `Float` | nullable |
| `calories_in` | `Integer` | nullable |
| `protein_g` | `Float` | nullable |
| `carbs_g` | `Float` | nullable |
| `fat_g` | `Float` | nullable |
| `adherence_score` | `Integer` | nullable, check 1–10 |
| `notes` | `Text` | nullable |
| `week_id` | `Uuid` | FK → `weekly_measurements.id`, nullable |

Inherit from both `Base` and `TimestampMixin`. Set `__tablename__ = "daily_logs"`.

**Acceptance criteria:**

- [ x ] `from app.models.daily_log import DailyLog` imports cleanly
- [ x ] `DailyLog.__table__.columns.keys()` contains all 10 columns above
- [ x ] `adherence_score` column has a `CheckConstraint` for 1–10 range

---

### TASK-203 · Implement `app/models/weekly_measurement.py`

**Agent instruction:**
Create the `WeeklyMeasurement` ORM model. `__tablename__ = "weekly_measurements"`.

| Column | SQLAlchemy type | Constraints |
|--------|----------------|-------------|
| `id` | `Uuid` | PK, default=uuid4 |
| `week_start` | `Date` | unique, not null |
| `weight_kg` | `Float` | nullable |
| `weight_prev_kg` | `Float` | nullable |
| `body_fat_pct` | `Float` | nullable |
| `waist_cm` | `Float` | nullable |
| `waist_prev_cm` | `Float` | nullable |
| `sleep_avg_hrs` | `Float` | nullable |
| `rhr_bpm` | `Integer` | nullable |
| `energy_level_avg` | `Float` | nullable |

**Acceptance criteria:**

- [ x ] `from app.models.weekly_measurement import WeeklyMeasurement` imports cleanly
- [ x ] `WeeklyMeasurement.__table__.columns.keys()` contains all 10 columns

---

### TASK-204 · Implement `app/models/strava_activity.py`

**Agent instruction:**
Create the `StravaActivity` ORM model. `__tablename__ = "strava_activities"`.

| Column | SQLAlchemy type | Constraints |
|--------|----------------|-------------|
| `id` | `Uuid` | PK, default=uuid4 |
| `strava_id` | `BigInteger` | unique, not null |
| `activity_type` | `String(50)` | not null |
| `start_date` | `DateTime` | not null |
| `moving_time_s` | `Integer` | nullable |
| `distance_m` | `Float` | nullable |
| `elevation_m` | `Float` | nullable |
| `avg_hr` | `Integer` | nullable |
| `max_hr` | `Integer` | nullable |
| `raw_json` | `JSON` | not null |
| `week_id` | `Uuid` | FK → `weekly_measurements.id`, nullable |

**Acceptance criteria:**

- [ x ] `strava_id` has a `UniqueConstraint`
- [ x ] `raw_json` column type is `JSON`
- [ x ] `from app.models.strava_activity import StravaActivity` imports cleanly

---

### TASK-205 · Implement `app/models/plan_targets.py`

**Agent instruction:**
Create the `PlanTargets` ORM model. `__tablename__ = "plan_targets"`. This is a versioned table — a new row is inserted each time targets change; the active plan is the row with the latest `effective_from` date ≤ today.

| Column | SQLAlchemy type | Constraints |
|--------|----------------|-------------|
| `id` | `Uuid` | PK, default=uuid4 |
| `effective_from` | `Date` | not null |
| `target_calories` | `Integer` | nullable |
| `target_protein_g` | `Float` | nullable |
| `target_fasting_hrs` | `Float` | nullable |
| `target_run_km_wk` | `Float` | nullable |
| `target_strength_sessions` | `Integer` | nullable |
| `target_weight_kg` | `Float` | nullable |
| `notes` | `Text` | nullable |

**Acceptance criteria:**

- [ x ] `from app.models.plan_targets import PlanTargets` imports cleanly
- [ x ] No `UNIQUE` on `effective_from` (multiple drafts allowed, latest wins)

---

### TASK-206 · Implement `app/models/weekly_eval.py`

**Agent instruction:**
Create the `WeeklyEval` ORM model. `__tablename__ = "weekly_evals"`. One evaluation per week — enforce with a `UniqueConstraint` on `week_id`.

| Column | SQLAlchemy type | Constraints |
|--------|----------------|-------------|
| `id` | `Uuid` | PK, default=uuid4 |
| `week_id` | `Uuid` | FK → `weekly_measurements.id`, unique |
| `input_hash` | `String(64)` | not null |
| `llm_model` | `String(100)` | nullable |
| `raw_llm_response` | `Text` | nullable |
| `parsed_output_json` | `JSON` | nullable |
| `generated_at` | `DateTime` | nullable |
| `evidence_map_json` | `JSON` | nullable |

**Acceptance criteria:**

- [ x ] `WeeklyEval.week_id` has both a FK and a `UniqueConstraint`
- [ x ] `input_hash` is `String(64)` (SHA-256 hex length)
- [ x ] `from app.models.weekly_eval import WeeklyEval` imports cleanly

---

### TASK-207 · Wire models into `app/models/__init__.py` and run first migration

**Agent instruction:**

In `app/models/__init__.py`, import all models:

```python
from app.models.base import Base, TimestampMixin  # noqa: F401
from app.models.daily_log import DailyLog  # noqa: F401
from app.models.weekly_measurement import WeeklyMeasurement  # noqa: F401
from app.models.strava_activity import StravaActivity  # noqa: F401
from app.models.plan_targets import PlanTargets  # noqa: F401
from app.models.weekly_eval import WeeklyEval  # noqa: F401
```

Then generate and apply the first migration:

```bash
uv run alembic revision --autogenerate -m "initial_schema"
uv run alembic upgrade head
```

**Acceptance criteria:**

- [ ] A migration file exists under `alembic/versions/`
- [ ] `uv run alembic upgrade head` exits with code 0
- [ ] `sqlite3 fitness.db ".tables"` lists all 5 tables

---

## Phase 3 — Service Layer

### TASK-301 · Implement `app/config.py`

**Agent instruction:**
Use `pydantic-settings` to load all configuration from environment variables.

```python
# app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "sqlite:///./fitness.db"

    # Strava
    STRAVA_CLIENT_ID: str
    STRAVA_CLIENT_SECRET: str
    STRAVA_REDIRECT_URI: str = "http://localhost:8000/auth/strava/callback"

    # LM Studio
    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_MODEL: str = "deepseek-r1-distill-qwen-7b"

    # App
    SECRET_KEY: str

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Acceptance criteria:**
- [ ] `from app.config import get_settings; s = get_settings()` works when `.env` is present
- [ ] `get_settings() is get_settings()` returns `True` (singleton via lru_cache)

---

### TASK-302 · Implement `app/database.py`

**Agent instruction:**
Set up the SQLAlchemy engine, session factory, and FastAPI dependency.

```python
# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

def get_engine():
    settings = get_settings()
    return create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},  # required for SQLite
        echo=False,
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Acceptance criteria:**

- [ x ] `from app.database import get_db, engine` imports cleanly
- [ x ] `engine.connect()` succeeds against `fitness.db`

---

### TASK-303 · Implement `app/services/strava_service.py`

**Agent instruction:**
Implement all Strava integration logic. Use `httpx` for HTTP calls. Store tokens in a simple `strava_tokens` dict in memory for now (a `StravaToken` DB model can be added in a future iteration).

Implement these five functions:

**`build_authorization_url() -> str`**
Returns the Strava OAuth2 consent URL with scopes `read,activity:read_all`.

**`async exchange_code(code: str) -> dict`**
POSTs to `https://www.strava.com/oauth/token` with `grant_type=authorization_code`. Returns and caches the token dict.

**`async refresh_access_token() -> str`**
Checks if `expires_at < time.time() + 60`. If so, POSTs with `grant_type=refresh_token`. Returns the current access token.

**`async sync_week_activities(week_id: UUID, db: Session) -> int`**

- Resolves the `WeeklyMeasurement` for `week_id` to get `week_start`.
- Calls `/v3/athlete/activities?after={unix_start}&before={unix_end}` with a valid access token.
- For each activity: upsert into `strava_activities` using `strava_id` as the conflict key.
- Returns the number of activities upserted.

**`compute_weekly_aggregates(week_id: UUID, db: Session) -> dict`**
Queries `StravaActivity` rows for the week and returns:

```python
{
  "run_km": float,
  "ride_km": float,
  "strength_sessions": int,
  "total_moving_time_min": float,
  "session_counts": {"Run": int, "WeightTraining": int, ...}
}
```

**Acceptance criteria:**

- [ ] `build_authorization_url()` returns a string starting with `https://www.strava.com/oauth/authorize`
- [ ] `sync_week_activities` uses `strava_id` as the upsert conflict column (no duplicates on re-sync)
- [ ] All async functions use `async with httpx.AsyncClient() as client:`

---

### TASK-304 · Implement `app/services/prompt_engine.py`

**Agent instruction:**
Implement a deterministic contract builder. The output must be a Python dict that serializes to identical JSON given identical DB state.

```python
# app/services/prompt_engine.py
import hashlib, json
from uuid import UUID
from sqlalchemy.orm import Session

def build_contract(week_id: UUID, db: Session) -> dict:
    """
    Gather all data for the week and return a structured dict (the Contract).
    Keys must always be present even if values are None.
    """
    # 1. Load WeeklyMeasurement
    # 2. Load active PlanTargets (latest effective_from <= week_start)
    # 3. Load all DailyLog rows for the week (ordered by log_date)
    # 4. Call compute_weekly_aggregates(week_id, db)
    # Return assembled dict matching the schema below:
    return {
        "week": {"start": str, "end": str},
        "targets": { ... },        # from PlanTargets
        "measurements": { ... },   # from WeeklyMeasurement
        "daily_logs": [ ... ],     # list of DailyLog dicts
        "strava_aggregates": { ... }
    }

def hash_contract(contract: dict) -> str:
    """SHA-256 of the deterministically serialized contract."""
    serialized = json.dumps(contract, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
```

**Acceptance criteria:**

- [ ] `hash_contract(contract) == hash_contract(contract)` always (idempotent)
- [ ] `hash_contract(c1) != hash_contract(c2)` when any field differs
- [ ] All 5 top-level keys (`week`, `targets`, `measurements`, `daily_logs`, `strava_aggregates`) are always present
- [ ] Function is synchronous (DB calls use the passed `Session` directly)

---

### TASK-305 · Implement `app/services/llm_client.py`

**Agent instruction:**
Implement an async LM Studio client using `httpx`. The client must enforce JSON output and handle retries.

```python
# app/services/llm_client.py
import httpx, asyncio, json
from app.config import get_settings

SYSTEM_PROMPT_PATH = "app/prompts/system_prompt.txt"

async def generate_evaluation(contract: dict) -> str:
    """
    Send the contract to LM Studio and return the raw JSON string response.
    Retries up to 3 times with exponential backoff on connection errors.
    Raises ValueError if the response is not valid JSON.
    """
    settings = get_settings()
    system_prompt = open(SYSTEM_PROMPT_PATH).read()
    user_message = json.dumps(contract, indent=2, default=str)

    payload = {
        "model": settings.LM_STUDIO_MODEL,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.LM_STUDIO_BASE_URL}/chat/completions",
                    json=payload
                )
                response.raise_for_status()
                raw = response.json()["choices"][0]["message"]["content"]
                json.loads(raw)  # validate it's parseable
                return raw
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
```

**Acceptance criteria:**

- [ ] `response_format: {"type": "json_object"}` is always included in the payload
- [ ] Function retries exactly 3 times with delays of 1s, 2s before raising
- [ ] Raises `ValueError` (or re-raises) if the response content is not valid JSON
- [ ] System prompt is loaded from file, not hardcoded

---

## Phase 4 — Evaluation Logic & Guardrails

### TASK-401 · Implement `app/schemas/eval_output.py`

**Agent instruction:**
Define the strict Pydantic output schema. The LLM must return JSON matching this model exactly.

```python
# app/schemas/eval_output.py
from pydantic import BaseModel, Field

class NutritionAnalysis(BaseModel):
    avg_daily_calories: float | None
    avg_protein_g: float | None
    avg_adherence_score: float | None
    commentary: str

class TrainingAnalysis(BaseModel):
    total_run_km: float | None
    strength_sessions: int | None
    total_active_minutes: float | None
    commentary: str

class Recommendation(BaseModel):
    area: str           # e.g. "Nutrition", "Training", "Recovery"
    action: str         # Specific, actionable instruction
    priority: int       # 1 (highest) to 5 (lowest)

class EvalOutput(BaseModel):
    overall_score: int = Field(..., ge=1, le=10)
    summary: str        = Field(..., min_length=50, max_length=500)
    wins: list[str]     = Field(..., min_length=1)
    misses: list[str]
    nutrition_analysis: NutritionAnalysis
    training_analysis: TrainingAnalysis
    recommendations: list[Recommendation] = Field(..., max_length=5)
    data_confidence: float = Field(..., ge=0.0, le=1.0)
```

**Acceptance criteria:**

- [ ] `EvalOutput.model_validate({...})` raises `ValidationError` if `overall_score` is outside 1–10
- [ ] `EvalOutput.model_validate({...})` raises `ValidationError` if `recommendations` has more than 5 items
- [ ] `EvalOutput.model_json_schema()` produces a valid JSON Schema dict

---

### TASK-402 · Implement `app/services/evidence_collector.py`

**Agent instruction:**
After receiving a validated `EvalOutput`, this service maps each analysis section back to the specific DB rows that support it.

```python
# app/services/evidence_collector.py
from uuid import UUID
from sqlalchemy.orm import Session
from app.schemas.eval_output import EvalOutput

def collect_evidence(eval_output: EvalOutput, week_id: UUID, db: Session) -> dict:
    """
    Returns a dict mapping claim categories to lists of DB record identifiers.
    Example output:
    {
      "nutrition": {
        "supporting_log_ids": ["uuid1", "uuid2", ...],
        "days_logged": 5,
        "days_in_week": 7,
        "coverage_pct": 71.4
      },
      "training": {
        "supporting_activity_ids": [123456, 789012],  # strava_ids
        "activity_types_found": ["Run", "WeightTraining"]
      },
      "measurements": {
        "measurement_id": "uuid",
        "fields_present": ["weight_kg", "waist_cm"]
      }
    }
    """
    # Query DailyLog rows for the week
    # Query StravaActivity rows for the week
    # Query WeeklyMeasurement for the week
    # Build and return the evidence map
    ...
```

**Acceptance criteria:**

- [ ] Returns a dict with keys `nutrition`, `training`, `measurements`
- [ ] `nutrition.coverage_pct` = (days with a log / 7) * 100
- [ ] `training.supporting_activity_ids` contains Strava integer IDs (not internal UUIDs)
- [ ] Function is synchronous

---

### TASK-403 · Write `app/prompts/system_prompt.txt`

**Agent instruction:**
Write the system prompt file with these exact sections. Do not truncate or paraphrase.

```
You are a supportive, data-driven fitness coach. Your role is to analyze a user's weekly fitness and nutrition data and produce a structured evaluation.

RESPONSE FORMAT:
You MUST respond ONLY with a valid JSON object. Do not include any text, explanation, or markdown outside the JSON. The JSON must conform exactly to this schema:
{
  "overall_score": <integer 1-10>,
  "summary": <string, 2-3 sentences>,
  "wins": [<string>, ...],
  "misses": [<string>, ...],
  "nutrition_analysis": {
    "avg_daily_calories": <float or null>,
    "avg_protein_g": <float or null>,
    "avg_adherence_score": <float or null>,
    "commentary": <string>
  },
  "training_analysis": {
    "total_run_km": <float or null>,
    "strength_sessions": <integer or null>,
    "total_active_minutes": <float or null>,
    "commentary": <string>
  },
  "recommendations": [
    { "area": <string>, "action": <string>, "priority": <integer 1-5> }
  ],
  "data_confidence": <float 0.0-1.0>
}

SAFETY CONSTRAINTS:
- You are NOT a medical professional.
- Do NOT provide medical diagnoses, suggest medications, or give advice about injuries beyond general rest and recovery guidance.
- If data suggests a potential health concern, acknowledge it supportively and recommend consulting a healthcare professional.

TONE & BEHAVIOR:
- Be encouraging and collaborative. Frame shortfalls as opportunities for improvement, not failures.
- Be specific: reference actual numbers from the data when making claims.
- Do not fabricate data. If a field is missing, reflect that uncertainty in data_confidence.
- Do not infer multi-week trends unless previous week data is explicitly provided.

DATA CONFIDENCE:
- Set data_confidence = 1.0 if all 7 daily logs are present and Strava is synced.
- Reduce by 0.1 for each missing daily log.
- Reduce by 0.2 if no Strava data is present.
- Minimum value is 0.0.
```

**Acceptance criteria:**

- [ ] File contains the phrase `"You MUST respond ONLY with a valid JSON object"`
- [ ] File contains safety constraint language about not being a medical professional
- [ ] File contains the `data_confidence` calculation rules
- [ ] File is plain text, no markdown formatting

---

## Phase 5 — API Endpoints & Repeatability

### TASK-501 · Implement `app/main.py`

**Agent instruction:**
Create the FastAPI application factory. Import and register all routers. Run `alembic upgrade head` on startup.

```python
# app/main.py
from fastapi import FastAPI
from app.api import auth, logs, strava, evaluate

app = FastAPI(title="Fitness Eval API", version="0.1.0")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(strava.router, prefix="/strava", tags=["strava"])
app.include_router(evaluate.router, prefix="/evaluate", tags=["evaluate"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Acceptance criteria:**
- [ ] `uv run uvicorn app.main:app --reload` starts without errors
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `GET /docs` renders the OpenAPI UI with all 4 route groups

---

### TASK-502 · Implement `app/api/logs.py`

**Agent instruction:**
Implement CRUD endpoints for manual data entry. Use `Depends(get_db)` for all database access.

| Method | Path | Logic |
|--------|------|-------|
| `POST` | `/logs/daily` | Upsert a `DailyLog` by `log_date`. Create `WeeklyMeasurement` for the week if it doesn't exist. |
| `GET` | `/logs/daily/{date}` | Return `DailyLog` for the date or 404. |
| `POST` | `/logs/weekly` | Upsert a `WeeklyMeasurement` by `week_start`. |
| `GET` | `/logs/weekly/{week_start}` | Return `WeeklyMeasurement` + all `DailyLog` rows for the week. |
| `POST` | `/logs/targets` | Insert a new `PlanTargets` row (never update — versioned). |

Request and response bodies must use Pydantic schemas from `app/schemas/log_schemas.py`.

**Acceptance criteria:**
- [ ] `POST /logs/daily` called twice with the same `log_date` updates the existing row, not inserts a duplicate
- [ ] `GET /logs/daily/{date}` returns HTTP 404 when no log exists for that date
- [ ] All endpoints return HTTP 422 on schema validation failure

---

### TASK-503 · Implement `app/api/strava.py`

**Agent instruction:**
Implement the Strava sync and listing endpoints.

| Method | Path | Logic |
|--------|------|-------|
| `POST` | `/strava/sync/{week_start}` | Resolve `week_start` to a `WeeklyMeasurement`, call `strava_service.sync_week_activities()`, return count of upserted activities. |
| `GET` | `/strava/activities/{week_start}` | Return list of `StravaActivity` rows for the week, excluding `raw_json` from the response. |

**Acceptance criteria:**
- [ ] `POST /strava/sync/{week_start}` returns `{"synced": <int>}` on success
- [ ] `GET /strava/activities/{week_start}` response never includes the `raw_json` field
- [ ] Both endpoints return HTTP 404 if `week_start` has no `WeeklyMeasurement` row

---

### TASK-504 · Implement `app/api/auth.py`

**Agent instruction:**
Implement the Strava OAuth2 callback flow.

| Method | Path | Logic |
|--------|------|-------|
| `GET` | `/auth/strava` | Call `strava_service.build_authorization_url()` and return `RedirectResponse`. |
| `GET` | `/auth/strava/callback` | Accept `code` query param. Call `strava_service.exchange_code(code)`. Return `{"status": "authorized"}`. |

**Acceptance criteria:**
- [ ] `GET /auth/strava` returns HTTP 302 with `Location` header pointing to `strava.com`
- [ ] `GET /auth/strava/callback?code=abc` calls `exchange_code` with `"abc"`
- [ ] Missing `code` query param returns HTTP 422

---

### TASK-505 · Implement `app/services/eval_service.py`

**Agent instruction:**
Implement the evaluation orchestrator. This is the core business logic that wires all services together with idempotency.

```python
# app/services/eval_service.py
async def run_evaluation(week_id: UUID, db: Session) -> dict:
    """
    1. Build the contract via prompt_engine.build_contract()
    2. Hash it via prompt_engine.hash_contract()
    3. Check weekly_evals for existing row with same week_id + input_hash
    4. If found: return parsed_output_json (cache hit — no LLM call)
    5. If not found:
       a. Call llm_client.generate_evaluation(contract)
       b. Parse and validate via EvalOutput.model_validate_json()
       c. Call evidence_collector.collect_evidence()
       d. Persist WeeklyEval row
       e. Return EvalOutput dict
    """
```

**Acceptance criteria:**

- [ ] Calling `run_evaluation` twice with the same `week_id` and unchanged data results in exactly 1 LLM call (second call returns cached result)
- [ ] If `EvalOutput.model_validate_json()` raises, the function raises HTTP 502 with a meaningful error (do not persist invalid LLM output)
- [ ] The persisted `WeeklyEval.input_hash` matches `hash_contract(contract)` exactly

---

### TASK-506 · Implement `app/api/evaluate.py`

**Agent instruction:**
Expose the evaluation service via REST endpoints.

| Method | Path | Logic |
|--------|------|-------|
| `POST` | `/evaluate/{week_id}` | Call `eval_service.run_evaluation(week_id, db)`. Returns `EvalOutput` JSON. |
| `GET` | `/evaluate/{week_id}` | Query `weekly_evals` for the most recent eval for `week_id`. Return 404 if none exists. |

```python
# app/api/evaluate.py
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.eval_service import run_evaluation
from app.models.weekly_eval import WeeklyEval

router = APIRouter()

@router.post("/{week_id}")
async def create_evaluation(week_id: UUID, db: Session = Depends(get_db)):
    try:
        result = await run_evaluation(week_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/{week_id}")
def get_evaluation(week_id: UUID, db: Session = Depends(get_db)):
    eval_row = db.query(WeeklyEval).filter(WeeklyEval.week_id == week_id).first()
    if not eval_row:
        raise HTTPException(status_code=404, detail="No evaluation found for this week")
    return eval_row.parsed_output_json
```

**Acceptance criteria:**

- [ ] `POST /evaluate/{week_id}` returns HTTP 404 if `week_id` has no `WeeklyMeasurement`
- [ ] `POST /evaluate/{week_id}` returns HTTP 502 if the LLM returns invalid JSON
- [ ] `GET /evaluate/{week_id}` returns the cached `parsed_output_json` without triggering a new LLM call
- [ ] Response schema matches `EvalOutput`

---

## End-to-End Smoke Test

### TASK-601 · Verify full pipeline

**Agent instruction:**
With the server running (`uv run uvicorn app.main:app --reload`), execute this sequence and verify each step:

```bash
# 1. Health check
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# 2. Set plan targets
curl -X POST http://localhost:8000/logs/targets \
  -H "Content-Type: application/json" \
  -d '{"effective_from": "2025-01-01", "target_calories": 2200, "target_protein_g": 180, "target_fasting_hrs": 16, "target_run_km_wk": 25, "target_strength_sessions": 3}'

# 3. Create weekly measurement
curl -X POST http://localhost:8000/logs/weekly \
  -H "Content-Type: application/json" \
  -d '{"week_start": "2025-01-06", "weight_kg": 84.5, "weight_prev_kg": 85.1}'

# 4. Log 3 daily entries
for date in "2025-01-06" "2025-01-07" "2025-01-08"; do
  curl -X POST http://localhost:8000/logs/daily \
    -H "Content-Type: application/json" \
    -d "{\"log_date\": \"$date\", \"calories_in\": 2150, \"protein_g\": 175, \"adherence_score\": 8, \"fasting_hours\": 16}"
done

# 5. Run evaluation (requires LM Studio running locally)
WEEK_ID=$(curl -s http://localhost:8000/logs/weekly/2025-01-06 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -X POST http://localhost:8000/evaluate/$WEEK_ID

# 6. Verify idempotency — second call should return identical result without LLM call
curl -X POST http://localhost:8000/evaluate/$WEEK_ID
```

**Acceptance criteria:**
- [ ] Steps 1–4 all return HTTP 200/201
- [ ] Step 5 returns a JSON body with keys: `overall_score`, `summary`, `wins`, `misses`, `recommendations`, `data_confidence`
- [ ] Step 6 returns the exact same `overall_score` and `summary` as Step 5
- [ ] Only 1 row exists in `weekly_evals` after both POST calls (verify with `sqlite3 fitness.db "SELECT COUNT(*) FROM weekly_evals"`)
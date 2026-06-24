# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Commands

**Start the full stack (Docker):**
```powershell
.\docker-run.ps1 -Command up        # Windows
./docker-run.sh up                  # Mac/Linux
```

**Run the app locally (without Docker):**
```bash
uv run uvicorn app.main:app --reload --port 8000
```

**Run all tests:**
```bash
uv run pytest
```

**Run a single test file:**
```bash
uv run pytest tests/test_chat_service.py -v
```

**Run a specific test:**
```bash
uv run pytest tests/test_chat_service.py::test_function_name -v
```

**Database migrations:**
```bash
uv run alembic upgrade head                          # Apply all migrations
uv run alembic revision --autogenerate -m "message"  # Generate new migration
```

**Install dependencies:**
```bash
uv sync
```

## Architecture Overview

**Stack:** FastAPI (Python 3.12) + SQLAlchemy + PostgreSQL/pgvector + Keycloak (auth) + Ollama/LM Studio (LLM) + SPA frontend

The app is an AI-powered fitness coaching platform. The backend serves a React SPA (catch-all route in `app/main.py` serves `public/index.html`), with all API routes under `/api/`.

### Layer Structure

```
app/api/        → FastAPI routers (thin: validate, call service, return)
app/services/   → Business logic (chat, evaluations, training plans, Strava sync)
app/ai/         → AI subsystem (skills, tools, context, retrieval, prompts)
app/models/     → SQLAlchemy ORM models
app/schemas/    → Pydantic request/response schemas
app/middleware/ → JWT auth middleware
```

### Authentication

`app/middleware/auth.py` — `get_current_athlete()` is the FastAPI dependency injected into protected endpoints. It validates Keycloak JWTs (RS256) by fetching the JWKS endpoint, then looks up the `Athlete` by `keycloak_sub`. Strava tokens are stored encrypted with Fernet (`STRAVA_ENCRYPTION_KEY`).

### AI Subsystem (`app/ai/`)

The AI subsystem has a clear internal hierarchy:

- **Skills** (`app/ai/skills/`) — Self-contained LLM capabilities (e.g., `TrainingPlanner`, `WorkoutAnalyzer`, `FitnessStateBuilder`). Each skill takes structured input, builds a context, calls the LLM, validates output against a contract, and returns structured output.
- **Context builder** (`app/ai/context/builder.py`) — Fluent builder for assembling LLM context: system instructions + task instructions + domain knowledge + retrieved data. Enforces token budgets (total ~2400 tokens, ~600 for retrieval).
- **RAG** (`app/ai/retrieval/`) — Intent-based retrieval. `RAGRetriever` classifies the query intent, applies policies from `retrieval_policies.yaml`, fetches data from the DB, and formats it as evidence cards.
- **Tools** (`app/ai/tools/`) — OpenAI-format function definitions callable by the LLM in a ReAct loop. Tool execution is orchestrated by `app/services/tool_orchestrator.py`.
- **Prompts** (`app/ai/prompts/`) — System and task prompts loaded from YAML files at runtime (`system/` and `tasks/` subdirectories).
- **Contracts** (`app/ai/contracts/`) — Pydantic schemas that validate LLM structured output before it's used.

### Chat Flow

1. `POST /api/chat/sessions/{id}/messages` → `ChatSessionService`
2. Service loads history, runs RAG retrieval (intent-classified), builds `Context`
3. `ChatService` invokes LLM; if it calls tools, `ToolOrchestrator` runs the ReAct loop (max iterations controlled by `CE_CHAT_MAX_TOOL_ITERATIONS`)
4. Response streamed back as SSE

Feature flags in config: `USE_CE_CHAT_RUNTIME`, `PILOT_ROLLOUT_ENABLED`, `LEGACY_CHAT_ENABLED`.

### Training Plan System

Plans are multi-table: `TrainingPlan` → `TrainingPlanWeek` → `TrainingPlanSession`. `PlanCoordinator` checks compatibility before saving new plans. `AdherenceCalculator` + `SessionMatcher` link Strava activities to scheduled sessions to compute compliance.

### Database

- PostgreSQL + pgvector (for `VectorEmbedding` table used in RAG)
- `get_db()` in `app/database.py` is the FastAPI dependency for DB sessions (pool_size=10, max_overflow=20)
- `TimestampMixin` on major models adds `created_at`/`updated_at`
- Migrations managed by Alembic (`alembic/versions/`)

### Key Config Properties (`app/config.py`)

Settings are loaded via Pydantic `BaseSettings` with `@lru_cache`. Computed properties derive `keycloak_issuer`, `keycloak_jwks_uri`, and `llm_base_url` from raw env vars. LLM provider is selected at runtime (Ollama vs LM Studio) based on which env vars are set.

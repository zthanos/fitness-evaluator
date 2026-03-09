# OpenAPI Documentation

## Interactive Documentation Endpoints

Once the server is running, you can access interactive API documentation:

### Swagger UI
**URL:** `http://localhost:8000/docs`

Full interactive API documentation with:
- Try-it-out functionality
- Request/response examples
- Schema validation
- Parameter documentation

### ReDoc
**URL:** `http://localhost:8000/redoc`

Alternative interactive documentation with:
- Clean, readable format
- Organized by tags
- Side-by-side code examples
- Search functionality

### OpenAPI Schema JSON
**URL:** `http://localhost:8000/openapi.json`

Raw OpenAPI 3.0 specification for:
- Code generation
- External tools
- Custom integrations
- CI/CD pipelines

## API Tags

The API is organized into 5 main categories:

### Health
- `GET /` — Root endpoint
- `GET /health` — Health check

### Auth
- `GET /auth/strava` — Initiate Strava OAuth flow
- `GET /auth/strava/callback` — Handle OAuth callback

### Logs
- Daily nutrition logs (create, retrieve, list)
- Weekly measurements (weight, body metrics, sleep, etc.)
- Plan targets (versioned goal tracking)

### Strava
- `POST /strava/sync/{week_start}` — Sync activities for a week
- `GET /strava/activities/{week_start}` — List week's activities
- `GET /strava/aggregates/{week_start}` — Get weekly totals

### Evaluate
- `POST /evaluate/{week_start}` — Generate or retrieve cached evaluation
- `GET /evaluate/{week_start}` — Retrieve evaluation without re-running
- `POST /evaluate/{week_start}/refresh` — Force re-evaluation

## Starting the Server

```bash
# Development with auto-reload
uv run uvicorn app.main:app --reload

# Production
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Quick Start

1. Visit `http://localhost:8000/docs` in browser
2. Expand an endpoint to see details
3. Click "Try it out" to make test requests
4. Fill in parameters and click "Execute"
5. View response and example code

## API Response Format

All endpoints return JSON with structured responses.

**Successful response (200):**
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

**Error response:**
```json
{
  "detail": "Description of the error"
}
```

## Example Workflow

1. Create daily log: `POST /logs/daily`
2. Create weekly measurement: `POST /logs/weekly`
3. Set plan targets: `POST /logs/targets`
4. Generate evaluation: `POST /evaluate/2025-01-06`
5. View evaluation: `GET /evaluate/2025-01-06`

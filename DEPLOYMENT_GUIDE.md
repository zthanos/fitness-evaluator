# Fitness Evaluator - Deployment & Launch Guide

## System Overview

The Fitness Evaluator is a full-stack application for weekly fitness analysis with AI-powered insights.

### Architecture
```
┌────────────────────────────────────────────────────┐
│          Web Browser (DaisyUI SPA)                 │
│  ├─ Dashboard, Forms, Evaluation Reports           │
│  └─ Vanilla JS + API Client                        │
└──────────────────┬─────────────────────────────────┘
                   │ HTTP/REST (localhost:8000)
┌──────────────────▼─────────────────────────────────┐
│          FastAPI Backend Server                    │
│  ├─ /api/logs/* (CRUD operations)                  │
│  ├─ /api/strava/* (OAuth + sync)                   │
│  ├─ /api/evaluate/* (LLM integration)              │
│  ├─ /api/auth/* (Strava OAuth)                     │
│  ├─ / (Static files - DaisyUI dashboard)          │
│  └─ /docs, /redoc (API documentation)             │
└──────────────────┬─────────────────────────────────┘
                   │ SQLAlchemy ORM
┌──────────────────▼─────────────────────────────────┐
│          SQLite Database                           │
│  ├─ daily_logs (nutrition, adherence)              │
│  ├─ weekly_measurements (body composition)         │
│  ├─ strava_activities (synced workouts)            │
│  ├─ plan_targets (weekly goals)                    │
│  └─ weekly_evals (AI analysis results)             │
└────────────────────────────────────────────────────┘
```

### External Integrations
- **Strava API**: OAuth2 for activity synchronization
- **LM Studio**: Local LLM endpoint for evaluation analysis
- **SQLite**: Embedded database (no external DB required)

## Prerequisites

### System Requirements
- Python 3.10+
- 2GB RAM minimum
- 500MB disk space
- Windows 10+, macOS 10.15+, or Linux (Ubuntu 20.04+)

### Software Dependencies
- UV (Python package manager)
- Alembic (database migrations)
- FastAPI 0.135+
- SQLAlchemy 2.0+

### External Services (Optional)
- **Strava Account** (for activity sync)
  - Create app at https://www.strava.com/settings/api
  - Get Client ID and Client Secret
  
- **LM Studio** (for AI evaluations)
  - Download from https://lmstudio.ai
  - Configure local endpoint (default: http://localhost:1234)

## Setup Instructions

### 1. Clone/Initialize Project

```bash
cd fitness-eval
```

### 2. Create Python Environment

```bash
# UV automatically creates and manages the environment
uv sync
```

### 3. Configure Environment Variables

Create `.env` file in project root:

```env
# Strava OAuth
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REDIRECT_URI=http://localhost:8000/api/auth/strava/callback

# LM Studio
LM_STUDIO_ENDPOINT=http://localhost:1234/v1
LM_STUDIO_MODEL=local-model

# Database (auto-created as fitness_eval.db)
DATABASE_URL=sqlite:///./fitness_eval.db

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
```

### 4. Initialize Database

```bash
# Create tables and run migrations
uv run alembic upgrade head
```

This creates:
- `fitness_eval.db` (SQLite database)
- All required tables with proper relationships

### 5. Start LM Studio (if using AI features)

```bash
# In a separate terminal/window
# 1. Download and launch LM Studio from https://lmstudio.ai
# 2. Download a model (e.g., Mistral 7B)
# 3. Start the server (default: http://localhost:1234)
# 4. Keep it running while the fitness app is active
```

### 6. Start FastAPI Server

```bash
# Development mode (with hot reload)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or production mode (no reload, single worker)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7. Access the Application

Open your browser and navigate to:

| Component | URL |
|-----------|-----|
| **Dashboard** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **API Docs (ReDoc)** | http://localhost:8000/redoc |
| **Health Check** | http://localhost:8000/health |

## File Structure

```
fitness-eval/
├── README.md                          # Project overview
├── FRONTEND_GUIDE.md                  # Frontend documentation
├── DEPLOYMENT_GUIDE.md                # This file
├── pyproject.toml                     # Python dependencies
├── alembic.ini                        # Database migration config
├── .env                               # Environment variables (create)
├── fitness_eval.db                    # SQLite database (auto-created)
├── main.py                            # Application entry point
│
├── app/
│   ├── main.py                        # FastAPI factory & static files
│   ├── config.py                      # Configuration & settings
│   ├── database.py                    # SQLAlchemy setup
│   ├── models/                        # ORM models
│   │   ├── base.py                    # Base model + timestamp mixin
│   │   ├── daily_log.py               # Daily logging model
│   │   ├── weekly_measurement.py      # Weekly metrics model
│   │   ├── strava_activity.py         # Strava sync model
│   │   ├── plan_targets.py            # Goals model
│   │   └── weekly_eval.py             # Evaluation results model
│   ├── schemas/                       # Pydantic validation
│   │   ├── log_schemas.py             # Log request/response schemas
│   │   └── eval_output.py             # Evaluation output schema
│   ├── services/                      # Business logic
│   │   ├── llm_client.py              # LM Studio integration
│   │   ├── prompt_engine.py           # Prompt templates & contracts
│   │   ├── eval_service.py            # Evaluation orchestration
│   │   ├── evidence_collector.py      # Data aggregation
│   │   └── strava_service.py          # Strava API client
│   ├── api/                           # API endpoints
│   │   ├── auth.py                    # Strava OAuth endpoints
│   │   ├── logs.py                    # CRUD for logs/measurements/targets
│   │   ├── strava.py                  # Strava sync endpoints
│   │   ├── evaluate.py                # Evaluation endpoints
│   │   └── v1/                        # API versioning (future)
│   └── prompts/
│       └── system_prompt.txt          # LLM system prompt
│
├── alembic/                           # Database migrations
│   ├── env.py                         # Migration configuration
│   ├── versions/
│   │   └── 001_initial_fitness_models_sqlite.py
│   └── script.py.mako                 # Migration template
│
├── public/                            # Static files (web UI)
│   ├── index.html                     # Dashboard landing page
│   ├── logs.html                      # Daily logging form
│   ├── measurements.html              # Weekly measurements form
│   ├── targets.html                   # Plan targets management
│   ├── evaluation.html                # Evaluation results page
│   ├── js/
│   │   ├── api.js                     # REST API client (~4KB)
│   │   └── utils.js                   # UI utilities (~3KB)
│   └── css/                           # Custom styles (optional)
│
├── specs/                             # Documentation
│   ├── plan.md                        # Feature specification
│   └── tasks.md                       # Task breakdown
│
├── tests/                             # Test files (future)
│   └── __init__.py
│
└── .gitignore                         # Git ignore rules
```

## Common Operations

### Daily Workflow

**Morning - Set Weekly Plan**:
```bash
# 1. Start server
uv run uvicorn app.main:app --reload

# 2. Open http://localhost:8000
# 3. Navigate to "Plan Targets"
# 4. Create goals for the week (calories, sleep, workouts, etc.)
```

**Daily - Log Data**:
```
# Open http://localhost:8000
# Click "Daily Logs"
# Fill in today's nutrition, adherence, sleep, energy
# Save entry
```

**Weekly - Record Measurements**:
```
# Every Sunday - go to "Measurements"
# Record weight, body fat, measurements
# Save for the week
```

**Weekly - Sync Strava**:
```
# Open Dashboard
# Click "Sync Activities" button
# Activities from Strava appear automatically
```

**Weekly - Get Evaluation**:
```
# Click "Generate Evaluation" button
# Select week to evaluate
# View AI-powered analysis and recommendations
```

### Database Management

```bash
# View database contents
uv run python -c "
from app.database import SessionLocal
from app.models import daily_log

db = SessionLocal()
logs = db.query(daily_log.DailyLog).all()
for log in logs:
    print(f'{log.log_date}: {log.calories_in} cal')
"

# Reset database (DELETE ALL DATA)
rm fitness_eval.db
uv run alembic upgrade head

# Create backup
cp fitness_eval.db fitness_eval.backup.$(date +%Y%m%d).db
```

### Troubleshooting

#### Issue: ModuleNotFoundError: No module named 'fastapi'
**Solution**:
```bash
# Reinstall dependencies
uv sync
```

#### Issue: API returns Connection refused on :1234
**Solution**:
```bash
# Make sure LM Studio is running
# 1. If offline evaluation not needed - skip LM Studio
# 2. Check LM Studio is listening on localhost:1234
# 3. Update `.env` with correct endpoint
```

#### Issue: Strava OAuth fails
**Solution**:
```bash
# 1. Check STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env
# 2. Verify redirect URI matches Strava app settings
# 3. Check network connectivity to strava.com
```

#### Issue: Database locked error
**Solution**:
```bash
# Close other processes using the database
# Or delete and recreate (loses all data)
rm fitness_eval.db
uv run alembic upgrade head
```

#### Issue: Port 8000 already in use
**Solution**:
```bash
# Use different port
uv run uvicorn app.main:app --port 8001

# Or find and kill process
# Windows: netstat -ano | findstr :8000
# Linux/Mac: lsof -i :8000
```

## Production Deployment

### Docker Deployment (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install uv && uv sync --frozen
COPY . .
RUN uv run alembic upgrade head
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t fitness-eval .
docker run -p 8000:8000 -v fitness-eval-data:/app/data fitness-eval
```

### Cloud Deployment (AWS/GCP/Azure)

#### Option 1: Heroku
```bash
heroku login
heroku create fitness-eval-app
git push heroku main
```

#### Option 2: Railway
```bash
railway login
railway link
railway up
```

#### Option 3: DigitalOcean App Platform
1. Create DigitalOcean account
2. Connect GitHub repo
3. Set environment variables in dashboard
4. Deploy

### SSL/TLS Configuration

For HTTPS in production:
```bash
# Using Caddy reverse proxy (recommended)
# Create Caddyfile:
# fitness-eval.example.com {
#     reverse_proxy localhost:8000
# }

caddy start
```

Or use Let's Encrypt with nginx:
```bash
sudo certbot certonly --standalone -d fitness-eval.example.com
# Configure nginx to proxy to localhost:8000
```

## Monitoring & Maintenance

### Health Checks

```bash
# Simple health check
curl http://localhost:8000/health

# Detailed API status
curl http://localhost:8000/docs

# Database integrity check
uv run python -c "
from app.database import engine
with engine.connect() as conn:
    result = conn.execute('SELECT COUNT(*) FROM daily_logs')
    print(f'Daily logs: {result.scalar()}')
"
```

### Log Files

Logs are printed to console. For persistent logging:

```bash
# Redirect to file
uv run uvicorn app.main:app --log-level info > app.log 2>&1 &

# Monitor in real-time
tail -f app.log
```

### Performance Optimization

```bash
# Use production mode (no reload, single worker)
uv run uvicorn app.main:app --workers 1

# For high traffic, scale workers
uv run uvicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## Backup & Recovery

### Automated Backups

```bash
# Create backup script (backup.sh)
#!/bin/bash
BACKUP_DIR="backups"
mkdir -p $BACKUP_DIR
cp fitness_eval.db $BACKUP_DIR/fitness_eval.$(date +%Y%m%d-%H%M%S).db

# Schedule with cron (Linux/Mac)
0 2 * * * /path/to/backup.sh
```

### Restore from Backup

```bash
# Stop the server
# Restore file
cp backups/fitness_eval.20241216-020000.db fitness_eval.db
# Restart server
uv run uvicorn app.main:app --reload
```

## Security Best Practices

1. **Environment Variables**: Never commit `.env` file to Git
2. **Database**: Use strong passwords if migrating to PostgreSQL
3. **CORS**: Restrict `allow_origins` in production
4. **API Keys**: Rotate Strava client secrets regularly
5. **HTTPS**: Enable SSL/TLS for all production instances
6. **Input Validation**: All inputs are validated via Pydantic
7. **SQL Injection**: SQLAlchemy ORM prevents SQL injection

## Support & Documentation

- **API Reference**: http://localhost:8000/docs
- **Frontend Guide**: See `FRONTEND_GUIDE.md`
- **Feature Specs**: See `specs/plan.md`
- **Issue Tracking**: GitHub Issues

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-12 | Initial release with dashboard, forms, and AI evaluation |

## License

See LICENSE file for details.

---

**Last Updated**: 2024-12  
**Maintainer**: Fitness Evaluator Team  
**Status**: Ready for Production

# 💪 Fitness Evaluator

**AI-powered fitness analysis system with automatic weekly evaluations, Strava integration, and nutrition tracking.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.135+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker Ready](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Quick Start (Docker) ⚡

Get running in 5 minutes with Docker Compose (recommended):

### Windows
```powershell
cp .env.example .env
.\docker-run.ps1 -Command up
```

### Mac/Linux
```bash
cp .env.example .env
chmod +x docker-run.sh
./docker-run.sh up
```

Then open **http://localhost:8000** in your browser.

See [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for complete Docker documentation.

## Traditional Setup (No Docker)

If you prefer to run without Docker:

```bash
# Create environment
uv sync

# Configure
cp .env.example .env
# Edit .env with your settings

# Initialize database
uv run alembic upgrade head

# Start server
uv run uvicorn app.main:app --reload
```

Visit http://localhost:8000

## Features 🎯

### 📊 Dashboard
- Weekly overview and statistics
- Quick access to all major features
- Recent activity timeline
- Score tracking

### 📝 Daily Logging
- Nutrition tracking (calories, macros)
- Adherence scoring (1-10 scale)
- Sleep and energy levels
- Notes and observations

### 📈 Weekly Measurements
- Body composition (weight, body fat %)
- Circumference measurements
- Recovery metrics (HR, sleep quality)
- Progress visualization

### 🎯 Plan Targets
- Category-based goal setting (Nutrition, Training, Recovery, etc.)
- Min/max range definitions
- Goal tracking and progress

### 🤖 AI Evaluations
- **Weekly Analysis** powered by local Ollama LLM
- Categor-specific scoring
- Personalized recommendations
- Evidence-backed insights
- Full evaluation history

### ⚡ Strava Integration
- OAuth2 authentication
- Automatic activity sync
- Workout aggregation
- Performance metrics

## Architecture 🏗️

```
Web UI (DaisyUI)
    ↓
FastAPI REST API (Dockerized)
    ↓
SQLite Database (Persistent Volume)

External Services:
• Ollama LLM (Docker) - Local AI analysis
• Strava API (Optional) - Activity sync
```

**Zero external vendor lock-in** - everything runs locally!

## Documentation 📚

| Document | Purpose |
|----------|---------|
| [DOCKER_GUIDE.md](DOCKER_GUIDE.md) | **START HERE** - Docker setup and commands |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Production deployment options |
| [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) | Web UI documentation |
| [specs/plan.md](specs/plan.md) | Feature specification |

## Tech Stack 🛠️

### Backend
- **FastAPI** 0.135+ - Modern async API framework
- **SQLAlchemy** 2.0 - ORM with UUID support
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **Ollama** - Local LLM inference

### Frontend
- **DaisyUI** - Tailwind CSS component library
- **Vanilla JavaScript** - ES6 modules
- **Fetch API** - HTTP client
- **Responsive Design** - Mobile-friendly

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Orchestration
- **SQLite** - Embedded database
- **GitHub Actions** - CI/CD ready

## API Endpoints 🔌

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/logs/daily` | Create daily log |
| `GET` | `/api/logs/daily` | List daily logs |
| `POST` | `/api/logs/measurements` | Record measurements |
| `GET` | `/api/logs/measurements` | List measurements |
| `POST` | `/api/logs/targets` | Create plan targets |
| `GET` | `/api/logs/targets` | List targets |
| `GET` | `/api/strava/sync` | Sync Strava activities |
| `POST` | `/api/evaluate/{week}` | Generate evaluation |
| `GET` | `/api/evaluate/{week}` | Get evaluation |

Full API documentation at http://localhost:8000/docs (Swagger UI)

## Environment Variables 🔐

Copy `.env.example` to `.env` and configure:

```env
# Database
DATABASE_URL=sqlite:///./data/fitness_eval.db

# LLM (Ollama via Docker)
LLM_TYPE=ollama
LM_STUDIO_ENDPOINT=http://ollama:11434/api
LM_STUDIO_MODEL=mistral

# Strava (optional)
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret

# API
API_HOST=0.0.0.0
API_PORT=8000
```

## Database Schema 🗂️

| Table | Purpose |
|-------|---------|
| `daily_logs` | Nutrition, adherence, sleep, energy |
| `weekly_measurements` | Weight, body fat, measurements |
| `strava_activities` | Synced workouts and activities |
| `plan_targets` | Weekly goals and targets |
| `weekly_evals` | AI evaluation results |

All tables include `created_at` and `updated_at` timestamps.

## Development 👨‍💻

### Local development (without Docker):
```bash
# Install dependencies
uv sync

# Setup database
uv run alembic upgrade head

# Run with hot-reload
uv run uvicorn app.main:app --reload
```

### Docker development:
```bash
# Changes to code are reflected automatically
docker-compose exec app /bin/bash
```

### Running tests:
```bash
docker-compose exec app uv run pytest tests/
```

## Deployment 🚀

### Quick cloud deployment:

**Heroku:**
```bash
heroku login
heroku create fitness-eval-app
git push heroku main
```

**Docker:**
```bash
docker build -t fitness-eval .
docker run -p 8000:8000 fitness-eval
```

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete production setup.

## Troubleshooting 🔧

### Port already in use
```bash
# Change port in docker-compose.yml or
.\docker-run.ps1 -Command logs app
```

### LLM service not starting
```bash
# Check logs
docker-compose logs ollama

# Rebuild
docker-compose down -v
./docker-run.sh up
```

### Database issues
```bash
# Backup and reset
./docker-run.sh backup
./docker-run.sh db-reset
```

### More help
See [DOCKER_GUIDE.md](DOCKER_GUIDE.md) troubleshooting section.

## File Structure 📋

```
fitness-eval/
├── README.md                      # This file
├── DOCKER_GUIDE.md               # Docker documentation
├── DEPLOYMENT_GUIDE.md           # Production guide
├── docker-compose.yml            # Docker services
├── Dockerfile                    # App container image
├── docker-run.ps1               # Windows helper script
├── docker-run.sh                # Mac/Linux helper script
├── .env.example                 # Configuration template
├── pyproject.toml               # Python dependencies
├── alembic.ini                  # Database migrations
│
├── app/
│   ├── main.py                  # FastAPI app factory
│   ├── config.py                # Configuration
│   ├── database.py              # SQLAlchemy setup
│   ├── models/                  # ORM models
│   ├── schemas/                 # Pydantic schemas
│   ├── services/                # Business logic
│   ├── api/                     # API endpoints
│   └── prompts/                 # LLM prompts
│
├── public/                      # Web UI
│   ├── index.html              # Dashboard
│   ├── logs.html               # Daily logging
│   ├── measurements.html       # Weekly metrics
│   ├── targets.html            # Plan targets
│   ├── evaluation.html         # Results display
│   └── js/
│       ├── api.js              # API client
│       └── utils.js            # UI utilities
│
└── specs/                       # Documentation
    ├── plan.md                 # Feature spec
    └── tasks.md                # Task breakdown
```

## Contributing 🤝

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License 📄

MIT License - See [LICENSE](LICENSE) file

## Support 💬

- **Documentation**: See files above
- **Issues**: GitHub Issues (coming soon)
- **Discussions**: GitHub Discussions (coming soon)

---

**Built with ❤️ using FastAPI, Ollama, and vanilla JavaScript**

**Last Updated**: 2024-12 | **Status**: Production Ready ✅

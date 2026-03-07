# Docker & Ollama Integration Summary

## Overview

The Fitness Evaluator now supports **Docker Compose with Ollama LLM**, eliminating the need for LM Studio and making deployment significantly simpler and more portable.

## What Was Added

### 1. Core Docker Files

| File | Purpose |
|------|---------|
| **docker-compose.yml** | Orchestrates FastAPI + Ollama services with volumes & networking |
| **Dockerfile** | FastAPI container with Python dependencies and health checks |
| **.dockerignore** | Optimizes Docker build by excluding unnecessary files |

### 2. Helper Scripts

| Script | Platform | Purpose |
|--------|----------|---------|
| **docker-run.sh** | Mac/Linux | Bash helper with commands: up, down, logs, backup, etc. |
| **docker-run.ps1** | Windows | PowerShell helper with same commands |

### 3. Documentation

| Document | Purpose |
|----------|---------|
| **QUICK_START.md** | 5-minute setup guide (new users start here) |
| **DOCKER_GUIDE.md** | Comprehensive Docker documentation (500+ lines) |
| **README.md** | Updated with Docker-first approach |
| **.env.example** | Configuration template with Ollama settings |

### 4. Code Updates

| File | Changes |
|------|---------|
| **app/config.py** | Added LLM_TYPE, Ollama endpoint support, backward compatibility |
| **app/services/llm_client.py** | Updated to handle both LM Studio and Ollama endpoints |
| **.gitignore** | Added Docker, .env, database, and data volume exclusions |

### 5. Verification Script

| File | Purpose |
|------|---------|
| **verify-docker-setup.py** | Checks Docker installation and required files |

## Key Features

### Docker Compose Architecture
```
ollama:11434 ─┐
              ├─→ fitness-network ─→ Browser (localhost:8000)
app:8000 ─────┘   (internal DNS)
```

- **Services**: FastAPI + Ollama
- **Volumes**: Model cache + SQLite persistence
- **Health Checks**: Automatic service monitoring
- **Networking**: Internal Docker network (no port conflicts)

### Ollama LLM Support
- **Default Model**: Mistral 7B (4GB, good balance)
- **Quick Switch**: `./docker-run.sh model-pull neural-chat`
- **No API Keys**: Everything runs locally
- **Auto Download**: First run pulls model automatically

### Environment Variable Configuration
```env
LLM_TYPE=ollama                          # Switch between 'ollama' or 'lm-studio'
LM_STUDIO_ENDPOINT=http://ollama:11434  # Ollama endpoint (Docker)
LM_STUDIO_MODEL=mistral                 # Model selection

# Backward compatible with LM Studio:
# LLM_TYPE=lm-studio
# LM_STUDIO_ENDPOINT=http://localhost:1234/v1
```

## Usage Examples

### Quick Start (< 5 minutes)
```bash
cp .env.example .env
./docker-run.sh up
# Visit http://localhost:8000
```

### View Logs
```bash
./docker-run.sh logs app      # FastAPI logs
./docker-run.sh logs ollama   # Ollama logs
./docker-run.sh logs          # All services
```

### Database Operations
```bash
./docker-run.sh backup        # Backup database
./docker-run.sh db-reset      # Delete all data
```

### Model Management
```bash
./docker-run.sh model-list    # Show available models
./docker-run.sh model-pull neural-chat  # Download different model
```

### Container Management
```bash
./docker-run.sh ps            # Show container status
./docker-run.sh restart       # Restart services
./docker-run.sh clean         # Remove containers & volumes
```

## Windows PowerShell Usage

```powershell
# All commands are similar but use PowerShell syntax:
.\docker-run.ps1 -Command up
.\docker-run.ps1 -Command logs -Args app
.\docker-run.ps1 -Command db-reset
```

## Configuration Files

### .env.example
Now includes:
- `LLM_TYPE=ollama` (new)
- `LM_STUDIO_ENDPOINT=http://ollama:11434/api` (Ollama endpoint)
- All existing Strava and API settings

### docker-compose.yml
Services:
- **ollama** (port 11434)
  - Persistent volume for models
  - Health checks
  - Auto-restart

- **app** (port 8000)
  - FastAPI service
  - Database volume
  - Depends on Ollama health
  - Code hot-reload support

## Backward Compatibility

**Still works with LM Studio!** To use local LM Studio instead of Ollama:

```env
LLM_TYPE=lm-studio
LM_STUDIO_ENDPOINT=http://localhost:1234/v1
```

Or run without Docker:
```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## System Requirements (Docker)

| Resource | Minimum | Recommended |
|----------|---------|------------|
| Disk | 10GB | 20GB+ |
| RAM | 4GB | 8GB+ |
| CPU | 2 cores | 4+ cores |
| Network | 2 Mbps | 10+ Mbps |

First run downloads ~4GB (Mistral model) - subsequent runs are instant.

## Security Considerations

1. **Sensitive Data**:
   - `.env` excluded from Git (in .gitignore)
   - Database stored in Docker volume, not committed
   - Strava secrets stay local

2. **Network**:
   - Internal Docker network (no external port exposure except 8000)
   - Ollama port (11434) exposed only within container
   - Use reverse proxy (nginx/Caddy) for HTTPS in production

3. **Data Persistence**:
   - SQLite database in volume `./data/`
   - Ollama models in volume `ollama-data`
   - Both survive container restarts

## Development Workflow

1. **Code Changes**: Automatically reflected (mounted volumes)
2. **Hot Reload**: Enabled in development
3. **Database**: Persisted between restarts
4. **Easy Reset**: `./docker-run.sh db-reset`

## Production Deployment

### Option 1: Docker Compose
```bash
docker-compose -f docker-compose.yml up -d
```

### Option 2: Cloud Platforms
See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:
- Heroku
- AWS ECS
- DigitalOcean App Platform
- Generic VPS

## Troubleshooting

### "docker: command not found"
→ Install Docker Desktop from https://www.docker.com

### "Port 8000 already in use"
→ Edit docker-compose.yml: `"8001:8000"` or stop conflicting service

### "Ollama stuck downloading"
→ Check logs: `./docker-run.sh logs ollama`
→ First run can take 5-10 minutes for model download

### "Database locked"
→ Reset: `./docker-run.sh db-reset`

### "LLM not responding"
→ Check health: `./docker-run.sh health`
→ Restart: `./docker-run.sh restart`

## File Sizes (First Run)

| Component | Size | Notes |
|-----------|------|-------|
| Docker images | 2-3GB | Downloaded once |
| Mistral model | 4GB | Downloaded on first Ollama run |
| SQLite (empty) | <10MB | Grows with data |
| **Total** | ~6-7GB | Subsequent runs only use running space |

## Benefits Over LM Studio

| Feature | Ollama Docker | LM Studio |
|---------|---------------|-----------|
| **Installation** | Docker Desktop only | Download separate app |
| **Portability** | Works on all systems | Platform specific |
| **Model Management** | CLI commands | GUI interface |
| **Memory Efficient** | Lighter than desktop app | Heavier |
| **Updates** | Docker image based | Manual updates |
| **Production Ready** | Yes (containerized) | Less suitable |
| **API Compatible** | Yes (OpenAI format) | Yes |

## Next Steps

1. **Read**: [QUICK_START.md](QUICK_START.md) (5-minute guide)
2. **Run**: `./docker-run.sh up`
3. **Explore**: http://localhost:8000
4. **Reference**: [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for all commands

## Support

- **Quick Issues**: See [QUICK_START.md](QUICK_START.md#troubleshooting)
- **Detailed Help**: See [DOCKER_GUIDE.md](DOCKER_GUIDE.md#troubleshooting)
- **Production**: See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

**Docker integration completed successfully! 🐳🚀**

The Fitness Evaluator is now:
- ✅ Fully containerized
- ✅ One-command startup (./docker-run.sh up)
- ✅ Zero dependency on LM Studio
- ✅ Production-ready deployment
- ✅ Local-only processing (no cloud required)

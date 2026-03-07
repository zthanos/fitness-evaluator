# Docker Setup Guide - Fitness Evaluator

## Overview

The Fitness Evaluator is now fully containerized with **Docker Compose**, making it easy to run with zero system dependencies beyond Docker.

### What's Included

- **FastAPI Backend** - Containerized Python application
- **Ollama LLM** - Local LLM service (no external API calls)
- **SQLite Database** - Persistent volume for data
- **Health Checks** - Automatic service monitoring
- **Helper Scripts** - Easy commands for common operations

## Prerequisites

### Required
- **Docker Desktop** (v4.0+)
  - Windows: Download from https://www.docker.com/products/docker-desktop
  - Mac: Download from https://www.docker.com/products/docker-desktop
  - Linux: Follow https://docs.docker.com/engine/install/
  
- **Docker Compose** (v2.0+) - included with Docker Desktop

### System Requirements
- **Disk Space**: 10-15GB (for Docker images and Ollama models)
- **RAM**: 4GB minimum, 8GB+ recommended
- **CPU**: Multi-core processor
- **Network**: Internet connection for initial image pull

## Quick Start (5 minutes)

### 1. Setup Configuration

```bash
cd fitness-eval

# Copy example env to .env
cp .env.example .env

# Edit .env with your Strava credentials (OPTIONAL)
# If you skip this, the app still works without Strava sync
```

### 2. Start Everything (Windows)

```powershell
# Windows - PowerShell
.\docker-run.ps1 -Command up
```

### 2. Start Everything (Mac/Linux)

```bash
# Mac/Linux - Bash
chmod +x docker-run.sh
./docker-run.sh up
```

### 3. Access the Application

Open your browser:
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

That's it! The LLM (Mistral model) will download automatically on first run (~4GB).

## Commands Reference

### Windows (PowerShell)

```powershell
# Start services
.\docker-run.ps1 -Command up

# Stop services
.\docker-run.ps1 -Command down

# View logs (all services)
.\docker-run.ps1 -Command logs

# View specific service logs
.\docker-run.ps1 -Command logs -Args app
.\docker-run.ps1 -Command logs -Args ollama

# Restart services
.\docker-run.ps1 -Command restart

# Check service status
.\docker-run.ps1 -Command ps

# Check service health
.\docker-run.ps1 -Command health

# Database backup
.\docker-run.ps1 -Command backup

# Database reset (DELETE ALL DATA)
.\docker-run.ps1 -Command db-reset

# Cleanup (remove containers and volumes)
.\docker-run.ps1 -Command clean

# List available Ollama models
.\docker-run.ps1 -Command model-list

# Download different model
.\docker-run.ps1 -Command model-pull -Args neural-chat
```

### Mac/Linux (Bash)

```bash
# Start services
./docker-run.sh up

# Stop services
./docker-run.sh down

# View logs (all services)
./docker-run.sh logs

# View specific service logs
./docker-run.sh logs app
./docker-run.sh logs ollama

# Restart services
./docker-run.sh restart

# Check service status
./docker-run.sh ps

# Check service health
./docker-run.sh health

# Database backup
./docker-run.sh backup

# Database reset (DELETE ALL DATA)
./docker-run.sh db-reset

# Cleanup (remove containers and volumes)
./docker-run.sh clean

# List available Ollama models
./docker-run.sh model-list

# Download different model
./docker-run.sh model-pull neural-chat
```

## Manual Docker Commands

If you prefer to run Docker commands directly:

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View all logs
docker-compose logs -f

# View app logs only
docker-compose logs -f app

# View Ollama logs only
docker-compose logs -f ollama

# Restart a service
docker-compose restart app

# Enter app container shell
docker-compose exec app /bin/bash

# Run database migrations manually
docker-compose exec app uv run alembic upgrade head

# Check if services are healthy
docker-compose ps
```

## Configuration

### Environment Variables (.env)

Key variables in your `.env` file:

```env
# Database location inside container
DATABASE_URL=sqlite:///./data/fitness_eval.db

# LLM Configuration
LLM_TYPE=ollama
LM_STUDIO_ENDPOINT=http://ollama:11434/api
LM_STUDIO_MODEL=mistral

# Strava OAuth (optional)
STRAVA_CLIENT_ID=your_id
STRAVA_CLIENT_SECRET=your_secret

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
```

### Switching LLM Models

Ollama supports many models. To use a different one:

```bash
# Download a model
./docker-run.sh model-pull neural-chat

# Update .env
LM_STUDIO_MODEL=neural-chat

# Restart services
./docker-run.sh restart
```

Available models:
- **mistral** (default, 7B, ~4GB) - Good balance
- **neural-chat** (7B, ~4GB) - Good for chat
- **dolphin-phi** (2.7B, ~2GB) - Lightweight
- **llama2** (7B, ~4GB) - Good reasoning
- **openchat** (3.5B, ~2GB) - Fast, lightweight
- **vicuna** (7B, ~4GB) - General purpose

## Architecture

```
┌─────────────────────────────────────────┐
│  Docker Host (your machine)             │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ Docker Network: fitness-network  │  │
│  │                                  │  │
│  │ ┌──────────────────────────────┐ │  │
│  │ │   FastAPI (port 8000)        │ │  │
│  │ │   ✓ /api/* endpoints         │ │  │
│  │ │   ✓ Static files (dashboard) │ │  │
│  │ │   ✓ Health checks            │ │  │
│  │ └──────────────────────────────┘ │  │
│  │              ↓                    │  │
│  │ ┌──────────────────────────────┐ │  │
│  │ │   Ollama (port 11434)        │ │  │
│  │ │   ✓ LLM service              │ │  │
│  │ │   ✓ Model management         │ │  │
│  │ │   ✓ Chat completions API     │ │  │
│  │ └──────────────────────────────┘ │  │
│  │              ↕                    │  │
│  │ ┌──────────────────────────────┐ │  │
│  │ │   SQLite (in volume)         │ │  │
│  │ │   ✓ Persistent data          │ │  │
│  │ │   ✓ Connected to app         │ │  │
│  │ └──────────────────────────────┘ │  │
│  └──────────────────────────────────┘  │
│         Browser (http://localhost:8000)│
└─────────────────────────────────────────┘
```

## Volumes & Persistence

Docker Compose creates two volumes:

```
ollama-data/
  └─ Storage for Ollama models (~4-8GB)

./data/
  └─ SQLite database (fitness_eval.db)
```

Both survive container restarts and removals (unless using `clean` command).

## Troubleshooting

### Issue: "docker: command not found"
**Solution**: Install Docker Desktop from https://www.docker.com/products/docker-desktop

### Issue: Port 8000 or 11434 already in use
**Solution**: Stop the service using that port or change in `docker-compose.yml`

```yaml
# In docker-compose.yml
services:
  app:
    ports:
      - "8001:8000"  # Change 8000 to 8001
  ollama:
    ports:
      - "11435:11434"  # Change 11434 to 11435
```

### Issue: Containers stop immediately after starting
**Check logs**:
```bash
docker-compose logs app
docker-compose logs ollama
```

### Issue: "No space left on device"
**Solution**: Clean up Docker
```bash
docker system prune -a
# Or specifically
./docker-run.sh clean
```

### Issue: LLM service not responding
**Check health**:
```bash
./docker-run.sh health

# Or manually
curl http://localhost:11434/api/tags
```

**Solution**: 
- Wait for Ollama to finish downloading model (check logs)
- Restart: `./docker-run.sh restart`

### Issue: Database locked error
**Solution**:
```bash
./docker-run.sh db-reset
# Or if that fails
docker-compose down -v
./docker-run.sh up
```

### Issue: Strava OAuth not working in Docker
**Solution**: Make sure `STRAVA_REDIRECT_URI` in `.env` matches your setup
```env
STRAVA_REDIRECT_URI=http://localhost:8000/api/auth/strava/callback
```

## Performance Tips

### For slower machines (< 8GB RAM):
```bash
# Use lightweight model
./docker-run.sh model-pull dolphin-phi

# Update .env
LM_STUDIO_MODEL=dolphin-phi

./docker-run.sh restart
```

### For faster machines (16GB+ RAM):
```bash
# Use larger model
./docker-run.sh model-pull llama2-uncensored

# Update .env
LM_STUDIO_MODEL=llama2-uncensored

./docker-run.sh restart
```

### Monitor resource usage:
```bash
docker stats

# Watch output, press Ctrl+C to exit
```

## Development Workflow

### Running tests locally (without Docker):
```bash
# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Run app
uv run uvicorn app.main:app --reload
```

### Running tests in Docker:
```bash
docker-compose exec app \
  uv run pytest tests/
```

### Making code changes with hot-reload:
The Docker image has code mounted as volume:
```yaml
volumes:
  - ./app:/app/app        # Changes reflected live
  - ./public:/app/public  # Changes reflected live
```

Just save your changes, the app will reload automatically (in development mode).

## Production Deployment

### Build production image:
```bash
docker-compose -f docker-compose.prod.yml build
```

### Deploy to cloud:
See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:
- Heroku deployment
- AWS ECS deployment
- DigitalOcean App Platform
- Generic server deployment

## Security Notes

1. **Never commit `.env` to Git** - Add to `.gitignore`
2. **Change `SECRET_KEY` in production** - See config.py
3. **Restrict ports in production** - Don't expose 11434
4. **Use HTTPS** - Add reverse proxy (nginx, Caddy)
5. **Regular backups** - Use `./docker-run.sh backup`

## Advanced: Custom docker-compose.yml

For production, create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  app:
    image: fitness-eval:latest
    environment:
      ENVIRONMENT: production
      LM_STUDIO_MODEL: dolphin-phi  # Lighter model for production
    restart: always
    # Don't expose ports directly, use reverse proxy
    
  ollama:
    # Disable if using external LLM
    # Or increase resource limits
    deploy:
      resources:
        limits:
          memory: 4G
```

Run with:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Support

- **Issues**: Check Docker logs with `./docker-run.sh logs`
- **Documentation**: See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **API Reference**: Visit http://localhost:8000/docs

---

**Last Updated**: 2024-12  
**Status**: Production Ready

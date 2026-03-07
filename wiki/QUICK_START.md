# 🚀 Quick Start Guide

**Get the Fitness Evaluator running in 5 minutes!**

## Prerequisites

- Docker Desktop installed ([download here](https://www.docker.com/products/docker-desktop))
- That's it!

## Step 1: Copy Configuration

```bash
cd fitness-eval
cp .env.example .env
```

**Optional**: Edit `.env` with your Strava credentials (app works fine without it)

```env
STRAVA_CLIENT_ID=your_id_here
STRAVA_CLIENT_SECRET=your_secret_here
```

## Step 2: Start Services

### Windows (PowerShell)
```powershell
.\docker-run.ps1 -Command up
```

### Mac/Linux (Bash)
```bash
chmod +x docker-run.sh
./docker-run.sh up
```

This will:
1. Download Docker images
2. Start FastAPI server
3. Start Ollama LLM service
4. Download Mistral AI model (~4GB)
5. Create the database

**First launch takes 3-5 minutes** while models download.

## Step 3: Open the App

Open your browser to:

**http://localhost:8000**

## You're Done! 🎉

### What to try:

1. **Dashboard** - See your overview
2. **Daily Logs** - Log today's nutrition
3. **Measurements** - Record weekly stats
4. **Plan Targets** - Set goals for the week
5. **Generate Evaluation** - Get AI analysis

## Common Commands

```bash
# Stop the app
./docker-run.sh down

# View logs
./docker-run.sh logs

# Reset database (deletes all data!)
./docker-run.sh db-reset

# Create backup
./docker-run.sh backup

# See all commands
./docker-run.sh help
```

## Windows PowerShell Commands

```powershell
# Stop the app
.\docker-run.ps1 -Command down

# View logs
.\docker-run.ps1 -Command logs

# Reset database
.\docker-run.ps1 -Command db-reset

# Create backup
.\docker-run.ps1 -Command backup

# All commands
.\docker-run.ps1
```

## Troubleshooting

### "command not found: docker"
- Install Docker Desktop: https://www.docker.com/products/docker-desktop
- Restart your terminal after installing

### "Port 8000 already in use"
- Another app is using that port
- Edit `docker-compose.yml` line 32: `"8001:8000"` 
- Then use http://localhost:8001

### "Containers not starting"
```bash
# Check logs
./docker-run.sh logs

# Restart
./docker-run.sh down
./docker-run.sh up
```

### "LLM service taking forever"
- First launch downloads model (~4GB)
- Check progress: `./docker-run.sh logs ollama`
- This only happens once

### "Database error"
```bash
# Reset database
./docker-run.sh db-reset
```

## Next Steps

- **API Docs**: http://localhost:8000/docs
- **Full Docker Guide**: [DOCKER_GUIDE.md](DOCKER_GUIDE.md)
- **Deployment**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Features**: [README.md](README.md)

## Get Help

If something doesn't work:

1. **Check logs**: `./docker-run.sh logs`
2. **Read**: [DOCKER_GUIDE.md](DOCKER_GUIDE.md#troubleshooting)
3. **Reset everything**: 
   ```bash
   ./docker-run.sh clean
   ./docker-run.sh up
   ```

---

**That's it! You now have a fully functional fitness evaluation system running locally.** 🎯

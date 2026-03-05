# Docker helper script for Fitness Evaluator (Windows PowerShell)

param(
    [string]$Command = "help",
    [string]$Args = ""
)

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

# Colors
function Write-Header {
    param([string]$Text)
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host $Text -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Text)
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Text)
    Write-Host "[WARN] $Text" -ForegroundColor Yellow
}

# Check if .env exists
function Test-Env {
    if (-not (Test-Path ".env")) {
        Write-Warning ".env file not found"
        Write-Host "Creating .env from .env.example..."
        Copy-Item .env.example .env
        Write-Warning "Please edit .env with your Strava credentials"
        exit 1
    }
}

# Main script
switch ($Command.ToLower()) {
    "up" {
        Write-Header "Starting Fitness Evaluator with Docker Compose"
        Test-Env
        Write-Host "Pulling latest images..."
        docker-compose pull
        Write-Host "Starting services..."
        docker-compose up -d
        Write-Host ""
        Write-Success "Services started!"
        Write-Host "Waiting for services to be healthy..."
        Start-Sleep -Seconds 10
        
        # Check health
        $appHealthy = $false
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "FastAPI is healthy"
                $appHealthy = $true
            }
        }
        catch {
            Write-Warning "FastAPI is starting, may take a moment..."
        }
        
        Write-Host ""
        Write-Host "Fitness Evaluator is ready!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Access points:"
        Write-Host "  Dashboard:    http://localhost:8000"
        Write-Host "  API Docs:     http://localhost:8000/docs"
        Write-Host "  Ollama API:   http://localhost:11434"
    }

    "down" {
        Write-Header "Stopping Fitness Evaluator"
        docker-compose down
        Write-Success "Services stopped"
    }

    "restart" {
        Write-Header "Restarting Fitness Evaluator"
        docker-compose restart
        Write-Success "Services restarted"
    }

    "logs" {
        Write-Header "Showing logs (Ctrl+C to exit)"
        if ($Args) {
            docker-compose logs -f $Args
        }
        else {
            docker-compose logs -f
        }
    }

    "ps" {
        Write-Header "Container Status"
        docker-compose ps
    }

    "shell-app" {
        Write-Header "Opening shell in FastAPI container"
        docker-compose exec app cmd
    }

    "shell-ollama" {
        Write-Header "Opening shell in Ollama container"
        docker-compose exec ollama cmd
    }

    "db-reset" {
        Write-Warning "This will DELETE all application data!"
        $confirm = Read-Host "Are you sure? (type 'yes' to confirm)"
        if ($confirm -eq "yes") {
            docker-compose exec app rm -Path /app/data/fitness_eval.db
            docker-compose exec app uv run alembic upgrade head
            Write-Success "Database reset"
        }
        else {
            Write-Host "Cancelled"
        }
    }

    "backup" {
        Write-Header "Creating database backup"
        $backupDir = "backups"
        if (-not (Test-Path $backupDir)) {
            New-Item -ItemType Directory -Path $backupDir | Out-Null
        }
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        docker-compose exec app cp /app/data/fitness_eval.db /app/data/fitness_eval.$timestamp.db.backup
        Write-Success "Backup created: $backupDir/fitness_eval.$timestamp.db.backup"
    }

    "clean" {
        Write-Header "Removing containers and volumes"
        docker-compose down -v
        Write-Success "Cleaned up"
    }

    "health" {
        Write-Header "Health Check"
        Write-Host "FastAPI:" -ForegroundColor Cyan
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
            $response.Content | ConvertFrom-Json | ConvertTo-Json
        }
        catch {
            Write-Host "Not responding"
        }
        
        Write-Host ""
        Write-Host "Ollama:" -ForegroundColor Cyan
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -ErrorAction SilentlyContinue
            $response.Content | ConvertFrom-Json | ConvertTo-Json
        }
        catch {
            Write-Host "Not responding"
        }
    }

    "model-list" {
        Write-Header "Available Ollama Models"
        docker-compose exec ollama ollama list
    }

    "model-pull" {
        Write-Header "Pulling Ollama Model"
        $model = if ($Args) { $Args } else { "mistral" }
        Write-Host "Pulling $model model..."
        docker-compose exec ollama ollama pull $model
        Write-Success "Model pulled"
    }

    default {
        Write-Host 'Fitness Evaluator Docker Helper'
        Write-Host ''
        Write-Host 'Usage: .\docker-run.ps1 -Command <command> [-Args <args>]'
        Write-Host ''
        Write-Host 'Commands:'
        Write-Host '  up                Start all services'
        Write-Host '  down              Stop all services'
        Write-Host '  restart           Restart services'
        Write-Host '  logs [service]    Show logs - app or ollama'
        Write-Host '  ps                Show container status'
        Write-Host '  shell-app         Open shell in FastAPI container'
        Write-Host '  shell-ollama      Open shell in Ollama container'
        Write-Host '  db-reset          Reset database (DELETE DATA)'
        Write-Host '  backup            Create database backup'
        Write-Host '  clean             Remove containers and volumes'
        Write-Host '  health            Check service health'
        Write-Host '  model-list        List available Ollama models'
        Write-Host '  model-pull NAME   Download Ollama model'
        Write-Host ''
        Write-Host 'Examples:'
        Write-Host '  .\docker-run.ps1 -Command up'
        Write-Host '  .\docker-run.ps1 -Command logs -Args app'
        Write-Host '  .\docker-run.ps1 -Command model-pull -Args neural-chat'
    }
}
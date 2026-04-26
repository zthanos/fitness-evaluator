# Docker helper script for Fitness Evaluator (Windows PowerShell)
# Manages the PostgreSQL + Keycloak + Ollama stack

param(
    [string]$Command = "help",
    [string]$Arg = ""
)

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

function Write-Header {
    param([string]$Text)
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host $Text -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
}

function Write-Ok   { param([string]$T); Write-Host "[OK]   $T" -ForegroundColor Green }
function Write-Warn { param([string]$T); Write-Host "[WARN] $T" -ForegroundColor Yellow }
function Write-Err  { param([string]$T); Write-Host "[ERR]  $T" -ForegroundColor Red }

function Test-Env {
    if (-not (Test-Path ".env")) {
        Write-Warn ".env not found - creating from .env.example"
        Copy-Item .env.example .env
        Write-Warn "Edit .env with your Strava credentials before continuing"
        exit 1
    }
}

function Stop-AppProcess {
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $procId = $conn.OwningProcess
        Write-Warn "Killing process on port 8000 (PID $procId)..."
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        Write-Ok "Process stopped"
    }
}

function Wait-Postgres {
    Write-Host "Waiting for PostgreSQL..." -NoNewline
    for ($i = 0; $i -lt 30; $i++) {
        docker exec fitness-postgres pg_isready -U postgres 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Host " ready" -ForegroundColor Green; return }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    Write-Host ""
    Write-Err "PostgreSQL did not become ready in time"
    exit 1
}

function Wait-Keycloak {
    Write-Host "Waiting for Keycloak..." -NoNewline
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8081/realms/master" -UseBasicParsing -ErrorAction Stop -TimeoutSec 5
            if ($r.StatusCode -eq 200) { Write-Host " ready" -ForegroundColor Green; return }
        } catch {}
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 5
    }
    Write-Host ""
    Write-Err "Keycloak did not become ready in time"
    exit 1
}

function Invoke-ConfigureKeycloak {
    Wait-Keycloak

    # Get admin token
    Write-Host "Authenticating with Keycloak admin..."
    try {
        $tokenResp = Invoke-RestMethod -Uri "http://localhost:8081/realms/master/protocol/openid-connect/token" `
            -Method Post -ContentType "application/x-www-form-urlencoded" `
            -Body "client_id=admin-cli&username=admin&password=admin&grant_type=password"
    } catch {
        Write-Err "Failed to get admin token: $_"; return
    }
    $headers = @{ Authorization = "Bearer $($tokenResp.access_token)" }

    # Apply fitness realm settings
    Write-Host "Applying fitness realm settings..."
    $body = '{"loginTheme":"fitness","registrationAllowed":true,"rememberMe":true,"resetPasswordAllowed":true,"loginWithEmailAllowed":true}'
    try {
        Invoke-RestMethod -Uri "http://localhost:8081/admin/realms/fitness" `
            -Method Put -Headers $headers -ContentType "application/json" -Body $body
        Write-Ok "Realm configured: theme=fitness, registration=enabled"
    } catch {
        Write-Warn "Could not update realm (may not exist yet - will be imported on next restart): $_"
    }
}

switch ($Command.ToLower()) {

    "up" {
        Write-Header "Starting Fitness Evaluator Stack"
        Test-Env
        Write-Host "Starting postgres, keycloak, ollama..."
        docker-compose up -d postgres keycloak ollama
        Wait-Postgres
        Write-Host "Running database migrations..."
        uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Write-Err "Migrations failed"; exit 1 }
        Write-Ok "Migrations applied"
        Invoke-ConfigureKeycloak
        Write-Host ""
        Write-Ok "Stack is ready"
        Write-Host ""
        Write-Host "  API / UI:    http://localhost:8000  (run: uv run uvicorn app.main:app --reload)"
        Write-Host "  API Docs:    http://localhost:8000/docs"
        Write-Host "  Keycloak:    http://localhost:8081"
        Write-Host "  Ollama:      http://localhost:11434"
        Write-Host "  PostgreSQL:  localhost:5460  (fitness_user / fitness_password)"
    }

    "configure-keycloak" {
        Write-Header "Configuring Keycloak fitness realm"
        Invoke-ConfigureKeycloak
    }

    "down" {
        Write-Header "Stopping Fitness Evaluator"
        docker-compose down
        Write-Ok "Stack stopped"
    }

    "restart" {
        Write-Header "Restarting Stack"
        docker-compose restart
        Write-Ok "Restarted"
    }

    "migrate" {
        Write-Header "Running Migrations"
        uv run alembic upgrade head
        if ($LASTEXITCODE -eq 0) { Write-Ok "Migrations applied" }
        else { Write-Err "Migrations failed" }
    }

    "logs" {
        Write-Header "Logs (Ctrl+C to exit)"
        if ($Arg) { docker-compose logs -f $Arg }
        else      { docker-compose logs -f }
    }

    "ps" {
        Write-Header "Container Status"
        docker-compose ps
    }

    "shell-app" {
        Write-Header "App shell (run locally with uv)"
        Write-Host "Tip: uv run python -c 'from app.database import engine; print(engine.url)'"
    }

    "shell-db" {
        Write-Header "PostgreSQL shell"
        docker exec -it fitness-postgres psql -U fitness_user -d fitness
    }

    "shell-ollama" {
        Write-Header "Ollama shell"
        docker exec -it fitness-ollama /bin/bash
    }

    "db-reset" {
        Write-Warn "This will DELETE all application data in PostgreSQL!"
        $confirm = Read-Host "Type 'yes' to confirm"
        if ($confirm -eq "yes") {
            Write-Host "Dropping and recreating fitness database..."
            docker exec fitness-postgres psql -U postgres -c 'DROP DATABASE IF EXISTS fitness;'
            docker exec fitness-postgres psql -U postgres -c 'CREATE DATABASE fitness;'
            docker exec fitness-postgres psql -U postgres -d fitness -c 'CREATE EXTENSION IF NOT EXISTS vector;'
            docker exec fitness-postgres psql -U postgres -d fitness -c 'GRANT ALL ON SCHEMA public TO fitness_user;'
            Write-Host "Running migrations..."
            uv run alembic upgrade head
            Write-Ok "Database reset complete"
        } else {
            Write-Host "Cancelled"
        }
    }

    "backup" {
        Write-Header "Creating PostgreSQL backup"
        $backupDir = "backups"
        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $file = "$backupDir/fitness_$timestamp.sql"
        docker exec fitness-postgres pg_dump -U fitness_user fitness | Out-File -FilePath $file -Encoding utf8
        Write-Ok "Backup saved to $file"
    }

    "restore" {
        if (-not $Arg) { Write-Err "Usage: .\docker-run.ps1 -Command restore -Arg backup.sql"; exit 1 }
        if (-not (Test-Path $Arg)) { Write-Err "File not found: $Arg"; exit 1 }
        Write-Warn "This will overwrite the current database!"
        $confirm = Read-Host "Type 'yes' to confirm"
        if ($confirm -eq "yes") {
            Get-Content $Arg | docker exec -i fitness-postgres psql -U fitness_user -d fitness
            Write-Ok "Restore complete"
        } else {
            Write-Host "Cancelled"
        }
    }

    "health" {
        Write-Header "Health Check"
        Write-Host "PostgreSQL:" -ForegroundColor Cyan
        $pg = docker exec fitness-postgres pg_isready -U postgres 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Ok $pg } else { Write-Err $pg }

        Write-Host ""
        Write-Host "Keycloak:" -ForegroundColor Cyan
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8081/health" -ErrorAction Stop -TimeoutSec 5
            Write-Ok "HTTP $($r.StatusCode)"
        } catch { Write-Warn "Not responding (may still be starting)" }

        Write-Host ""
        Write-Host "Ollama:" -ForegroundColor Cyan
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -ErrorAction Stop -TimeoutSec 5
            Write-Ok "HTTP $($r.StatusCode)"
        } catch { Write-Warn "Not responding" }

        Write-Host ""
        Write-Host "App:" -ForegroundColor Cyan
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction Stop -TimeoutSec 5
            Write-Ok "HTTP $($r.StatusCode)"
        } catch { Write-Warn "Not running - start with: uv run uvicorn app.main:app --reload" }
    }

    "clean" {
        Write-Header "Removing containers (data volumes preserved)"
        docker-compose down
        Write-Ok "Containers removed. Data volumes are intact."
        Write-Host "To also wipe all data, run: .\docker-run.ps1 -Command db-reset"
    }

    "start-app" {
        Write-Header "Starting App (uvicorn)"
        Stop-AppProcess
        Write-Host "Starting: uv run uvicorn app.main:app --reload"
        uv run uvicorn app.main:app --reload
    }

    "model-list" {
        Write-Header "Available Ollama Models"
        docker exec fitness-ollama ollama list
    }

    "model-pull" {
        $model = if ($Arg) { $Arg } else { "mistral" }
        Write-Header "Pulling Ollama model: $model"
        docker exec fitness-ollama ollama pull $model
        Write-Ok "Model pulled"
    }

    default {
        Write-Host "Fitness Evaluator Docker Helper"
        Write-Host ""
        Write-Host "Usage: .\docker-run.ps1 -Command COMMAND [-Arg VALUE]"
        Write-Host ""
        Write-Host "Stack management:"
        Write-Host "  up              Start postgres + keycloak + ollama, run migrations"
        Write-Host "  down            Stop all containers"
        Write-Host "  restart         Restart all containers"
        Write-Host "  clean           Remove containers (volumes/data kept)"
        Write-Host "  ps              Show container status"
        Write-Host "  logs [service]  Tail logs (postgres / keycloak / ollama)"
        Write-Host "  health          Check all services"
        Write-Host ""
        Write-Host "Database:"
        Write-Host "  migrate         Run pending Alembic migrations"
        Write-Host "  db-reset        Drop and recreate database (DESTROYS DATA)"
        Write-Host "  backup          pg_dump to backups/ directory"
        Write-Host "  restore         Restore from backup: -Arg path\to\backup.sql"
        Write-Host "  shell-db        Open psql session"
        Write-Host ""
        Write-Host "Ollama:"
        Write-Host "  model-list      List downloaded models"
        Write-Host "  model-pull      Download a model: -Arg mistral"
        Write-Host "  shell-ollama    Open Ollama container shell"
        Write-Host ""
        Write-Host "Keycloak:"
        Write-Host "  configure-keycloak   Apply theme + settings to fitness realm via API"
        Write-Host ""
        Write-Host "App (runs locally, not in Docker):"
        Write-Host "  start-app            Kill port 8000 then start uvicorn with --reload"
    }
}

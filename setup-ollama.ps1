# PowerShell script to set up Ollama in Docker
# Run this script to quickly set up Ollama with Mistral model

Write-Host "🚀 Setting up Ollama in Docker..." -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Start Ollama container
Write-Host "Starting Ollama container..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Ollama container started" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to start Ollama container" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Wait for Ollama to be ready
Write-Host "Waiting for Ollama to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Check if Ollama is responding
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ Ollama is responding" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ollama might not be ready yet, but continuing..." -ForegroundColor Yellow
}

Write-Host ""

# Pull Mistral model
Write-Host "Pulling Mistral model (this may take a few minutes, ~4GB download)..." -ForegroundColor Yellow
Write-Host "Please wait..." -ForegroundColor Gray
docker exec -it fitness-ollama ollama pull mistral

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Mistral model downloaded" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to download Mistral model" -ForegroundColor Red
    Write-Host "You can try manually: docker exec -it fitness-ollama ollama pull mistral" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# List available models
Write-Host "Available models:" -ForegroundColor Yellow
docker exec -it fitness-ollama ollama list

Write-Host ""
Write-Host "🎉 Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Make sure .env has:" -ForegroundColor White
Write-Host "   LLM_TYPE=ollama" -ForegroundColor Gray
Write-Host "   OLLAMA_ENDPOINT=http://localhost:11434" -ForegroundColor Gray
Write-Host "   OLLAMA_MODEL=mistral" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Start your FastAPI server:" -ForegroundColor White
Write-Host "   uvicorn app.main:app --reload" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Test the chat at:" -ForegroundColor White
Write-Host "   http://localhost:8000/chat.html" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop Ollama: docker-compose down" -ForegroundColor Yellow
Write-Host "To restart Ollama: docker-compose up -d" -ForegroundColor Yellow

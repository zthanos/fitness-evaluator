#!/bin/bash
# Docker helper scripts for Fitness Evaluator

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored output
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if .env exists
check_env() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found"
        echo "Creating .env from .env.example..."
        cp .env.example .env
        print_warning "Please edit .env with your Strava credentials"
        exit 1
    fi
}

# Main commands
case "${1:-help}" in
    up)
        print_header "Starting Fitness Evaluator with Docker Compose"
        check_env
        echo "Pulling latest images..."
        docker-compose pull
        echo "Starting services..."
        docker-compose up -d
        echo ""
        print_success "Services started!"
        echo "Waiting for services to be healthy..."
        sleep 10
        
        # Check health
        if docker-compose exec -T app curl -f http://localhost:8000/health > /dev/null 2>&1; then
            print_success "FastAPI is healthy"
        else
            print_warning "FastAPI is starting, may take a moment..."
        fi
        
        if docker-compose exec -T ollama curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
            print_success "Ollama is healthy"
            echo "Downloading Mistral model (first time may take several minutes)..."
            docker-compose exec -T ollama ollama pull mistral
        fi
        
        echo ""
        echo "🎉 Fitness Evaluator is ready!"
        echo ""
        echo "Access points:"
        echo "  Dashboard:    http://localhost:8000"
        echo "  API Docs:     http://localhost:8000/docs"
        echo "  Ollama API:   http://localhost:11434"
        ;;

    down)
        print_header "Stopping Fitness Evaluator"
        docker-compose down
        print_success "Services stopped"
        ;;

    restart)
        print_header "Restarting Fitness Evaluator"
        docker-compose restart
        print_success "Services restarted"
        ;;

    logs)
        print_header "Showing logs (Ctrl+C to exit)"
        docker-compose logs -f ${2:-}
        ;;

    ps)
        print_header "Container Status"
        docker-compose ps
        ;;

    shell-app)
        print_header "Opening shell in FastAPI container"
        docker-compose exec app /bin/bash
        ;;

    shell-ollama)
        print_header "Opening shell in Ollama container"
        docker-compose exec ollama /bin/bash
        ;;

    db-reset)
        print_warning "This will DELETE all application data!"
        read -p "Are you sure? (type 'yes' to confirm): " confirm
        if [ "$confirm" = "yes" ]; then
            docker-compose exec app rm -f /app/data/fitness_eval.db
            docker-compose exec app uv run alembic upgrade head
            print_success "Database reset"
        else
            echo "Cancelled"
        fi
        ;;

    backup)
        print_header "Creating database backup"
        BACKUP_DIR="backups"
        mkdir -p "$BACKUP_DIR"
        TIMESTAMP=$(date +%Y%m%d-%H%M%S)
        docker-compose exec app cp /app/data/fitness_eval.db /app/data/fitness_eval.$TIMESTAMP.db.backup
        print_success "Backup created: $BACKUP_DIR/fitness_eval.$TIMESTAMP.db.backup"
        ;;

    clean)
        print_header "Removing containers and volumes"
        docker-compose down -v
        print_success "Cleaned up"
        ;;

    health)
        print_header "Health Check"
        echo "FastAPI:"
        curl -s http://localhost:8000/health | jq . || echo "Not responding"
        echo ""
        echo "Ollama:"
        curl -s http://localhost:11434/api/tags | jq . || echo "Not responding"
        ;;

    model-list)
        print_header "Available Ollama Models"
        docker-compose exec ollama ollama list
        ;;

    model-pull)
        print_header "Pulling Ollama Model"
        MODEL=${2:-mistral}
        echo "Pulling $MODEL model..."
        docker-compose exec ollama ollama pull "$MODEL"
        print_success "Model pulled"
        ;;

    *)
        echo "Fitness Evaluator Docker Helper"
        echo ""
        echo "Usage: ./docker-run.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  up                Start all services"
        echo "  down              Stop all services"
        echo "  restart           Restart services"
        echo "  logs [service]    Show logs (app, ollama)"
        echo "  ps                Show container status"
        echo "  shell-app         Open shell in FastAPI container"
        echo "  shell-ollama      Open shell in Ollama container"
        echo "  db-reset          Reset database (DELETE DATA)"
        echo "  backup            Create database backup"
        echo "  clean             Remove containers and volumes"
        echo "  health            Check service health"
        echo "  model-list        List available Ollama models"
        echo "  model-pull <name> Download Ollama model"
        echo ""
        echo "Examples:"
        echo "  ./docker-run.sh up                # Start all services"
        echo "  ./docker-run.sh logs app          # Show FastAPI logs"
        echo "  ./docker-run.sh model-pull neural-chat  # Download different model"
        ;;
esac

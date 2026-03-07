from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.database import engine
from app.models.base import Base
from app.api import auth, logs, strava, evaluate, metrics, goals, chat, dashboard, settings

# Import all models to register them with SQLAlchemy
from app.models import daily_log, weekly_measurement, strava_activity, plan_targets, weekly_eval, athlete_goal

def custom_openapi():
    """Generate custom OpenAPI schema with proper grouping and descriptions."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Fitness Evaluation API",
        version="1.0.0",
        description="""
## Overview
Comprehensive fitness and nutrition evaluation system with:
- **Weekly Fitness Evaluations** — AI-powered analysis via LM Studio
- **Data Logging** — Manual nutrition, adherence, and measurement tracking
- **Strava Integration** — Automatic activity sync and aggregation
- **Idempotent Operations** — Contract-based evaluation with input hashing

## Key Features
- **Data-Driven Evaluation**: LLM-based weekly analysis with evidence mapping
- **Strava OAuth2**: Seamless activity synchronization
- **Measurement Tracking**: Weekly metrics (weight, body composition, sleep, etc.)
- **Nutrition Logging**: Daily caloric and macro tracking
- **Plan Targets**: Versioned goal progression tracking

## Authentication
Currently uses Strava OAuth2 for activity data. Plan targets and logging endpoints are public.
        """,
        routes=app.routes,
    )
    
    # Add tags metadata
    openapi_schema["tags"] = [
        {"name": "health", "description": "Health check endpoints"},
        {"name": "auth", "description": "Strava OAuth2 authentication"},
        {"name": "logs", "description": "Log management (daily, weekly, targets)"},
        {"name": "strava", "description": "Strava activity sync and aggregation"},
        {"name": "evaluate", "description": "Weekly fitness evaluation"},
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    app = FastAPI(
        title="Fitness Evaluation API",
        description="""
## Overview
Comprehensive fitness and nutrition evaluation system with:
- **Weekly Fitness Evaluations** — AI-powered analysis via LM Studio
- **Data Logging** — Manual nutrition, adherence, and measurement tracking
- **Strava Integration** — Automatic activity sync and aggregation
- **Idempotent Operations** — Contract-based evaluation with input hashing

## Key Features
- **Data-Driven Evaluation**: LLM-based weekly analysis with evidence mapping
- **Strava OAuth2**: Seamless activity synchronization
- **Measurement Tracking**: Weekly metrics (weight, body composition, sleep, etc.)
- **Nutrition Logging**: Daily caloric and macro tracking
- **Plan Targets**: Versioned goal progression tracking

## Getting Started
1. Set up `.env` file with Strava credentials and LM Studio endpoint
2. Run migrations: `uv run alembic upgrade head`
3. Start server: `uv run uvicorn app.main:app --reload`
4. Visit `/docs` for Swagger UI or `/redoc` for ReDoc
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "health", "description": "System health check"},
            {"name": "auth", "description": "Strava OAuth2 authentication flow"},
            {"name": "logs", "description": "Log and measurement management"},
            {"name": "metrics", "description": "Body metrics tracking"},
            {"name": "strava", "description": "Strava integration and sync"},
            {"name": "evaluate", "description": "Weekly fitness evaluation"},
            {"name": "goals", "description": "Athlete goal management with LLM assistance"},
            {"name": "chat", "description": "AI coach chat interface"},
            {"name": "dashboard", "description": "Dashboard overview statistics and charts"},
            {"name": "settings", "description": "Profile, Strava, and LLM settings management"},
        ]
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers BEFORE mounting static files
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
    app.include_router(strava.router, prefix="/api/strava", tags=["strava"])
    app.include_router(evaluate.router, prefix="/api/evaluate", tags=["evaluate"])
    app.include_router(goals.router, prefix="/api/goals", tags=["goals"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
    
    # Health check endpoints
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint - verify API is responsive."""
        return {"status": "healthy"}
    
    # HTML page routes
    @app.get("/activities", tags=["pages"])
    async def activities_page():
        """Serve the activities list page."""
        static_dir = Path(__file__).parent.parent / "public"
        return FileResponse(static_dir / "activities.html")
    
    @app.get("/activities/{activity_id}", tags=["pages"])
    async def activity_detail_page(activity_id: int):
        """Serve the activity detail page."""
        static_dir = Path(__file__).parent.parent / "public"
        return FileResponse(static_dir / "activity-detail.html")
    
    @app.get("/metrics", tags=["pages"])
    async def metrics_page():
        """Serve the body metrics page."""
        static_dir = Path(__file__).parent.parent / "public"
        return FileResponse(static_dir / "metrics.html")
    
    @app.get("/logs", tags=["pages"])
    async def logs_page():
        """Serve the daily logs page."""
        static_dir = Path(__file__).parent.parent / "public"
        return FileResponse(static_dir / "logs.html")
    
    @app.get("/settings.html", tags=["pages"])
    async def settings_page():
        """Serve the settings page."""
        static_dir = Path(__file__).parent.parent / "public"
        return FileResponse(static_dir / "settings.html")
    
    @app.get("/chat.html", tags=["pages"])
    async def chat_page():
        """Serve the AI coach chat page."""
        static_dir = Path(__file__).parent.parent / "public"
        return FileResponse(static_dir / "chat.html")
    
    # Mount static files AFTER routers so API routes take precedence
    static_dir = Path(__file__).parent.parent / "public"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    
    # Set custom OpenAPI schema
    app.openapi = custom_openapi
    
    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


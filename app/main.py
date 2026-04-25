"""
main.py  —  SPA Edition
=======================
Key changes from the MPA version:
  1. Individual HTML page routes (GET /metrics, GET /logs, etc.) are REMOVED.
     The SPA router in the browser handles all navigation.
  2. A catch-all route at the very end serves index.html for every path
     that doesn't match an API endpoint.  This makes browser refresh /
     deep-linking work correctly.
  3. Static files are still served (CSS, JS, assets).
"""

import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from app.limiter import limiter

from app.api import (
    auth, logs, strava, metrics, goals,
    chat, dashboard, settings, evaluations, training_plans,
)
from app.api import telemetry
from app.services.metrics_collector import metrics as req_metrics


class _MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith('/api/'):
            req_metrics.record(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        return response

# ─── OpenAPI schema ──────────────────────────────────────────────────────────

def custom_openapi(app: FastAPI):
    def _schema():
        if app.openapi_schema:
            return app.openapi_schema
        app.openapi_schema = get_openapi(
            title="Fitness Evaluation API",
            version="1.0.0",
            description="Comprehensive fitness and nutrition evaluation system.",
            routes=app.routes,
        )
        app.openapi_schema["tags"] = [
            {"name": "health",   "description": "Health check endpoints"},
            {"name": "auth",     "description": "Strava OAuth2 authentication"},
            {"name": "logs",     "description": "Daily log management"},
            {"name": "metrics",  "description": "Body metrics tracking"},
            {"name": "strava",   "description": "Strava integration and sync"},
            {"name": "evaluate", "description": "Weekly fitness evaluation"},
        ]
        return app.openapi_schema
    return _schema


# ─── App factory ─────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="Fitness Evaluation API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "health",         "description": "System health check"},
            {"name": "auth",           "description": "Strava OAuth2 authentication flow"},
            {"name": "logs",           "description": "Log and measurement management"},
            {"name": "metrics",        "description": "Body metrics tracking"},
            {"name": "strava",         "description": "Strava integration and sync"},
            {"name": "evaluate",       "description": "Weekly fitness evaluation"},
            {"name": "goals",          "description": "Athlete goal management"},
            {"name": "chat",           "description": "AI coach chat interface"},
            {"name": "dashboard",      "description": "Dashboard overview statistics"},
            {"name": "settings",       "description": "Profile and settings management"},
            {"name": "training-plans", "description": "Training plan management"},
        ],
    )

    # ── Rate limiter ────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Metrics middleware (must be added before CORS) ───────────────────────
    app.add_middleware(_MetricsMiddleware)

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routers  (must be registered BEFORE static files & catch-all) ──
    app.include_router(auth.router,           prefix="/api/auth",           tags=["auth"])
    app.include_router(logs.router,           prefix="/api/logs",           tags=["logs"])
    app.include_router(metrics.router,        prefix="/api/metrics",        tags=["metrics"])
    app.include_router(strava.router,         prefix="/api/strava",         tags=["strava"])
    app.include_router(evaluations.router,    prefix="/api/evaluations",    tags=["evaluations"])
    app.include_router(goals.router,          prefix="/api/goals",          tags=["goals"])
    app.include_router(chat.router,           prefix="/api/chat",           tags=["chat"])
    app.include_router(dashboard.router,      prefix="/api/dashboard",      tags=["dashboard"])
    app.include_router(settings.router,       prefix="/api/settings",       tags=["settings"])
    app.include_router(training_plans.router, prefix="/api/training-plans", tags=["training-plans"])
    app.include_router(telemetry.router,      prefix="/api/telemetry",      tags=["telemetry"])

    # ── Health check ────────────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "healthy"}

    # ── Landing page (public, no auth) ───────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def landing():
        page = static_dir / "landing.html"
        return FileResponse(page)

    # ── Telemetry page ───────────────────────────────────────────────────────
    @app.get("/telemetry", include_in_schema=False)
    async def telemetry_page():
        page = static_dir / "telemetry.html"
        return FileResponse(page)

    # ── Static assets (CSS, JS, images) ─────────────────────────────────────
    # Mount ONLY the asset sub-directories, not the whole public/ root.
    # This prevents StaticFiles from intercepting paths like /activities
    # before the catch-all route below has a chance to serve index.html.
    static_dir = Path(__file__).parent.parent / "public"

    for sub in ("css", "js", "assets"):
        sub_path = static_dir / sub
        if sub_path.exists():
            app.mount(f"/{sub}", StaticFiles(directory=sub_path), name=sub)

    # ── SPA catch-all: serve index.html for every unmatched GET ─────────────
    # This is what makes browser refresh and deep-linking work.
    # IMPORTANT: must be the LAST route registered.
    @app.get("/{full_path:path}", tags=["spa"])
    async def spa_fallback(full_path: str):
        """
        Serve the SPA shell (index.html) for any path that hasn't been
        matched by an API router or a static file mount.
        """
        index = static_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"error": "index.html not found"}, 404

    # ── Custom OpenAPI schema ────────────────────────────────────────────────
    app.openapi = custom_openapi(app)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
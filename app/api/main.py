# app/api/main.py
from fastapi import FastAPI
from app.api.v1.evaluations import router as evaluations_router
from app.api.evaluations import router as evaluations_v2_router
from app.api.goals import router as goals_router
from app.api.auth import router as auth_router
from app.database import engine
from app.models.base import Base
from app.models import *  
# Import all models to ensure they're registered
 
# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Fitness Evaluation API",
    description="API for fitness evaluations and tracking",
    version="1.0.0"
)
# Include routers
app.include_router(evaluations_router)
app.include_router(evaluations_v2_router, prefix="/api/evaluations", tags=["evaluations-v2"])
app.include_router(goals_router, prefix="/api/goals", tags=["goals"])
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
@app.get("/", tags=["health"])
async def root():
    return {"message": "Fitness Evaluation API is running!"}

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}
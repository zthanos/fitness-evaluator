# app/api/main.py
from fastapi import FastAPI
from app.api.v1.evaluations import router as evaluations_router
from app.database import engine, Base
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
@app.get("/", tags=["health"])
async def root():
    return {"message": "Fitness Evaluation API is running!"}

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}
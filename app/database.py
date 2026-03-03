# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

def get_engine():
    settings = get_settings()
    return create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},  # required for SQLite
        echo=False,
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings


def get_engine():
    settings = get_settings()
    kwargs = {}
    if not settings.is_postgres:
        # SQLite requires this for use across threads
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL: use a connection pool suitable for production
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    return create_engine(settings.DATABASE_URL, echo=False, **kwargs)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

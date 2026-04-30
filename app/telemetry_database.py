"""Separate SQLAlchemy engine and session factory for the fitness_telemetry database.

The telemetry database is intentionally isolated from the main app database so
telemetry writes can never interfere with application data, and the schema can
evolve independently.

Call `init_telemetry_db(app_database_url)` once at startup (inside create_app).
If the database does not exist yet, a warning with the required SQL is printed
and all writes degrade to no-ops — the app continues normally.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class TelemetryBase(DeclarativeBase):
    pass


_SessionFactory: Optional[sessionmaker] = None


def _derive_url(app_url: str) -> str:
    """Replace the database name in the URL with fitness_telemetry."""
    return app_url.rsplit("/", 1)[0] + "/fitness_telemetry"


def init_telemetry_db(app_database_url: str, telemetry_url: Optional[str] = None) -> bool:
    """Connect to (or create tables on) the telemetry database.

    Returns True on success.  On failure logs a warning with setup instructions
    and returns False — the caller should not raise.
    """
    global _SessionFactory

    url = telemetry_url or _derive_url(app_database_url)
    masked = url.split("@")[-1]  # hide credentials in logs

    try:
        engine = create_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=5,
        )
        # Import models so they register with TelemetryBase.metadata before create_all
        import app.models.telemetry  # noqa: F401

        TelemetryBase.metadata.create_all(engine)
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Telemetry database ready at %s", masked)
        return True

    except Exception as exc:
        logger.warning(
            "Telemetry database unavailable at %s (%s). "
            "To create it run:\n"
            "  CREATE DATABASE fitness_telemetry;\n"
            "  GRANT ALL PRIVILEGES ON DATABASE fitness_telemetry TO fitness_user;\n"
            "  \\c fitness_telemetry\n"
            "  GRANT ALL ON SCHEMA public TO fitness_user;",
            masked,
            exc,
        )
        return False


def get_session() -> Optional[Session]:
    """Return a new telemetry DB session, or None if the DB is unavailable."""
    if _SessionFactory is None:
        return None
    return _SessionFactory()

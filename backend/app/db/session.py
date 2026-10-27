"""
Database engine and session management.

Brick 04 scope: connection setup and a `get_db` FastAPI dependency that
yields a request-scoped session. No repository/service abstractions are
added yet — those arrive with Brick 05 (User/Profile APIs) once there is
an actual API surface to serve.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

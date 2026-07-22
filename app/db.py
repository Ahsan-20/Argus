"""Database engine and session setup (Supabase Postgres via psycopg 3).

Falls back to a local SQLite file when DATABASE_URL is empty so the app can
boot on a fresh clone before Supabase is wired up.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()


def _normalize_url(url: str) -> str:
    """Force the psycopg 3 driver and dev SQLite fallback."""
    if not url:
        return "sqlite:///./argus_dev.db"
    # Supabase hands out `postgresql://...`; point SQLAlchemy at psycopg 3.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(
    _normalize_url(settings.database_url),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables on startup (no Alembic needed at this size)."""
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
